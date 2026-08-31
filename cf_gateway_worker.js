// ══════════════════════════════════════════════════════════════════════════════
// EMIX Gateway — Cloudflare Worker v2.0.0-wte (Worker-Terminated Egress)
// ─────────────────────────────────────────────────────────────────────────────
// 🚀 چی تازه در v2.0 (WTE = خاتمه‌ی تونل داخل خود وورکر):
//
//   کاربر ──► IP آنیکست کلادفلر (colo دلخواه) ──► این Worker
//              ├── /vl        : سرور VLESS داخل وورکر — تونل همین‌جا خاتمه می‌یابد
//              │               و خروج اینترنت از «همان colo اجرای وورکر» انجام می‌شود.
//              │               → سایت‌ها IP کلادفلر آن region را می‌بینند، نه Railway!
//              │               → این همان جعلِ خروجیِ واقعیِ چندلوکیشن است (بدون سرور اضافه)
//              ├── /egress-test: IP و کشورِ خروج واقعی از دید همین colo (با مدرک)
//              └── /loc/{name} : (مثل قبل) تونل پایدار → بک‌اند Railway
//
// ✅ کاملاً سازگار با v1.x — همه‌ی اندپوینت‌های قبلی سر جایشان هستند.
// ✅ UUID ها یا در KV «vless_uuids» ذخیره می‌شوند (سینک از پنل EMIX) یا در
//    متغیر محیطی VLESS_UUIDS (با کاما جدا).
// ✅ TCP با cloudflare:sockets connect() — UDP فقط برای DNS (روی DoH).
//
// دیپلوی: dash.cloudflare.com → Workers & Pages → (وورکر emix-gateway موجود را
// باز کن) → Edit code → همه را با همین فایل عوض کن → Save & Deploy.
// ══════════════════════════════════════════════════════════════════════════════

import { connect } from 'cloudflare:sockets';

const GATEWAY_VERSION = '2.0.0-wte';

// ─── لوکیشن‌های پیش‌فرض (حالت تونل /loc — مثل v1) ───
const DEFAULT_LOCATIONS = {
  auto: {
    label: 'Auto — Railway EMIX',
    flag: '🌍',
    upstream: 'emix-pro-production.up.railway.app',
    note: 'مسیر پیش‌فرض — مستقیم به بک‌اند EMIX روی Railway',
    healthy: true,
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
        if (parsed && typeof parsed === 'object' && Object.keys(parsed).length) kvLocs = parsed;
      }
    } catch (e) { /* KV خطا خورد → پیش‌فرض */ }
  }
  const merged = { ...DEFAULT_LOCATIONS };
  if (kvLocs) {
    for (const [k, v] of Object.entries(kvLocs)) {
      if (v && v.upstream) merged[k] = v;
      else if (merged[k]) merged[k] = { ...merged[k], ...v, upstream: merged[k].upstream };
      else merged[k] = v;
    }
  }
  if (!merged.auto) merged.auto = DEFAULT_LOCATIONS.auto;
  return merged;
}

async function saveLocations(env, locs) {
  if (!env || !env.LOCATIONS) {
    return { ok: false, error: 'KV namespace «LOCATIONS» به worker بایند نشده' };
  }
  await env.LOCATIONS.put('locations', JSON.stringify(locs));
  return { ok: true };
}

function checkToken(request, env) {
  const expected = (env && env.EMIX_TOKEN) || '';
  if (!expected) return false;
  return request.headers.get('x-emix-token') === expected;
}

// ─── UUIDهای مجاز VLESS (از KV سینک‌شده توسط پنل، یا متغیر محیطی) ───
async function getAllowedUuids(env) {
  const allowed = new Set();
  const envList = (env && env.VLESS_UUIDS) || '';
  for (const u of envList.split(',')) {
    const t = u.trim().toLowerCase();
    if (t) allowed.add(t);
  }
  if (env && env.LOCATIONS) {
    try {
      const raw = await env.LOCATIONS.get('vless_uuids');
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) for (const u of parsed) allowed.add(String(u).toLowerCase());
      }
    } catch (e) { /* ignore */ }
  }
  return allowed;
}

// ══════════════════════════════════════════════════════════════════════════════
// 🆕 بخش WTE — سرور VLESS داخل وورکر (edgetunnel-style)
// ══════════════════════════════════════════════════════════════════════════════

function toUuidString(bytes) {
  const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function parseVlessHeader(buf) {
  if (buf.length < 24) return null;
  try {
    const version = buf[0];
    const uuidStr = toUuidString(buf.slice(1, 17));
    let idx = 17;
    const addonLen = buf[idx];
    idx += 1 + addonLen;
    if (buf.length < idx + 4) return null;
    const command = buf[idx]; idx++;
    const port = (buf[idx] << 8) | buf[idx + 1]; idx += 2;
    const atype = buf[idx]; idx++;
    let hostname = '';
    if (atype === 1) {
      if (buf.length < idx + 4) return null;
      hostname = `${buf[idx]}.${buf[idx + 1]}.${buf[idx + 2]}.${buf[idx + 3]}`;
      idx += 4;
    } else if (atype === 2) {
      if (buf.length < idx + 1) return null;
      const len = buf[idx]; idx++;
      if (buf.length < idx + len) return null;
      hostname = new TextDecoder().decode(buf.slice(idx, idx + len));
      idx += len;
    } else if (atype === 3) {
      if (buf.length < idx + 16) return null;
      const parts = [];
      for (let i = 0; i < 16; i += 2) {
        parts.push((buf[idx + i] * 256 + buf[idx + i + 1]).toString(16));
      }
      hostname = parts.join(':');
      idx += 16;
    } else {
      return null;
    }
    if (idx > buf.length) return null;
    return { version, uuidStr, command, port, hostname, payload: buf.slice(idx) };
  } catch (e) {
    return null;
  }
}

async function wsBytes(data) {
  if (data instanceof ArrayBuffer) return new Uint8Array(data);
  if (typeof data === 'string') return new TextEncoder().encode(data);
  try { return new Uint8Array(await data.arrayBuffer()); } catch (e) { return null; }
}

async function handleDnsOverHttps(ws, payload) {
  // UDP فقط برای DNS (پورت 53) — روی DoH کلادفلر پاسخ داده می‌شود
  ws.send(new Uint8Array([0, 0]));
  try {
    const dnsQuery = payload.slice(2); // حذف پیشوند طول ۲ بایتی UDP
    const resp = await fetch('https://1.1.1.1/dns-query', {
      method: 'POST',
      headers: { 'content-type': 'application/dns-message' },
      body: dnsQuery,
    });
    const respBuf = new Uint8Array(await resp.arrayBuffer());
    const out = new Uint8Array(2 + respBuf.length);
    out[0] = (respBuf.length >> 8) & 0xff;
    out[1] = respBuf.length & 0xff;
    out.set(respBuf, 2);
    ws.send(out);
  } catch (e) { /* سکوت — کلاینت retry می‌کند */ }
}

async function handleVlessSession(ws, env) {
  const allowed = await getAllowedUuids(env);
  let headerDone = false;
  let writer = null;
  let tcpSocket = null;
  let closed = false;

  const cleanup = () => {
    if (closed) return;
    closed = true;
    try { if (tcpSocket) tcpSocket.close(); } catch (e) {}
    try { ws.close(); } catch (e) {}
  };

  ws.addEventListener('message', async (event) => {
    try {
      const data = await wsBytes(event.data);
      if (!data || data.length === 0) return;

      if (!headerDone) {
        headerDone = true;
        const hdr = parseVlessHeader(data);
        if (!hdr) { ws.close(1002, 'bad header'); return; }
        if (!allowed.has(hdr.uuidStr)) { ws.close(1008, 'unauthorized'); return; }
        if (hdr.command === 0x02) { // UDP
          if (hdr.port === 53) { await handleDnsOverHttps(ws, hdr.payload); }
          else { ws.close(1002, 'udp-dns-only'); }
          return;
        }
        if (hdr.command !== 0x01) { ws.close(1002, 'cmd'); return; }

        // پاسخ VLESS: [version, addonLen=0]
        ws.send(new Uint8Array([hdr.version, 0]));

        tcpSocket = connect({ hostname: hdr.hostname, port: hdr.port });
        writer = tcpSocket.writable.getWriter();
        if (hdr.payload && hdr.payload.length) await writer.write(hdr.payload);

        // TCP → WebSocket (خروج اینترنت از colo همین وورکر)
        tcpSocket.readable.pipeTo(new WritableStream({
          write(chunk) {
            if (ws.readyState === 1) { try { ws.send(chunk); } catch (e) {} }
          },
          close() { cleanup(); },
          abort() { cleanup(); },
        })).catch(() => cleanup());
        return;
      }

      // پیام‌های بعدی → TCP
      if (writer && data.length) {
        try { await writer.write(data); } catch (e) { cleanup(); }
      }
    } catch (e) {
      cleanup();
    }
  });

  ws.addEventListener('close', () => cleanup());
  ws.addEventListener('error', () => cleanup());
}

async function handleVlessUpgrade(request, env) {
  const pair = new WebSocketPair();
  const [client, server] = Object.values(pair);
  server.accept();
  handleVlessSession(server, env).catch(() => { try { server.close(); } catch (e) {} });
  return new Response(null, { status: 101, webSocket: client, headers: { ...CORS } });
}

// ══════════════════════════════════════════════════════════════════════════════
// روتینگ اصلی
// ══════════════════════════════════════════════════════════════════════════════

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS });
    }

    // ─── 🆕 سرور VLESS داخل وورکر (WTE) ───
    if (url.pathname === '/vl' || url.pathname.startsWith('/vl/')) {
      const upgrade = (request.headers.get('Upgrade') || '').toLowerCase();
      if (upgrade !== 'websocket') {
        return json({
          ok: true, wte: true, endpoint: '/vl',
          hint: 'این مسیر WebSocket می‌خواهد — لینک vless-ws پنل EMIX همین‌جا ختم می‌شود',
          colo: (request.cf && request.cf.colo) || null,
        }, 426);
      }
      return handleVlessUpgrade(request, env);
    }

    // ─── 🆕 تست خروج واقعی از دید همین colo (مدرک زنده) ───
    if (url.pathname === '/egress-test') {
      const t0 = Date.now();
      const colo = (request.cf && request.cf.colo) || null;
      const country = (request.cf && request.cf.country) || null;
      const city = (request.cf && request.cf.city) || null;
      try {
        const r = await fetch('https://ipapi.co/json/', {
          headers: { 'User-Agent': 'EMIX-EgressTest/2.0' },
          signal: AbortSignal.timeout(8000),
        });
        const j = await r.json();
        return json({
          ok: true, mode: 'worker-colo-egress', wte: true,
          colo, colo_country: country, colo_city: city,
          exit_ip: j.ip || null,
          exit_country: j.country_name || null,
          exit_country_code: j.country || null,
          exit_city: j.city || null,
          exit_isp: j.org || null,
          latency_ms: Date.now() - t0,
          note: 'این IP خروجِ واقعی است که سایت‌ها از تونل /vl می‌بینند (نه IP Railway)',
        });
      } catch (e) {
        return json({
          ok: false, mode: 'worker-colo-egress', colo,
          error: String((e && e.message) || e).slice(0, 140),
        }, 502);
      }
    }

    // ─── عمومی: وضعیت گیت‌وی ───
    if (url.pathname === '/gateway-status') {
      const locs = await getLocations(env);
      const allowed = await getAllowedUuids(env);
      const payload = {
        ok: true,
        gateway: 'emix-gateway',
        version: GATEWAY_VERSION,
        wte: true,
        vless_endpoint: '/vl',
        vless_uuid_count: allowed.size,
        time: new Date().toISOString(),
        colo: (request.cf && request.cf.colo) || null,
        country: (request.cf && request.cf.country) || null,
        city: (request.cf && request.cf.city) || null,
        client_ip: request.headers.get('cf-connecting-ip') || null,
        kv_bound: !!(env && env.LOCATIONS),
        token_set: !!(env && env.EMIX_TOKEN),
        locations: Object.entries(locs).map(([name, v]) => ({
          name, label: v.label || name, flag: v.flag || '',
          upstream: v.upstream, note: v.note || '',
          pending: v.pending || false, healthy: v.healthy || false,
        })),
      };
      if (url.searchParams.get('check') === '1') {
        const checks = await Promise.all(Object.entries(locs).map(async ([name, v]) => {
          const t0 = Date.now();
          try {
            const r = await fetch(`https://${v.upstream}/api/ping`, {
              method: 'GET',
              signal: AbortSignal.timeout(8000),
              headers: { 'x-emix-gateway-check': '1' },
            });
            return { name, ok: r.ok, status: r.status, latency_ms: Date.now() - t0 };
          } catch (e) {
            return { name, ok: false, status: 0, latency_ms: Date.now() - t0, error: String((e && e.message) || e).slice(0, 120) };
          }
        }));
        payload.location_health = checks;
        payload.all_healthy = checks.every(c => c.ok);
      }
      return json(payload);
    }

    if (url.pathname === '/health') {
      const t0 = Date.now();
      try {
        const r = await fetch(`https://${DEFAULT_LOCATIONS.auto.upstream}/api/ping`, {
          method: 'GET', signal: AbortSignal.timeout(6000),
        });
        return json({ ok: r.ok, gateway: 'emix-gateway', wte: true, upstream_ok: r.ok, latency_ms: Date.now() - t0, colo: (request.cf && request.cf.colo) || null });
      } catch (e) {
        return json({ ok: false, upstream_ok: false, latency_ms: Date.now() - t0, error: String((e && e.message) || e).slice(0, 120) }, 502);
      }
    }

    // ─── بررسی IP خروج واقعی برای یک لوکیشن (حالت تونل) ───
    if (url.pathname === '/exit-ip') {
      const locName = url.searchParams.get('loc') || 'auto';
      const via = url.searchParams.get('via') || 'upstream';
      if (via === 'worker') {
        // خروج از خود وورکر (WTE) — بدون عبور از Railway
        const t0 = Date.now();
        try {
          const r = await fetch('https://ipapi.co/json/', {
            headers: { 'User-Agent': 'EMIX-ExitCheck/2.0' },
            signal: AbortSignal.timeout(8000),
          });
          const j = await r.json();
          return json({
            ok: true, loc: locName, via: 'worker', wte: true,
            colo: (request.cf && request.cf.colo) || null,
            exit_ip: j.ip || null, exit_country: j.country_name || null,
            exit_city: j.city || null, exit_isp: j.org || null,
            latency_ms: Date.now() - t0,
          });
        } catch (e) {
          return json({ ok: false, error: String((e && e.message) || e).slice(0, 120) }, 502);
        }
      }
      const locs = await getLocations(env);
      const loc = locs[locName] || locs.auto;
      if (!loc) return json({ ok: false, error: 'لوکیشن یافت نشد' }, 404);
      const t0 = Date.now();
      try {
        const target = `https://${loc.upstream}/api/exit-check`;
        const r = await fetch(target, {
          method: 'GET', signal: AbortSignal.timeout(8000),
          headers: { 'x-emix-gateway-check': '1' },
        });
        if (!r.ok) {
          return json({ ok: false, loc: locName, label: loc.label, upstream: loc.upstream, pending: loc.pending || false, error: `upstream ${r.status}`, latency_ms: Date.now() - t0 }, 502);
        }
        const j = await r.json();
        return json({
          ok: true, loc: locName, label: loc.label, flag: loc.flag || '',
          upstream: loc.upstream, pending: loc.pending || false,
          exit_ip: j.exit_ip || j.ip || null,
          exit_country: j.country || j.country_code || null,
          exit_city: j.city || null, exit_isp: j.isp || j.org || null,
          latency_ms: Date.now() - t0, colo: (request.cf && request.cf.colo) || null,
        });
      } catch (e) {
        return json({ ok: false, loc: locName, label: loc.label, upstream: loc.upstream, pending: loc.pending || false, error: String((e && e.message) || e).slice(0, 120), latency_ms: Date.now() - t0 }, 502);
      }
    }

    // ─── ادمین: مدیریت لوکیشن‌ها (توکن‌دار) ───
    if (url.pathname === '/admin/locations') {
      if (!checkToken(request, env)) {
        return json({ ok: false, error: 'توکن نامعتبر — header «X-EMIX-Token» لازم است' }, 401);
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

    // ─── 🆕 ادمین: سینک UUIDهای VLESS از پنل EMIX (توکن‌دار) ───
    if (url.pathname === '/admin/vless-uuids') {
      if (!checkToken(request, env)) {
        return json({ ok: false, error: 'توکن نامعتبر — header «X-EMIX-Token» لازم است' }, 401);
      }
      if (request.method === 'GET') {
        const allowed = await getAllowedUuids(env);
        return json({ ok: true, count: allowed.size, uuids: Array.from(allowed) });
      }
      if (request.method === 'POST') {
        if (!env || !env.LOCATIONS) {
          return json({ ok: false, error: 'KV «LOCATIONS» بایند نشده — UUIDها فقط از متغیر VLESS_UUIDS خوانده می‌شوند' }, 400);
        }
        try {
          const body = await request.json();
          const uuids = Array.isArray(body && body.uuids)
            ? body.uuids.map(u => String(u).toLowerCase()).filter(u => u.length === 36)
            : [];
          if (!uuids.length) return json({ ok: false, error: 'uuids خالی یا نامعتبر است' }, 400);
          await env.LOCATIONS.put('vless_uuids', JSON.stringify(uuids));
          if (body.pools && typeof body.pools === 'object') {
            await env.LOCATIONS.put('colo_pools', JSON.stringify(body.pools));
          }
          return json({ ok: true, synced: uuids.length, pools: Object.keys((body && body.pools) || {}).length });
        } catch (e) {
          return json({ ok: false, error: 'JSON نامعتبر: ' + e.message }, 400);
        }
      }
      if (request.method === 'DELETE') {
        if (!env || !env.LOCATIONS) return json({ ok: false, error: 'KV بایند نشده' }, 400);
        await env.LOCATIONS.delete('vless_uuids');
        return json({ ok: true });
      }
    }

    // ─── روتینگ لوکیشن: /loc/{name}/بقیه‌ی مسیر (حالت تونل) ───
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

    // ⚠ حیاتی برای WebSocket: پاسخ 101 باید همان‌طور که هست برگردد
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
