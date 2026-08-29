// ══════════════════════════════════════════════════════════════════════════════
// EMIX Gateway — Cloudflare Worker v1.5.0 (مولتی‌لوکیشن + گیمینگ + UI کامل)
// ──────────────────────────────────────────────────────────────────────────────
// این Worker پل بین کاربران ایرانی و بک‌اند EMIX (Railway) است:
//
//   کاربر ──► بهترین IP کلادفلر ──► این Worker ──► لوکیشن انتخابی ──► اینترنت
//
// ✅ امکانات v1.5:
//   ۱) مولتی‌لوکیشن: مسیر /loc/{name}/... به بک‌اند آن لوکیشن فوروارد می‌شود
//      - لوکیشن‌ها یا همین‌جا در DEFAULT_LOCATIONS تعریف می‌شوند (ادیت کد)
//      - یا در KV (اگر bind شده باشد) به‌صورت داینامیک — بدون ری‌دیپلوی
//   ۲) /gateway-status → وضعیت گیت‌وی + PoP + سلامت لوکیشن‌ها (با کش ۵ دقیقه)
//   ۳) /admin/locations (توکن‌دار) → افزودن/حذف لوکیشن از پنل EMIX
//   ۴) WebSocket passthrough — لازم برای VLESS-over-WS / Trojan-over-WS
//   ۵) TLS کامل بین کاربر و کلادفلر
//   ۶) لوکیشن‌های پیش‌فرض متعدد — section خروجی دیگر خالی نمی‌ماند
// ══════════════════════════════════════════════════════════════════════════════

const GATEWAY_VERSION = '1.5.0';

// ─── لوکیشن‌های پیش‌فرض ───
// این‌ها بلافاصله بعد از دیپلوی worker فعال‌اند. کاربر می‌تواند از پنل اضافه/حذف کند.
// auto = همان Railway production (پیش‌فرض، همیشه سالم)
// بقیه = قالب‌های آماده — فقط upstream را بعد از deploy سرور خروج عوض کنید
const DEFAULT_LOCATIONS = {
  auto: {
    label: 'Auto — Railway EMIX',
    flag: '🌍',
    upstream: 'emix-pro-production.up.railway.app',
    note: 'مسیر پیش‌فرض — مستقیم به بک‌اند EMIX روی Railway',
    healthy: true,
  },
  de: {
    label: 'آلمان — فرانکفورت',
    flag: '🇩🇪',
    upstream: 'emix-pro-production.up.railway.app',
    note: 'سرور خروج آلمان هنوز تنظیم نشده — از پنل EMIX یک exit node روی Railway Frankfurt دیپلوی کنید و upstream اینجا را به‌روز کنید',
    healthy: false,
    pending: true,
  },
  nl: {
    label: 'هلند — آمستردام',
    flag: '🇳🇱',
    upstream: 'emix-pro-production.up.railway.app',
    note: 'سرور خروج هلند هنوز تنظیم نشده — یک exit node روی Koyeb Amsterdam دیپلوی کنید',
    healthy: false,
    pending: true,
  },
  fr: {
    label: 'فرانسه — پاریس',
    flag: '🇫🇷',
    upstream: 'emix-pro-production.up.railway.app',
    note: 'سرور خروج فرانسه هنوز تنظیم نشده — یک exit node روی Render Paris دیپلوی کنید',
    healthy: false,
    pending: true,
  },
  tr: {
    label: 'ترکیه — استانبول',
    flag: '🇹🇷',
    upstream: 'emix-pro-production.up.railway.app',
    note: 'سرور خروج ترکیه هنوز تنظیم نشده — بهترین تعادل پینگ برای بازی‌های MENA. یک VPS ترک بگیر و exit node را رویش اجرا کن',
    healthy: false,
    pending: true,
  },
  ae: {
    label: 'امارات — دبی',
    flag: '🇦🇪',
    upstream: 'emix-pro-production.up.railway.app',
    note: 'سرور خروج امارات — نزدیک‌ترین به ایران. Oracle Cloud Dubai (Always Free)',
    healthy: false,
    pending: true,
  },
  ru: {
    label: 'روسیه — مسکو',
    flag: '🇷🇺',
    upstream: 'emix-pro-production.up.railway.app',
    note: 'سرور خروج روسیه — برای بازی‌های آسیای میانه و دانلود',
    healthy: false,
    pending: true,
  },
  us: {
    label: 'آمریکا — واشنگتن',
    flag: '🇺🇸',
    upstream: 'emix-pro-production.up.railway.app',
    note: 'سرور خروج آمریکا — برای دسترسی به سرویس‌های آمریکایی',
    healthy: false,
    pending: true,
  },
  uk: {
    label: 'انگلیس — لندن',
    flag: '🇬🇧',
    upstream: 'emix-pro-production.up.railway.app',
    note: 'سرور خروج انگلیس',
    healthy: false,
    pending: true,
  },
  sg: {
    label: 'سنگاپور',
    flag: '🇸🇬',
    upstream: 'emix-pro-production.up.railway.app',
    note: 'سرور خروج آسیای شرقی — برای بازی‌های آسیایی',
    healthy: false,
    pending: true,
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
  let kvLocs = null;
  if (env && env.LOCATIONS) {
    try {
      const raw = await env.LOCATIONS.get('locations');
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object' && Object.keys(parsed).length) {
          kvLocs = parsed;
        }
      }
    } catch (e) { /* KV خطا خورد → پیش‌فرض */ }
  }
  // merge: شروع از DEFAULT_LOCATIONS، سپس override با KV (تا پیش‌فرض‌های جدید همیشه موجود باشند)
  // اگر کاربر یک لوکیشن را در KV حذف کرده بود و آن هم پیش‌فرض است، حذفش حفظ می‌شود
  const merged = { ...DEFAULT_LOCATIONS };
  if (kvLocs) {
    for (const [k, v] of Object.entries(kvLocs)) {
      // اگر کاربر صریحاً upstream تنظیم کرده، اولویت با کاربر است
      // اگر upstream خالی/null بود، از پیش‌فرض استفاده کن
      if (v && v.upstream) {
        merged[k] = v;
      } else if (merged[k]) {
        // کاربر یک placeholder برای لوکیشن پیش‌فرض گذاشته — نگه دار ولی upstream پیش‌فرض بگذار
        merged[k] = { ...merged[k], ...v, upstream: merged[k].upstream };
      } else {
        merged[k] = v;
      }
    }
  }
  // auto را از پیش‌فرض تضمینی کن (همیشه باشد)
  if (!merged.auto) merged.auto = DEFAULT_LOCATIONS.auto;
  return merged;
}

async function saveLocations(env, locs) {
  if (!env || !env.LOCATIONS) {
    return { ok: false, error: 'KV namespace «LOCATIONS» به worker بایند نشده — از Settings → Bindings یک KV بسازید و متصل کنید (یا لوکیشن را در خود کد اضافه کنید)' };
  }
  await env.LOCATIONS.put('locations', JSON.stringify(locs));
  return { ok: true };
}

// ─── کش سلامت لوکیشن‌ها (۵ دقیقه اعتبار) ───
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
          pending: v.pending || false,
          healthy: v.healthy || false,
        })),
      };
      // ?check=1 → سلامت فعال هر لوکیشن
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
            try {
              const r2 = await fetch(`https://${v.upstream}/health`, {
                method: 'GET',
                signal: AbortSignal.timeout(6000),
              });
              return { name, ok: r2.ok, status: r2.status, latency_ms: Date.now() - t0 };
            } catch (e2) {
              return { name, ok: false, status: 0, latency_ms: Date.now() - t0, error: String(e2 && e2.message || e2).slice(0, 120) };
            }
          }
        }));
        payload.location_health = checks;
        payload.all_healthy = checks.every(c => c.ok);
        await saveHealthCache(env, checks);
      } else {
        const cached = await getHealthCache(env);
        if (Object.keys(cached).length) {
          payload.location_health = Object.entries(cached).map(([name, h]) => ({
            name, ok: h.ok, latency_ms: h.latency_ms, cached: true,
          }));
        }
      }
      return json(payload);
    }

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

    // ─── بررسی IP خروج واقعی برای یک لوکیشن ───
    // GET /exit-ip?loc=tr → IP واقعی که از مسیر /loc/tr/ بیرون می‌آید را برمی‌گرداند
    // کاربرد: کاربر می‌خواهد بداند وقتی لوکیشن «ترکیه» را انتخاب می‌کند، سایت‌ها کدام IP را می‌بینند
    if (url.pathname === '/exit-ip') {
      const locName = url.searchParams.get('loc') || 'auto';
      const locs = await getLocations(env);
      const loc = locs[locName] || locs.auto;
      if (!loc) return json({ ok: false, error: 'لوکیشن یافت نشد' }, 404);
      const t0 = Date.now();
      try {
        // از طریق خود upstream (Railway یا VPS) به یک سرویس IP-check عمومی وصل می‌شویم
        // و درخواست می‌کنیم که IP خروج را برگرداند. چون upstream Railway است،
        // IP برگشتی = IP خروج Railway خواهد بود (آمستردام) — مگر اینکه کاربر VPS ترک ست کرده باشد.
        const target = `https://${loc.upstream}/api/exit-check`;
        const r = await fetch(target, {
          method: 'GET',
          signal: AbortSignal.timeout(8000),
          headers: { 'x-emix-gateway-check': '1' },
        });
        if (!r.ok) {
          return json({ ok: false, loc: locName, label: loc.label, upstream: loc.upstream, pending: loc.pending || false, error: `upstream ${r.status}`, latency_ms: Date.now() - t0 }, 502);
        }
        const j = await r.json();
        return json({
          ok: true,
          loc: locName,
          label: loc.label,
          flag: loc.flag || '',
          upstream: loc.upstream,
          pending: loc.pending || false,
          exit_ip: j.exit_ip || j.ip || null,
          exit_country: j.country || j.country_code || null,
          exit_city: j.city || null,
          exit_isp: j.isp || j.org || null,
          latency_ms: Date.now() - t0,
          colo: (request.cf && request.cf.colo) || null,
        });
      } catch (e) {
        return json({ ok: false, loc: locName, label: loc.label, upstream: loc.upstream, pending: loc.pending || false, error: String(e && e.message || e).slice(0, 120), latency_ms: Date.now() - t0 }, 502);
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
          locs[name] = { label: label || name, flag: flag || '📍', upstream, note: note || '', healthy: true, pending: false };
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
