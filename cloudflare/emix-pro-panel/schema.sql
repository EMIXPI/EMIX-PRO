-- EMIX-PRO Panel (Workers edition) — D1 schema
-- این فایل مرجع است؛ خودِ Worker در اولین request هر isolate همین اسکیمای
-- idempotent را با CREATE TABLE IF NOT EXISTS می‌سازد (خودکار در هر دیپلوی).

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS links (
  id TEXT PRIMARY KEY,                      -- UUID (VLESS credential)
  label TEXT NOT NULL DEFAULT 'EMIX',
  protocol TEXT NOT NULL DEFAULT 'vless-ws',-- vless-ws | trojan-ws
  secret TEXT NOT NULL,                     -- رمز Trojan
  secret_hash TEXT,                         -- hex(SHA-224(secret)) — lookup هنگام اتصال
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
);

CREATE TABLE IF NOT EXISTS ping_stats (
  link_id TEXT PRIMARY KEY,
  median_ms REAL, min_ms REAL, max_ms REAL, avg_ms REAL,
  jitter_ms REAL, loss REAL, samples INTEGER,
  measured_at TEXT, measured_by TEXT
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  type TEXT NOT NULL,
  detail TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  exp INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_links_secret_hash ON links(secret_hash);

-- مقادیر پیش‌فرض (Worker خودش materialize می‌کند — فقط اگر غایب باشند):
--   admin_salt, admin_password_hash, sub_secret,
--   sr_worker_url, panel_created_at, seeded_version
