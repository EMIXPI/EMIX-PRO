// ═════════════════════════════════════════════════════════════════════════════
// EMIX-PRO — Cloudflare Workers Edition (Panel + Proxy + D1/KV)
// ─────────────────────────────────────────────────────────────────────────────
// هسته‌ی Python پروژه (Railway) دست‌نخورده می‌ماند؛ این Worker یک مسیر دیپلوی
// مستقل برای همان پنل است: مدیریت کانفیگ + لینک‌ها + اشتراک + پینگ کلاینت +
// سرو واقعی VLESS/Trojan روی WebSocket — همه روی لبه‌ی کلادفلیر.
//
// Bindings:
//   DB        (D1)  — داده‌های پایدار: کانفیگ‌ها، تنظیمات، رویدادها، سشن‌ها
//   SESSIONS  (KV)  — کش سشن ورود (۷ روز TTL)
//   ADMIN_PASSWORD (secret) — رمز اولیه‌ی پیش‌فرض (فقط بار اول seed می‌شود؛
//                             تغییر رمز از داخل پنل، مقدار D1 را باارث می‌برد)
//   PROJECT_SIGNING_KEY (secret) — کلید امضای HMAC برای probe ورکر SR
//
// Self-init: در اولین request هر isolate، اسکیمای D1 و مقادیر پیش‌فرض به‌صورت
// idempotent ساخته می‌شوند (CREATE TABLE IF NOT EXISTS + INSERT فقط برای
// کلیدهای غایب) — یعنی هر دیپلوی/ری‌دیپلوی بدون کار دستی، خودکار آماده است.
// ═════════════════════════════════════════════════════════════════════════════
import { connect } from "cloudflare:sockets";

const VERSION = "13.7.0-emix-pro";
const PLATFORM = "cloudflare-workers";
const PANEL_TITLE = "EMIX-PRO";
const SESSION_COOKIE = "rvg_session";
const SESSION_TTL_SEC = 7 * 86400;
const DEFAULT_ADMIN_PASSWORD = "123456";
const SR_WORKER_URL_DEFAULT = "https://emix-smart-routing-v1.personalemixone.workers.dev";
const PROJECT_SIGNING_KEY_DEFAULT = "emix-sr-v1-PgoGyDWhGeJHKiuH4aPU3K0nSns_TzJ4Vn56_4s1phM";
const PROTOCOLS = ["vless-ws", "trojan-ws"];
const FINGERPRINTS = ["chrome", "firefox", "ios"];
const IRAN_MODES = ["OFF", "AUTO", "DIRECT"];
const LOGIN_RATE_LIMIT = 8;      // تلاش در پنجره‌ی ۵ دقیقه‌ای
const LOGIN_RATE_WINDOW = 300;

// ─── ابزارهای رمزنگاری ───────────────────────────────────────────────────────

const TE = new TextEncoder();
const TD = new TextDecoder();

function bytesToHex(buf) {
  const u8 = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < u8.length; i++) s += u8[i].toString(16).padStart(2, "0");
  return s;
}

async function sha256hex(text) {
  const d = await crypto.subtle.digest("SHA-256", TE.encode(text));
  return bytesToHex(d);
}

function randomHex(nBytes) {
  const u8 = new Uint8Array(nBytes);
  crypto.getRandomValues(u8);
  return bytesToHex(u8);
}

function randomToken(nBytes) {
  const u8 = new Uint8Array(nBytes);
  crypto.getRandomValues(u8);
  let s = "";
  for (let i = 0; i < u8.length; i++) s += String.fromCharCode(u8[i]);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

// SHA-224 خالص (Trojan به hex(SHA-224(password)) احتیاج دارد — WebCrypto ندارد)
const K256 = [
  0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
  0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
  0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
  0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
  0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
  0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
  0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2,
];
function rotr(x, n) { return (x >>> n) | (x << (32 - n)); }

function sha224hex(text) {
  const msg = TE.encode(text);
  const h = [0xc1059ed8,0x367cd507,0x3070dd17,0xf70e5939,0xffc00b31,0x68581511,0x64f98fa7,0xbefa4fa4];
  const bitLen = msg.length * 8;
  const padded = new Uint8Array(((msg.length + 8) >> 6 << 6) + 64);
  padded.set(msg);
  padded[msg.length] = 0x80;
  const dv = new DataView(padded.buffer);
  dv.setUint32(padded.length - 8, Math.floor(bitLen / 0x100000000));
  dv.setUint32(padded.length - 4, bitLen >>> 0);
  const w = new Int32Array(64);
  for (let off = 0; off < padded.length; off += 64) {
    for (let i = 0; i < 16; i++) w[i] = dv.getInt32(off + i * 4);
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i-15],7) ^ rotr(w[i-15],18) ^ (w[i-15] >>> 3);
      const s1 = rotr(w[i-2],17) ^ rotr(w[i-2],19) ^ (w[i-2] >>> 10);
      w[i] = (w[i-16] + s0 + w[i-7] + s1) | 0;
    }
    let [a,b,c,d,e,f,g,hh] = h;
    for (let i = 0; i < 64; i++) {
      const S1 = rotr(e,6) ^ rotr(e,11) ^ rotr(e,25);
      const ch = (e & f) ^ (~e & g);
      const t1 = (hh + S1 + ch + K256[i] + w[i]) | 0;
      const S0 = rotr(a,2) ^ rotr(a,13) ^ rotr(a,22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const t2 = (S0 + maj) | 0;
      hh = g; g = f; f = e; e = (d + t1) | 0;
      d = c; c = b; b = a; a = (t1 + t2) | 0;
    }
    h[0]=(h[0]+a)|0; h[1]=(h[1]+b)|0; h[2]=(h[2]+c)|0; h[3]=(h[3]+d)|0;
    h[4]=(h[4]+e)|0; h[5]=(h[5]+f)|0; h[6]=(h[6]+g)|0; h[7]=(h[7]+hh)|0;
  }
  let out = "";
  for (let i = 0; i < 7; i++) out += (h[i] >>> 0).toString(16).padStart(8, "0");
  return out;
}

// رمز پنل: SHA-256 تکراری با نمک (256 دور — سبک برای CPU ورکر، مقاوم برای پنل)
async function hashPassword(password, saltHex) {
  let h = saltHex + ":" + password;
  for (let i = 0; i < 256; i++) h = await sha256hex(h);
  return h;
}

function b64encode(text) {
  const u8 = TE.encode(text);
  let s = "";
  for (let i = 0; i < u8.length; i++) s += String.fromCharCode(u8[i]);
  return btoa(s);
}

// ─── D1: اسکیما + مقادیر پیش‌فرض (idempotent — هر دیپلوی خودکار) ────────────

const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS settings (
     key TEXT PRIMARY KEY,
     value TEXT NOT NULL
   )`,
  `CREATE TABLE IF NOT EXISTS links (
     id TEXT PRIMARY KEY,
     label TEXT NOT NULL DEFAULT 'EMIX',
     protocol TEXT NOT NULL DEFAULT 'vless-ws',
     secret TEXT NOT NULL,
     secret_hash TEXT,
     limit_bytes INTEGER,
     used_bytes INTEGER NOT NULL DEFAULT 0,
     sessions INTEGER NOT NULL DEFAULT 0,
     last_seen_at TEXT,
     active INTEGER NOT NULL DEFAULT 1,
     note TEXT DEFAULT '',
     alpn TEXT DEFAULT 'h2',
     fingerprint TEXT DEFAULT 'chrome',
     spoof_sni TEXT,
     spoof_sni_enabled INTEGER NOT NULL DEFAULT 0,
     turbo_enabled INTEGER NOT NULL DEFAULT 0,
     iran_mode TEXT DEFAULT 'OFF',
     created_at TEXT
   )`,
  `CREATE TABLE IF NOT EXISTS ping_stats (
     link_id TEXT PRIMARY KEY,
     median_ms REAL, min_ms REAL, max_ms REAL, avg_ms REAL,
     jitter_ms REAL, loss REAL, samples INTEGER,
     measured_at TEXT, measured_by TEXT
   )`,
  `CREATE TABLE IF NOT EXISTS events (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     ts TEXT NOT NULL,
     type TEXT NOT NULL,
     detail TEXT NOT NULL
   )`,
  `CREATE TABLE IF NOT EXISTS sessions (
     token_hash TEXT PRIMARY KEY,
     exp INTEGER NOT NULL
   )`,
  `CREATE INDEX IF NOT EXISTS idx_links_secret_hash ON links(secret_hash)`,
];

let readyPromise = null;

async function ensureReady(env) {
  if (!readyPromise) {
    readyPromise = (async () => {
      await env.DB.batch(SCHEMA.map(sql => env.DB.prepare(sql)));
      await materializeDefaults(env);
    })().catch(err => {
      readyPromise = null; // شکست → تلاش دوباره در request بعدی
      throw err;
    });
  }
  await readyPromise;
}

async function getSettings(env, keys) {
  const rows = await env.DB.prepare(
    `SELECT key, value FROM settings WHERE key IN (${keys.map(() => "?").join(",")})`
  ).bind(...keys).all();
  const out = {};
  for (const r of rows.results || []) out[r.key] = r.value;
  return out;
}

async function setSetting(env, key, value) {
  await env.DB.prepare(`INSERT INTO settings(key, value) VALUES(?, ?)
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value`)
    .bind(key, String(value)).run();
}

// فقط کلیدهای غایب را می‌نویسد — مقدار ادمین هرگز بازنویسی نمی‌شود
async function materializeDefaults(env) {
  const st = await getSettings(env, [
    "admin_salt", "admin_password_hash", "sub_secret", "sr_worker_url",
    "panel_created_at", "seeded_version",
  ]);
  const now = new Date().toISOString();
  if (!st.admin_salt || !st.admin_password_hash) {
    const salt = randomHex(16);
    const pw = env.ADMIN_PASSWORD || DEFAULT_ADMIN_PASSWORD;
    const hash = await hashPassword(pw, salt);
    await setSetting(env, "admin_salt", salt);
    await setSetting(env, "admin_password_hash", hash);
    await logEvent(env, "boot", "seed اولیه: رمز ادمین از پیش‌فرض پروژه ساخته شد");
  }
  if (!st.sub_secret) await setSetting(env, "sub_secret", randomToken(18));
  if (!st.sr_worker_url) await setSetting(env, "sr_worker_url", SR_WORKER_URL_DEFAULT);
  if (!st.panel_created_at) await setSetting(env, "panel_created_at", now);
  if (!st.seeded_version) await setSetting(env, "seeded_version", VERSION);
}

async function logEvent(env, type, detail) {
  try {
    await env.DB.prepare(`INSERT INTO events(ts, type, detail) VALUES(?, ?, ?)`)
      .bind(new Date().toISOString(), type, String(detail).slice(0, 300)).run();
  } catch (_) { /* رویداد هرگز request را نمی‌شکند */ }
}

// ─── احراز هویت (سشن KV + D1) ───────────────────────────────────────────────

function getCookie(req, name) {
  const raw = req.headers.get("Cookie") || "";
  for (const part of raw.split(";")) {
    const idx = part.indexOf("=");
    if (idx < 0) continue;
    if (part.slice(0, idx).trim() === name) return part.slice(idx + 1).trim();
  }
  return null;
}

function sessionCookie(token, maxAge) {
  return `${SESSION_COOKIE}=${token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`;
}

async function createSession(env) {
  const token = randomToken(32);
  const tokenHash = await sha256hex(token);
  const exp = Math.floor(Date.now() / 1000) + SESSION_TTL_SEC;
  const val = JSON.stringify({ exp });
  await env.SESSIONS.put("sess:" + tokenHash, val, { expirationTtl: SESSION_TTL_SEC });
  await env.DB.prepare(`INSERT OR REPLACE INTO sessions(token_hash, exp) VALUES(?, ?)`)
    .bind(tokenHash, exp).run();
  if (Math.random() < 0.1) {
    try {
      await env.DB.prepare(`DELETE FROM sessions WHERE exp < ?`).bind(Math.floor(Date.now() / 1000)).run();
    } catch (_) {}
  }
  return token;
}

async function isValidSession(env, req) {
  const token = getCookie(req, SESSION_COOKIE);
  if (!token) return false;
  const tokenHash = await sha256hex(token);
  // مسیر سریع KV
  try {
    const v = await env.SESSIONS.get("sess:" + tokenHash, "json");
    if (v && v.exp > Date.now() / 1000) return true;
  } catch (_) {}
  // منبع حقیقت D1 (در صورت miss شدن KV)
  try {
    const row = await env.DB.prepare(`SELECT exp FROM sessions WHERE token_hash = ?`).bind(tokenHash).first();
    if (row && row.exp > Date.now() / 1000) {
      try {
        await env.SESSIONS.put("sess:" + tokenHash, JSON.stringify({ exp: row.exp }), { expirationTtl: SESSION_TTL_SEC });
      } catch (_) {}
      return true;
    }
  } catch (_) {}
  return false;
}

async function destroySession(env, req) {
  const token = getCookie(req, SESSION_COOKIE);
  if (!token) return;
  const tokenHash = await sha256hex(token);
  try { await env.SESSIONS.delete("sess:" + tokenHash); } catch (_) {}
  try { await env.DB.prepare(`DELETE FROM sessions WHERE token_hash = ?`).bind(tokenHash).run(); } catch (_) {}
}

async function checkPassword(env, password) {
  const st = await getSettings(env, ["admin_salt", "admin_password_hash"]);
  if (!st.admin_salt || !st.admin_password_hash) return false;
  const h = await hashPassword(String(password || ""), st.admin_salt);
  return timingSafeEqual(h, st.admin_password_hash);
}

// محدودسازی تلاش ورود (بر پایه‌ی IP — KV با TTL)
async function loginRateGate(env, ip) {
  const key = "rl:" + ip;
  try {
    const n = parseInt(await env.SESSIONS.get(key) || "0", 10);
    if (n >= LOGIN_RATE_LIMIT) return false;
    await env.SESSIONS.put(key, String(n + 1), { expirationTtl: LOGIN_RATE_WINDOW });
  } catch (_) {}
  return true;
}

// ─── ساخت لینک اشتراک (وفادار به generate_share_link هسته‌ی Python) ─────────

function applyLinkFeatures(params, link) {
  // Turbo (ed=2048): فقط ترنسپورت WS
  if (link.turbo_enabled && params.type === "ws") {
    const p = String(params.path || "");
    if (!p.includes("ed=")) params.path = p + "?ed=2048";
  }
  // جعل SNI: در مسیر Worker پشتیبانی نمی‌شود — کلادفلیر بر اساس SNI روت می‌کند
  // و SNI غلط (= دامنه‌ی متعلق به دیگران) اتصال را می‌شکند. پرچم ذخیره می‌شود
  // اما هرگز در لینک اعمال نمی‌شود (UI هم صادقانه توضیح می‌دهد).
  // (هسته‌ی Python این ویژگی را دارد چون خودش TLS را terminate می‌کند.)
}

function buildShareLink(link, host) {
  const remark = encodeURIComponent(link.label || "EMIX");
  const params = {
    security: "tls",
    type: "ws",
    host: host,
    sni: host,
    fp: link.fingerprint || "chrome",
    alpn: link.alpn || "h2",
  };
  if (link.protocol === "trojan-ws") {
    params.path = "/trojan-ws";
    applyLinkFeatures(params, link);
    const q = Object.entries(params).map(([k, v]) => k + "=" + encodeURIComponent(v)).join("&");
    return "trojan://" + link.secret + "@" + host + ":443?" + q + "#" + remark;
  }
  // پیش‌فرض: vless-ws
  params.encryption = "none";
  params.path = "/ws/" + link.id;
  applyLinkFeatures(params, link);
  const q = Object.entries(params).map(([k, v]) => k + "=" + encodeURIComponent(v)).join("&");
  return "vless://" + link.id + "@" + host + ":443?" + q + "#" + remark;
}

function linkPublicJSON(link, host, subSecret, ping) {
  const used = link.used_bytes || 0;
  const limit = link.limit_bytes || 0;
  return {
    id: link.id,
    label: link.label,
    protocol: link.protocol,
    active: !!link.active,
    note: link.note || "",
    alpn: link.alpn,
    fingerprint: link.fingerprint,
    turbo_enabled: !!link.turbo_enabled,
    spoof_sni_enabled: !!link.spoof_sni_enabled,
    spoof_sni: link.spoof_sni || null,
    spoof_sni_supported: false, // صادق: روی Worker قابل اعمال نیست
    iran_mode: link.iran_mode || "OFF",
    created_at: link.created_at,
    expires_at: link.expires_at || null,
    limit_bytes: limit || null,
    used_bytes: used,
    usage_pct: limit ? Math.min(100, Math.round(used / limit * 100)) : 0,
    sessions: link.sessions || 0,
    last_seen_at: link.last_seen_at || null,
    share_url: buildShareLink(link, host),
    sub_url: "https://" + host + "/sub/" + link.id,
    ping: ping || null,
  };
}
// ─── پاسخ‌های JSON و هدرهای امنیتی ───────────────────────────────────────────

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...headers },
  });
}

function securityHeaders(extra = {}) {
  return {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    ...extra,
  };
}

function html(body, status = 200, headers = {}) {
  return new Response(body, {
    status,
    headers: securityHeaders({
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      "Content-Security-Policy":
        "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; " +
        "font-src 'self' https://fonts.gstatic.com data:; script-src 'self' 'unsafe-inline'; " +
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
      ...headers,
    }),
  });
}

async function readJSON(req) {
  try { return await req.json(); } catch (_) { return {}; }
}

function reqIP(req) {
  return req.headers.get("cf-connecting-ip") || "0.0.0.0";
}

// ─── API: احراز هویت ────────────────────────────────────────────────────────

async function apiLogin(req, env) {
  const body = await readJSON(req);
  const ip = reqIP(req);
  if (!(await loginRateGate(env, ip))) {
    await logEvent(env, "login_blocked", "تلاش بیش از حد از " + ip);
    return json({ ok: false, error: "تعداد تلاش‌ها زیاد است — ۵ دقیقه صبر کنید" }, 429);
  }
  if (await checkPassword(env, body.password)) {
    const token = await createSession(env);
    await logEvent(env, "login_ok", "ورود موفق از " + ip);
    return json({ ok: true }, 200, { "Set-Cookie": sessionCookie(token, SESSION_TTL_SEC) });
  }
  await logEvent(env, "login_fail", "رمز نادرست از " + ip);
  return json({ ok: false, error: "رمز عبور نادرست است" }, 401);
}

async function apiLogout(req, env) {
  await destroySession(env, req);
  return json({ ok: true }, 200, {
    "Set-Cookie": sessionCookie("", 0),
    Location: "/login",
  });
}

// ─── API: کانفیگ‌ها (CRUD) ──────────────────────────────────────────────────

function validIranMode(m) { return IRAN_MODES.includes(m) ? m : "OFF"; }
function validFp(fp) { return FINGERPRINTS.includes(fp) ? fp : "chrome"; }
function validLabel(s) { return String(s || "").trim().slice(0, 60) || "EMIX"; }

async function listLinksRaw(env) {
  const rows = await env.DB.prepare(
    `SELECT * FROM links ORDER BY created_at DESC`
  ).all();
  return rows.results || [];
}

async function loadPings(env) {
  const rows = await env.DB.prepare(`SELECT * FROM ping_stats`).all();
  const out = {};
  for (const r of rows.results || []) out[r.link_id] = r;
  return out;
}

async function apiListLinks(req, env) {
  const host = new URL(req.url).host;
  const st = await getSettings(env, ["sub_secret"]);
  const [links, pings] = await Promise.all([listLinksRaw(env), loadPings(env)]);
  return json({
    ok: true,
    count: links.length,
    links: links.map(l => linkPublicJSON(l, host, st.sub_secret, pings[l.id])),
  });
}

async function apiCreateLink(req, env) {
  const body = await readJSON(req);
  let protocol = String(body.protocol || "vless-ws");
  if (!PROTOCOLS.includes(protocol)) protocol = "vless-ws";

  const label = validLabel(body.label);
  const limitGb = parseFloat(body.limit_gb);
  const limitBytes = (isFinite(limitGb) && limitGb > 0) ? Math.floor(limitGb * 1024 ** 3) : null;

  const link = {
    id: crypto.randomUUID(),
    label,
    protocol,
    secret: protocol === "trojan-ws" ? randomToken(14) : "",
    secret_hash: null,
    limit_bytes: limitBytes,
    used_bytes: 0,
    sessions: 0,
    active: 1,
    note: String(body.note || "").trim().slice(0, 200),
    alpn: "h2",
    fingerprint: validFp(body.fingerprint),
    spoof_sni: null,
    spoof_sni_enabled: 0,
    turbo_enabled: body.turbo_enabled ? 1 : 0,
    iran_mode: validIranMode(body.iran_mode),
    created_at: new Date().toISOString(),
  };
  if (protocol === "trojan-ws") link.secret_hash = sha224hex(link.secret);

  await env.DB.prepare(
    `INSERT INTO links(id, label, protocol, secret, secret_hash, limit_bytes, used_bytes,
                       sessions, active, note, alpn, fingerprint, spoof_sni, spoof_sni_enabled,
                       turbo_enabled, iran_mode, created_at)
     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`
  ).bind(link.id, link.label, link.protocol, link.secret, link.secret_hash, link.limit_bytes,
         0, 0, 1, link.note, link.alpn, link.fingerprint, null, 0,
         link.turbo_enabled, link.iran_mode, link.created_at).run();

  await logEvent(env, "link_create", "کانفیگ «" + link.label + "» (" + protocol + ") ساخته شد");
  const host = new URL(req.url).host;
  return json({ ok: true, link: linkPublicJSON(link, host, null, null) }, 201);
}

async function apiUpdateLink(req, env, id) {
  const body = await readJSON(req);
  const cur = await env.DB.prepare(`SELECT * FROM links WHERE id = ?`).bind(id).first();
  if (!cur) return json({ ok: false, error: "کانفیگ پیدا نشد" }, 404);

  const label = body.label !== undefined ? validLabel(body.label) : cur.label;
  const active = body.active !== undefined ? (body.active ? 1 : 0) : cur.active;
  const note = body.note !== undefined ? String(body.note).trim().slice(0, 200) : cur.note;
  const turbo = body.turbo_enabled !== undefined ? (body.turbo_enabled ? 1 : 0) : cur.turbo_enabled;
  const iran = body.iran_mode !== undefined ? validIranMode(body.iran_mode) : cur.iran_mode;
  const fp = body.fingerprint !== undefined ? validFp(body.fingerprint) : cur.fingerprint;
  let limitBytes = cur.limit_bytes;
  if (body.limit_gb !== undefined) {
    const gb = parseFloat(body.limit_gb);
    limitBytes = (isFinite(gb) && gb > 0) ? Math.floor(gb * 1024 ** 3) : null;
  }
  let resetUsage = body.reset_usage ? 1 : 0;

  await env.DB.prepare(
    `UPDATE links SET label=?, active=?, note=?, turbo_enabled=?, iran_mode=?, fingerprint=?,
                      limit_bytes=?, used_bytes = CASE WHEN ? THEN 0 ELSE used_bytes END,
                      sessions = CASE WHEN ? THEN 0 ELSE sessions END
     WHERE id = ?`
  ).bind(label, active, note, turbo, iran, fp, limitBytes, resetUsage, resetUsage, id).run();

  if (body.iran_mode !== undefined && body.iran_mode !== cur.iran_mode) {
    await logEvent(env, "link_edit", "کانفیگ «" + label + "» → iran_mode=" + body.iran_mode);
  }
  await logEvent(env, "link_edit", "کانفیگ «" + label + "» ویرایش شد");
  return json({ ok: true });
}

async function apiDeleteLink(req, env, id) {
  const cur = await env.DB.prepare(`SELECT label FROM links WHERE id = ?`).bind(id).first();
  if (!cur) return json({ ok: false, error: "کانفیگ پیدا نشد" }, 404);
  await env.DB.batch([
    env.DB.prepare(`DELETE FROM links WHERE id = ?`).bind(id),
    env.DB.prepare(`DELETE FROM ping_stats WHERE link_id = ?`).bind(id),
  ]);
  await logEvent(env, "link_delete", "کانفیگ «" + cur.label + "» حذف شد");
  return json({ ok: true });
}

// ─── API: پینگ کلاینت (صادق — مثل هسته: ≥۵ نمونه، محاسبه سمت سرور) ──────────

async function apiClientPing(req, env, id) {
  const cur = await env.DB.prepare(`SELECT id, label FROM links WHERE id = ?`).bind(id).first();
  if (!cur) return json({ ok: false, error: "کانفیگ پیدا نشد" }, 404);
  const body = await readJSON(req);
  const raw = Array.isArray(body.samples) ? body.samples.map(Number) : [];
  const sent = Number(body.sent) || raw.length;
  // اعتبارسنجی ضد-جعل: حداقل ۵ نمونه، هر نمونه ۱ تا ۱۵۰۰۰ میلی‌ثانیه
  const samples = raw.filter(x => isFinite(x) && x >= 1 && x <= 15000);
  if (samples.length < 5) {
    return json({ ok: false, error: "حداقل ۵ نمونه‌ی معتبر لازم است" }, 400);
  }
  samples.sort((a, b) => a - b);
  const min = samples[0], max = samples[samples.length - 1];
  const median = samples.length % 2
    ? samples[(samples.length - 1) / 2]
    : (samples[samples.length / 2 - 1] + samples[samples.length / 2]) / 2;
  const avg = samples.reduce((a, b) => a + b, 0) / samples.length;
  let jitter = 0;
  for (let i = 1; i < samples.length; i++) jitter += Math.abs(samples[i] - samples[i - 1]);
  jitter = samples.length > 1 ? jitter / (samples.length - 1) : 0;
  const loss = sent > samples.length ? +(1 - samples.length / sent).toFixed(4) : 0;
  const rec = {
    median_ms: +median.toFixed(1), min_ms: +min.toFixed(1), max_ms: +max.toFixed(1),
    avg_ms: +avg.toFixed(1), jitter_ms: +jitter.toFixed(1), loss,
    samples: samples.length, measured_at: new Date().toISOString(),
    measured_by: "client-browser",
  };
  await env.DB.prepare(
    `INSERT INTO ping_stats(link_id, median_ms, min_ms, max_ms, avg_ms, jitter_ms, loss, samples, measured_at, measured_by)
     VALUES(?,?,?,?,?,?,?,?,?,?)
     ON CONFLICT(link_id) DO UPDATE SET median_ms=excluded.median_ms, min_ms=excluded.min_ms,
       max_ms=excluded.max_ms, avg_ms=excluded.avg_ms, jitter_ms=excluded.jitter_ms,
       loss=excluded.loss, samples=excluded.samples, measured_at=excluded.measured_at,
       measured_by=excluded.measured_by`
  ).bind(id, rec.median_ms, rec.min_ms, rec.max_ms, rec.avg_ms, rec.jitter_ms, rec.loss,
         rec.samples, rec.measured_at, rec.measured_by).run();
  return json({ ok: true, ping: rec });
}

// ─── API: داشبورد / تنظیمات / مسیریابی هوشمند ───────────────────────────────

async function apiStats(env) {
  const agg = await env.DB.prepare(
    `SELECT COUNT(*) AS total,
            SUM(active) AS active,
            COALESCE(SUM(used_bytes),0) AS used_bytes,
            COALESCE(SUM(sessions),0) AS sessions
     FROM links`
  ).first();
  const ev = await env.DB.prepare(`SELECT COUNT(*) AS c FROM events`).first();
  const events = await env.DB.prepare(
    `SELECT ts, type, detail FROM events ORDER BY id DESC LIMIT 8`
  ).all();
  return json({
    ok: true,
    version: VERSION,
    platform: PLATFORM,
    stats: {
      total_links: agg.total || 0,
      active_links: agg.active || 0,
      used_bytes: agg.used_bytes || 0,
      sessions: agg.sessions || 0,
      events: ev.c || 0,
    },
    events: events.results || [],
  });
}

async function apiSettings(req, env) {
  const host = new URL(req.url).host;
  const st = await getSettings(env, ["sub_secret", "sr_worker_url", "panel_created_at"]);
  return json({
    ok: true,
    version: VERSION,
    platform: PLATFORM,
    panel_created_at: st.panel_created_at,
    sub_url: "https://" + host + "/sub/" + (st.sub_secret || ""),
    sr_worker_url: st.sr_worker_url || SR_WORKER_URL_DEFAULT,
    repository: "https://github.com/EMIXPI/EMIX-PRO",
  });
}

async function apiChangePassword(req, env) {
  const body = await readJSON(req);
  const current = String(body.current || "");
  const next = String(body.next || "");
  if (!(await checkPassword(env, current))) {
    return json({ ok: false, error: "رمز فعلی نادرست است" }, 401);
  }
  if (next.length < 6) {
    return json({ ok: false, error: "رمز جدید باید حداقل ۶ نویسه باشد" }, 400);
  }
  const salt = randomHex(16);
  const hash = await hashPassword(next, salt);
  await env.DB.batch([
    env.DB.prepare(`INSERT INTO settings(key, value) VALUES('admin_salt', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value`).bind(salt),
    env.DB.prepare(`INSERT INTO settings(key, value) VALUES('admin_password_hash', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value`).bind(hash),
  ]);
  await logEvent(env, "password_change", "رمز ورود پنل تغییر کرد");
  return json({ ok: true });
}

async function apiRegenSub(req, env) {
  const secret = randomToken(18);
  await setSetting(env, "sub_secret", secret);
  await logEvent(env, "sub_regen", "کلید اشتراک کلی بازتولید شد");
  const host = new URL(req.url).host;
  return json({ ok: true, sub_url: "https://" + host + "/sub/" + secret });
}

async function apiExport(req, env) {
  const host = new URL(req.url).host;
  const links = await listLinksRaw(env);
  const st = await getSettings(env, ["sub_secret"]);
  const pings = await loadPings(env);
  return json({
    ok: true,
    exported_at: new Date().toISOString(),
    version: VERSION,
    links: links.map(l => linkPublicJSON(l, host, st.sub_secret, pings[l.id])),
  });
}

// مسیریابی هوشمند — وضعیت صادق ورکر SR موجود (بررسی واقعی، نه عدد ساختگی)
async function apiSmartRouting(req, env) {
  const st = await getSettings(env, ["sr_worker_url"]);
  const workerUrl = (st.sr_worker_url || SR_WORKER_URL_DEFAULT).replace(/\/+$/, "");
  const out = {
    ok: true,
    panel_platform: PLATFORM,
    sr_worker_url: workerUrl,
    state: "UNKNOWN", health: null, probe: null,
    note: "پنل اکنون مستقیماً روی لبه‌ی کلادفلیر سرو می‌شود؛ ورکر SR به‌عنوان نقاط انتهایی پایش باقی است.",
  };
  const UA = { "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36" };
  // Service Binding = مسیر رسمی worker-to-worker در همان حساب
  // (fetch مستقیم به *.workers.dev همان حساب → خطای 1042 کلادفلیر)
  const doFetch = async (url, init) => {
    if (env.SR_WORKER) return await env.SR_WORKER.fetch(url, init);
    return await fetch(url, init);
  };
  // ۱) بررسی سلامت عمومی — با تشخیص کامل برای عیب‌یابی
  try {
    const r = await doFetch(workerUrl + "/sr/health", { headers: UA, signal: AbortSignal.timeout(10000) });
    if (r.ok) {
      out.health = await r.json();
      out.state = "REGISTERED";
    } else {
      out.state = "FAILED";
      out.health_status = r.status;
      out.health_body = (await r.text()).slice(0, 200);
    }
  } catch (e) { out.state = "UNKNOWN"; out.health_error = String(e && e.message || e).slice(0, 200); }
  // ۲) probe امضادار با کلید پروژه (HMAC واقعی)
  try {
    const ts = String(Math.floor(Date.now() / 1000));
    const nonce = randomToken(12);
    const bodyS = "{}";
    const bodyHash = await sha256hex(bodyS);
    const canonical = ts + "." + nonce + ".POST./sr/probe-upstream." + bodyHash;
    const key = await crypto.subtle.importKey(
      "raw", TE.encode(env.PROJECT_SIGNING_KEY || PROJECT_SIGNING_KEY_DEFAULT),
      { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
    const sig = bytesToHex(await crypto.subtle.sign("HMAC", key, TE.encode(canonical)));
    const r2 = await doFetch(workerUrl + "/sr/probe-upstream", {
      method: "POST", body: bodyS, headers: {
        ...UA, "Content-Type": "application/json",
        "x-sr-timestamp": ts, "x-sr-nonce": nonce, "x-sr-signature": sig,
      },
      signal: AbortSignal.timeout(10000),
    });
    if (r2.ok) {
      out.probe = await r2.json();
      if (out.state === "REGISTERED") {
        out.state = (out.probe && out.probe.ok) ? "HEALTHY" : "DEGRADED";
      }
    } else {
      out.probe_status = r2.status;
      out.probe_body = (await r2.text()).slice(0, 200);
      if (out.state === "REGISTERED") { out.state = "DEGRADED"; }
    }
  } catch (e) {
    out.probe_error = String(e && e.message || e).slice(0, 200);
    if (out.state === "REGISTERED") out.state = "DEGRADED";
  }
  if (out.health && out.health.upstream && out.health.upstream.ok === false) {
    out.upstream_note = "upstream ورکر SR (پنل Railway قبلی) پاسخ نمی‌دهد — سرویس Railway حذف شده است.";
  }
  return json(out);
}

// ─── اشتراک‌ها ──────────────────────────────────────────────────────────────

async function handleSubscription(req, env, key) {
  const st = await getSettings(env, ["sub_secret"]);
  let links = [];
  if (key === st.sub_secret) {
    links = (await listLinksRaw(env)).filter(l => l.active);
  } else {
    const l = await env.DB.prepare(`SELECT * FROM links WHERE id = ?`).bind(key).first();
    if (l) links = [l];
  }
  if (!links.length) return new Response("not found", { status: 404 });
  const host = new URL(req.url).host;
  const lines = links.map(l => buildShareLink(l, host));
  const used = links.reduce((a, l) => a + (l.used_bytes || 0), 0);
  const limit = links.reduce((a, l) => a + (l.limit_bytes || 0), 0);
  const headers = {
    "Content-Type": "text/plain; charset=utf-8",
    "Cache-Control": "no-store",
    "Profile-Title": b64encode(PANEL_TITLE + " — " + host),
  };
  if (limit > 0) headers["Subscription-Userinfo"] = "upload=" + used + "; total=" + limit + ";";
  else if (used > 0) headers["Subscription-Userinfo"] = "upload=" + used + ";";
  return new Response(b64encode(lines.join("\n")), { status: 200, headers });
}

// قوانین مسیریابی ایران (split-routing صادق برای کلاینت‌های v2ray)
const IRAN_DOMAINS = [
  "bale.ir", "divar.ir", "digikala.com", "aparat.com", "namnak.com", "zoomit.ir",
  "varzesh3.com", "isna.ir", "irna.ir", "mehrnews.com", "tasnimnews.com",
  "khabaronline.ir", "ircbot.ga", "blog.ir", "persianblog.ir", "irancell.ir",
  "mci.ir", "rightel.ir", "shatel.ir", "mihanmail.ir", "post.ir", "gig.ir",
  "parspack.com", "arvancloud.ir", "eserver.ir", "parsdata.com", "sina.ir",
  "sharif.ir", "ut.ac.ir", "iust.ac.ir", "sbu.ac.ir", "tmu.ac.ir",
];
async function handleIranConfig(req, env, id) {
  const l = await env.DB.prepare(`SELECT * FROM links WHERE id = ?`).bind(id).first();
  if (!l) return json({ ok: false, error: "کانفیگ پیدا نشد" }, 404);
  const host = new URL(req.url).host;
  return json({
    ok: true,
    mode: l.iran_mode || "OFF",
    mode_note: {
      OFF: "مسیریابی ایران خاموش است — تمام ترافیک از تونل می‌گذرد.",
      AUTO: "حالت خودکار: دامنه‌ها و IPهای ایران مستقیم، بقیه از تونل.",
      DIRECT: "ترافیک ایران مستقیم (direct) با قوانین صریح geoip+دامنه.",
    }[l.iran_mode || "OFF"],
    routing: {
      domainStrategy: "IPIfNonMatch",
      rules: [
        { type: "field", domain: ["geosite:category-ir", ...IRAN_DOMAINS], outboundTag: "direct" },
        { type: "field", ip: ["geoip:ir", "224.0.0.0/3", "geoip:private"], outboundTag: "direct" },
        { type: "field", network: "tcp,udp", outboundTag: "proxy" },
      ],
    },
    outbounds: ["proxy", "direct", "block"],
    share_url: buildShareLink(l, host),
  });
}
// ─── پروکسی: VLESS / Trojan روی WebSocket (با connect() رسمی کلادفلیر) ──────

function wsReject(status, msg) {
  return new Response(msg, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
}

// خواندن «داده‌ی زودهنگام» (Early-Data / ed=2048) از هدر Sec-WebSocket-Protocol
function readEarlyData(req) {
  const proto = req.headers.get("sec-websocket-protocol") || "";
  if (!proto) return null;
  const m = proto.match(/[A-Za-z0-9+/=]{8,}/);
  if (!m) return null;
  try {
    const b64 = m[0];
    const bin = atob(b64);
    const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return u8;
  } catch (_) { return null; }
}

async function getLinkForUse(env, id, secretHash) {
  let row;
  if (id) row = await env.DB.prepare(`SELECT * FROM links WHERE id = ?`).bind(id).first();
  else if (secretHash) row = await env.DB.prepare(
    `SELECT * FROM links WHERE secret_hash = ?`).bind(secretHash.toLowerCase()).first();
  if (!row) return { err: wsReject(401, "unknown") };
  if (!row.active) return { err: wsReject(403, "inactive") };
  if (row.limit_bytes && (row.used_bytes || 0) >= row.limit_bytes) return { err: wsReject(403, "limit") };
  return { link: row };
}

// شمارش مصرف واقعی — پس از بسته شدن اتصال در D1 ثبت می‌شود (fire-and-forget)
async function recordUsage(env, linkId, upBytes, downBytes, ok) {
  try {
    await env.DB.prepare(
      `UPDATE links SET used_bytes = used_bytes + ?, sessions = sessions + ?,
                        last_seen_at = ? WHERE id = ?`
    ).bind(upBytes + downBytes, ok ? 1 : 0, new Date().toISOString(), linkId).run();
  } catch (_) {}
}

// پارس هدر VLESS: [ver][uuid×16][addons_len][addons][cmd][port×2][atyp][addr][payload]
function parseVless(buf) {
  if (buf.length < 24) return null;
  if (buf[0] !== 0x00) return null;
  let uuid = "";
  for (let i = 1; i <= 16; i++) uuid += buf[i].toString(16).padStart(2, "0");
  uuid = uuid.slice(0, 8) + "-" + uuid.slice(8, 12) + "-" + uuid.slice(12, 16) +
         "-" + uuid.slice(16, 20) + "-" + uuid.slice(20);
  const addonsLen = buf[17];
  let off = 18 + addonsLen;
  const cmd = buf[off]; off += 1;
  const port = (buf[off] << 8) | buf[off + 1]; off += 2;
  const atyp = buf[off]; off += 1;
  let addr = "";
  if (atyp === 0x01) {
    addr = buf[off] + "." + buf[off + 1] + "." + buf[off + 2] + "." + buf[off + 3];
    off += 4;
  } else if (atyp === 0x02) {
    const len = buf[off]; off += 1;
    addr = TD.decode(buf.subarray(off, off + len));
    off += len;
  } else if (atyp === 0x03) {
    const groups = [];
    for (let i = 0; i < 16; i += 2) groups.push(((buf[off + i] << 8) | buf[off + i + 1]).toString(16));
    addr = groups.join(":");
    off += 16;
  } else return null;
  return { uuid, cmd, port, addr, payloadOffset: off };
}

// پارس هدر Trojan: hex(sha224(pw)) CRLF [cmd][atyp][addr][port] CRLF [payload]
function parseTrojan(buf) {
  if (buf.length < 62) return null;
  let hash = "";
  for (let i = 0; i < 56; i++) {
    const c = buf[i];
    if (!((c >= 0x30 && c <= 0x39) || (c >= 0x61 && c <= 0x66) || (c >= 0x41 && c <= 0x46))) return null;
    hash += String.fromCharCode(c);
  }
  if (buf[56] !== 0x0d || buf[57] !== 0x0a) return null;
  let off = 58;
  const cmd = buf[off]; off += 1;
  const atyp = buf[off]; off += 1;
  let addr = "";
  if (atyp === 0x01) {
    addr = buf[off] + "." + buf[off + 1] + "." + buf[off + 2] + "." + buf[off + 3];
    off += 4;
  } else if (atyp === 0x03) {
    const len = buf[off]; off += 1;
    addr = TD.decode(buf.subarray(off, off + len));
    off += len;
  } else if (atyp === 0x04) {
    const groups = [];
    for (let i = 0; i < 16; i += 2) groups.push(((buf[off + i] << 8) | buf[off + i + 1]).toString(16));
    addr = groups.join(":");
    off += 16;
  } else return null;
  const port = (buf[off] << 8) | buf[off + 1]; off += 2;
  if (buf[off] !== 0x0d || buf[off + 1] !== 0x0a) return null;
  off += 2;
  return { hash: hash.toLowerCase(), cmd, port, addr, payloadOffset: off };
}

// لوله‌ی WebSocket ↔ TCP با شمارش بایت واقعی
async function pipeWS2TCP(ws, tcpSocket, firstPayload, link, env, isVless) {
  let upBytes = firstPayload ? firstPayload.length : 0;
  let downBytes = 0;
  const writer = tcpSocket.writable.getWriter();
  let closed = false;

  const finish = () => {
    if (closed) return;
    closed = true;
    try { writer.releaseLock(); } catch (_) {}
    try { tcpSocket.close(); } catch (_) {}
    try { ws.close(1000, "done"); } catch (_) {}
    recordUsage(env, link.id, upBytes, downBytes, true);
  };

  // VLESS: پاسخ پروتکل = [version=0][addons_len=0]
  if (isVless) {
    try { ws.send(new Uint8Array([0x00, 0x00])); } catch (_) {}
  }
  // Trojan: پاسخی ندارد — داده‌ی مقصد خام ارسال می‌شود

  if (firstPayload && firstPayload.length) {
    try { await writer.write(firstPayload); } catch (e) { finish(); return; }
  }

  ws.addEventListener("message", async (ev) => {
    if (closed) return;
    try {
      let u8;
      if (ev.data instanceof ArrayBuffer) u8 = new Uint8Array(ev.data);
      else if (typeof ev.data === "string") u8 = TE.encode(ev.data);
      else u8 = new Uint8Array(ev.data);
      upBytes += u8.length;
      await writer.write(u8);
    } catch (_) { finish(); }
  });
  ws.addEventListener("close", () => {
    if (closed) return;
    closed = true;
    try { writer.close(); } catch (_) {}
    try { tcpSocket.close(); } catch (_) {}
    recordUsage(env, link.id, upBytes, downBytes, true);
  });
  ws.addEventListener("error", () => finish());

  // مقصد → کلاینت
  (async () => {
    try {
      const reader = tcpSocket.readable.getReader();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (value && value.length) {
          downBytes += value.length;
          ws.send(value);
        }
      }
    } catch (_) {}
    finish();
  })();
}

async function handleVlessWS(req, env, pathId) {
  if (req.headers.get("Upgrade") !== "websocket") {
    return wsReject(400, "EMIX-PRO: WebSocket required");
  }
  const auth = await getLinkForUse(env, pathId, null);
  if (auth.err) return auth.err;
  const link = auth.link;

  const pair = new WebSocketPair();
  const [client, server] = Object.values(pair);
  server.accept();
  server.binaryType = "arraybuffer";

  let headerParsed = false;

  const onFirst = async (u8) => {
    headerParsed = true;
    const hdr = parseVless(u8);
    if (!hdr || hdr.uuid !== link.id) {
      try { server.close(1008, "auth"); } catch (_) {}
      return;
    }
    if (hdr.cmd !== 0x01) { // فقط TCP؛ UDP/MUX پشتیبانی نمی‌شود (صادق)
      try { server.close(1008, "unsupported"); } catch (_) {}
      return;
    }
    const payload = u8.subarray(hdr.payloadOffset);
    try {
      const tcp = connect({ hostname: hdr.addr, port: hdr.port });
      await pipeWS2TCP(server, tcp, payload, link, env, true);
    } catch (e) {
      try { server.close(1011, "connect-fail"); } catch (_) {}
      recordUsage(env, link.id, 0, 0, false);
    }
  };

  const early = readEarlyData(req);
  if (early && early.length) {
    // داده‌ی زودهنگام (turbo ed=2048): همان پیام اول است
    ctx_safe(onFirst(early));
  }

  server.addEventListener("message", (ev) => {
    if (headerParsed) return; // بعد از هدر، لوله خودش پیام‌ها را می‌گیرد
    let u8;
    if (ev.data instanceof ArrayBuffer) u8 = new Uint8Array(ev.data);
    else if (typeof ev.data === "string") u8 = TE.encode(ev.data);
    else u8 = new Uint8Array(ev.data);
    ctx_safe(onFirst(u8));
  });
  server.addEventListener("close", () => {
    if (!headerParsed) recordUsage(env, link.id, 0, 0, false);
  });

  return new Response(null, { status: 101, webSocket: client });
}

async function handleTrojanWS(req, env) {
  if (req.headers.get("Upgrade") !== "websocket") {
    return wsReject(400, "EMIX-PRO: WebSocket required");
  }
  const pair = new WebSocketPair();
  const [client, server] = Object.values(pair);
  server.accept();
  server.binaryType = "arraybuffer";

  let headerParsed = false;
  let pendingLink = null;

  const onFirst = async (u8) => {
    headerParsed = true;
    const hdr = parseTrojan(u8);
    if (!hdr) { try { server.close(1008, "bad"); } catch (_) {} return; }
    const auth = await getLinkForUse(env, null, hdr.hash);
    if (auth.err) { try { server.close(1008, "auth"); } catch (_) {} return; }
    pendingLink = auth.link;
    if (hdr.cmd !== 0x01) { // فقط TCP CONNECT
      try { server.close(1008, "unsupported"); } catch (_) {}
      return;
    }
    const payload = u8.subarray(hdr.payloadOffset);
    try {
      const tcp = connect({ hostname: hdr.addr, port: hdr.port });
      await pipeWS2TCP(server, tcp, payload, auth.link, env, false);
    } catch (e) {
      try { server.close(1011, "connect-fail"); } catch (_) {}
      recordUsage(env, auth.link.id, 0, 0, false);
    }
  };

  const early = readEarlyData(req);
  if (early && early.length) ctx_safe(onFirst(early));

  server.addEventListener("message", (ev) => {
    if (headerParsed) return;
    let u8;
    if (ev.data instanceof ArrayBuffer) u8 = new Uint8Array(ev.data);
    else if (typeof ev.data === "string") u8 = TE.encode(ev.data);
    else u8 = new Uint8Array(ev.data);
    ctx_safe(onFirst(u8));
  });
  server.addEventListener("close", () => {
    if (!headerParsed && pendingLink) recordUsage(env, pendingLink.id, 0, 0, false);
  });

  return new Response(null, { status: 101, webSocket: client });
}

// اجرای امن promiseهای پسا-پاسخ (بدون waitUntil خارجی)
function ctx_safe(p) { p.catch(_ => {}); }
// ─── UI: صفحات HTML (RTL فارسی — همان زبان طراحی EMIX-PRO) ─────────────────

const BASE_CSS = `
:root{
  --bg:#0a0f1c; --bg2:#0d1526; --card:#111a2e; --card2:#16213a;
  --border:#1e2a44; --border2:#2a3a5e;
  --text:#e6edf7; --muted:#8aa0bf; --muted2:#5c7191;
  --accent:#22d3ee; --accent2:#34d399; --warn:#fbbf24; --danger:#f87171;
  --vless:#38bdf8; --trojan:#a78bfa;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{
  background:var(--bg); color:var(--text);
  font-family:'Vazirmatn',Tahoma,'Segoe UI',sans-serif;
  font-size:14px; line-height:1.7; direction:rtl;
  -webkit-font-smoothing:antialiased; overflow-x:hidden;
}
a{color:var(--accent);text-decoration:none}
.mono{font-family:'JetBrains Mono',Consolas,monospace;direction:ltr;unicode-bidi:embed}
button{font-family:inherit;cursor:pointer;border:none;font-size:13px}
input,select,textarea{
  font-family:inherit;font-size:13px;color:var(--text);
  background:var(--bg2);border:1px solid var(--border2);border-radius:10px;
  padding:10px 14px;width:100%;outline:none;transition:border-color .15s;
}
input:focus,select:focus,textarea:focus{border-color:var(--accent)}
.btn{
  display:inline-flex;align-items:center;justify-content:center;gap:8px;
  background:linear-gradient(135deg,#0ea5e9,#22d3ee);color:#03121d;
  font-weight:700;border-radius:10px;padding:10px 18px;transition:filter .15s,transform .05s;
}
.btn:hover{filter:brightness(1.1)}
.btn:active{transform:scale(.98)}
.btn.ghost{background:transparent;color:var(--text);border:1px solid var(--border2)}
.btn.ghost:hover{border-color:var(--accent);color:var(--accent)}
.btn.danger{background:transparent;color:var(--danger);border:1px solid rgba(248,113,113,.35)}
.btn.danger:hover{background:rgba(248,113,113,.12)}
.btn.sm{padding:6px 12px;font-size:12px;border-radius:8px}
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:20px}
.badge{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;
  padding:3px 10px;border-radius:99px;letter-spacing:.2px}
.badge.ok{background:rgba(52,211,153,.14);color:var(--accent2)}
.badge.off{background:rgba(140,160,191,.12);color:var(--muted)}
.badge.warn{background:rgba(251,191,36,.14);color:var(--warn)}
.badge.vless{background:rgba(56,189,248,.14);color:var(--vless)}
.badge.trojan{background:rgba(167,139,250,.15);color:var(--trojan)}
.toast-box{position:fixed;bottom:20px;left:20px;z-index:999;display:flex;flex-direction:column;gap:8px}
.toast{background:var(--card2);border:1px solid var(--border2);color:var(--text);
  border-radius:10px;padding:10px 16px;font-size:13px;box-shadow:0 8px 30px rgba(0,0,0,.45);
  animation:tin .25s ease;max-width:340px}
.toast.err{border-color:rgba(248,113,113,.5)}
@keyframes tin{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes spin{to{transform:rotate(360deg)}}
.spin{animation:spin 1s linear infinite;display:inline-block}
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:4px}
::-webkit-scrollbar-track{background:transparent}
`;

const LOGIN_HTML = `<!DOCTYPE html>
<html lang="fa" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>ورود — EMIX-PRO</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;800&display=swap">
<style>${BASE_CSS}
body{display:flex;align-items:center;justify-content:center;min-height:100vh;
  background:radial-gradient(1200px 600px at 80% -10%,rgba(34,211,238,.08),transparent),
             radial-gradient(900px 500px at 10% 110%,rgba(52,211,153,.06),transparent),var(--bg)}
.login-card{width:min(400px,92vw);padding:36px 32px;text-align:center}
.logo{display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:6px}
.logo svg{width:34px;height:34px}
.logo b{font-size:22px;font-weight:800;letter-spacing:.5px}
.logo b span{color:var(--accent)}
.sub{color:var(--muted);font-size:12.5px;margin-bottom:26px}
.field{text-align:right;margin-bottom:16px}
.field label{display:block;font-size:12px;color:var(--muted);margin-bottom:7px}
.field input{direction:ltr;text-align:center;letter-spacing:2px;font-size:15px}
.btn{width:100%;margin-top:6px}
.err{color:var(--danger);font-size:12.5px;margin-top:14px;min-height:20px}
.foot{margin-top:22px;color:var(--muted2);font-size:11px}
.foot a{color:var(--muted)}
</style></head><body>
<div class="card login-card">
  <div class="logo">
    <svg viewBox="0 0 24 24" fill="none"><path d="M12 2l7 3v6c0 5-3.5 8.5-7 11-3.5-2.5-7-6-7-11V5l7-3z" stroke="#22d3ee" stroke-width="1.6"/><path d="M9 12l2 2 4-4" stroke="#34d399" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
    <b>EMIX<span>-PRO</span></b>
  </div>
  <div class="sub">پنل مدیریت کانفیگ — نسخه Cloudflare Workers</div>
  <form id="f">
    <div class="field">
      <label>رمز عبور پنل</label>
      <input id="pw" type="password" autocomplete="current-password" autofocus required>
    </div>
    <button class="btn" id="go" type="submit">ورود به پنل</button>
    <div class="err" id="err"></div>
  </form>
  <div class="foot">EMIX-PRO v${VERSION} · <a href="https://github.com/EMIXPI/EMIX-PRO" target="_blank" rel="noopener">گیت‌هاب</a></div>
</div>
<script>
document.getElementById('f').addEventListener('submit', async function(e){
  e.preventDefault();
  var b=document.getElementById('go'), err=document.getElementById('err');
  b.disabled=true; b.innerHTML='در حال بررسی…'; err.textContent='';
  try{
    var r=await fetch('/api/login',{method:'POST',credentials:'same-origin',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({password:document.getElementById('pw').value})});
    var j=await r.json();
    if(j.ok){location.href='/';return}
    err.textContent=j.error||'ورود ناموفق بود';
  }catch(x){err.textContent='خطای شبکه'}
  b.disabled=false; b.textContent='ورود به پنل';
});
</script></body></html>`;

const PANEL_HTML = `<!DOCTYPE html>
<html lang="fa" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>EMIX-PRO — پنل مدیریت</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;800&display=swap">
<style>${BASE_CSS}
.wrap{max-width:1100px;margin:0 auto;padding:18px 16px 60px}
header{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:10px 0 18px}
header .logo{margin:0}
header .logo b{font-size:19px}
.ver{font-size:11px;color:var(--muted2);border:1px solid var(--border);border-radius:99px;padding:2px 10px}
nav{display:flex;gap:8px;flex-wrap:wrap;margin-inline-start:auto}
nav button{background:var(--card);border:1px solid var(--border);color:var(--muted);
  border-radius:10px;padding:8px 16px;font-weight:600;transition:all .15s}
nav button.on{color:var(--accent);border-color:var(--accent);background:rgba(34,211,238,.08)}
h2{font-size:17px;font-weight:800;margin:6px 0 16px}
h2 small{font-weight:400;color:var(--muted);font-size:12px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:16px}
.stat .n{font-size:24px;font-weight:800;color:var(--accent)}
.stat .t{color:var(--muted);font-size:12px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:800px){.two{grid-template-columns:1fr}}
.ev{display:flex;gap:10px;align-items:baseline;padding:8px 0;border-bottom:1px dashed var(--border);font-size:12.5px}
.ev:last-child{border:none}
.ev .ts{color:var(--muted2);font-size:11px;min-width:78px;direction:ltr;text-align:right}
.ev .ty{font-size:10.5px;font-weight:700;border-radius:6px;padding:1px 8px;min-width:52px;text-align:center}
.ty.ok{background:rgba(52,211,153,.12);color:var(--accent2)}
.ty.warn{background:rgba(251,191,36,.12);color:var(--warn)}
.ty.info{background:rgba(34,211,238,.12);color:var(--accent)}
.ty.err{background:rgba(248,113,113,.12);color:var(--danger)}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px;align-items:center}
.toolbar input{max-width:260px}
.cfgs{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
@media(max-width:400px){.cfgs{grid-template-columns:1fr}}
.cfg .top{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.cfg .name{font-weight:700;font-size:15px;word-break:break-word}
.cfg .secret{display:block;color:var(--muted2);font-size:10.5px;margin:2px 0 10px;word-break:break-all}
.usebar{height:7px;border-radius:4px;background:var(--bg2);overflow:hidden;margin:6px 0 4px}
.usebar i{display:block;height:100%;background:linear-gradient(90deg,#0ea5e9,#22d3ee)}
.usebar i.hot{background:linear-gradient(90deg,#f59e0b,#fbbf24)}
.usebar i.full{background:linear-gradient(90deg,#ef4444,#f87171)}
.usetxt{color:var(--muted);font-size:11.5px;display:flex;justify-content:space-between}
.meta{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 12px}
.acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.subrow{display:flex;gap:6px;align-items:center;margin-top:10px}
.subrow .mono{font-size:10.5px;color:var(--muted);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;direction:ltr;text-align:left}
.srgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.srgrid .k{color:var(--muted);font-size:11.5px;margin-bottom:4px}
.srgrid .v{font-size:14px;font-weight:700}
.note{background:rgba(34,211,238,.06);border:1px solid rgba(34,211,238,.2);border-radius:12px;
  padding:14px 16px;font-size:12.5px;color:var(--muted);margin-top:14px;line-height:1.9}
.note b{color:var(--accent)}
.note.warn{background:rgba(251,191,36,.06);border-color:rgba(251,191,36,.25)}
.note.warn b{color:var(--warn)}
label.chk{display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;color:var(--text)}
label.chk input{width:16px;height:16px;accent-color:var(--accent)}
form .field{margin-bottom:14px}
form .field label{display:block;font-size:12px;color:var(--muted);margin-bottom:6px}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:480px){.form-row{grid-template-columns:1fr}}
.modal-bg{position:fixed;inset:0;background:rgba(4,8,18,.72);backdrop-filter:blur(4px);
  z-index:50;display:none;align-items:flex-start;justify-content:center;overflow-y:auto;padding:40px 14px}
.modal-bg.show{display:flex}
.modal{width:min(460px,96vw);background:var(--card);border:1px solid var(--border2);
  border-radius:16px;padding:22px;animation:tin .2s ease}
.modal h3{font-size:15px;margin-bottom:18px}
.modal .btn{width:100%;margin-top:8px}
.hint{font-size:11px;color:var(--muted2);margin-top:4px;line-height:1.8}
.set-card{margin-bottom:14px}
.set-card h3{font-size:14px;margin-bottom:12px;color:var(--accent)}
.kv{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-bottom:1px dashed var(--border);font-size:12.5px}
.kv:last-child{border:none}
.kv .k{color:var(--muted)}
.kv .v{font-weight:600;word-break:break-all;text-align:left;direction:ltr}
.empty{padding:40px 20px;text-align:center;color:var(--muted2);font-size:13px}
.pingbadge{font-variant-numeric:tabular-nums}
footer{margin-top:30px;padding-top:16px;border-top:1px solid var(--border);
  color:var(--muted2);font-size:11px;display:flex;gap:14px;flex-wrap:wrap;justify-content:center}
</style></head><body>
<div class="wrap">
<header>
  <div class="logo">
    <svg viewBox="0 0 24 24" width="26" height="26" fill="none"><path d="M12 2l7 3v6c0 5-3.5 8.5-7 11-3.5-2.5-7-6-7-11V5l7-3z" stroke="#22d3ee" stroke-width="1.6"/><path d="M9 12l2 2 4-4" stroke="#34d399" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
    <b>EMIX<span style="color:var(--accent)">-PRO</span></b>
  </div>
  <span class="ver" id="ver">…</span>
  <nav>
    <button data-v="dashboard" class="on">داشبورد</button>
    <button data-v="configs">کانفیگ‌ها</button>
    <button data-v="smart">مسیریابی هوشمند</button>
    <button data-v="settings">تنظیمات</button>
    <button id="logout" class="danger" style="border-color:rgba(248,113,113,.35);color:var(--danger)">خروج</button>
  </nav>
</header>

<section id="v-dashboard">
  <h2>داشبورد <small>نمای کلی پنل</small></h2>
  <div class="stats" id="stats"></div>
  <div class="two">
    <div class="card"><h2 style="font-size:14px">رویدادهای اخیر</h2><div id="events"></div></div>
    <div class="card"><h2 style="font-size:14px">وضعیت سیستم</h2><div id="sysinfo"></div></div>
  </div>
</section>

<section id="v-configs" style="display:none">
  <h2>کانفیگ‌ها <small id="cfg-count"></small></h2>
  <div class="toolbar">
    <button class="btn sm" id="new-cfg">+ کانفیگ جدید</button>
    <button class="btn ghost sm" id="copy-sub">کپی لینک اشتراک کل</button>
    <input id="q" placeholder="جستجو…">
  </div>
  <div class="cfgs" id="cfgs"></div>
</section>

<section id="v-smart" style="display:none">
  <h2>مسیریابی هوشمند <small>وضعیت صادق زیرساخت</small></h2>
  <div class="card">
    <div class="toolbar" style="margin:0 0 14px">
      <button class="btn ghost sm" id="sr-refresh">بررسی مجدد</button>
      <span id="sr-live" class="badge off">…</span>
    </div>
    <div class="srgrid" id="srgrid"></div>
    <div id="sr-notes"></div>
  </div>
</section>

<section id="v-settings" style="display:none">
  <h2>تنظیمات</h2>
  <div class="card set-card">
    <h3>تغییر رمز عبور پنل</h3>
    <form id="pwform">
      <div class="field"><label>رمز فعلی</label><input type="password" id="cur" required></div>
      <div class="field"><label>رمز جدید (حداقل ۶ نویسه)</label><input type="password" id="new" minlength="6" required></div>
      <button class="btn" type="submit">تغییر رمز</button>
    </form>
  </div>
  <div class="card set-card">
    <h3>اشتراک کلی</h3>
    <div class="subrow"><span class="mono" id="sub-url"></span><button class="btn ghost sm" id="copy-sub2">کپی</button></div>
    <div class="toolbar" style="margin-top:12px">
      <button class="btn ghost sm" id="regen-sub">بازتولید کلید اشتراک</button>
      <button class="btn ghost sm" id="export">خروجی JSON کانفیگ‌ها</button>
    </div>
  </div>
  <div class="card">
    <h3>درباره</h3>
    <div id="about"></div>
  </div>
</section>

<footer>
  <span>EMIX-PRO · هسته Python روی Railway دست‌نخورده</span>
  <a href="https://github.com/EMIXPI/EMIX-PRO" target="_blank" rel="noopener">پروژه در گیت‌هاب</a>
</footer>
</div>

<div class="modal-bg" id="modal-bg">
  <div class="modal">
    <h3 id="m-title">کانفیگ جدید</h3>
    <form id="m-form">
      <input type="hidden" id="m-id">
      <div class="field"><label>نام / برچسب</label><input id="m-label" placeholder="مثلاً: کانفیگ اصلی" maxlength="60"></div>
      <div class="form-row">
        <div class="field"><label>پروتکل</label>
          <select id="m-protocol"><option value="vless-ws">VLESS (WebSocket)</option><option value="trojan-ws">Trojan (WebSocket)</option></select>
        </div>
        <div class="field"><label>اثر انگشت TLS</label>
          <select id="m-fp"><option value="chrome">chrome</option><option value="firefox">firefox</option><option value="ios">ios</option></select>
        </div>
      </div>
      <div class="form-row">
        <div class="field"><label>محدودیت حجم (گیگابایت)</label><input id="m-limit" type="number" min="0" step="0.5" placeholder="نامحدود"></div>
        <div class="field"><label>مسیریابی ایران</label>
          <select id="m-iran"><option value="OFF">خاموش</option><option value="AUTO">خودکار</option><option value="DIRECT">مستقیم</option></select>
        </div>
      </div>
      <div class="field"><label>یادداشت</label><input id="m-note" maxlength="200" placeholder="اختیاری"></div>
      <label class="chk"><input type="checkbox" id="m-turbo"> توربو (Early-Data ed=2048 — کاهش پینگ)</label>
      <div class="hint" id="m-edit-extra" style="display:none;margin-top:10px">
        <label class="chk" style="margin-bottom:8px"><input type="checkbox" id="m-active"> فعال</label>
        <label class="chk"><input type="checkbox" id="m-reset"> صفر کردن مصرف و سشن‌ها</label>
      </div>
      <button class="btn" type="submit" id="m-save">ساخت کانفیگ</button>
      <button class="btn ghost" type="button" id="m-cancel">انصراف</button>
    </form>
  </div>
</div>

<div class="toast-box" id="toasts"></div>

<script>
var VERSION='';
var LINKS=[], SETTINGS={};

// ── helpers ─────────────────────────────────────────────────────
function toast(msg, err){
  var t=document.createElement('div'); t.className='toast'+(err?' err':'');
  t.textContent=msg; document.getElementById('toasts').appendChild(t);
  setTimeout(function(){t.style.opacity='0';t.style.transition='opacity .3s';setTimeout(function(){t.remove()},320)},2600);
}
function copy(text, label){
  var done=function(){toast((label||'کپی شد')+' ✓')};
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(done,function(){fallback()});
  } else fallback();
  function fallback(){
    var ta=document.createElement('textarea');ta.value=text;ta.style.position='fixed';ta.style.opacity='0';
    document.body.appendChild(ta);ta.select();
    try{document.execCommand('copy');done()}catch(e){toast('کپی ناموفق',true)}
    ta.remove();
  }
}
function fmtBytes(n){
  if(!n||n<1)return '۰ بایت';
  var u=['بایت','کیلوبایت','مگابایت','گیگابایت','ترابایت'],i=0,v=n;
  while(v>=1024&&i<u.length-1){v/=1024;i++}
  return (v>=100?v.toFixed(0):v.toFixed(1))+' '+u[i];
}
function faNum(s){return String(s).replace(/[0-9]/g,function(d){return '۰۱۲۳۴۵۶۷۸۹'[+d]})}
function timeAgo(iso){
  if(!iso)return '—';
  var s=(Date.now()-new Date(iso).getTime())/1000;
  if(s<60)return 'همین حالا'; if(s<3600)return faNum(Math.floor(s/60))+' دقیقه پیش';
  if(s<86400)return faNum(Math.floor(s/3600))+' ساعت پیش';
  return faNum(Math.floor(s/86400))+' روز پیش';
}
function api(path, opts){
  opts=opts||{}; opts.credentials='same-origin';
  if(opts.body&&typeof opts.body==='object'){opts.headers={'Content-Type':'application/json'};opts.body=JSON.stringify(opts.body)}
  return fetch(path,opts).then(function(r){return r.json().catch(function(){return{}}).then(function(j){
    if(r.status===401&&location.pathname!=='/login'){location.href='/login';throw new Error('unauthorized')}
    return j;
  })});
}
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}

// ── ناوبری ──────────────────────────────────────────────────────
var views=['dashboard','configs','smart','settings'];
function show(v){
  views.forEach(function(x){
    var el=document.getElementById('v-'+x); if(el)el.style.display=(x===v?'':'none');
  });
  document.querySelectorAll('nav button[data-v]').forEach(function(b){b.classList.toggle('on',b.dataset.v===v)});
  location.hash=v;
  if(v==='smart')loadSmart();
}
document.querySelectorAll('nav button[data-v]').forEach(function(b){
  b.addEventListener('click',function(){show(b.dataset.v)});
});
var h=location.hash.replace('#',''); if(views.indexOf(h)<0)h='dashboard';

// ── داشبورد ─────────────────────────────────────────────────────
function loadDashboard(){
  api('/api/stats').then(function(j){
    if(!j.ok)return;
    var s=j.stats;
    document.getElementById('stats').innerHTML=
      '<div class="card stat"><div class="n">'+faNum(s.total_links)+'</div><div class="t">کانفیگ‌ها</div></div>'+
      '<div class="card stat"><div class="n">'+faNum(s.active_links)+'</div><div class="t">فعال</div></div>'+
      '<div class="card stat"><div class="n">'+fmtBytes(s.used_bytes)+'</div><div class="t">مصرف کل</div></div>'+
      '<div class="card stat"><div class="n">'+faNum(s.sessions)+'</div><div class="t">اتصالات ثبت‌شده</div></div>';
    var map={login_ok:'ok',login_fail:'err',login_blocked:'err',link_create:'info',link_edit:'info',
             link_delete:'err',password_change:'warn',sub_regen:'info',boot:'info',proxy:'info'};
    var names={login_ok:'ورود',login_fail:'ورود ناموفق',login_blocked:'مسدود',link_create:'ساخت',
               link_edit:'ویرایش',link_delete:'حذف',password_change:'رمز',sub_regen:'اشتراک',boot:'راه‌اندازی',proxy:'پروکسی'};
    document.getElementById('events').innerHTML=(j.events||[]).map(function(e){
      return '<div class="ev"><span class="ts">'+new Date(e.ts).toLocaleTimeString('fa-IR')+'</span>'+
        '<span class="ty '+(map[e.type]||'info')+'">'+(names[e.type]||e.type)+'</span>'+
        '<span>'+esc(e.detail)+'</span></div>';
    }).join('')||'<div class="empty">رویدادی نیست</div>';
    document.getElementById('sysinfo').innerHTML=
      kv('نسخه',j.version)+kv('پلتفرم',j.platform)+
      kv('ذخیره‌سازی','Cloudflare D1')+
      kv('سشن‌ها','Cloudflare KV')+kv('کل رویدادها',faNum(s.events));
    function kv(k,v){return '<div class="kv"><span class="k">'+k+'</span><span class="v">'+v+'</span></div>'}
  });
}

// ── کانفیگ‌ها ───────────────────────────────────────────────────
function loadConfigs(){
  api('/api/links').then(function(j){
    if(!j.ok)return;
    LINKS=j.links;
    document.getElementById('cfg-count').textContent='('+faNum(j.count)+' کانفیگ)';
    renderConfigs();
  });
}
function renderConfigs(){
  var q=(document.getElementById('q').value||'').trim();
  var list=LINKS.filter(function(l){return !q||l.label.indexOf(q)>-1||(l.id||'').indexOf(q)>-1});
  var box=document.getElementById('cfgs');
  if(!list.length){box.innerHTML='<div class="empty" style="grid-column:1/-1">کانفیگی نیست — «کانفیگ جدید» را بزنید</div>';return}
  box.innerHTML=list.map(function(l){
    var protoBadge=l.protocol==='trojan-ws'?'<span class="badge trojan">TROJAN</span>':'<span class="badge vless">VLESS</span>';
    var status=l.active?'<span class="badge ok">فعال</span>':'<span class="badge off">غیرفعال</span>';
    var used=l.used_bytes||0, lim=l.limit_bytes||0;
    var pct=lim?Math.min(100,Math.round(used/lim*100)):0;
    var bar=pct>=100?'full':(pct>=80?'hot':'');
    var secretShort=l.protocol==='trojan-ws'?l.share_url.split('@')[0].split('//')[1]:(l.id||'');
    var pingB=l.ping&&l.ping.median_ms?'<span class="badge warn pingbadge">'+faNum(l.ping.median_ms)+' ms · Client</span>':'<span class="badge off">Ping —</span>';
    var iranB=l.iran_mode&&l.iran_mode!=='OFF'?'<span class="badge warn">ایران: '+({AUTO:'خودکار',DIRECT:'مستقیم'}[l.iran_mode]||l.iran_mode)+'</span>':'';
    var turboB=l.turbo_enabled?'<span class="badge ok">توربو</span>':'';
    return '<div class="card cfg" data-id="'+l.id+'">'+
      '<div class="top"><span class="name">'+esc(l.label)+'</span>'+protoBadge+status+'</div>'+
      '<span class="secret mono">'+esc(secretShort.slice(0,26))+'</span>'+
      '<div class="usebar"><i class="'+bar+'" style="width:'+pct+'%"></i></div>'+
      '<div class="usetxt"><span>'+fmtBytes(used)+(lim?' / '+fmtBytes(lim):' (نامحدود)')+'</span><span>'+faNum(pct)+'٪</span></div>'+
      '<div class="meta">'+pingB+iranB+turboB+
        (l.sessions?'<span class="badge off">'+faNum(l.sessions)+' اتصال</span>':'')+'</div>'+
      '<div class="subrow"><span class="mono">…/sub/'+esc(l.id.slice(0,8))+'</span>'+
        '<button class="btn ghost sm" data-act="copysub">کپی اشتراک</button></div>'+
      '<div class="acts">'+
        '<button class="btn sm" data-act="copy">کپی لینک</button>'+
        '<button class="btn ghost sm" data-act="ping">تست پینگ</button>'+
        '<button class="btn ghost sm" data-act="edit">ویرایش</button>'+
        '<button class="btn danger sm" data-act="del">حذف</button>'+
      '</div></div>';
  }).join('');
  box.querySelectorAll('button[data-act]').forEach(function(b){
    b.addEventListener('click',function(){var id=b.closest('.cfg').dataset.id;cfgAction(b.dataset.act,id,b)});
  });
}
function cfgAction(act,id,btn){
  var l=LINKS.filter(function(x){return x.id===id})[0]; if(!l)return;
  if(act==='copy'){copy(l.share_url,'لینک کانفیگ');return}
  if(act==='copysub'){copy(l.sub_url,'لینک اشتراک');return}
  if(act==='edit'){openModal(l);return}
  if(act==='del'){
    if(!confirm('کانفیگ «'+l.label+'» حذف شود؟'))return;
    api('/api/links/'+id,{method:'DELETE'}).then(function(j){
      if(j.ok){toast('حذف شد');loadConfigs();loadDashboard()}else toast(j.error||'خطا',true);
    });
    return;
  }
  if(act==='ping'){
    var old=btn.innerHTML; btn.innerHTML='<span class="spin">↻</span>'; btn.disabled=true;
    measureClientPing().then(function(samples){
      if(samples.length<5){btn.innerHTML=old;btn.disabled=false;toast('اندازه‌گیری ناموفق (نمونه کافی نیست)',true);return}
      return api('/api/links/'+id+'/client-ping',{method:'POST',body:{samples:samples,sent:6}})
        .then(function(j){
          btn.innerHTML=old;btn.disabled=false;
          if(j.ok&&j.ping){toast('پینگ کلاینت: '+faNum(j.ping.median_ms)+' ms (median)');loadConfigs()}
          else toast((j&&j.error)||'خطا',true);
        });
    }).catch(function(){btn.innerHTML=old;btn.disabled=false;toast('خطای اندازه‌گیری',true)});
  }
}
// پینگ صادق کلاینت: RTT واقعی HTTPS از همین مرورگر (مثل هسته: ۱ گرم + ۶ نمونه)
function measureClientPing(){
  var samples=[];
  return fetch('/health',{mode:'no-cors',cache:'no-store'}).catch(function(){})
    .then(function(){return probe()});
  function probe(){
    if(samples.length>=6)return samples;
    var t0=performance.now();
    return fetch('/health',{mode:'no-cors',cache:'no-store'}).catch(function(){})
      .then(function(){
        var dt=performance.now()-t0; if(dt>0)samples.push(Math.round(dt*10)/10);
        return probe();
      });
  }
}

// ── مودال ساخت/ویرایش ──────────────────────────────────────────
var modalBg=document.getElementById('modal-bg');
function openModal(l){
  document.getElementById('m-title').textContent=l?'ویرایش کانفیگ':'کانفیگ جدید';
  document.getElementById('m-save').textContent=l?'ذخیره تغییرات':'ساخت کانفیگ';
  document.getElementById('m-id').value=l?l.id:'';
  document.getElementById('m-label').value=l?l.label:'';
  document.getElementById('m-protocol').value=l?l.protocol:'vless-ws';
  document.getElementById('m-protocol').disabled=!!l;
  document.getElementById('m-fp').value=l?l.fingerprint:'chrome';
  document.getElementById('m-limit').value=l&&l.limit_bytes?(l.limit_bytes/1073741824):'';
  document.getElementById('m-iran').value=l?l.iran_mode:'OFF';
  document.getElementById('m-note').value=l?l.note:'';
  document.getElementById('m-turbo').checked=!!(l&&l.turbo_enabled);
  document.getElementById('m-edit-extra').style.display=l?'':'none';
  if(l){document.getElementById('m-active').checked=!!l.active;document.getElementById('m-reset').checked=false}
  modalBg.classList.add('show');
}
document.getElementById('new-cfg').addEventListener('click',function(){openModal(null)});
document.getElementById('m-cancel').addEventListener('click',function(){modalBg.classList.remove('show')});
modalBg.addEventListener('click',function(e){if(e.target===modalBg)modalBg.classList.remove('show')});
document.getElementById('m-form').addEventListener('submit',function(e){
  e.preventDefault();
  var id=document.getElementById('m-id').value;
  var body={
    label:document.getElementById('m-label').value,
    protocol:document.getElementById('m-protocol').value,
    fingerprint:document.getElementById('m-fp').value,
    limit_gb:parseFloat(document.getElementById('m-limit').value)||0,
    iran_mode:document.getElementById('m-iran').value,
    note:document.getElementById('m-note').value,
    turbo_enabled:document.getElementById('m-turbo').checked,
  };
  var p;
  if(id){
    body.active=document.getElementById('m-active').checked;
    body.reset_usage=document.getElementById('m-reset').checked;
    p=api('/api/links/'+id,{method:'PATCH',body:body});
  } else p=api('/api/links',{method:'POST',body:body});
  p.then(function(j){
    if(j.ok){modalBg.classList.remove('show');toast(id?'ذخیره شد':'کانفیگ ساخته شد');loadConfigs();loadDashboard()}
    else toast((j&&j.error)||'خطا',true);
  });
});
document.getElementById('q').addEventListener('input',renderConfigs);

// ── مسیریابی هوشمند ────────────────────────────────────────────
var SR_BUSY=false;
function loadSmart(){
  if(SR_BUSY)return; SR_BUSY=true;
  var live=document.getElementById('sr-live');
  live.className='badge off'; live.textContent='در حال بررسی…';
  api('/api/smart-routing/status').then(function(j){
    SR_BUSY=false;
    if(!j.ok){live.textContent='خطا';live.className='badge warn';return}
    var stateTxt={HEALTHY:'سالم (HEALTHY)',REGISTERED:'ثبت‌شده (REGISTERED)',DEGRADED:'مضطرب (DEGRADED)',
                  FAILED:'خراب (FAILED)',UNKNOWN:'نامشخص (UNKNOWN)'}[j.state]||j.state;
    live.className='badge '+(j.state==='HEALTHY'?'ok':(j.state==='DEGRADED'||j.state==='FAILED'?'warn':'off'));
    live.textContent=stateTxt;
    var h=j.health||{}, p=j.probe||{};
    var up=h.upstream||{};
    document.getElementById('srgrid').innerHTML=
      srow('وضعیت ورکر SR',stateTxt)+
      srow('ورکر',esc((j.sr_worker_url||'').replace('https://','')))+
      srow('مرکز داده (Colo)',esc(h.colo||'—'))+
      srow('نسخه ورکر',esc(h.version||'—'))+
      srow('سلامت upstream',(up.ok===true?'✓ سالم':(up.ok===false?'✗ بی‌پاسخ':'—')))+
      srow('تأخیر upstream',up.latency_ms!=null?faNum(up.latency_ms)+' ms':'—')+
      srow('probe امضادار',(p.ok===true?'✓ موفق':(p.ok===false?'✗ ناموفق':'—')))+
      srow('Edge→Upstream',p.edge_to_upstream_ms!=null?faNum(p.edge_to_upstream_ms)+' ms':'—');
    function srow(k,v){return '<div class="card"><div class="k">'+k+'</div><div class="v">'+v+'</div></div>'}
    var notes='<div class="note"><b>معماری فعلی:</b> پنل روی لبه‌ی کلادفلیر سرو می‌شود (همین دامنه)؛ '+
      'ورکر SR به‌عنوان نقطه‌ی پایش باقی است و upstream آن پنل Railway قبلی بود.</div>';
    if(j.upstream_note)notes+='<div class="note warn"><b>صادقانه:</b> '+esc(j.upstream_note)+
      ' — کانفیگ‌های این پنل مستقیماً از همین Worker سرو می‌شوند و مستقل از upstream هستند.</div>';
    document.getElementById('sr-notes').innerHTML=notes;
  }).catch(function(){SR_BUSY=false;live.textContent='خطا';live.className='badge warn'});
}
document.getElementById('sr-refresh').addEventListener('click',loadSmart);

// ── تنظیمات ────────────────────────────────────────────────────
function loadSettings(){
  api('/api/settings').then(function(j){
    if(!j.ok)return; SETTINGS=j;
    document.getElementById('sub-url').textContent=j.sub_url;
    document.getElementById('about').innerHTML=
      '<div class="kv"><span class="k">نسخه</span><span class="v">'+esc(j.version)+'</span></div>'+
      '<div class="kv"><span class="k">پلتفرم</span><span class="v">Cloudflare Workers · D1 + KV</span></div>'+
      '<div class="kv"><span class="k">تاریخ راه‌اندازی</span><span class="v">'+esc(timeAgo(j.panel_created_at))+'</span></div>'+
      '<div class="kv"><span class="k">مخزن</span><span class="v"><a href="'+esc(j.repository)+'" target="_blank" rel="noopener">EMIXPI/EMIX-PRO</a></span></div>';
  });
}
document.getElementById('pwform').addEventListener('submit',function(e){
  e.preventDefault();
  api('/api/settings/password',{method:'POST',body:{
    current:document.getElementById('cur').value,next:document.getElementById('new').value
  }}).then(function(j){
    if(j.ok){toast('رمز تغییر کرد ✓');document.getElementById('pwform').reset()}
    else toast(j.error||'خطا',true);
  });
});
document.getElementById('copy-sub').addEventListener('click',function(){if(SETTINGS.sub_url)copy(SETTINGS.sub_url,'لینک اشتراک')});
document.getElementById('copy-sub2').addEventListener('click',function(){if(SETTINGS.sub_url)copy(SETTINGS.sub_url,'لینک اشتراک')});
document.getElementById('regen-sub').addEventListener('click',function(){
  if(!confirm('کلید اشتراک قبلی بی‌اعتبار می‌شود. ادامه؟'))return;
  api('/api/settings/sub-regenerate',{method:'POST'}).then(function(j){
    if(j.ok){toast('کلید اشتراک بازتولید شد');loadSettings()}else toast(j.error||'خطا',true);
  });
});
document.getElementById('export').addEventListener('click',function(){
  api('/api/export').then(function(j){
    if(!j.ok)return;
    var blob=new Blob([JSON.stringify(j,null,2)],{type:'application/json'});
    var a=document.createElement('a');a.href=URL.createObjectURL(blob);
    a.download='emix-pro-configs.json';a.click();URL.revokeObjectURL(a.href);
    toast('خروجی آماده شد');
  });
});

// ── خروج و شروع ────────────────────────────────────────────────
document.getElementById('logout').addEventListener('click',function(){
  api('/api/logout',{method:'POST'}).then(function(){location.href='/login'});
});
api('/api/version').then(function(j){VERSION=j.version||'';
  document.getElementById('ver').textContent='نسخه '+VERSION+' · Workers'});
show(h); loadDashboard(); loadConfigs(); loadSettings();
</script></body></html>`;
// ─── روتر اصلی ───────────────────────────────────────────────────────────────

const FAVICON = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
<path d="M12 2l7 3v6c0 5-3.5 8.5-7 11-3.5-2.5-7-6-7-11V5l7-3z" stroke="#22d3ee" stroke-width="1.6"/>
<path d="M9 12l2 2 4-4" stroke="#34d399" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const path = decodeURIComponent(url.pathname);
    const method = req.method;

    // مقداردهی خودکار در هر دیپلوی/ری‌دیپلوی (idempotent)
    try {
      await ensureReady(env);
    } catch (e) {
      return json({ ok: false, error: "init failed: " + (e && e.message) }, 500);
    }

    try {
      // ── پروکسی (WebSocket) ──
      if (req.headers.get("Upgrade") === "websocket") {
        if (path.startsWith("/ws/")) return await handleVlessWS(req, env, path.slice(4).split("?")[0]);
        if (path === "/trojan-ws") return await handleTrojanWS(req, env);
        return wsReject(404, "EMIX-PRO");
      }

      // ── عمومی ──
      if (path === "/health" && method === "GET") {
        return json({ ok: true, panel: "emix-pro", version: VERSION, platform: PLATFORM, storage: "d1+kv" });
      }
      if (path === "/api/version" && method === "GET") {
        return json({ ok: true, version: VERSION, platform: PLATFORM });
      }
      if (path === "/robots.txt") {
        return new Response("User-agent: *\nDisallow: /\n", { headers: { "Content-Type": "text/plain" } });
      }
      if (path === "/favicon.ico") {
        return new Response(FAVICON, { headers: { "Content-Type": "image/svg+xml", "Cache-Control": "public, max-age=86400" } });
      }
      if (path === "/api/login" && method === "POST") return await apiLogin(req, env);
      if (path === "/api/authenticated" && method === "GET") {
        return json({ authenticated: await isValidSession(env, req) });
      }
      if (path === "/api/logout" && method === "POST") return await apiLogout(req, env);

      // ── اشتراک‌ها (عمومی — کلید/UUID خودشان راز‌اند) ──
      if (path.startsWith("/sub/") && method === "GET") {
        return await handleSubscription(req, env, path.slice(5).split("?")[0]);
      }
      const iranMatch = path.match(/^\/api\/links\/([A-Za-z0-9-]+)\/iran-config$/);
      if (iranMatch && method === "GET") {
        return await handleIranConfig(req, env, iranMatch[1]);
      }

      // ── صفحات پنل ──
      if (method === "GET" && (path === "/login" || path === "/")) {
        const authed = await isValidSession(env, req);
        if (path === "/login") {
          if (authed) return Response.redirect(url.origin + "/", 302);
          return html(LOGIN_HTML);
        }
        if (!authed) return Response.redirect(url.origin + "/login", 302);
        return html(PANEL_HTML);
      }

      // ── API محافظت‌شده ──
      if (path.startsWith("/api/")) {
        if (!(await isValidSession(env, req))) {
          return json({ ok: false, error: "unauthorized" }, 401);
        }
        if (path === "/api/links" && method === "GET") return await apiListLinks(req, env);
        if (path === "/api/links" && method === "POST") return await apiCreateLink(req, env);
        if (path === "/api/stats" && method === "GET") return await apiStats(env);
        if (path === "/api/settings" && method === "GET") return await apiSettings(req, env);
        if (path === "/api/settings/password" && method === "POST") return await apiChangePassword(req, env);
        if (path === "/api/settings/sub-regenerate" && method === "POST") return await apiRegenSub(req, env);
        if (path === "/api/export" && method === "GET") return await apiExport(req, env);
        if (path === "/api/smart-routing/status" && method === "GET") return await apiSmartRouting(req, env);

        const m = path.match(/^\/api\/links\/([A-Za-z0-9-]+)(\/client-ping)?$/);
        if (m) {
          const id = m[1];
          if (m[2] === "/client-ping" && method === "POST") return await apiClientPing(req, env, id);
          if (method === "PATCH") return await apiUpdateLink(req, env, id);
          if (method === "DELETE") return await apiDeleteLink(req, env, id);
        }
        return json({ ok: false, error: "not found" }, 404);
      }

      return Response.redirect(url.origin + "/", 302);
    } catch (e) {
      return json({ ok: false, error: "internal: " + (e && e.message) }, 500);
    }
  },
};
