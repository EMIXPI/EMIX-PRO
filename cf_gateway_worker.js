// ══════════════════════════════════════════════════════════════════════════════
// EMIX Gateway — Cloudflare Worker (مولتی‌لوکیشن + گیمینگ)
// ──────────────────────────────────────────────────────────────────────────────
// این Worker پل بین کاربران ایرانی و بک‌اند EMIX (Railway) است:
//
//   کاربر ──► بهترین IP کلادفلر ──► این Worker ──► لوکیشن انتخابی ──► اینترنت
//
// ✅ امکانات:
//   ۱) مولتی‌لوکیشن: مسیر /loc/{name}/... به بک‌اند آن لوکیشن فوروارد می‌شود
//      - لوکیشن‌ها یا همین‌جا در DEFAULT_LOCATIONS تعریف می‌شوند (ادیت کد)
//      - یا در KV (اگر bind شده باشد) به‌صورت داینامیک — بدون ری‌دیپلوی
//   ۲) /gateway-status → وضعیت گیت‌وی + اینکه این درخواست از کدام PoP کلادفلر
//      سرویس شده (colo) — برای بخش گیمینگ پنل (تشخیص استانبول/فرانکفورت/...)
//   ۳) /admin/locations (توکن‌دار) → افزودن/حذف لوکیشن از پنل EMIX
//   ۴) WebSocket passthrough — لازم برای VLESS-over-WS
//   ۵) TLS کامل بین کاربر و کلادفلر — کلادفلر فقط TCP/TLS رله می‌کند
//
// ⚙️ راه‌اندازی سریع:
//   1) dash.cloudflare.com → Workers & Pages → Create Worker → این کد → Deploy
//   2) (اختیاری) KV بسازید و با نام LOCATIONS بایند کنید (Settings → Bindings)
//   3) (اختیاری) Secret با نام EMIX_TOKEN بگذارید (wrangler secret put EMIX_TOKEN)
//      تا پنل بتواند لوکیشن اضافه کند؛ در غیر این صورت فقط /loc/auto فعال است
//
// 📝 افزودن لوکیشن (مثال ترکیه):
//   KV یا POST /admin/locations با body:
//     {"name":"tr","label":"ترکیه استانبول","flag":"🇹🇷","upstream":"tr.example.com"}
//   بعد لینک کاربر این‌طور می‌شود: /loc/tr/ws/{uuid}
// ══════════════════════════════════════════════════════════════════════════════

const GATEWAY_VERSION = '1.4.0';

// ─── لوکیشن‌های پیش‌فرض (وقتی KV وصل نیست یا خالی است) ───
// برای افزودن لوکیشن جدید همین‌جا اضافه کنید یا از پنل (KV) استفاده کنید
const DEFAULT_LOCATIONS = {
  auto: {
    label: 'Auto — Railway',
    flag: '🌍',
    upstream: 'emix-pro-production.up.railway.app',
    note: 'مسیر پیش‌فرض — مستقیم به بک‌اند EMIX روی Railway',
  },
};

const CORS = {
  'access-control-allow-origin': '*',
  'access-control-allow-headers': '*',
  'access-control-allow-methods': 'GET,POST,DELETE,OPTIONS',
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', ...CORS },
  });
}

async function getLocations(env) {
  if (env && env.LOCATIONS) {
    try {
      const raw = await env.LOCATIONS.get('locations');
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object' && Object.keys(parsed).length) {
          if (!parsed.auto) parsed.auto = DEFAULT_LOCATIONS.auto;
          return parsed;
        }
      }
    } catch (e) { /* KV خطا خورد → پیش‌فرض */ }
  }
  return { ...DEFAULT_LOCATIONS };
}

async function saveLocations(env, locs) {
  if (!env || !env.LOCATIONS) {
    return { ok: false, error: 'KV namespace «LOCATIONS» به worker بایند نشده — از Settings → Bindings یک KV بسازید و متصل کنید (یا لوکیشن را در خود کد اضافه کنید)' };
  }
  await env.LOCATIONS.put('locations', JSON.stringify(locs));
  return { ok: true };
}

// ─── کش سلامت لوکیشن‌ها (۵ دقیقه اعتبار) — پنل بدون تست فعال هم سلامت را می‌بیند ───
async function getHealthCache(env) {
  if (!env || !env.LOCATIONS) return {};
  try {
    const raw = await env.LOCATIONS.get('health_cache');
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || !parsed.ts || Date.now() - parsed.ts > 5 * 60 * 1000) return {};
    return parsed.data || {};
  } catch (e) { return {}; }
}

async function saveHealthCache(env, checks) {
  if (!env || !env.LOCATIONS) return;
  try {
    const data = {};
    for (const c of checks) data[c.name] = { ok: c.ok, latency_ms: c.latency_ms, ts: Date.now() };
    await env.LOCATIONS.put('health_cache', JSON.stringify({ ts: Date.now(), data }));
  } catch (e) { /* کش اختیاری است */ }
}

function checkToken(request, env) {
  const expected = (env && env.EMIX_TOKEN) || '';
  if (!expected) return false;
  return request.headers.get('x-emix-token') === expected;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS });
    }

    // ─── عمومی: وضعیت گیت‌وی (پنل + تست پینگ + تشخیص PoP) ───
    if (url.pathname === '/gateway-status') {
      const locs = await getLocations(env);
      const payload = {
        ok: true,
        gateway: 'emix-gateway',
        version: GATEWAY_VERSION,
        time: new Date().toISOString(),
        // کدوم دیتاسنتر کلادفلر این درخواست را سرو کرد — کلید بخش گیمینگ
        colo: (request.cf && request.cf.colo) || null,
        country: (request.cf && request.cf.country) || null,
        city: (request.cf && request.cf.city) || null,
        client_ip: request.headers.get('cf-connecting-ip') || null,
        kv_bound: !!(env && env.LOCATIONS),
        token_set: !!(env && env.EMIX_TOKEN),
        locations: Object.entries(locs).map(([name, v]) => ({
          name,
          label: v.label || name,
          flag: v.flag || '',
          upstream: v.upstream,
          note: v.note || '',
        })),
      };
      // ?check=1 → سلامت هر لوکیشن به‌صورت فعال تست می‌شود (تأخیر واقعی تا آپ‌استریم)
      // نتیجه در KV کش می‌شود تا پنل بدون تست فعال هم بتواند نشان بدهد
      if (url.searchParams.get('check') === '1') {
        const checks = await Promise.all(Object.entries(locs).map(async ([name, v]) => {
          const t0 = Date.now();
          try {
            const r = await fetch(`https://${v.upstream}/api/ping`, {
              method: 'GET',
              signal: AbortSignal.timeout(8000),
              headers: { 'x-emix-gateway-check': '1' },
            });
            return {
              name,
              ok: r.ok,
              status: r.status,
              latency_ms: Date.now() - t0,
            };
          } catch (e) {
            // exit node ها /api/ping و /health و / همه را ۲۰۰ می‌دهند؛ fallback بزن
            try {
              const r2 = await fetch(`https://${v.upstream}/health`, {
                method: 'GET',
                signal: AbortSignal.timeout(6000),
              });
              return { name, ok: r2.ok, status: r2.status, latency_ms: Date.now() - t0, error: r2.ok ? undefined : 'upstream /api/ping ناموفق' };
            } catch (e2) {
              return { name, ok: false, status: 0, latency_ms: Date.now() - t0, error: String(e2 && e2.message || e2).slice(0, 120) };
            }
          }
        }));
        payload.location_health = checks;
        payload.all_healthy = checks.every(c => c.ok);
        await saveHealthCache(env, checks);
      } else {
        // کش سلامت تازه (اگر بود) — بدون هزینه‌ی تست فعال
        const cached = await getHealthCache(env);
        if (Object.keys(cached).length) {
          payload.location_health = Object.entries(cached).map(([name, h]) => ({
            name, ok: h.ok, latency_ms: h.latency_ms, cached: true,
          }));
        }
      }
      return json(payload);
    }

    // ─── سلامت سبک برای مانیتورینگ پنل (بدون احراز هویت) ───
    if (url.pathname === '/health') {
      const t0 = Date.now();
      try {
        const r = await fetch(`https://${DEFAULT_LOCATIONS.auto.upstream}/api/ping`, {
          method: 'GET',
          signal: AbortSignal.timeout(6000),
        });
        return json({ ok: r.ok, gateway: 'emix-gateway', upstream_ok: r.ok, latency_ms: Date.now() - t0, colo: (request.cf && request.cf.colo) || null });
      } catch (e) {
        return json({ ok: false, upstream_ok: false, latency_ms: Date.now() - t0, error: String(e && e.message || e).slice(0, 120) }, 502);
      }
    }

    // ─── ادمین: مدیریت لوکیشن‌ها (نیازمند X-EMIX-Token) ───
    if (url.pathname === '/admin/locations') {
      if (!checkToken(request, env)) {
        return json({ ok: false, error: 'توکن نامعتبر — header «X-EMIX-Token» لازم است (Secret با نام EMIX_TOKEN در worker ست کنید)' }, 401);
      }
      const locs = await getLocations(env);

      if (request.method === 'GET') return json({ ok: true, locations: locs });

      if (request.method === 'POST') {
        try {
          const body = await request.json();
          if (body && body.locations && typeof body.locations === 'object') {
            if (!body.locations.auto) body.locations.auto = DEFAULT_LOCATIONS.auto;
            const r = await saveLocations(env, body.locations);
            return json(r, r.ok ? 200 : 400);
          }
          const { name, label, flag, upstream, note } = body || {};
          if (!name || !upstream) return json({ ok: false, error: '«name» و «upstream» الزامی است' }, 400);
          if (!/^[a-z0-9-]{2,16}$/.test(name)) return json({ ok: false, error: 'نام باید ۲-۱۶ کاراکتر انگلیسی کوچک/خط تیره باشد' }, 400);
          locs[name] = { label: label || name, flag: flag || '📍', upstream, note: note || '' };
          const r = await saveLocations(env, locs);
          return json(r, r.ok ? 200 : 400);
        } catch (e) {
          return json({ ok: false, error: 'JSON نامعتبر: ' + e.message }, 400);
        }
      }

      if (request.method === 'DELETE') {
        const name = url.searchParams.get('name');
        if (!name || name === 'auto') return json({ ok: false, error: 'نام نامعتبر یا «auto» (غیرقابل حذف)' }, 400);
        delete locs[name];
        const r = await saveLocations(env, locs);
        return json(r, r.ok ? 200 : 400);
      }
    }

    // ─── روتینگ لوکیشن: /loc/{name}/بقیه‌ی مسیر ───
    let locName = 'auto';
    const m = url.pathname.match(/^\/loc\/([a-z0-9-]+)(\/.*)?$/);
    if (m) {
      locName = m[1];
      url.pathname = m[2] || '/';
    }
    const locs = await getLocations(env);
    const loc = locs[locName];
    if (!loc) {
      return json({ ok: false, error: `لوکیشن «${locName}» تعریف نشده`, available: Object.keys(locs) }, 404);
    }

    // ─── پروکسی به آپ‌استریم (WS + HTTP + همه‌ی متدها) ───
    const upstreamUrl = `https://${loc.upstream}${url.pathname}${url.search}`;
    let proxyReq;
    try {
      proxyReq = new Request(upstreamUrl, request);
    } catch (e) {
      return json({ ok: false, error: 'ساخت درخواست ناموفق: ' + e.message }, 500);
    }
    proxyReq.headers.set('x-emix-gateway', `emix-gateway/${GATEWAY_VERSION}`);
    proxyReq.headers.set('x-emix-location', locName);

    let resp;
    try {
      resp = await fetch(proxyReq);
    } catch (e) {
      return json({ ok: false, error: 'خطای آپ‌استریم: ' + e.message, upstream: loc.upstream, location: locName }, 502);
    }

    // ⚠ حیاتی برای WebSocket: پاسخ 101 (Switching Protocols) قابل بازسازی با
    // new Response() نیست — کد status 101 در سازنده‌ی Response مجاز نیست و باعث
    // خطای 500 و قطع همه‌ی تونل‌های WS می‌شود. برای آپگرید WS باید پاسخ اصلی
    // دقیقاً همان‌طور که هست برگردد (استریم دوطرفه‌ی WebSocket حفظ می‌شود).
    if (resp.status === 101 || resp.websocket) {
      return resp;
    }

    const h = new Headers(resp.headers);
    h.set('x-emix-colo', (request.cf && request.cf.colo) || '');
    h.set('x-emix-location', locName);
    h.set('x-emix-gateway-version', GATEWAY_VERSION);
    h.set('access-control-allow-origin', '*');
    return new Response(resp.body, { status: resp.status, statusText: resp.statusText, headers: h });
  },
};
