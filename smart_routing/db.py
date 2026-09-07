# smart_routing/db.py — ذخیره‌گاه SQLite افزودنی (Railway-volume-compatible)
# ══════════════════════════════════════════════════════════════════════════════
# طراحی:
#   • فایل مستقل: DATA_DIR/smart_routing.db — state مهم هرگز فقط در RAM نیست.
#   • کاملاً additive: rvg_state.json هسته دست نمی‌خورد؛ migration فقط
#     CREATE TABLE IF NOT EXISTS / ADD COLUMN گاردشده (غیر destructive).
#   • Railway: DATA_DIR=/data روی volume → بین دیپلوی‌ها می‌ماند.
#   • Thread-safe با lock (تراکنش‌های کوتاه میلی‌ثانیه‌ای).
# ══════════════════════════════════════════════════════════════════════════════

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

# DATA_DIR مستقیماً از env (همان قرارداد main.py — بدون import برای جلوگیری از
# circular import؛ سمت پروداکشن Railway آن را /data ست می‌کند).
DB_FILE = Path(os.environ.get("DATA_DIR", "/data")) / "smart_routing.db"

_LOCK = threading.RLock()
_CONN: sqlite3.Connection | None = None

SCHEMA_VERSION = 1

# ── Schema v1 (جداول سند کاربر) — همه‌ی IF NOT EXISTS ─────────────────────────
_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS sr_meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);
CREATE TABLE IF NOT EXISTS smart_endpoints (
  id                 TEXT PRIMARY KEY,          -- شناسه‌ی پایدار (sha256 آدرس نرمال‌شده)
  address            TEXT NOT NULL,             -- آدرس فرانت (hostname)
  port               INTEGER NOT NULL DEFAULT 443,
  protocol           TEXT,                      -- vless-ws / trojan-ws / mixed
  transport          TEXT DEFAULT 'ws',
  tls                INTEGER DEFAULT 1,
  sni                TEXT,
  country            TEXT,                      -- ادعای متادیتا (فقط نمایش؛ verdict = observed_*)
  asn                TEXT,
  egress_ip          TEXT,                      -- observed (اندازه‌گیری‌شده)
  observed_ip        TEXT,
  observed_country   TEXT,
  observed_asn       TEXT,
  observed_asn_num   INTEGER,
  latency_ms         REAL,
  jitter_ms          REAL,
  packet_loss        REAL,                      -- 0..1
  uptime_pct         REAL,                      -- 0..100 از تاریخچه
  health_status      TEXT DEFAULT 'UNKNOWN',    -- HEALTHY/DEGRADED_HEALTH/UNHEALTHY
  status             TEXT DEFAULT 'UNKNOWN',    -- UNKNOWN/ACTIVE/DEGRADED/UNHEALTHY/QUARANTINED/INVALID
  score              REAL,
  source             TEXT,                      -- panel-link / cf-worker / manual / public-list
  capabilities       TEXT DEFAULT '{}',         -- JSON: {"IRAN_EGRESS": bool, ...}
  verification       TEXT DEFAULT '{}',         -- JSON: pipeline کامل + stageها
  history            TEXT DEFAULT '[]',         -- JSON: آخرین N چک
  last_check         REAL,
  created_at         REAL,
  updated_at         REAL
);
CREATE TABLE IF NOT EXISTS smart_routes (
  id             TEXT PRIMARY KEY,
  endpoint_id    TEXT NOT NULL,
  mode           TEXT,                          -- AUTO/LOW_LATENCY/STABLE/IRAN_OPTIMIZED
  current_score  REAL,
  is_primary     INTEGER DEFAULT 0,
  fallback_order INTEGER DEFAULT 0,
  created_at     REAL,
  updated_at     REAL
);
CREATE TABLE IF NOT EXISTS route_health_checks (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  endpoint_id  TEXT NOT NULL,
  ts           REAL,
  ok           INTEGER,
  latency_ms   REAL,
  jitter_ms    REAL,
  packet_loss  REAL,
  detail       TEXT
);
CREATE TABLE IF NOT EXISTS route_events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          REAL,
  kind        TEXT,                             -- discovery/verify/status/selection/failover/worker
  endpoint_id TEXT,
  message     TEXT,
  detail      TEXT
);
CREATE TABLE IF NOT EXISTS route_selections (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  ts                 REAL,
  link_uid           TEXT,
  mode               TEXT,
  chosen_endpoint_id TEXT,
  reason             TEXT,
  score              REAL
);
CREATE TABLE IF NOT EXISTS smart_settings (
  key   TEXT PRIMARY KEY,
  value TEXT                                    -- JSON
);
CREATE TABLE IF NOT EXISTS sr_nonces (
  nonce TEXT PRIMARY KEY,
  ts    REAL
);
CREATE INDEX IF NOT EXISTS idx_rhc_endpoint_ts ON route_health_checks(endpoint_id, ts);
CREATE INDEX IF NOT EXISTS idx_re_ts ON route_events(ts);
"""


def _connect() -> sqlite3.Connection:
    global _CONN
    if _CONN is None:
        DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CONN = sqlite3.connect(str(DB_FILE), check_same_thread=False)
        _CONN.row_factory = sqlite3.Row
        _CONN.execute("PRAGMA journal_mode=WAL")
        _CONN.execute("PRAGMA synchronous=NORMAL")
    return _CONN


def ensure_schema() -> None:
    """ایجاد/به‌روزرسانی امن schema — idempotent و غیر destructive."""
    with _LOCK:
        conn = _connect()
        conn.executescript(_SCHEMA_V1)
        cur = conn.execute("SELECT value FROM sr_meta WHERE key='schema_version'")
        row = cur.fetchone()
        if row is None:
            conn.execute(
                "INSERT OR REPLACE INTO sr_meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
        else:
            current = int(row["value"] or 1)
            if current > SCHEMA_VERSION:          # downgrade → دست نمی‌زنیم
                pass
            else:
                conn.execute(
                    "UPDATE sr_meta SET value=? WHERE key='schema_version'",
                    (str(SCHEMA_VERSION),),
                )
        conn.commit()


def _add_column_safe(table: str, column: str, ddl: str) -> None:
    """ADD COLUMN گاردشده — برای migrationهای آینده (idempotent)."""
    with _LOCK:
        conn = _connect()
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
            conn.commit()


# ── settings ──────────────────────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "enabled": True,               # v13.5.0: پیش‌فرض روشن — fresh-deploy بدون تگل دستی کار می‌کند (row DB → override ادمین)
    "worker_url": "https://emix-smart-routing-v1.personalemixone.workers.dev",  # v13.5.0: Worker پیش‌فرض پروژه (public URL — secret نیست)
    "worker_key": "",               # کلید HMAC مشترک (ثبت‌شده از UI/API یا env SR_SIGNING_KEY — هرگز hardcode)
    "score_weights": {              # وزن‌های قابل‌تنظیم (جمع = 1)
        "latency": 0.30, "jitter": 0.15, "packet_loss": 0.20,
        "uptime": 0.15, "availability": 0.10, "egress": 0.10,
    },
    "discovery_interval_s": 900,    # ۱۵ دقیقه
    "health_interval_active_s": 60,
    "health_interval_idle_s": 300,
    "health_interval_quarantine_s": 600,
    "probe_rounds": 5,              # تعداد پروب برای jitter/loss (چند‌باره — ضد تصادفی)
    "manual_candidates": [],        # [{address, port, note}] — اپراتور
    "public_list_urls": [],         # URLهای https منابع عمومی (پیش‌فرض خالی = بدون اسکن)
    "iran_direct_enabled": False,   # Iran Direct (DOMESTIC_ROUTE) — قابل خاموش/روشن
    "selection_gap_pct": 10,        # hysteresis: حداقل فاصله‌ی امتیاز برای سوییچ
    "selection_cooldown_s": 120,    # ضد oscillation
}


def get_setting(key: str, default=None):
    try:
        with _LOCK:
            row = _connect().execute(
                "SELECT value FROM smart_settings WHERE key=?", (key,)
            ).fetchone()
        if row is None:
            return DEFAULT_SETTINGS.get(key, default)
        return json.loads(row["value"])
    except Exception:
        return DEFAULT_SETTINGS.get(key, default)


def has_setting(key: str) -> bool:
    """آیا row تنظیم وجود دارد؟ (تمایز «هرگز ثبت نشده» از «ثبتِ خالیِ صریح»)"""
    try:
        with _LOCK:
            row = _connect().execute(
                "SELECT value FROM smart_settings WHERE key=?", (key,)
            ).fetchone()
        return row is not None
    except Exception:
        return False


def set_setting(key: str, value) -> None:
    with _LOCK:
        conn = _connect()
        conn.execute(
            "INSERT OR REPLACE INTO smart_settings(key, value) VALUES(?, ?)",
            (key, json.dumps(value, ensure_ascii=False)),
        )
        conn.commit()


def all_settings() -> dict:
    out = dict(DEFAULT_SETTINGS)
    try:
        with _LOCK:
            rows = _connect().execute("SELECT key, value FROM smart_settings").fetchall()
        for r in rows:
            try:
                out[r["key"]] = json.loads(r["value"])
            except Exception:
                pass
    except Exception:
        pass
    # کلید حساس هرگز خاموش برگردانده نمی‌شود (فقط mask)
    if out.get("worker_key"):
        k = out["worker_key"]
        out["worker_key_masked"] = (k[:4] + "…" + k[-4:]) if len(k) > 8 else "…"
    out.pop("worker_key", None)
    return out


# ── endpoints ─────────────────────────────────────────────────────────────────
def endpoint_id_for(address: str, port: int) -> str:
    import hashlib
    host = (address or "").strip().lower()
    return hashlib.sha256(f"{host}:{int(port or 443)}".encode()).hexdigest()[:16]


def upsert_endpoint(ep: dict) -> None:
    cols = [
        "id", "address", "port", "protocol", "transport", "tls", "sni", "country",
        "asn", "egress_ip", "observed_ip", "observed_country", "observed_asn",
        "observed_asn_num", "latency_ms", "jitter_ms", "packet_loss", "uptime_pct",
        "health_status", "status", "score", "source", "capabilities",
        "verification", "history", "iran_egress", "last_check", "created_at", "updated_at",
    ]
    # iran_egress ستون جدا ندارد در _SCHEMA_V1؟ دارد در capabilities؛ ولی ستون هم می‌گذاریم (موجود در schema؟ نه) → capabilities نگه‌دار
    clean = {k: v for k, v in ep.items() if k in cols}
    for k in ("capabilities", "verification", "history"):
        if k in clean and not isinstance(clean[k], str):
            clean[k] = json.dumps(clean[k], ensure_ascii=False)
    clean.setdefault("updated_at", time.time())
    keys = ", ".join(clean.keys())
    marks = ", ".join("?" for _ in clean)
    with _LOCK:
        conn = _connect()
        conn.execute(
            f"INSERT OR REPLACE INTO smart_endpoints({keys}) VALUES({marks})",
            list(clean.values()),
        )
        conn.commit()


def get_endpoint(ep_id: str) -> dict | None:
    with _LOCK:
        row = _connect().execute(
            "SELECT * FROM smart_endpoints WHERE id=?", (ep_id,)
        ).fetchone()
    return _row_to_endpoint(row)


def list_endpoints(only_pool: str | None = None) -> list[dict]:
    q = "SELECT * FROM smart_endpoints"
    args: list = []
    if only_pool:
        q += " WHERE status=?"
        args.append(only_pool)
    q += " ORDER BY (score IS NULL), score DESC"
    with _LOCK:
        rows = _connect().execute(q, args).fetchall()
    return [_row_to_endpoint(r) for r in rows]


def _row_to_endpoint(row) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for k in ("capabilities", "verification", "history"):
        v = d.get(k)
        if isinstance(v, str) and v:
            try:
                d[k] = json.loads(v)
            except Exception:
                d[k] = {} if k != "history" else []
    return d


# ── health checks / events / selections ───────────────────────────────────────
def add_health_check(endpoint_id: str, ok: bool, latency_ms=None, jitter_ms=None,
                     packet_loss=None, detail: dict | None = None) -> None:
    with _LOCK:
        conn = _connect()
        conn.execute(
            "INSERT INTO route_health_checks(endpoint_id, ts, ok, latency_ms, jitter_ms, packet_loss, detail)"
            " VALUES(?,?,?,?,?,?,?)",
            (endpoint_id, time.time(), int(bool(ok)), latency_ms, jitter_ms, packet_loss,
             json.dumps(detail or {}, ensure_ascii=False)),
        )
        conn.commit()


def recent_checks(endpoint_id: str, limit: int = 20) -> list[dict]:
    with _LOCK:
        rows = _connect().execute(
            "SELECT * FROM route_health_checks WHERE endpoint_id=? ORDER BY ts DESC LIMIT ?",
            (endpoint_id, int(limit)),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["detail"] = json.loads(d.get("detail") or "{}")
        except Exception:
            d["detail"] = {}
        out.append(d)
    return out


def add_event(kind: str, message: str, endpoint_id: str | None = None,
              detail: dict | None = None) -> None:
    with _LOCK:
        conn = _connect()
        conn.execute(
            "INSERT INTO route_events(ts, kind, endpoint_id, message, detail) VALUES(?,?,?,?,?)",
            (time.time(), kind, endpoint_id, message,
             json.dumps(detail or {}, ensure_ascii=False)),
        )
        conn.commit()


def recent_events(limit: int = 50) -> list[dict]:
    with _LOCK:
        rows = _connect().execute(
            "SELECT * FROM route_events ORDER BY ts DESC LIMIT ?", (int(limit),)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["detail"] = json.loads(d.get("detail") or "{}")
        except Exception:
            d["detail"] = {}
        out.append(d)
    return out


def add_selection(link_uid: str, mode: str, endpoint_id: str, reason: str,
                  score=None) -> None:
    with _LOCK:
        conn = _connect()
        conn.execute(
            "INSERT INTO route_selections(ts, link_uid, mode, chosen_endpoint_id, reason, score)"
            " VALUES(?,?,?,?,?,?)",
            (time.time(), link_uid, mode, endpoint_id, reason, score),
        )
        conn.commit()


def last_selection(mode: str) -> dict | None:
    with _LOCK:
        row = _connect().execute(
            "SELECT * FROM route_selections WHERE mode=? ORDER BY ts DESC LIMIT 1",
            (mode,),
        ).fetchone()
    return dict(row) if row else None


# ── nonce replay protection (worker ↔ panel) ──────────────────────────────────
def nonce_seen(nonce: str) -> bool:
    """True اگر nonce قبلاً دیده شده (replay) — در غیر این صورت ثبت می‌کند."""
    with _LOCK:
        conn = _connect()
        conn.execute("DELETE FROM sr_nonces WHERE ts < ?", (time.time() - 600,))
        cur = conn.execute("SELECT 1 FROM sr_nonces WHERE nonce=?", (nonce,))
        if cur.fetchone() is not None:
            return True
        conn.execute("INSERT OR IGNORE INTO sr_nonces(nonce, ts) VALUES(?,?)",
                     (nonce, time.time()))
        conn.commit()
        return False


def db_status() -> dict:
    try:
        with _LOCK:
            conn = _connect()
            counts = {}
            for t in ("smart_endpoints", "smart_routes", "route_health_checks",
                      "route_events", "route_selections", "smart_settings"):
                counts[t] = conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
        return {"ok": True, "file": str(DB_FILE), "schema_version": SCHEMA_VERSION,
                "tables": counts}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}
