import subprocess
import sys

_PACKAGES = [
    "fastapi==0.104.1",
    "uvicorn[standard]==0.24.0",
    "uvloop>=0.19.0",
    "httptools>=0.6.0",
    "httpx[http2]==0.25.1",
    "websockets==12.0",
    "aiofiles>=23.2.1",
    "cryptography>=39.0.0",
]

def _install_packages():
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", *_PACKAGES],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        print(f"[STARTUP] خطا در نصب پکیج‌ها:\n{e.stderr.decode()}", file=sys.stderr)
        sys.exit(1)

# _install_packages()  # deps preinstalled for local test

import asyncio
import json
import os
import hashlib
import secrets
import sys
import time
import traceback
import central
import aiofiles
import compat
import endpoint_profiles
import config_compiler
import config_lifecycle
import node_manager
import runtime_supervisor
import network_health
import diagnostics as diagnostics_mod
from job_system import jobs as job_system
from config_layer import CONFIG as _EMIX_RUNTIME_CFG  # audit fix: env knobs are now real
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote
from collections import deque, defaultdict
from pathlib import Path
import bottokentcpproxy
from protocol.mtproto import mtproto_native as mtproto
from typing import Optional
import base64
import botgeneratedomin
import zeussocks5
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import Response, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import httpx
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EMIX")

IRAN_TZ = ZoneInfo("Asia/Tehran")

app = FastAPI(title="EMIX", docs_url=None, redoc_url=None)

# وقتی مستقیم با `python main.py` اجرا میشه، این ماژول با نام "__main__" ثبت
# میشه نه "main". چون protocol/vless/vless.py و protocol/trojan/trojan.py با
# `from main import (...)` به این فایل رفرنس می‌دن، بدون این خط پایتون مجبور
# میشه کل main.py رو یک‌بار دیگه از صفر به‌عنوان ماژول جداگانه‌ی "main" اجرا کنه
# که باعث circular import و کرش میشه. با alias کردن sys.modules، هر دو اسم
# به همین نمونه‌ی در حال اجرا اشاره می‌کنن.
sys.modules.setdefault("main", sys.modules[__name__])

# ── CORS (Phase 7.13 — configurable, never wildcard + credentials) ──────────
# Behavior:
#   - If EMIX_CORS_ORIGINS is set (comma-separated) → use explicit list,
#     allow_credentials=True (spec-compliant).
#   - If EMIX_CORS_ORIGINS is unset → allow_origins=["*"] but
#     allow_credentials=False (spec-compliant — browsers refuse to send
#     credentials when origin is "*").
# Dashboard code uses same-origin requests by default, so disabling
# credentials under wildcard does NOT break the panel.
from config_layer import CONFIG as _EMIX_RUNTIME_CFG
app.add_middleware(
    CORSMiddleware,
    allow_origins=_EMIX_RUNTIME_CFG.cors_origins_list,
    allow_credentials=_EMIX_RUNTIME_CFG.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Persistence ───────────────────────────────────────────────────────────────
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DATA_FILE = DATA_DIR / "rvg_state.json"
SECRET_FILE = DATA_DIR / ".rvg_secret"
SAVE_LOCK = asyncio.Lock()


def _get_or_create_secret() -> str:
    env_secret = os.environ.get("SECRET_KEY")
    if env_secret:
        return env_secret
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if SECRET_FILE.exists():
            val = SECRET_FILE.read_text(encoding="utf-8").strip()
            if val:
                return val
        new_secret = secrets.token_urlsafe(32)
        SECRET_FILE.write_text(new_secret, encoding="utf-8")
        logger.info("SECRET_KEY جدید ساخته و در دیسک ذخیره شد (پایدار بین ری‌استارت‌ها).")
        return new_secret
    except Exception as e:
        logger.warning(f"عدم امکان ذخیره‌ی SECRET_KEY روی دیسک: {e} — از مقدار موقت استفاده می‌شود.")
        return secrets.token_urlsafe(32)


CONFIG = {
    "port": int(os.environ.get("PORT", 8000)),
    "secret": _get_or_create_secret(),
    "host": os.environ.get("RAILWAY_PUBLIC_DOMAIN", "localhost"),
    "disable_logging": False,
}


def apply_logging_state():
    """logging.disable سطح‌بندی سراسریه (روی کل ماژول logging اثر می‌ذاره)، پس
    یک‌جا همه‌ی logger های پروژه (EMIX، uvicorn.access، uvicorn.error،
    mtproto و ...) رو خاموش/روشن می‌کنه. چک داخلیش خیلی ارزونه، پس این خودش
    باعث می‌شه سربار I/O و فرمت‌کردن استرینگ لاگ‌ها کاملاً حذف بشه."""
    if CONFIG.get("disable_logging"):
        logging.disable(logging.CRITICAL)
    else:
        logging.disable(logging.NOTSET)


async def load_state():
    global LINKS, AUTH, SUBS
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if DATA_FILE.exists():
            async with aiofiles.open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = await f.read()
            data = json.loads(raw)
            # ── SNI spoofing backward-compat (Phase 1, §6.1) ────────────────────
            # Old backups created before this feature was added will be missing
            # `spoof_sni` and `spoof_sni_enabled`. Fill in safe defaults so the
            # rest of the code can assume the fields exist. Behavior is identical
            # to before (effective SNI = host when spoof_sni_enabled is False).
            for uid, link in (data.get("links") or {}).items():
                if isinstance(link, dict):
                    if "spoof_sni" not in link:
                        link["spoof_sni"] = None
                    if "spoof_sni_enabled" not in link:
                        link["spoof_sni_enabled"] = False
            LINKS.update(data.get("links", {}))
            SUBS.update(data.get("subs", {}))
            # Endpoint Profile Engine restore (Phase 25)
            try:
                endpoint_profiles.restore_snapshot(data)
            except Exception as _ep_exc:
                logger.warning(f"endpoint_profiles restore failed (ignored): {_ep_exc}")
            # Node Manager restore (Phase 37.9)
            try:
                node_manager.restore_snapshot(data)
            except Exception as _nm_exc:
                logger.warning(f"node_manager restore failed (ignored): {_nm_exc}")
            # ── Audit fix 2026-09 (P1 persistence restore) ─────────────────────
            try:
                import sni_management
                n_sni = sni_management.restore_snapshot(data)
                if n_sni:
                    logger.info(f"sni_management: {n_sni} profiles restored")
            except Exception as _sni_exc:
                logger.warning(f"sni_profiles restore failed (ignored): {_sni_exc}")
            try:
                import vpn_pro
                n_vpn = vpn_pro.restore_snapshot(data)
                if n_vpn:
                    logger.info(f"vpn_pro: {n_vpn} VPN nodes restored (keys intact)")
            except Exception as _vpn_exc:
                logger.warning(f"vpn_nodes restore failed (ignored): {_vpn_exc}")
            # Phase 38 — Accounts + domestic routing restore
            try:
                import account_manager
                account_manager.restore_snapshot(data.get("account_manager") or {})
                n_acc = len(account_manager.list_accounts())
                if n_acc:
                    logger.info(f"account_manager: {n_acc} accounts restored")
            except Exception as _am_exc:
                logger.warning(f"account_manager restore failed (ignored): {_am_exc}")
            try:
                import domestic_route_engine as _dre
                _dre.restore_policy_snapshot(data.get("domestic_routing") or {})
                n_ir = _dre.load_seed()
                logger.info(
                    f"domestic_route_engine: seed dataset loaded "
                    f"({n_ir} IR prefixes, policy={_dre.get_active_policy_name()})")
            except Exception as _dre_exc:
                logger.warning(f"domestic_route_engine restore failed (ignored): {_dre_exc}")
            # Phase 38+ — Iran Gateway + Config Builder history restore
            try:
                import iran_gateway as _ig
                _ig.restore_snapshot(data.get("iran_gateway") or {})
                _ig_summary = _ig.summary()
                if _ig_summary.get("gateways"):
                    logger.info(f"iran_gateway: {_ig_summary['gateways']} gateway(s) "
                                f"restored (state={_ig_summary.get('state')})")
            except Exception as _ig_exc:
                logger.warning(f"iran_gateway restore failed (ignored): {_ig_exc}")
            try:
                import config_builder as _cb
                _cb.restore_snapshot(data.get("config_builder") or {})
                _cb_sum = _cb.history_summary()
                if _cb_sum.get("entries"):
                    logger.info(f"config_builder: {_cb_sum['entries']} history "
                                f"entries restored")
            except Exception as _cb_exc:
                logger.warning(f"config_builder restore failed (ignored): {_cb_exc}")
            # Sessions: restore non-expired tokens (survive redeploy)
            now_ts = time.time()
            for tok, exp in (data.get("sessions") or {}).items():
                if isinstance(tok, str) and isinstance(exp, (int, float)) and exp > now_ts:
                    SESSIONS[tok] = exp
            # Lifetime traffic totals
            totals = data.get("stats_totals") or {}
            if isinstance(totals, dict):
                stats["total_bytes"] = int(totals.get("total_bytes") or 0)
                stats["total_requests"] = int(totals.get("total_requests") or 0)
                stats["total_errors"] = int(totals.get("total_errors") or 0)
            NODE_KEYS.update(data.get("node_keys", {}))
            for nid, n in (data.get("nodes") or {}).items():
                NODES[nid] = _normalize_node(n)
            if "password_hash" in data:
                stored = data["password_hash"]
                # Only accept sha256-format hashes (64 lowercase hex chars).
                # Reject PBKDF2 format (pbkdf2$...) that may have been written
                # by a newer version — prevents login lockout after downgrade.
                if isinstance(stored, str) and len(stored) == 64 and all(c in "0123456789abcdef" for c in stored.lower()):
                    AUTH["password_hash"] = stored
                else:
                    logger.warning("Stored password_hash is not sha256 format — ignoring and using fresh hash.")
                    asyncio.create_task(save_state())  # persist fresh sha256 hash
            CONFIG["disable_logging"] = bool(data.get("disable_logging", False))
            apply_logging_state()
            logger.info(
                f"State loaded: {len(LINKS)} links, {len(SUBS)} subs, "
                f"{len(NODES)} nodes, {len(NODE_KEYS)} node keys"
            )
    except Exception as e:
        logger.warning(f"Could not load state: {e}")

async def save_state():
    async with SAVE_LOCK:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "links": dict(LINKS),
                "subs": dict(SUBS),
                "node_keys": dict(NODE_KEYS),
                "nodes": dict(NODES),
                "password_hash": AUTH["password_hash"],
                "disable_logging": CONFIG.get("disable_logging", False),
                # Endpoint & Transport Profile Engine (Phase 25) — replaces
                # the standalone SNI-spoof store; legacy spoof fields already
                # live inside each link record.
                "endpoint_profiles": endpoint_profiles.persist_snapshot().get("endpoint_profiles", []),
                # Node Manager (Phase 37.9) — node registry + heartbeat history
                "managed_nodes": node_manager.persist_snapshot(),
                # ── Audit fix 2026-09 (P1 persistence): این‌ها قبلاً فقط
                # در-memory بودند و بعد از هر restart از بین می‌رفتند.
                # (importها defensive هستند چون این ماژول‌ها در try/except
                # دیرهنگام bootstrap می‌شوند.)
                **_persist_optional_engines(),
                # Phase 38 — Accounts/Devices/Subscriptions engine snapshot
                **_persist_phase38_engines(),
                # Sessions survive restarts (Railway redeploy خروج اجباری نمی‌دهد)
                "sessions": {t: exp for t, exp in SESSIONS.items() if exp > time.time()},
                # Lifetime traffic totals (per-link used_bytes قبلاً هم ذخیره
                # می‌شد؛ این مجموع‌های session-bound بودند که ریست می‌شدند)
                "stats_totals": {
                    "total_bytes": stats.get("total_bytes", 0),
                    "total_requests": stats.get("total_requests", 0),
                    "total_errors": stats.get("total_errors", 0),
                },
                "saved_at": datetime.now().isoformat(),
            }
            tmp = DATA_FILE.with_suffix(".tmp")
            async with aiofiles.open(tmp, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
            tmp.replace(DATA_FILE)
        except Exception as e:
            logger.warning(f"Could not save state: {e}")


def _persist_phase38_engines() -> dict:
    """Phase 38 snapshots (defensive — engines may be absent in degraded boots)."""
    out: dict = {}
    try:
        import account_manager
        out["account_manager"] = account_manager.persist_snapshot()
    except Exception:
        out["account_manager"] = {}
    try:
        import domestic_route_engine
        out["domestic_routing"] = domestic_route_engine.persist_policy_snapshot()
    except Exception:
        out["domestic_routing"] = {"active_policy": "ALL_VPN"}
    # Phase 38+ — Iran Gateway registry + Unified Config Builder history
    try:
        import iran_gateway
        out["iran_gateway"] = iran_gateway.persist_snapshot()
    except Exception:
        out["iran_gateway"] = {"gateways": []}
    try:
        import config_builder
        out["config_builder"] = config_builder.persist_snapshot()
    except Exception:
        out["config_builder"] = {"history": []}
    return out


def _persist_optional_engines() -> dict:
    """Snapshots of engines whose bootstrap import may have been skipped."""
    out: dict = {}
    try:
        import sni_management
        out["sni_profiles"] = sni_management.persist_snapshot().get("sni_profiles", [])
    except Exception:
        out["sni_profiles"] = []
    try:
        import vpn_pro
        out["vpn_nodes"] = vpn_pro.persist_snapshot().get("vpn_nodes", [])
    except Exception:
        out["vpn_nodes"] = []
    return out


# ── Debounced save ─────────────────────────────────────────────────────────────
# هر بار که یک کانکشن (trojan/vless/shadowsocks/xhttp) بسته میشه، schedule_save()
# صدا زده میشه به‌جای save_state() مستقیم. اگه صدها کانکشن در ثانیه باز و بسته بشن
# (که برای WebSocket-based transportها عادیه)، save_state() قبلی باعث میشد به همون
# تعداد، کل state سریالایز و روی دیسک نوشته بشه و event loop تک‌هسته‌ای رو مسدود کنه.
# اینجا چندین درخواست ذخیره‌سازی که در بازه‌ی SAVE_DEBOUNCE_SECONDS اتفاق بیفتن،
# در یک نوشتن واحد روی دیسک ادغام میشن.
# Audit fix: EMIX_SAVE_DEBOUNCE قبلاً در ۵ مستند ذکر شده بود ولی هرگز خوانده
# نمی‌شد (hardcoded 2.0). حالا واقعاً از config_layer خوانده می‌شود.
SAVE_DEBOUNCE_SECONDS = float(_EMIX_RUNTIME_CFG.save_debounce_seconds)
_save_pending = False
_save_dirty_again = False


async def schedule_save():
    """نسخه‌ی debounce شده‌ی save_state — برای صدا زدن مکرر و پرتعداد (هر بسته شدن کانکشن) امن است."""
    global _save_pending, _save_dirty_again
    if _save_pending:
        _save_dirty_again = True
        return
    _save_pending = True
    try:
        while True:
            _save_dirty_again = False
            await asyncio.sleep(SAVE_DEBOUNCE_SECONDS)
            await save_state()
            if not _save_dirty_again:
                break
    finally:
        _save_pending = False

# ── In-memory state ───────────────────────────────────────────────────────────
connections: dict = {}
stats = {
    "total_bytes": 0,
    "total_requests": 0,
    "total_errors": 0,
    "start_time": time.time(),
}
class _ErrorLogDeque(deque):
    """deque معمولی، با این تفاوت که وقتی توقف لاگ‌گیری فعال باشه append() هیچ کاری
    نمی‌کنه. با این روش همه‌ی error_logs.append(...) های پخش‌شده توی پروژه
    (websocket.py ها، xhttp_core.py ها و ...) بدون نیاز به تغییر خودشون از این
    فلگ پیروی می‌کنن."""
    def append(self, item):
        if CONFIG.get("disable_logging"):
            return
        super().append(item)


error_logs: deque = _ErrorLogDeque(maxlen=50)
activity_logs: deque = deque(maxlen=200)
# hourly_traffic now keyed by full ISO datetime string ("YYYY-MM-DD HH:00") so it
# can be pruned across day boundaries. The /stats endpoint still exposes the
# {"HH:00": bytes} view to keep dashboard code backward-compatible.
hourly_traffic: dict = defaultdict(int)
http_client: httpx.AsyncClient | None = None
LINKS: dict = {}
LINKS_LOCK = asyncio.Lock()
SUBS: dict = {}
SUBS_LOCK = asyncio.Lock()


def _hourly_traffic_key() -> str:
    """Sortable ISO key for hourly_traffic. Format: 'YYYY-MM-DD HH:00'."""
    return datetime.now().strftime("%Y-%m-%d %H:00")


def _hourly_traffic_public_view() -> dict:
    """Return the backward-compatible {HH:00: bytes} view for /stats."""
    out = {}
    for k, v in hourly_traffic.items():
        # 'YYYY-MM-DD HH:00' → 'HH:00'
        if " " in k:
            out[k.split(" ", 1)[1]] = out.get(k.split(" ", 1)[1], 0) + v
        else:
            out[k] = out.get(k, 0) + v
    return out


def _prune_hourly_traffic():
    """Drop hours older than the configured retention window. Idempotent + safe."""
    from config_layer import CONFIG as _EMIX_CFG
    retention = _EMIX_CFG.hourly_traffic_retention_hours
    if retention <= 0:
        return
    try:
        cutoff = datetime.now() - timedelta(hours=retention)
        cutoff_key = cutoff.strftime("%Y-%m-%d %H:00")
        stale = [k for k in hourly_traffic if k < cutoff_key]
        for k in stale:
            hourly_traffic.pop(k, None)
        if stale:
            logger.info(f"[hourly-traffic] pruned {len(stale)} entries older than {retention}h")
    except Exception as exc:
        logger.warning(f"[hourly-traffic] prune error (continuing): {exc}")

# ── MTProto (mtproto_native / باینری رسمی تلگرام) — هر لینک = یک پروسه‌ی جدا،
# روی پورت خودش، با ad_tag مستقل خودش (per-instance، دقیقاً مثل mtg قدیم) ──

# ── Node linking (اتصال چند پنل به هم) ────────────────────────────────────────
# NODE_KEYS: کلیدهایی که *این* پنل صادر کرده. هر کلید به یک پنل دیگه اجازه میده
#            دیتای این پنل رو بخونه و روی کانفیگ‌هاش بنویسه (سمت inbound).
# NODES:     پنل‌هایی که *این* پنل بهشون وصل شده و دیتاشون رو ادغام می‌کنه (سمت outbound).
NODE_KEYS: dict = {}
NODE_KEYS_LOCK = asyncio.Lock()
NODES: dict = {}
NODES_LOCK = asyncio.Lock()
_NODE_CACHE: dict = {}          # node_id -> {"at": float, "data": dict}
NODE_CACHE_TTL = 8.0
NODE_KEY_PREFIX = "rvg-"
NODE_KEY_HEADER = "X-RVG-Node-Key"
NODE_SHARE_PARTS = ("usage", "links", "subs", "requests", "logs")

PROTOCOLS = (
    "vless-ws", "xhttp-packet-up", "xhttp-stream-up",
    "trojan-ws", "trojan-xhttp-packet-up", "trojan-xhttp-stream-up",
    "mtproto", "shadowsocks",
)
DEFAULT_PROTOCOL = "vless-ws"

def log_activity(kind: str, message: str, level: str = "info"):
    activity_logs.append({
        "kind": kind,
        "level": level,
        "message": message,
        "time": datetime.now().isoformat(),
    })


# ── Auth ──────────────────────────────────────────────────────────────────────
SESSION_COOKIE = "rvg_session"
# Audit fix: EMIX_SESSION_TTL قبلاً در مستندات ذکر شده بود ولی هرگز خوانده
# نمی‌شد (hardcoded 7d). حالا واقعاً از config_layer خوانده می‌شود.
SESSION_TTL = int(_EMIX_RUNTIME_CFG.session_ttl_seconds)

def hash_password(pw: str) -> str:
    return hashlib.sha256(f"{pw}{CONFIG['secret']}".encode()).hexdigest()

AUTH = {"password_hash": hash_password(os.environ.get("ADMIN_PASSWORD", "123456"))}
SESSIONS: dict = {}
SESSIONS_LOCK = asyncio.Lock()

async def create_session() -> str:
    token = secrets.token_urlsafe(32)
    async with SESSIONS_LOCK:
        SESSIONS[token] = time.time() + SESSION_TTL
    return token

async def is_valid_session(token: str | None) -> bool:
    if not token:
        return False
    async with SESSIONS_LOCK:
        exp = SESSIONS.get(token)
        if exp is None:
            return False
        if exp < time.time():
            SESSIONS.pop(token, None)
            return False
        return True

async def destroy_session(token: str | None):
    if not token:
        return
    async with SESSIONS_LOCK:
        SESSIONS.pop(token, None)

async def require_auth(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not await is_valid_session(token):
        raise HTTPException(status_code=401, detail="unauthorized")
    return token

# ── Session cleanup background task ──────────────────────────────────────────
# Sessions that are never accessed again (user closes browser, network drops)
# would otherwise leak forever. This task periodically drops expired entries
# under the lock. Started once in startup(), cancelled in shutdown().
_session_cleanup_task: asyncio.Task | None = None

async def _session_cleanup_loop():
    """Periodically prune expired sessions. Safe under SESSIONS_LOCK."""
    from config_layer import CONFIG as _EMIX_CFG
    interval = _EMIX_CFG.session_cleanup_interval_seconds
    try:
        while True:
            await asyncio.sleep(interval)
            try:
                now = time.time()
                # Snapshot keys under the lock, then pop expired ones.
                # Pop happens under the same lock — no race with reads/writes.
                async with SESSIONS_LOCK:
                    expired = [t for t, exp in SESSIONS.items() if exp < now]
                    for t in expired:
                        SESSIONS.pop(t, None)
                if expired:
                    logger.info(f"[session-cleanup] pruned {len(expired)} expired sessions")
                # Also prune hourly_traffic on the same schedule
                _prune_hourly_traffic()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Never let the cleanup loop die from an unexpected error.
                logger.warning(f"[session-cleanup] iteration error (continuing): {exc}")
    except asyncio.CancelledError:
        logger.info("[session-cleanup] task cancelled (shutdown)")
        return

# ── Startup / Shutdown ────────────────────────────────────────────────────────
# ─── Background job definitions (Phase 20) ──────────────────────────────────

_HEALTH_SWEEP_ENABLED = os.environ.get("EMIX_HEALTH_SWEEP_ENABLED", "1") not in ("0", "false", "no")
_HEALTH_SWEEP_INTERVAL = max(60, int(os.environ.get("EMIX_HEALTH_SWEEP_INTERVAL", "600")))
_EXPIRY_SWEEP_INTERVAL = max(60, int(os.environ.get("EMIX_EXPIRY_SWEEP_INTERVAL", "300")))


async def _job_health_sweep():
    """Probe all allowed configs end-to-end (Network Health Engine, Phase 7)."""
    async def _links_provider():
        async with LINKS_LOCK:
            return [(uid, dict(d)) for uid, d in LINKS.items() if is_link_allowed(d)]
    result = await network_health.sweep(links_provider=_links_provider, concurrency=4)
    # Audit fix (P0): sweep probes COPIES of link dicts (the lock must not be
    # held across network I/O), so the engine's link["health"] side-effect
    # wrote to throwaway dicts and background sweep results were NEVER
    # persisted. Write the engine's records back into the live LINKS here.
    if result.get("ok"):
        persisted = 0
        async with LINKS_LOCK:
            for uid in list(LINKS.keys()):
                rec = network_health.get_health_dict(uid)
                if rec is not None and LINKS[uid].get("health") != rec:
                    LINKS[uid]["health"] = rec
                    persisted += 1
        if persisted:
            asyncio.create_task(schedule_save())
        result["persisted"] = persisted
    return result


async def _job_expiry_sweep():
    """Mark disabled/expired/quota-exhausted configs INVALID (no probing)."""
    async with LINKS_LOCK:
        targets = [(uid, dict(d)) for uid, d in LINKS.items() if not is_link_allowed(d)]
    for uid, d in targets:
        network_health.mark_invalid(uid, d, "disabled / expired / quota exhausted")
    return {"marked": len(targets)}


async def _job_ip_quality_prune():
    """Drop IP-quality cache entries older than 2× TTL."""
    import ip_quality as _ipq
    now = time.time()
    stale = [ip for ip, a in list(_ipq._cache.items())
             if now - a.checked_at > 2 * _ipq.CACHE_TTL]
    for ip in stale:
        _ipq._cache.pop(ip, None)
        _ipq._history.pop(ip, None)
    return {"pruned": len(stale)}


# ─── Phase 37 jobs: node heartbeat / runtime supervision / mtproto stats ────

async def _job_node_heartbeat():
    """Node Manager sweep (37.9): evaluate runtime health + expire stale states."""
    for rec in list(node_manager.list_nodes()):
        nid = rec.get("id")
        if nid and rec.get("kind") in ("panel", "worker", "vps"):
            await node_manager.evaluate_runtime_health(nid)
    states = await node_manager.check_all()
    return {"nodes": len(states),
            "online": sum(1 for s in states.values() if s["state"] == "ONLINE")}


async def _job_runtime_supervision():
    """Runtime supervisor pass (37.10): crash detection + backoff restarts."""
    results = await runtime_supervisor.supervisor.monitor_once()
    acted = {rid: r for rid, r in results.items() if r.get("action") not in ("none", "error")}
    if acted:
        log_activity("system", f"runtime supervision acted on {len(acted)} runtime(s)", "warn")
    return {"checked": len(results), "acted": len(acted)}


async def _job_mtproto_stats():
    """Poll MTProto binary stats (37.10): honest activity accounting."""
    try:
        from protocol.mtproto import mtproto_native as _mtp
        return await _mtp.poll_all_stats()
    except Exception as exc:
        return {"error": str(exc)[:120]}


async def _job_lifecycle_reconcile():
    """Config lifecycle reconciliation (37.11): refresh derived states on links."""
    async with LINKS_LOCK:
        targets = {uid: dict(d) for uid, d in LINKS.items()}
    updated = 0
    for uid, link in targets.items():
        ann = config_lifecycle.lifecycle_annotation(uid, link, network_health.get_health_dict(uid))
        async with LINKS_LOCK:
            live = LINKS.get(uid)
            if live is not None and live.get("lifecycle_state") != ann["lifecycle_state"]:
                live["lifecycle_state"] = ann["lifecycle_state"]
                live["lifecycle_reason"] = ann["lifecycle_reason"]
                updated += 1
    if updated:
        asyncio.create_task(schedule_save())
    return {"reconciled": len(targets), "changed": updated}


# ─── Node registration + runtime health evaluators (Phase 37.9) ────────────

async def _panel_runtime_health(rec):
    """Panel node: healthy only when its in-panel relays actually serve.

    Evidence = Network Health Engine results for configs served by this node
    (NOT an HTTP ping of the panel). DEGRADED when >1/3 tracked configs are
    UNREACHABLE; DOWN when every tracked config is UNREACHABLE with evidence.
    """
    summary = network_health.summary()
    by = summary.get("by_state", {})
    tracked = summary.get("tracked", 0)
    if tracked == 0:
        return {"runtime_health": "UNKNOWN",
                "load": None, "clients": None}
    unreachable = by.get("UNREACHABLE", 0)
    healthy = by.get("HEALTHY", 0)
    if unreachable >= tracked:
        return {"runtime_health": "DOWN", "load": 100.0, "clients": None}
    if unreachable / tracked > 0.34:
        return {"runtime_health": "DEGRADED",
                "load": round(100.0 * unreachable / tracked, 1), "clients": None}
    load = 100.0 * (tracked - healthy) / tracked if tracked else 0.0
    # Audit fix: قبلاً `'connections' in dir()` بود که در scope تابع همیشه False
    # است (dir() فقط local names را می‌دهد) → clients همیشه None بود.
    try:
        clients = len(connections)
    except NameError:
        clients = None
    return {"runtime_health": "OK", "load": round(load, 1), "clients": clients}


async def _worker_runtime_health(rec):
    """Cloudflare Worker node: probed via the gaming/worker health path."""
    try:
        import gaming_boost
        # worker health is validated through the WTE path when configured;
        # without a worker token the honest answer is UNKNOWN.
        token = getattr(gaming_boost, "WORKER_TOKEN", "") or ""
        if not token:
            return {"runtime_health": "UNKNOWN", "load": None, "clients": None}
        res = await gaming_boost._call_worker("gateway-status")
        ok = bool(res and res.get("ok"))
        return {"runtime_health": "OK" if ok else "DEGRADED",
                "load": None, "clients": None}
    except Exception:
        return {"runtime_health": "UNKNOWN", "load": None, "clients": None}


async def _vps_runtime_health(rec):
    """Gaming VPS node: real TCP+TLS+certificate probe of the bridge."""
    try:
        import gaming_boost
        vps_ip = (gaming_boost._gaming_state().get("vps_ip") or "").strip()
        if not vps_ip:
            return {"runtime_health": "UNKNOWN", "load": None, "clients": None}
        res = await gaming_boost._vps_health(vps_ip)
        ok = bool(res and res.get("tls_ok"))
        return {"runtime_health": "OK" if ok else "DEGRADED",
                "load": None, "clients": None}
    except Exception:
        return {"runtime_health": "UNKNOWN", "load": None, "clients": None}


def _register_managed_nodes() -> None:
    """Register the traffic-carrying nodes of this deployment (37.9)."""
    async def _reg():
        await node_manager.register_node(node_manager.NodeRecord(
            id="panel", name="EMIX Panel (in-panel relays)", kind="panel",
            runtime="in-panel-relays",
            capabilities=list(compat.SERVER_RUNTIME.keys()) and
            [f"{p}-{t}" if t != "tcp" else p for (p, t) in compat.SERVER_RUNTIME],
            region="", address="",
        ))
    node_manager.register_runtime_health_fn("panel", _panel_runtime_health)
    node_manager.register_runtime_health_fn("worker", _worker_runtime_health)
    node_manager.register_runtime_health_fn("vps", _vps_runtime_health)
    asyncio.create_task(_reg())


def _supervise_mtproto_instance(uuid: str) -> None:
    """(Re)attach the runtime supervisor to ONE MTProto instance.

    Audit fix (37.10 gap): instances created AFTER boot (link-create path,
    ad_tag update) were never registered with the Runtime Supervisor —
    crash detection/backoff only covered boot-time instances. Idempotent:
    safe to call repeatedly (supervisor.register keeps existing counters).
    """
    try:
        from protocol.mtproto import mtproto_native as _mtp
        info = _mtp.instance_runtime_status(uuid)
        if not info.get("exists"):
            return
        link = LINKS.get(uuid) or {}
        runtime_supervisor.supervisor.register(
            runtime_supervisor.SupervisedRuntime(
                id=f"mtproto-{uuid[:8]}",
                name=f"MTProto instance {link.get('label', uuid[:8])}",
                kind="mtproto-subprocess",
                node_id="panel",
                is_alive_fn=(lambda u=uuid: _mtp.instance_runtime_status(u).get("alive", False)),
                restart_fn=(lambda u=uuid, l=dict(link):
                            _restart_mtproto_instance(u, l)),
            )
        )
    except Exception as exc:
        logger.warning(f"[supervisor] MTProto[{uuid[:8]}] attach failed: {exc}")


async def _register_mtproto_runtimes() -> None:
    """Attach the runtime supervisor to live MTProto instances (37.10)."""
    try:
        from protocol.mtproto import mtproto_native as _mtp
    except Exception:
        return
    for uuid in _mtp.list_instance_uuids():
        _supervise_mtproto_instance(uuid)


async def _restart_mtproto_instance(uuid: str, link: dict) -> bool:
    """Restart one MTProto instance (supervisor callback, 37.10)."""
    try:
        from protocol.mtproto import mtproto_native as _mtp
        await _mtp.stop_instance(uuid)
        await _mtp.start_instance(
            uuid,
            secret=link.get("mtproto_secret"),
            domain=link.get("mtproto_domain"),
            preferred_port=link.get("mtproto_port"),
            ad_tag=link.get("mtproto_ad_tag"),
        )
        return True
    except Exception as exc:
        logger.warning(f"supervisor: mtproto restart {uuid[:8]} failed: {exc}")
        return False


async def _mtproto_activity_callback(uuid: str, stats: dict) -> None:
    """Record honest MTProto activity evidence on the link record (37.10)."""
    async with LINKS_LOCK:
        link = LINKS.get(uuid)
        if link is None:
            return
        link["mtproto_stats"] = {
            "active_connections": stats.get("active_connections"),
            "connections_total": stats.get("connections_total"),
            "queries_total": stats.get("queries_total"),
        }
        link["mtproto_last_activity_ts"] = stats.get("ts")


def _register_phase37_jobs() -> None:
    job_system.register("node-heartbeat", _job_node_heartbeat,
                        interval=120.0, timeout=60.0, retries=1)
    job_system.register("runtime-supervision", _job_runtime_supervision,
                        interval=60.0, timeout=60.0, retries=1)
    job_system.register("mtproto-stats", _job_mtproto_stats,
                        interval=120.0, timeout=30.0, retries=1)
    job_system.register("lifecycle-reconcile", _job_lifecycle_reconcile,
                        interval=300.0, timeout=30.0, retries=1)


def _register_default_jobs() -> None:
    if _HEALTH_SWEEP_ENABLED:
        job_system.register("health-sweep", _job_health_sweep,
                            interval=_HEALTH_SWEEP_INTERVAL, timeout=180.0, retries=1)
    job_system.register("expiry-sweep", _job_expiry_sweep,
                        interval=_EXPIRY_SWEEP_INTERVAL, timeout=30.0, retries=1)
    job_system.register("ip-quality-prune", _job_ip_quality_prune,
                        interval=3600.0, timeout=30.0, retries=1)
    _register_phase37_jobs()


def _wire_phase38_engines() -> None:
    """Phase 38 runtime wiring (all defensive; failures never block boot):

    * account_manager compiles subscription configs THROUGH the unified
      Config Compiler — no duplicate URI logic anywhere.
    * route_engine gets a real control-plane RTT provider (egress_engine).
    * failover_engine gets a real route re-point function (route registry).
    * domestic engine gets a REAL DNS resolver (getaddrinfo) so the
      Test-Route diagnostic follows actual destination IPs.
    * default Iranian prefix dataset loads if the seed was not yet applied.
    """
    import account_manager
    import config_compiler
    import route_engine
    import failover_engine
    import egress_engine
    import domestic_route_engine as dre

    account_manager.set_compile_fn(config_compiler.compile_from_link)

    route_engine.set_metrics_provider("control_plane_rtt",
                                      egress_engine.measure_control_plane_rtt)

    async def _repoint_routes(old_node: str, new_node: str) -> None:
        """Re-point registered routes from a failed node to its replacement."""
        repointed = 0
        for r in list(route_engine._routes.values()):
            if r.exit_node == old_node:
                r.exit_node = new_node
                r.notes.append(f"re-pointed {old_node}→{new_node} (failover)")
                repointed += 1
        if repointed:
            logger.info(f"[failover] {repointed} routes re-pointed "
                        f"{old_node} → {new_node}")
    failover_engine.set_route_repoint_fn(_repoint_routes)

    # Real (but timeout-bounded) resolver for the Test Route diagnostics
    async def _resolve_domain(domain: str):
        loop = asyncio.get_running_loop()
        try:
            infos = await asyncio.wait_for(
                loop.getaddrinfo(domain, None, family=0, proto=IPPROTO_TCP), 5.0)
            for info in infos:
                sockaddr = info[4]
                if sockaddr and sockaddr[0]:
                    return sockaddr[0]
        except Exception:
            return None
        return None
    dre.set_resolver(_resolve_domain)

    if dre.dataset_status().get("prefix_count", 0) == 0:
        dre.load_seed()

    # ─── Phase 38+ wiring — capability/config-builder/iran-gateway/events ──
    import capability_engine
    import config_builder
    import iran_gateway
    import structured_events

    # Config Builder DI: host / worker-domain / CDN providers (no import cycles)
    config_builder.set_host_provider(get_host)

    def _worker_domain() -> str:
        try:
            import gaming_boost
            cfg = gaming_boost._load_cfg()
            return gaming_boost._norm_domain(cfg.get("worker_domain", ""))
        except Exception:
            return ""
    config_builder.set_worker_domain_provider(_worker_domain)
    config_builder.set_cdn_domain_provider(lambda: CONFIG.get("cdn_domain", ""))

    # IRAN_PROXY gateway verdict → domestic engine (honest attribution)
    dre.set_gateway_status_fn(iran_gateway.iran_proxy_egress_status)

    # Railway validation matrix: LIVE listener evidence from the running app
    capability_engine.set_listener_paths({
        "vless:ws": ["/ws/{uuid}"],
        "vless:xhttp-packet-up": ["/xhttp-siz10/packet-up/{uuid}"],
        "vless:xhttp-stream-up": ["/xhttp-siz10/stream-up/{uuid}"],
        "trojan:ws": ["/trojan-ws"],
        "trojan:xhttp-packet-up": ["/txhttp-siz10/packet-up/{uuid}"],
        "trojan:xhttp-stream-up": ["/txhttp-siz10/stream-up/{uuid}"],
        "shadowsocks:ws": ["/ss-ws"],
        "__mtproto_probe__": _mtproto_instance_probe,
    })
    logger.info("[phase38+] capability/config-builder/iran-gateway/events wired")


def _mtproto_instance_probe() -> int:
    """Live count of running mtg subprocesses (validation-matrix evidence)."""
    try:
        from protocol.mtproto import mtproto_native
        return len(getattr(mtproto_native, "_instances", {}))
    except Exception:
        return 0


async def _job_domestic_rules_update() -> None:
    """Daily atomic refresh of the IR prefix dataset (rollback-safe)."""
    import domestic_rules_updater as dru
    report = await dru.update_rules()
    if report.get("ok"):
        logger.info(f"[domestic-rules] dataset updated: {report.get('applied')} prefixes")
    else:
        logger.warning(f"[domestic-rules] update failed (kept previous): "
                       f"{report.get('error')}")


async def _job_account_sweep() -> None:
    """Expire subscriptions, close stale sessions (backend-enforced limits)."""
    import account_manager as am
    changed = await am.reconcile_subscription_statuses()
    if changed:
        logger.info(f"[accounts] subscription status changes: {changed}")
        asyncio.create_task(schedule_save())
    closed = await am.sweep_stale_sessions()
    if closed:
        logger.info(f"[accounts] closed {closed} stale sessions")


async def _job_iran_gateway_check() -> None:
    """Periodic Iran Gateway health + egress re-verification (evidence TTL)."""
    import iran_gateway
    results = await iran_gateway.check_all()
    verified = sum(1 for r in results.values()
                   if r.get("state") == "VERIFIED_IRAN_EGRESS")
    if results:
        logger.info(f"[iran-gateway] checked {len(results)} gateway(s), "
                    f"{verified} VERIFIED_IRAN_EGRESS")


def _register_phase38_jobs() -> None:
    job_system.register("domestic-rules-update", _job_domestic_rules_update,
                        interval=86400.0, timeout=60.0, retries=0)
    job_system.register("account-sweep", _job_account_sweep,
                        interval=300.0, timeout=30.0, retries=1)
    job_system.register("iran-gateway-check", _job_iran_gateway_check,
                        interval=21600.0, timeout=60.0, retries=1)


async def _persistence_health() -> dict:
    """Persistence health for the Diagnostics Center."""
    try:
        writable = DATA_DIR.exists() and os.access(str(DATA_DIR), os.W_OK)
        size = DATA_FILE.stat().st_size if DATA_FILE.exists() else 0
        return {
            "status": "OK" if writable else "ERROR",
            "data_dir": str(DATA_DIR),
            "writable": writable,
            "state_file_bytes": size,
            "links": len(LINKS), "subs": len(SUBS), "nodes": len(NODES),
        }
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)[:120]}


@app.on_event("startup")
async def startup():
    asyncio.create_task(central.heartbeat_loop())
    global http_client, _session_cleanup_task
    limits = httpx.Limits(max_connections=500, max_keepalive_connections=100)
    timeout = httpx.Timeout(30.0, connect=10.0)
    http_client = httpx.AsyncClient(
        limits=limits, timeout=timeout, follow_redirects=True,
    )
    await load_state()
    # Start session cleanup background task (Phase 1.2)
    if _session_cleanup_task is None or _session_cleanup_task.done():
        _session_cleanup_task = asyncio.create_task(_session_cleanup_loop())
        logger.info("[startup] session cleanup task started")
    # ─── Network Health Engine wiring (Phases 6/7) ─────────────────────────
    # Real probes come from link_health._run_link_ping (protocol-authentic
    # end-to-end tests). Injection avoids circular imports.
    try:
        network_health.set_probe_fn(link_health._run_link_ping)
        network_health.set_allowed_fn(is_link_allowed)
    except Exception as _nh_exc:
        logger.warning(f"[startup] network_health wiring failed: {_nh_exc}")

    # ─── Background Job System (Phase 20 + Phase 37) ─────────────────────
    try:
        _register_default_jobs()
        await job_system.start()
    except Exception as _job_exc:
        logger.warning(f"[startup] job system failed to start: {_job_exc}")

    # ─── Node Manager + MTProto activity wiring (Phase 37.9/37.10) ────────
    try:
        _register_managed_nodes()
    except Exception as _nm_exc:
        logger.warning(f"[startup] node manager registration failed: {_nm_exc}")
    try:
        mtproto.set_activity_callback(_mtproto_activity_callback)
    except Exception as _cb_exc:
        logger.warning(f"[startup] mtproto activity callback wiring failed: {_cb_exc}")

    # ─── Diagnostics persistence probe (Phase 21) ─────────────────────────
    diagnostics_mod.set_persistence_probe(_persistence_health)

    # اگر دیتای پایدار روی Railway Volume وصل نباشد، LINKS خالی خواهد بود.
    # سه کانفیگ پیش‌فرض (vless-ws / trojan-ws / shadowsocks) می‌سازیم تا کاربر
    # بلافاصله پس از دیپلوی بتواند پینگ بگیرد و پنل را تست کند.
    try:
        await ensure_default_link()
    except Exception as _e:
        logger.warning(f"[startup] ensure_default_link ناموفق بود: {_e}")
    await _restart_mtproto_instances()
    # attach the runtime supervisor to live MTProto subprocesses (37.10)
    try:
        await _register_mtproto_runtimes()
    except Exception as _rs_exc:
        logger.warning(f"[startup] runtime supervisor registration failed: {_rs_exc}")
    # ─── Phase 38 wiring — route/failover/accounts/domestic ────────────────
    try:
        _wire_phase38_engines()
    except Exception as _p38_exc:
        logger.warning(f"[startup] phase38 wiring failed: {_p38_exc}")
    try:
        _register_phase38_jobs()
    except Exception as _p38j_exc:
        logger.warning(f"[startup] phase38 jobs failed: {_p38j_exc}")
    log_activity("system", "سرور راه‌اندازی شد", "ok")
    logger.info(f"EMIX v{EMIX_VERSION} started on port {CONFIG['port']}")
    # ─── هشدار پایداری دیتا روی Railway ────────────────────────────────────
    # اگر روی Railway هستید و Volume به /data وصل نشده، هر ری‌دیپلوی کل state
    # (LINKS + SUBS + NODES + password_hash) را پاک می‌کند. این هشدار کمک
    # می‌کند علت «کانفیگ‌ها نمی‌آیند پس از ری‌دیپلوی» را پیدا کنید.
    try:
        if not DATA_DIR.exists() or not os.access(str(DATA_DIR), os.W_OK):
            logger.warning(
                "⚠️ DATA_DIR (%s) قابل نوشتن نیست — کانفیگ‌ها پس از ری‌دیپلوی پاک می‌شوند. "
                "روی Railway یک Volume به مسیر /data وصل کنید." % DATA_DIR
            )
        else:
            test_file = DATA_DIR / ".emix_write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            logger.info(f"✓ DATA_DIR ({DATA_DIR}) قابل نوشتن — state پایدار است.")
    except Exception as _e:
        logger.warning(
            "⚠️ DATA_DIR (%s) قابل نوشتن نیست (%s) — کانفیگ‌ها پس از ری‌دیپلوی پاک می‌شوند. "
            "روی Railway یک Volume به مسیر /data وصل کنید." % (DATA_DIR, _e)
        )

async def _restart_mtproto_instances():
    """بعد از بالا اومدن پنل، به‌ازای هر لینک MTProto فعال یک پروسه‌ی جدای
    mtproto_native (باینری رسمی تلگرام) روی پورت خودش بالا می‌آره."""
    async with LINKS_LOCK:
        targets = [
            (uid, d) for uid, d in LINKS.items()
            if d.get("protocol") == "mtproto" and d.get("active", True)
        ]
    if targets and not bottokentcpproxy.has_saved_token():
        logger.error(
            f"⚠️ {len(targets)} لینک MTProto وجود دارد ولی توکن Railway ذخیره نشده — "
            f"هیچ TCP Proxy عمومی ساخته/بازسازی نمی‌شود و این لینک‌ها از بیرون کار نمی‌کنند. "
            f"(اگر قبلاً توکن را وارد کرده بودید، یعنی دایرکتوری DATA_DIR بین دیپلوی‌ها "
            f"پاک می‌شود و باید یک Volume پایدار روی Railway بهش وصل کنید.)"
        )
    for uid, d in targets:
        try:
            inst = await mtproto.start_instance(
                uid,
                secret=d.get("mtproto_secret"),
                domain=d.get("mtproto_domain", mtproto.DEFAULT_FAKE_TLS_DOMAIN),
                preferred_port=d.get("mtproto_port"),
                force_port=d.get("mtproto_manual_port", False),
                ad_tag=d.get("ad_tag"),
            )
        except Exception as exc:
            logger.error(f"MTProto[{uid[:8]}]: راه‌اندازی ناموفق بود: {exc}\n{traceback.format_exc()}")
            continue

        old_port = d.get("mtproto_port")
        async with LINKS_LOCK:
            if uid in LINKS:
                LINKS[uid]["mtproto_port"] = inst["port"]
                LINKS[uid]["mtproto_secret"] = inst["secret"]

        if (d.get("mtproto_proxy_id") and inst["port"] != old_port
                and not d.get("mtproto_manual_port", False)):
            asyncio.create_task(_reattach_mtproto_public_proxy(
                uid, inst["port"], d.get("mtproto_proxy_id"), d.get("label", "")
            ))
        elif not d.get("mtproto_proxy_id") and bottokentcpproxy.has_saved_token():
            # لینکی که هنوز هیچ TCP Proxy عمومی نداره (مثلاً چون با نسخه‌ی قدیمی
            # ساخته شده) — بدون این، لینکش مرده می‌مونه.
            asyncio.create_task(_attach_mtproto_public_proxy(
                uid, inst["port"], d.get("label", "")
            ))


async def _mtproto_usage_callback(uuid: str, n_bytes: int) -> bool:
    async with LINKS_LOCK:
        link = LINKS.get(uuid)
        if link is None:
            return False
        if not is_link_allowed(link):
            return False
        link["used_bytes"] += n_bytes
        stats["total_bytes"] += n_bytes
        hourly_traffic[_hourly_traffic_key()] += n_bytes
    return True

mtproto.set_usage_callback(_mtproto_usage_callback)


async def _attach_mtproto_public_proxy(uid: str, application_port: int, label: str):
    """TCP Proxy عمومی روی Railway برای پورت این instance خاص می‌سازه (هر لینک
    پورت جدای خودش رو داره، پس هرکدوم TCP Proxy جدای خودش رو لازم داره)."""
    try:
        pub = await bottokentcpproxy.create_public_proxy_for_port(application_port)
    except Exception as exc:
        logger.warning(f"TCP Proxy عمومی برای {uid[:8]} ناموفق بود: {exc}")
        log_activity("link", f"ساخت TCP Proxy عمومی برای «{label}» ناموفق بود: {exc}", "err")
        return
    async with LINKS_LOCK:
        if uid in LINKS:
            LINKS[uid]["mtproto_public_host"] = pub["domain"]
            LINKS[uid]["mtproto_public_port"] = pub["port"]
            LINKS[uid]["mtproto_proxy_id"] = pub["id"]
            LINKS[uid]["mtproto_public_pending"] = False
    asyncio.create_task(save_state())
    log_activity("link", f"TCP Proxy عمومی «{label}» آماده شد ({pub['domain']}:{pub['port']})", "ok")


async def _reattach_mtproto_public_proxy(uid: str, new_port: int, old_proxy_id: Optional[str], label: str):
    if old_proxy_id:
        await bottokentcpproxy.delete_public_proxy(old_proxy_id)
    await _attach_mtproto_public_proxy(uid, new_port, label)


async def _update_mtproto_ad_tag(uuid: str, ad_tag: str):
    """پروسه‌ی این کاربر رو stop/start می‌کنه تا ad_tag جدید (که -P هست، سطح
    process، نه runtime-API) اعمال بشه. force_port=True چون تازه stop شده و
    پورت قدیمی باید آزاد باشه؛ اگه بازم آزاد نشد، پورت جدید می‌گیره و TCP Proxy
    عمومی رو دوباره به پورت جدید وصل می‌کنیم."""
    try:
        async with LINKS_LOCK:
            link = LINKS.get(uuid)
            if not link:
                return
            label = link.get("label", "")
            secret = link.get("mtproto_secret")
            domain = link.get("mtproto_domain", mtproto.DEFAULT_FAKE_TLS_DOMAIN)
            old_port = link.get("mtproto_port")
            old_proxy_id = link.get("mtproto_proxy_id")
            manual_port = link.get("mtproto_manual_port", False)
            if not secret:
                logger.error(f"MTProto[{uuid[:8]}]: سکرت پیدا نشد")
                return

        await mtproto.stop_instance(uuid)
        try:
            inst = await mtproto.start_instance(
                uuid,
                secret=secret,
                domain=domain,
                preferred_port=old_port,
                force_port=True,
                ad_tag=ad_tag,
            )
        except RuntimeError as exc:
            logger.warning(f"ad_tag ناموفق بود ({exc})، تلاش با پورت جدید...")
            inst = await mtproto.start_instance(
                uuid,
                secret=secret,
                domain=domain,
                preferred_port=None,
                force_port=False,
                ad_tag=ad_tag,
            )

        async with LINKS_LOCK:
            link = LINKS.get(uuid)
            if not link:
                asyncio.create_task(mtproto.stop_instance(uuid))
                return
            link["mtproto_port"] = inst["port"]
            link["mtproto_secret"] = inst["secret"]
            link["mtproto_domain"] = inst["domain"]
            link["ad_tag"] = ad_tag
            link["ad_tag_status"] = "done"
            link["ad_tag_link"] = generate_share_link(
                uuid, get_host(), remark=f"EMIX-{link.get('label','')}", protocol="mtproto"
            )
        _supervise_mtproto_instance(uuid)  # audit fix: re-supervise after ad_tag restart

        if inst["port"] != old_port and old_proxy_id and not manual_port:
            asyncio.create_task(_reattach_mtproto_public_proxy(
                uuid, inst["port"], old_proxy_id, label
            ))

        asyncio.create_task(save_state())
        logger.info(
            f"MTProto[{uuid[:8]}]: ad_tag به‌روز شد، instance ری‌استارت شد "
            f"(پورت: {old_port} -> {inst['port']})"
        )
        log_activity("link", f"تبلیغ کانال برای «{label}» با موفقیت اعمال شد", "ok")

    except Exception as exc:
        logger.error(f"خطا در به‌روزرسانی ad_tag برای {uuid[:8]}: {exc}")
        async with LINKS_LOCK:
            if uuid in LINKS:
                LINKS[uuid]["ad_tag_status"] = "error"
        log_activity("link", f"به‌روزرسانی ad_tag برای «{LINKS.get(uuid,{}).get('label','')}» ناموفق بود", "err")
        asyncio.create_task(save_state())


@app.on_event("shutdown")
async def shutdown():
    # Cancel background tasks first (Phase 26 — graceful shutdown)
    global _session_cleanup_task
    if _session_cleanup_task is not None and not _session_cleanup_task.done():
        _session_cleanup_task.cancel()
        try:
            await _session_cleanup_task
        except asyncio.CancelledError:
            pass
        _session_cleanup_task = None
    # Stop the background job system before saving state (Phase 20/26)
    try:
        await job_system.stop()
    except Exception:
        pass
    await save_state()
    await mtproto.stop_all()
    if http_client:
        await http_client.aclose()

# ── Helpers ───────────────────────────────────────────────────────────────────
# دامنه‌ی عمومی خودآموخته: در دیپلوی‌های جدید Railway متغیر RAILWAY_PUBLIC_DOMAIN
# همیشه ست نمی‌شود و لینک‌ها روی localhost می‌مانند. این مکانیزم دامنه را از
# هدر Host درخواست‌های ورودی یاد می‌گیرد (پشت edge ریلوی، Host همیشه دامنه‌ی
# واقعی سرویس است) و get_host به‌صورت خودشفابا به آن ارتقا می‌یابد.
_LEARNED_PUBLIC_HOST: str | None = None

@app.middleware("http")
async def _learn_public_host_middleware(request: Request, call_next):
    global _LEARNED_PUBLIC_HOST
    try:
        if not os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
            host = (request.headers.get("host") or "").split(":")[0].strip().lower()
            if (
                host
                and "." in host
                and host not in ("localhost", "127.0.0.1", "0.0.0.0")
                and not host.startswith("10.")
                and not host.startswith("192.168.")
                and not host.startswith("172.")
            ):
                if _LEARNED_PUBLIC_HOST != host:
                    _LEARNED_PUBLIC_HOST = host
                    logger.info(f"[host] دامنه‌ی عمومی از درخواست یاد گرفته شد: {host}")
    except Exception:
        pass
    response = await call_next(request)
    # Phase 36 — Cache safety: NEVER cache tunnel/auth/subscription/admin paths.
    # Applied globally so every response (including static sub pages) gets the headers.
    try:
        from reverseproxy import is_tunnel_path, add_cache_safety_headers
        if is_tunnel_path(request.url.path):
            new_headers = dict(response.headers)
            new_headers = add_cache_safety_headers(new_headers, request.url.path)
            for k, v in new_headers.items():
                # Use existing header if present (replace), else add
                response.headers[k] = v
    except Exception as _e:
        logger.debug(f"[cache-safety] middleware error (continuing): {_e}")
    return response

def get_host() -> str:
    env_host = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if env_host:
        return env_host
    if _LEARNED_PUBLIC_HOST:
        return _LEARNED_PUBLIC_HOST
    return CONFIG["host"]

def generate_uuid() -> str:
    h = secrets.token_hex(16)
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"

def now_ir() -> datetime:
    return datetime.now(IRAN_TZ)

def _emit_mtproto_link(link: dict, host: str, remark: str) -> str:
    """MTProto emitter — keeps mtg FakeTLS + public-proxy-host semantics
    exactly as before (never falls back to the panel domain: the internal
    port is unreachable from outside Railway)."""
    secret = link.get("mtproto_secret")
    if not secret:
        return f"tg://proxy?server={host}&port=0&secret=not_ready#{quote(remark)}"
    pub_host = link.get("mtproto_public_host")
    pub_port = link.get("mtproto_public_port")
    if not pub_host or not pub_port:
        return f"tg://proxy?server={host}&port=0&secret=not_ready#{quote(remark)}"
    return mtproto.generate_mtproto_link(
        pub_host, pub_port, secret,
        mtproto.sanitize_domain(link.get("mtproto_domain"))
    )


def generate_share_link(uuid: str, host: str, remark: str = "EMIX", protocol: str = DEFAULT_PROTOCOL) -> str:
    """[Config Compiler facade — Phase 3 refactor]

    THE emission path is now config_compiler.compile_from_link():
      normalize → compat validation → endpoint resolution → deterministic
      emit → self-check → version + checksum.
    Output is byte-identical with the previous inline emitter (verified by
    tests/unit/test_config_compiler.py::test_wire_compat_*).

    The legacy inline body is preserved below as `_generate_share_link_legacy`
    and is used ONLY as an emergency fallback if the compiler rejects a
    stored record (cannot happen for records created through the API) —
    this guarantees no existing subscription can ever break.
    """
    link = LINKS.get(uuid) or {}
    if protocol == "mtproto":
        return _emit_mtproto_link(link, host, remark)
    eff_link = dict(link)
    eff_link["protocol"] = protocol
    eff_link["label"] = remark
    compiled = config_compiler.compile_from_link(
        eff_link, host,
        cdn_domain=os.environ.get("EMIX_CDN_DOMAIN", "").strip().lower(),
        credential=uuid,
    )
    if compiled.ok and compiled.uri is not None:
        return compiled.uri
    logger.warning(
        f"[compiler] falling back to legacy emitter for {uuid[:8]} "
        f"protocol={protocol!r}: {compiled.errors}"
    )
    try:
        diagnostics_mod.record_error_sync(
            code="CONFIG_COMPILER_FALLBACK",
            message=f"compile failed for protocol={protocol!r}: {'; '.join(compiled.errors)[:200]}",
            component="config-compiler",
            severity="WARNING",
            context={"protocol": protocol},
        )
    except Exception:
        pass
    return _generate_share_link_legacy(uuid, host, remark, protocol)


def _generate_share_link_legacy(uuid: str, host: str, remark: str = "EMIX", protocol: str = DEFAULT_PROTOCOL) -> str:
    """[DEPRECATED — emergency fallback only; primary path is the Config
    Compiler. Kept verbatim so a compiler rejection can never break an
    existing subscription.]"""
    link = LINKS.get(uuid) or {}
    alpn = link.get("alpn", "h2")
    fp = link.get("fingerprint", "chrome")
    # SNI Spoofing (per-link, opt-in): returns `host` unchanged when disabled
    # or when the configured spoof value fails validation. 100% backward compat.
    effective_sni = _get_effective_sni(link, host)

    # ── CDN-domain routing for SNI Spoofing ──────────────────────────────
    # SNI Spoofing works in two modes:
    #
    # Mode A — CDN routing (preferred, when EMIX_CDN_DOMAIN is set):
    #   - URL host = CDN domain (client connects to CDN edge, not Railway)
    #   - host param = CDN domain (for CDN routing via Host header)
    #   - sni param = spoofed domain (CDN accepts any SNI)
    #   - No allowInsecure needed (CDN's cert is valid)
    #
    # Mode B — Direct Railway with allowInsecure (when no CDN):
    #   - URL host = panel domain (client connects to Railway directly)
    #   - host param = panel domain
    #   - sni param = spoofed domain (Railway presents *.up.railway.app cert)
    #   - allowInsecure=1 → client skips cert verification → TLS succeeds
    #   - Less secure (no MITM protection) but works for DPI evasion
    #   - DPI sees the spoofed SNI in the ClientHello, not the cert
    cdn_domain = os.environ.get("EMIX_CDN_DOMAIN", "").strip().lower()
    spoof_enabled = bool(link.get("spoof_sni_enabled"))
    spoof_valid = bool(_validate_sni(link.get("spoof_sni")))
    use_cdn_routing = spoof_enabled and spoof_valid and cdn_domain
    allow_insecure = False
    if use_cdn_routing:
        # Mode A — CDN routing
        connection_host = cdn_domain
        ws_host = cdn_domain
        effective_sni = _validate_sni(link.get("spoof_sni")) or host
    elif spoof_enabled and spoof_valid and not cdn_domain:
        # Mode B — Direct Railway with allowInsecure=1
        # Client connects to Railway → sends SNI=spoofed → Railway presents
        # its own cert → client skips verification (allowInsecure=1) → TLS OK
        # DPI sees the spoofed SNI in ClientHello → doesn't block
        connection_host = host
        ws_host = host
        effective_sni = _validate_sni(link.get("spoof_sni"))
        allow_insecure = True
    else:
        # No spoof — standard behavior (100% backward compat)
        connection_host = host
        ws_host = host

    if protocol == "mtproto":
        # MTProto uses its own FakeTLS domain (mtproto_domain) — SNI spoofing
        # is NOT applicable here. Skip entirely to preserve behavior.
        secret = link.get("mtproto_secret")
        if not secret:
            return f"tg://proxy?server={host}&port=0&secret=not_ready#{quote(remark)}"
        # مهم: برای MTProto هیچ‌وقت به دامنه‌ی پنل fallback نمی‌کنیم. دامنه‌ی اصلی
        # Railway فقط HTTP/443 رو سرو می‌کنه و پورت داخلی (مثلاً 8477) از بیرون
        # اصلاً باز نیست — چنین لینکی کاملاً مرده‌ست (نه پینگ می‌ده نه وصل می‌شه).
        # تنها آدرس معتبر، دامنه/پورتی هست که Railway موقع ساخت TCP Proxy می‌ده.
        pub_host = link.get("mtproto_public_host")
        pub_port = link.get("mtproto_public_port")
        if not pub_host or not pub_port:
            return f"tg://proxy?server={host}&port=0&secret=not_ready#{quote(remark)}"
        return mtproto.generate_mtproto_link(
            pub_host, pub_port, secret,
            mtproto.sanitize_domain(link.get("mtproto_domain"))
        )

    if protocol == "shadowsocks":
        # SS v2ray-plugin uses `host=` parameter for BOTH WS Host header AND
        # TLS SNI. Changing it would break WS routing through CDN edge.
        # The protocol file (protocol/shadowsocks/shadowsocks.py) is NOT modified.
        # SNI spoofing for SS is therefore NOT supported in this implementation
        # — falls back to original host behavior (the panel domain).
        # This is documented as "Partial support" in the protocol matrix.
        cipher = link.get("ss_cipher", DEFAULT_CIPHER)
        password = link.get("ss_password", "")
        return generate_ss_link(host, 443, cipher, password, remark)

    if protocol == "trojan-ws":
        params = {
            "security": "tls", "type": "ws", "host": ws_host,
            "path": "/trojan-ws", "sni": effective_sni, "fp": fp, "alpn": alpn,
        }
        if allow_insecure:
            params["allowInsecure"] = "1"
        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return f"trojan://{uuid}@{connection_host}:443?{query}#{quote(remark)}"

    if protocol.startswith("trojan-xhttp-"):
        mode = protocol.replace("trojan-xhttp-", "")
        path = f"/txhttp-siz10/{mode}/{uuid}"
        params = {
            "security": "tls", "type": "xhttp", "mode": mode, "host": ws_host,
            "path": path, "sni": effective_sni, "fp": fp, "alpn": alpn,
        }
        if allow_insecure:
            params["allowInsecure"] = "1"
        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return f"trojan://{uuid}@{connection_host}:443?{query}#{quote(remark)}"

    if protocol == "vless-ws":
        path = f"/ws/{uuid}"
        params = {
            "encryption": "none",
            "security": "tls",
            "type": "ws",
            "host": ws_host,
            "path": path,
            "sni": effective_sni,
            "fp": fp,
            "alpn": alpn,
        }
        if allow_insecure:
            params["allowInsecure"] = "1"
    else:
        mode = protocol.replace("xhttp-", "")
        path = f"/xhttp-siz10/{mode}/{uuid}"
        params = {
            "encryption": "none",
            "security": "tls",
            "type": "xhttp",
            "mode": mode,
            "host": ws_host,
            "path": path,
            "sni": effective_sni,
            "fp": fp,
            "alpn": alpn,
        }
        if allow_insecure:
            params["allowInsecure"] = "1"
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return f"vless://{uuid}@{connection_host}:443?{query}#{quote(remark)}"

def uptime() -> str:
    secs = int(time.time() - stats["start_time"])
    h, m, s = secs // 3600, (secs % 3600) // 60, secs % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def parse_size_to_bytes(value: float, unit: str) -> int:
    """Convert a (value, unit) pair to bytes.

    Strict validation (Phase 2.8):
      - value must be a real number (reject NaN, inf, None, malformed strings)
      - value must be >= 0
      - unit must be one of {"B","KB","MB","GB"} (case-insensitive, trimmed)

    Raises:
      ValueError on any invalid input.
      TypeError on non-numeric input.
    """
    # Reject non-finite floats (NaN, inf) — `float(value)` will accept them,
    # so we have to explicitly check.
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"size value must be a number, got {value!r}") from exc
    if v != v:  # NaN
        raise ValueError("size value must not be NaN")
    if v in (float("inf"), float("-inf")):
        raise ValueError("size value must be finite")
    if v < 0:
        raise ValueError(f"size value must not be negative, got {v}")
    u = (unit or "").strip().upper()
    if u == "GB": return int(v * 1024 ** 3)
    if u == "MB": return int(v * 1024 ** 2)
    if u == "KB": return int(v * 1024)
    if u in ("B", ""): return int(v)
    raise ValueError(f"unsupported size unit: {unit!r} (must be B/KB/MB/GB)")


# ─── SNI Spoofing helpers (per-link, opt-in, zero breaking changes) ────────
# Default behavior preserved: when spoof_sni_enabled is False or unset,
# _get_effective_sni() returns the original host — code path is 100%
# identical to behavior before this feature was introduced.
import re as _re

_SNI_HOSTNAME_RE = _re.compile(r"^[a-z0-9][a-z0-9\-\.]*[a-z0-9]$")
_SNI_IPV4_RE = _re.compile(r"^\d+\.\d+\.\d+\.\d+$")
_SNI_BLOCKED_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", "ip6-localhost"})


def _validate_sni(value) -> str | None:
    """Validate and normalize a spoof SNI value. Returns None if invalid.

    Rules (RFC 1123 subset):
      - non-empty string after trim+lower
      - 3 ≤ length ≤ 253
      - only ASCII letters/digits/hyphens/dots
      - must contain at least one dot (TLD separator)
      - must NOT be an IPv4 or IPv6 address
      - must NOT be localhost / 127.0.0.1 / 0.0.0.0 / ::1
    """
    if not value:
        return None
    try:
        s = str(value).strip().lower()
    except Exception:
        return None
    if not s:
        return None
    if len(s) > 253 or len(s) < 3:
        return None
    if not _SNI_HOSTNAME_RE.fullmatch(s):
        return None
    if "." not in s:
        return None
    if _SNI_IPV4_RE.match(s):
        return None
    if s in _SNI_BLOCKED_HOSTS:
        return None
    return s


def _get_effective_sni(link: dict | None, host: str) -> str:
    """Return spoofed SNI if enabled+valid, otherwise return original host.

    Defensive: if link is None, spoof_sni_enabled is False/missing, or the
    configured spoof value fails validation, fall back to the original host.
    This preserves 100% backward compatibility — every existing link
    continues to use its host as the SNI.
    """
    if not link or not link.get("spoof_sni_enabled"):
        return host
    spoof = _validate_sni(link.get("spoof_sni"))
    return spoof if spoof else host

def is_link_expired(link: dict) -> bool:
    exp = link.get("expires_at")
    if not exp:
        return False
    try:
        return datetime.now() > datetime.fromisoformat(exp)
    except Exception:
        return False

def is_link_allowed(link: dict | None) -> bool:
    if link is None:
        return False
    if not link.get("active", True):
        return False
    if is_link_expired(link):
        return False
    lb = link.get("limit_bytes", 0)
    if lb > 0 and link.get("used_bytes", 0) >= lb:
        return False
    return True

def fmt_bytes(b: int) -> str:
    if b < 1024: return f"{b} B"
    if b < 1024**2: return f"{b/1024:.1f} KB"
    if b < 1024**3: return f"{b/1024**2:.2f} MB"
    return f"{b/1024**3:.2f} GB"

def build_sub_headers(label: str, used_bytes: int, limit_bytes: int, expires_at: str | None, support_url: str = "https://t.me/emixpi") -> dict:
    total = limit_bytes if limit_bytes > 0 else 0
    expire_ts = 0
    if expires_at:
        try:
            expire_ts = int(datetime.fromisoformat(expires_at).timestamp())
        except Exception:
            expire_ts = 0
    userinfo = f"upload=0; download={used_bytes}; total={total}; expire={expire_ts}"
    title_b64 = base64.b64encode(label.encode("utf-8")).decode()
    return {
        "profile-title": f"base64:{title_b64}",
        "subscription-userinfo": userinfo,
        "profile-update-interval": "6",
        "support-url": support_url,
    }

def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "نامشخص"

# ── Node linking helpers ──────────────────────────────────────────────────────
def _b64u_encode(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode().rstrip("=")


def _b64u_decode(s: str) -> str:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad).decode("utf-8")


def build_node_key(host: str, secret: str) -> str:
    """کلید خودکفا: دامنه‌ی این پنل داخل خودِ کلید کدگذاری میشه."""
    return f"{NODE_KEY_PREFIX}{_b64u_encode(host)}.{secret}"


def parse_node_key(key: str) -> tuple[str, str]:
    """برمی‌گرداند (host, secret). در صورت نامعتبر بودن ValueError می‌دهد."""
    key = (key or "").strip()
    if not key.startswith(NODE_KEY_PREFIX):
        raise ValueError("کلید باید با rvg- شروع شود")
    body = key[len(NODE_KEY_PREFIX):]
    if "." not in body:
        raise ValueError("ساختار کلید نامعتبر است")
    host_part, secret = body.split(".", 1)
    if not secret:
        raise ValueError("بخش سکرت کلید خالی است")
    try:
        host = _b64u_decode(host_part).strip()
    except Exception:
        raise ValueError("دامنه‌ی داخل کلید قابل خواندن نیست")
    if not host or "/" in host or " " in host:
        raise ValueError("دامنه‌ی داخل کلید نامعتبر است")
    return host, secret


def _node_scheme(host: str) -> str:
    # فقط برای تست محلی http مجاز است؛ در بقیه‌ی موارد اجباراً https
    return "http" if host.startswith(("localhost", "127.0.0.1")) else "https"


def _normalize_node(n: dict) -> dict:
    share = n.get("share") or {}
    return {
        "label": str(n.get("label") or n.get("host") or "نود")[:60],
        "host": str(n.get("host") or ""),
        "key": str(n.get("key") or ""),
        "enabled": bool(n.get("enabled", True)),
        "merge_dashboard": bool(n.get("merge_dashboard", True)),
        "share": {p: bool(share.get(p, p != "logs")) for p in NODE_SHARE_PARTS},
        "created_at": n.get("created_at") or datetime.now().isoformat(),
        "last_sync_at": n.get("last_sync_at"),
        "last_error": n.get("last_error"),
        "peer_version": n.get("peer_version"),
    }


def _node_public(node_id: str, n: dict) -> dict:
    """نسخه‌ی امن برای فرانت‌اند — کلید خام بیرون نمی‌رود."""
    out = {k: v for k, v in n.items() if k != "key"}
    out["node_id"] = node_id
    out["key_preview"] = (n.get("key") or "")[:14] + "…"
    return out


async def _node_request(node: dict, method: str, path: str, *,
                        params: dict | None = None,
                        json_body: dict | None = None,
                        timeout: float = 10.0) -> httpx.Response:
    host = node["host"]
    url = f"{_node_scheme(host)}://{host}{path}"
    client = http_client or httpx.AsyncClient()
    return await client.request(
        method, url,
        params=params, json=json_body,
        headers={NODE_KEY_HEADER: node["key"]},
        timeout=timeout, follow_redirects=False,
    )


async def require_node_key(request: Request) -> str:
    """احراز هویت پنل مقابل با هدر X-RVG-Node-Key (بدون کوکی سشن)."""
    raw = (request.headers.get(NODE_KEY_HEADER) or "").strip()
    if not raw:
        raise HTTPException(status_code=401, detail="node key missing")
    try:
        _, secret = parse_node_key(raw)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid node key")
    matched = None
    async with NODE_KEYS_LOCK:
        for key_id, entry in NODE_KEYS.items():
            if entry.get("revoked"):
                continue
            if secrets.compare_digest(str(entry.get("secret", "")), secret):
                matched = key_id
                break
        if matched is None:
            raise HTTPException(status_code=401, detail="unknown or revoked node key")
        entry = NODE_KEYS[matched]
        entry["last_used_at"] = datetime.now().isoformat()
        entry["use_count"] = int(entry.get("use_count", 0)) + 1
    asyncio.create_task(schedule_save())
    return matched

# ── Default link ──────────────────────────────────────────────────────────────
_default_link_created = False

async def ensure_default_link():
    """اگر هیچ کانفیگی وجود نداشته باشد، چندین کانفیگ پیش‌فرض سالم می‌سازد تا
    کاربر بلافاصله پس از دیپلوی (حتی بدون Volume پایدار) بتواند پینگ بگیرد.
    کانفیگ‌ها: vless-ws، trojan-ws، shadowsocks — هر سه روی پورت 443 با TLS."""
    global _default_link_created
    if _default_link_created:
        return
    async with LINKS_LOCK:
        # اگر از قبل کانفیگ وجود دارد، چیزی نساز
        if LINKS:
            _default_link_created = True
            return
        # سه کانفیگ پیش‌فرض با UUID پایدار (مشتق از SECRET_KEY) می‌سازد
        # تا بین ری‌استارت‌ها ثابت بمانند (مهم برای کلاینت‌های متصل)
        base = hashlib.sha256(f"emix-default-{CONFIG['secret']}".encode()).hexdigest()
        # سه UUID مجزا از هم بساز
        uids = []
        for i, prefix in enumerate(["vless", "trojan", "ss"]):
            h = hashlib.sha256(f"{prefix}-{base}".encode()).hexdigest()
            uid = f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"
            uids.append((prefix, uid))
        protocols_map = {
            "vless": ("vless-ws", "VLESS · WS+TLS", "کانونفیگ سبک و پایدار — بهترین گزینه برای موبایل و دسکتاپ"),
            "trojan": ("trojan-ws", "Trojan · WS+TLS", "کانونفیگ Trojan با TLS — پایدار روی اکثر شبکه‌ها"),
            "ss": ("shadowsocks", "Shadowsocks · WS+TLS", "کانفیگ Shadowsocks با WebSocket — سبک و سریع"),
        }
        now_iso = datetime.now().isoformat()
        for prefix, uid in uids:
            if uid in LINKS:
                continue
            proto, label, note = protocols_map[prefix]
            LINKS[uid] = {
                "label": label,
                "limit_bytes": 0,           # نامحدود
                "used_bytes": 0,
                "created_at": now_iso,
                "active": True,
                "expires_at": None,         # بدون انقضا
                "note": note,
                "is_default": True,
                "sub_id": None,
                "protocol": proto,
                "alpn": "h2,http/1.1",
                "fingerprint": "chrome",
            }
        logger.info(
            f"[bootstrap] {len(uids)} کانفیگ پیش‌فرض ساخته شد (vless-ws / trojan-ws / shadowsocks) — "
            f"با UUID پایدار. این کانفیگ‌ها پس از هر ری‌دیپلوی به‌صورت خودکار بازسازی می‌شوند."
        )
        asyncio.create_task(save_state())
        _default_link_created = True

# ── Basic endpoints ───────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "service": "EMIX",
        "version": EMIX_VERSION,
        "build_date": EMIX_BUILD_DATE,
        "status": "active",
        "channel": "https://t.me/emixpi",
        "version_endpoint": "/api/deployment-version",
    }

@app.get("/health")
async def health():
    return {"status": "ok", "connections": len(connections), "uptime": uptime()}

# ── Subscription (single link) ────────────────────────────────────────────────
@app.get("/sub/{uuid}")
async def subscription_single(uuid: str):
    async with LINKS_LOCK:
        link = LINKS.get(uuid)
    if not link or not is_link_allowed(link):
        raise HTTPException(status_code=404, detail="not found or inactive")
    host = get_host()
    proto = link.get("protocol", DEFAULT_PROTOCOL)
    vless = generate_share_link(uuid, host, remark=f"EMIX-{link['label']}", protocol=proto)
    content = base64.b64encode(vless.encode()).decode()
    headers = build_sub_headers(link["label"], link.get("used_bytes", 0), link.get("limit_bytes", 0), link.get("expires_at"))
    return Response(content=content, media_type="text/plain", headers=headers)

@app.get("/sub-all")
async def subscription_all(_=Depends(require_auth)):
    host = get_host()
    async with LINKS_LOCK:
        allowed = [d for d in LINKS.values() if is_link_allowed(d)]
        lines = [
            generate_share_link(uid, host, remark=f"EMIX-{d['label']}", protocol=d.get("protocol", DEFAULT_PROTOCOL))
            for uid, d in LINKS.items()
            if is_link_allowed(d)
        ]
        total_used = sum(d.get("used_bytes", 0) for d in allowed)
        total_limit = sum(d.get("limit_bytes", 0) for d in allowed)
        expiries = [d["expires_at"] for d in allowed if d.get("expires_at")]
    nearest_exp = min(expiries) if expiries else None
    content = base64.b64encode("\n".join(lines).encode()).decode()
    headers = build_sub_headers("EMIX-All", total_used, total_limit, nearest_exp)
    return Response(content=content, media_type="text/plain", headers=headers)

# ══════════════════════════════════════════════════════════════════════════════
# SUB GROUP endpoints (بدون تغییر)
# ══════════════════════════════════════════════════════════════════════════════

async def _create_sub_core(body: dict) -> dict:
    name = (body.get("name") or "گروه جدید").strip()[:60]
    desc = (body.get("desc") or "").strip()[:200]
    password = (body.get("password") or "").strip()
    sub_id = generate_uuid()
    uuid_key = secrets.token_urlsafe(16)
    async with SUBS_LOCK:
        SUBS[sub_id] = {
            "name": name,
            "desc": desc,
            "password_hash": hash_password(password) if password else None,
            "uuid_key": uuid_key,
            "created_at": datetime.now().isoformat(),
            "link_ids": [],
            "node_link_ids": [],
        }
    asyncio.create_task(save_state())
    log_activity("sub", f"گروه «{name}» ساخته شد", "ok")
    host = get_host()
    return {
        "sub_id": sub_id,
        **SUBS[sub_id],
        "public_url": f"https://{host}/p/{uuid_key}",
        "sub_url": f"https://{host}/sub-group/{uuid_key}",
    }

@app.post("/api/subs")
async def create_sub(request: Request, _=Depends(require_auth)):
    body = await request.json()
    return await _create_sub_core(body)

@app.post("/api/node/subs")
async def node_create_sub(request: Request, key_id: str = Depends(require_node_key)):
    await _require_node_manage(key_id)
    body = await request.json()
    return await _create_sub_core(body)

@app.get("/api/subs")
async def list_subs(_=Depends(require_auth)):
    host = get_host()
    async with SUBS_LOCK:
        snap_subs = dict(SUBS)
    async with LINKS_LOCK:
        snap_links = dict(LINKS)
    result = []
    for sid, s in snap_subs.items():
        link_ids = s.get("link_ids", [])
        node_link_ids = s.get("node_link_ids", [])
        foreign_links = s.get("foreign_links", [])
        active_count = sum(1 for lid in link_ids if is_link_allowed(snap_links.get(lid)))
        total_used = sum(snap_links[lid].get("used_bytes", 0) for lid in link_ids if lid in snap_links)
        total_used += sum(int(fl.get("used_bytes") or 0) for fl in foreign_links)
        result.append({
            "sub_id": sid,
            **s,
            "node_link_ids": node_link_ids,
            "foreign_links": foreign_links,
            "password_hash": None,
            "has_password": s.get("password_hash") is not None,
            "links_count": len(link_ids) + len(node_link_ids) + len(foreign_links),
            "active_count": active_count + len(foreign_links),
            "total_used_bytes": total_used,
            "total_used_fmt": fmt_bytes(total_used),
            "public_url": f"https://{host}/p/{s['uuid_key']}",
            "sub_url": f"https://{host}/sub-group/{s['uuid_key']}",
        })
    result.sort(key=lambda x: x["created_at"], reverse=True)
    return {"subs": result}

@app.patch("/api/subs/{sub_id}")
async def update_sub(sub_id: str, request: Request, _=Depends(require_auth)):
    body = await request.json()
    async with SUBS_LOCK:
        if sub_id not in SUBS:
            raise HTTPException(status_code=404, detail="sub not found")
        s = SUBS[sub_id]
        if "name" in body:
            s["name"] = str(body["name"])[:60]
        if "desc" in body:
            s["desc"] = str(body["desc"])[:200]
        if "password" in body:
            pw = str(body["password"]).strip()
            s["password_hash"] = hash_password(pw) if pw else None
        if "link_ids" in body:
            s["link_ids"] = list(body["link_ids"])
        if "node_link_ids" in body:
            s["node_link_ids"] = [str(x) for x in body["node_link_ids"] if "::" in str(x)]
        if "foreign_links" in body:
            fl = body["foreign_links"] if isinstance(body["foreign_links"], list) else []
            clean = []
            for it in fl:
                if not isinstance(it, dict) or not it.get("vless_link"):
                    continue
                clean.append({
                    "key": str(it.get("key") or "")[:120],
                    "label": str(it.get("label") or "کانفیگ")[:60],
                    "vless_link": str(it.get("vless_link"))[:2000],
                    "used_bytes": int(it.get("used_bytes") or 0),
                    "source": str(it.get("source") or "")[:60],
                })
            s["foreign_links"] = clean
    asyncio.create_task(save_state())
    return {"ok": True}

@app.delete("/api/subs/{sub_id}")
async def delete_sub(sub_id: str, _=Depends(require_auth)):
    async with SUBS_LOCK:
        if sub_id not in SUBS:
            raise HTTPException(status_code=404, detail="sub not found")
        name = SUBS[sub_id].get("name", sub_id)
        del SUBS[sub_id]
    async with LINKS_LOCK:
        for link in LINKS.values():
            if link.get("sub_id") == sub_id:
                link["sub_id"] = None
    asyncio.create_task(save_state())
    log_activity("sub", f"گروه «{name}» حذف شد", "warn")
    return {"ok": True, "deleted": sub_id}

@app.post("/api/subs/{sub_id}/links")
async def assign_link_to_sub(sub_id: str, request: Request, _=Depends(require_auth)):
    body = await request.json()
    link_id = str(body.get("link_id", ""))
    action = str(body.get("action", "add"))
    async with SUBS_LOCK:
        if sub_id not in SUBS:
            raise HTTPException(status_code=404, detail="sub not found")
        s = SUBS[sub_id]
        ids = s.setdefault("link_ids", [])
        if action == "add":
            if link_id not in ids:
                ids.append(link_id)
        else:
            if link_id in ids:
                ids.remove(link_id)
    async with LINKS_LOCK:
        if link_id in LINKS:
            LINKS[link_id]["sub_id"] = sub_id if action == "add" else None
    asyncio.create_task(save_state())
    return {"ok": True}

# ── مدیریت گروه از راه دور (توسط پنل مرکزی روی این نود) ──────────────────────
@app.patch("/api/node/subs/{sub_id}")
async def node_update_sub(sub_id: str, request: Request, key_id: str = Depends(require_node_key)):
    peer = await _require_node_manage(key_id)
    result = await update_sub(sub_id, request, None)
    log_activity("node", f"گروه {sub_id[:8]} از راه دور توسط «{peer}» ویرایش شد", "warn")
    return result

@app.delete("/api/node/subs/{sub_id}")
async def node_delete_sub(sub_id: str, key_id: str = Depends(require_node_key)):
    peer = await _require_node_manage(key_id)
    result = await delete_sub(sub_id, None)
    log_activity("node", f"گروه {sub_id[:8]} از راه دور توسط «{peer}» حذف شد", "err")
    return result

@app.post("/api/node/subs/{sub_id}/links")
async def node_assign_link_to_sub(sub_id: str, request: Request, key_id: str = Depends(require_node_key)):
    await _require_node_manage(key_id)
    return await assign_link_to_sub(sub_id, request, None)

# ── Public sub-group subscription file ───────────────────────────────────────
@app.get("/sub-group/{uuid_key}")
async def sub_group_subscription(uuid_key: str, request: Request):
    async with SUBS_LOCK:
        sub = next((s for s in SUBS.values() if s.get("uuid_key") == uuid_key), None)
    if not sub:
        raise HTTPException(status_code=404, detail="not found")
    if sub.get("password_hash"):
        pw = request.query_params.get("pw", "")
        if hash_password(pw) != sub["password_hash"]:
            raise HTTPException(status_code=403, detail="wrong password")
    host = get_host()
    link_ids = sub.get("link_ids", [])
    node_link_ids = sub.get("node_link_ids", [])
    async with LINKS_LOCK:
        lines = []
        allowed_links = []
        for lid in link_ids:
            link = LINKS.get(lid)
            if link and is_link_allowed(link):
                lines.append(generate_share_link(lid, host, remark=f"EMIX-{link['label']}", protocol=link.get("protocol", DEFAULT_PROTOCOL)))
                allowed_links.append(link)
        total_used = sum(l.get("used_bytes", 0) for l in allowed_links)
        total_limit = sum(l.get("limit_bytes", 0) for l in allowed_links)
        expiries = [l["expires_at"] for l in allowed_links if l.get("expires_at")]
    if node_link_ids:
        async with NODES_LOCK:
            nodes_snap = {nid: dict(n) for nid, n in NODES.items()}
        needed_nodes = list({ref.split("::", 1)[0] for ref in node_link_ids if "::" in ref})
        needed_nodes = [nid for nid in needed_nodes if nid in nodes_snap]
        snapshots = await asyncio.gather(
            *(_fetch_node_snapshot(nid, nodes_snap[nid], fresh=True) for nid in needed_nodes),
            return_exceptions=True,
        )
        snap_by_node = dict(zip(needed_nodes, snapshots))
        for ref in node_link_ids:
            if "::" not in ref:
                continue
            nid, uid = ref.split("::", 1)
            snap = snap_by_node.get(nid)
            if not snap or isinstance(snap, Exception):
                continue
            node_link = next((l for l in (snap.get("links") or []) if l.get("uuid") == uid), None)
            if not node_link or not node_link.get("vless_link"):
                continue
            if not node_link.get("active", True):
                continue
            if node_link.get("expired"):
                continue
            lb = node_link.get("limit_bytes", 0)
            if lb > 0 and node_link.get("used_bytes", 0) >= lb:
                continue
            lines.append(node_link["vless_link"])
            total_used += node_link.get("used_bytes", 0)
            total_limit += node_link.get("limit_bytes", 0)
            if node_link.get("expires_at"):
                expiries.append(node_link["expires_at"])
    for fl in sub.get("foreign_links", []):
        vl = fl.get("vless_link")
        if not vl:
            continue
        lines.append(vl)
        total_used += int(fl.get("used_bytes") or 0)
    nearest_exp = min(expiries) if expiries else None
    content = base64.b64encode("\n".join(lines).encode()).decode()
    headers = build_sub_headers(f"پنل: {sub['name']}", total_used, total_limit, nearest_exp)
    return Response(content=content, media_type="text/plain", headers=headers)

# ── Auth endpoints ────────────────────────────────────────────────────────────
@app.post("/api/login")
async def api_login(request: Request):
    body = await request.json()
    ip = client_ip(request)
    # Brute-force guard (audit fix): همیشه فعال؛ فقط شکست‌ها شمرده می‌شوند.
    from security_exp import login_rate_limited, record_login_failure, clear_login_failures
    if login_rate_limited(ip):
        log_activity("auth", f"ورود مسدود (rate-limit) از {ip}", "err")
        raise HTTPException(status_code=429, detail="تعداد تلاش‌های ناموفق بیش از حد. ۱۵ دقیقه صبر کنید.")
    if hash_password(str(body.get("password", ""))) != AUTH["password_hash"]:
        record_login_failure(ip)
        log_activity("auth", f"تلاش ورود ناموفق از {ip}", "err")
        raise HTTPException(status_code=401, detail="رمز عبور اشتباه است")
    clear_login_failures(ip)
    token = await create_session()
    log_activity("auth", f"ورود موفق به پنل از {ip}", "ok")
    resp = JSONResponse({"ok": True})
    resp.set_cookie(SESSION_COOKIE, token, max_age=SESSION_TTL, httponly=True, samesite="lax", path="/")
    return resp

@app.post("/api/logout")
async def api_logout(request: Request):
    await destroy_session(request.cookies.get(SESSION_COOKIE))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp

@app.get("/api/me")
async def api_me(request: Request):
    return {"authenticated": await is_valid_session(request.cookies.get(SESSION_COOKIE))}

@app.post("/api/change-password")
async def api_change_password(request: Request, token=Depends(require_auth)):
    body = await request.json()
    if hash_password(str(body.get("current_password", ""))) != AUTH["password_hash"]:
        raise HTTPException(status_code=400, detail="رمز فعلی اشتباه است")
    new = str(body.get("new_password", ""))
    if len(new) < 4:
        raise HTTPException(status_code=400, detail="رمز جدید باید حداقل ۴ کاراکتر باشد")
    AUTH["password_hash"] = hash_password(new)
    async with SESSIONS_LOCK:
        SESSIONS.clear()
        SESSIONS[token] = time.time() + SESSION_TTL
    await save_state()
    log_activity("auth", "رمز عبور پنل تغییر کرد", "ok")
    return {"ok": True}
# ── Backup / Restore ──────────────────────────────────────────────────────────
@app.get("/api/backup/export")
async def backup_export(_=Depends(require_auth)):
    async with LINKS_LOCK:
        links_snap = dict(LINKS)
    async with SUBS_LOCK:
        subs_snap = dict(SUBS)
    async with NODE_KEYS_LOCK:
        node_keys_snap = dict(NODE_KEYS)
    async with NODES_LOCK:
        nodes_snap = dict(NODES)
    data = {
        "kind": "rvg-backup",
        "version": "9.2",
        "exported_at": datetime.now().isoformat(),
        "host": get_host(),
        "links": links_snap,
        "subs": subs_snap,
        "node_keys": node_keys_snap,
        "nodes": nodes_snap,
        "password_hash": AUTH["password_hash"],
    }
    content = json.dumps(data, ensure_ascii=False, indent=2)
    filename = f"rvg-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    log_activity("system", "فایل بکاپ دانلود شد", "info")
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/backup/import")
async def backup_import(request: Request, _=Depends(require_auth)):
    """Strict backup import — VALIDATE → STAGE → BACKUP CURRENT → APPLY → VERIFY → COMMIT.

    On any failure: rollback automatically from the staged pre-restore backup.
    Never leaves the panel in a half-written state.
    """
    import backup_validator
    import shutil as _shutil

    body = await request.json()
    data = body.get("data")

    # ── Step 1: VALIDATE (no state change) ─────────────────────────────────
    result = backup_validator.validate_backup(data)
    if not result.ok:
        msg = "; ".join(result.errors[:8])
        if len(result.errors) > 8:
            msg += f" (and {len(result.errors) - 8} more)"
        log_activity("system", f"بکاپ نامعتبر وارد شد ({len(result.errors)} خطا)", "err")
        raise HTTPException(status_code=400, detail=f"backup validation failed: {msg}")
    validated = result.data
    keep_password = bool(body.get("keep_current_password", True))
    new_pw_hash = validated.get("password_hash") if not keep_password else None
    if new_pw_hash:
        # sha256-format check (mirrors load_state's existing guard)
        if not (isinstance(new_pw_hash, str) and len(new_pw_hash) == 64
                and all(c in "0123456789abcdef" for c in new_pw_hash.lower())):
            new_pw_hash = None  # silently ignore non-sha256 hashes

    # ── Step 2: STAGE — snapshot current state for rollback ────────────────
    async with LINKS_LOCK:
        staged_links = dict(LINKS)
    async with SUBS_LOCK:
        staged_subs = dict(SUBS)
    async with NODE_KEYS_LOCK:
        staged_node_keys = dict(NODE_KEYS)
    async with NODES_LOCK:
        staged_nodes = dict(NODES)
    staged_pw_hash = AUTH["password_hash"]
    # Also keep an on-disk backup file in case of crash mid-apply
    pre_restore_path = DATA_FILE.with_name(DATA_FILE.stem + ".pre-restore.json")
    try:
        if DATA_FILE.exists():
            _shutil.copy2(DATA_FILE, pre_restore_path)
            logger.info(f"[backup-import] staged pre-restore snapshot at {pre_restore_path}")
    except Exception as exc:
        logger.warning(f"[backup-import] could not stage pre-restore file: {exc}")

    # ── Step 3: BACKUP CURRENT STATE in memory (done above) ────────────────

    # ── Step 4: APPLY new state ────────────────────────────────────────────
    new_links = validated.get("links", {}) or {}
    new_subs = validated.get("subs", {}) or {}
    new_node_keys = validated.get("node_keys", {}) or {}
    new_nodes_raw = validated.get("nodes", {}) or {}
    try:
        # Stop MTProto processes before clearing (existing behavior)
        try:
            await mtproto.stop_all()
        except Exception as exc:
            logger.warning(f"توقف MTProto قبل از ایمپورت ناموفق بود: {exc}")

        async with LINKS_LOCK:
            LINKS.clear()
            LINKS.update(new_links)
        async with SUBS_LOCK:
            SUBS.clear()
            SUBS.update(new_subs)
        if new_node_keys:
            async with NODE_KEYS_LOCK:
                NODE_KEYS.clear()
                NODE_KEYS.update(new_node_keys)
        if new_nodes_raw:
            async with NODES_LOCK:
                NODES.clear()
                for nid, n in new_nodes_raw.items():
                    if isinstance(n, dict):
                        NODES[nid] = _normalize_node(n)
            _NODE_CACHE.clear()
        if new_pw_hash:
            AUTH["password_hash"] = new_pw_hash
            async with SESSIONS_LOCK:
                SESSIONS.clear()
                # Preserve the current admin's session so they don't get logged out
                token = request.cookies.get(SESSION_COOKIE)
                if token:
                    SESSIONS[token] = time.time() + SESSION_TTL
    except Exception as apply_exc:
        # ── ROLLBACK ────────────────────────────────────────────────────────
        logger.error(f"[backup-import] apply failed — rolling back: {apply_exc}")
        async with LINKS_LOCK:
            LINKS.clear()
            LINKS.update(staged_links)
        async with SUBS_LOCK:
            SUBS.clear()
            SUBS.update(staged_subs)
        async with NODE_KEYS_LOCK:
            NODE_KEYS.clear()
            NODE_KEYS.update(staged_node_keys)
        async with NODES_LOCK:
            NODES.clear()
            NODES.update(staged_nodes)
        AUTH["password_hash"] = staged_pw_hash
        log_activity("system", f"ایمپورت بکاپ شکست خورد — rollback انجام شد: {apply_exc}", "err")
        raise HTTPException(status_code=500, detail=f"restore failed (rolled back): {apply_exc}")

    # ── Step 5: VERIFY — sanity-check the new state ────────────────────────
    try:
        async with LINKS_LOCK:
            verify_links_count = len(LINKS)
        async with SUBS_LOCK:
            verify_subs_count = len(SUBS)
        if verify_links_count != len(new_links):
            raise RuntimeError(f"link count mismatch: expected {len(new_links)}, got {verify_links_count}")
        if verify_subs_count != len(new_subs):
            raise RuntimeError(f"sub count mismatch: expected {len(new_subs)}, got {verify_subs_count}")
    except Exception as verify_exc:
        # Rollback
        logger.error(f"[backup-import] verify failed — rolling back: {verify_exc}")
        async with LINKS_LOCK:
            LINKS.clear()
            LINKS.update(staged_links)
        async with SUBS_LOCK:
            SUBS.clear()
            SUBS.update(staged_subs)
        async with NODE_KEYS_LOCK:
            NODE_KEYS.clear()
            NODE_KEYS.update(staged_node_keys)
        async with NODES_LOCK:
            NODES.clear()
            NODES.update(staged_nodes)
        AUTH["password_hash"] = staged_pw_hash
        log_activity("system", f"ایمپورت بکاپ شکست خورد (verify) — rollback انجام شد", "err")
        raise HTTPException(status_code=500, detail=f"restore verification failed (rolled back): {verify_exc}")

    # ── Step 6: COMMIT — persist to disk ───────────────────────────────────
    await save_state()
    try:
        await _restart_mtproto_instances()
    except Exception as exc:
        logger.error(f"راه‌اندازی مجدد MTProto بعد از ایمپورت ناموفق بود: {exc}")

    log_activity("system", "بکاپ با موفقیت روی پنل بازیابی شد", "ok")
    return {"ok": True, "links_count": len(LINKS), "subs_count": len(SUBS), "nodes_count": len(NODES)}
    

# ── Stats ─────────────────────────────────────────────────────────────────────
@app.get("/stats")
async def get_stats(_=Depends(require_auth)):
    async with LINKS_LOCK:
        snap = dict(LINKS)
    return {
        "active_connections": len(connections),
        "total_traffic_mb": round(stats["total_bytes"] / (1024 ** 2), 2),
        "total_requests": stats["total_requests"],
        "total_errors": stats["total_errors"],
        "uptime": uptime(),
        "timestamp": datetime.now().isoformat(),
        "hourly": _hourly_traffic_public_view(),
        "recent_errors": list(error_logs)[-10:],
        "links_count": len(snap),
        "active_links": sum(1 for l in snap.values() if is_link_allowed(l)),
        "expired_links": sum(1 for l in snap.values() if is_link_expired(l)),
        "subs_count": len(SUBS),
    }

@app.get("/api/bot-tcp-proxy/domains")
async def api_bot_tcp_proxy_domains(_=Depends(require_auth)):
    return {"domains": bottokentcpproxy.get_known_domains()}

@app.post("/api/bot-tcp-proxy/start")
async def api_bot_tcp_proxy_start(request: Request, _=Depends(require_auth)):
    body = await request.json()
    token = str(body.get("token", "")).strip()
    # هر لینک MTProto پورت جدای خودش رو داره (per-instance)، پس پورت باید
    # از ورودی کاربر/فرانت (لینکی که TCP Proxy براش ساخته می‌شه) بیاد.
    uid = str(body.get("uuid") or "").strip()
    port = body.get("port")
    if port is None and uid:
        async with LINKS_LOCK:
            link = LINKS.get(uid)
            port = link.get("mtproto_port") if link else None
    if port is None:
        raise HTTPException(status_code=400, detail="پورت (یا uuid لینک) مشخص نشده")
    port = int(port)
    reachable_domains = body.get("reachable_domains") or []
    force = bool(body.get("force"))
    try:
        bottokentcpproxy.start_job(token, port, reachable_domains=reachable_domains, force=force)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    log_activity("system", "جست‌وجوی TCP Proxy آغاز شد", "info")
    return {"ok": True}

@app.post("/api/mtproto/fix-proxy")
async def api_mtproto_fix_proxy(request: Request, _=Depends(require_auth)):
    """راه مستقیم برای درست‌کردن لینک‌های MTProto بدون TCP Proxy:
    توکن Railway رو (اگه فرستاده بشه) ذخیره می‌کنه و بعد برای همه‌ی لینک‌های
    MTProto که هنوز TCP Proxy عمومی ندارن، یکی می‌سازه — بدون نیاز به طی‌کردن
    کل فرآیند جست‌وجوی دامنه."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    token = str(body.get("token", "")).strip()
    if token:
        bottokentcpproxy.save_token(token)

    if not bottokentcpproxy.has_saved_token():
        raise HTTPException(status_code=400, detail="توکن Railway ذخیره نشده — آن را در همین درخواست بفرستید")

    async with LINKS_LOCK:
        targets = [
            (uid, d.get("mtproto_port"), d.get("label", ""))
            for uid, d in LINKS.items()
            if d.get("protocol") == "mtproto" and not d.get("mtproto_public_host")
        ]

    fixed, failed = [], []
    for uid, port, label in targets:
        if not port:
            failed.append({"uuid": uid, "label": label, "error": "پورت داخلی ندارد (instance اجرا نشده)"})
            continue
        try:
            pub = await bottokentcpproxy.create_public_proxy_for_port(int(port))
        except Exception as exc:
            failed.append({"uuid": uid, "label": label, "error": str(exc)})
            continue
        async with LINKS_LOCK:
            if uid in LINKS:
                LINKS[uid]["mtproto_public_host"] = pub["domain"]
                LINKS[uid]["mtproto_public_port"] = pub["port"]
                LINKS[uid]["mtproto_proxy_id"] = pub["id"]
                LINKS[uid]["mtproto_public_pending"] = False
        fixed.append({
            "uuid": uid, "label": label,
            "host": pub["domain"], "port": pub["port"],
            "link": generate_share_link(uid, get_host(), remark=f"EMIX-{label}", protocol="mtproto"),
        })
        log_activity("link", f"TCP Proxy عمومی «{label}» ساخته شد ({pub['domain']}:{pub['port']})", "ok")

    asyncio.create_task(save_state())
    return {"ok": True, "fixed": fixed, "failed": failed}


@app.get("/api/mtproto/{uid}/stats")
async def api_mtproto_stats(uid: str, _=Depends(require_auth)):
    """آمار خام خود باینری mtproto-proxy برای این لینک.
    اگه total_special_connections صفر بمونه حتی بعد از تلاش برای اتصال، یعنی
    هیچ پکتی به پروسه نمی‌رسه (مشکل مسیر شبکه/TCP Proxy). اگه بالا بره ولی
    اتصال برقرار نشه، یعنی پکت می‌رسه و مشکل در handshake/سکرت است."""
    async with LINKS_LOCK:
        if uid not in LINKS:
            raise HTTPException(status_code=404, detail="link not found")
    return await mtproto.get_stats(uid)


@app.post("/api/zeus-proxy/create")
async def api_zeus_proxy_create(request: Request, _=Depends(require_auth)):
    """ساخت پروکسی Zeus با پشتیبانی از محدودیت حجم، انقضا و اتصال per IP."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    token = str(body.get("token", "")).strip()
    # ── کانفیگ‌های اختیاری ──
    traffic_limit_gb = body.get("traffic_limit_gb")
    expires_days = body.get("expires_days")
    max_connections_per_ip = body.get("max_connections_per_ip")
    try:
        result = await zeussocks5.create_zeus_proxy(
            token or None,
            traffic_limit_gb=float(traffic_limit_gb) if traffic_limit_gb is not None else None,
            expires_days=int(expires_days) if expires_days is not None else None,
            max_connections_per_ip=int(max_connections_per_ip) if max_connections_per_ip is not None else None,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ساخت پروکسی Zeus ناموفق بود: {exc}")
    log_activity("system", f"پروکسی Zeus ساخته شد ({result['domain']}:{result['public_port']})", "ok")
    return {"ok": True, **result}

@app.get("/api/zeus-proxy/status")
async def api_zeus_proxy_status(_=Depends(require_auth)):
    return zeussocks5.get_zeus_status()

@app.post("/api/zeus-proxy/delete")
async def api_zeus_proxy_delete(_=Depends(require_auth)):
    await zeussocks5.delete_zeus_proxy()
    log_activity("system", "پروکسی Zeus حذف شد", "warn")
    return {"ok": True}

@app.post("/api/zeus-proxy/config")
async def api_zeus_proxy_config(request: Request, _=Depends(require_auth)):
    """تغییر کانفیگ‌های پروکسی Zeus (حجم/انقضا/اتصال per IP) بدون ری‌استارت."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    traffic_limit_gb = body.get("traffic_limit_gb")
    expires_days = body.get("expires_days")
    max_connections_per_ip = body.get("max_connections_per_ip")
    cfg = zeussocks5.update_zeus_config(
        traffic_limit_gb=float(traffic_limit_gb) if traffic_limit_gb is not None else None,
        expires_days=int(expires_days) if expires_days is not None else None,
        max_connections_per_ip=int(max_connections_per_ip) if max_connections_per_ip is not None else None,
    )
    log_activity("system", f"کانفیگ پروکسی Zeus آپدیت شد", "ok")
    return {"ok": True, "config": cfg}
@app.post("/api/bot-tcp-proxy/stop")
async def api_bot_tcp_proxy_stop(_=Depends(require_auth)):
    stopped = bottokentcpproxy.stop_job()
    if stopped:
        log_activity("system", "جست‌وجوی TCP Proxy متوقف شد", "warn")
    return {"ok": True, "stopped": stopped}

@app.get("/api/bot-tcp-proxy/status")
async def api_bot_tcp_proxy_status(_=Depends(require_auth)):
    return bottokentcpproxy.get_status()

@app.post("/api/bot-tcp-proxy/attach")
async def api_bot_tcp_proxy_attach(request: Request, _=Depends(require_auth)):
    """وقتی جست‌وجو یک دامنه‌ی سالم پیدا کرد (phase=='done')، این دامنه/پورت به‌عنوان
    TCP Proxy عمومیِ همون لینک MTProto مشخص‌شده (با uuid) ثبت می‌شود. اگر uuid
    داده نشده باشه و هیچ لینک MTProtoای وجود نداشته باشه، یکی پیش‌فرض ساخته می‌شود."""
    status = bottokentcpproxy.get_status()
    chosen = status.get("result")
    if status.get("phase") != "done" or not chosen:
        raise HTTPException(status_code=409, detail="هنوز نتیجه‌ای برای ساخت پروکسی آماده نیست")

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    label = str(body.get("label") or "").strip() or f"TCP-{chosen['domain'].split('.')[0]}"
    uid = str(body.get("uuid") or "").strip() or None

    attached_link = None
    if not uid:
        async with LINKS_LOCK:
            existing = next((u for u, d in LINKS.items() if d.get("protocol") == "mtproto"), None)
        uid = existing

    if not uid:
        uid = generate_uuid()
        secret = mtproto.generate_secret()
        link_data = {
            "label": label, "limit_bytes": 0, "used_bytes": 0,
            "created_at": datetime.now().isoformat(),
            "alpn": "h2,http/1.1", "fingerprint": "chrome", "active": True,
            "expires_at": None, "note": "", "is_default": False, "sub_id": None,
            "protocol": "mtproto", "ad_tag": None, "mtproto_secret": secret,
        }
        async with LINKS_LOCK:
            LINKS[uid] = link_data
        try:
            inst = await mtproto.start_instance(uid, secret=secret, ad_tag=None)
        except Exception as exc:
            logger.error(f"راه‌اندازی mtproto ناموفق بود: {exc}")
            raise HTTPException(status_code=502, detail=f"راه‌اندازی MTProto ناموفق بود: {exc}")
        _supervise_mtproto_instance(uid)  # audit fix: supervise post-boot instances
        async with LINKS_LOCK:
            LINKS[uid]["mtproto_port"] = inst["port"]
            LINKS[uid]["mtproto_secret"] = inst["secret"]
        attached_link = {"uuid": uid, "label": label}

    old_proxy_id = None
    async with LINKS_LOCK:
        link = LINKS.get(uid)
        if link is None:
            raise HTTPException(status_code=404, detail="لینک پیدا نشد")
        old_proxy_id = link.get("mtproto_proxy_id")
        link["mtproto_public_host"] = chosen["domain"]
        link["mtproto_public_port"] = chosen["port"]
        link["mtproto_proxy_id"] = chosen["id"]
        link["mtproto_public_pending"] = False
        cur_label = link.get("label", label)

    if old_proxy_id and old_proxy_id != chosen["id"]:
        asyncio.create_task(bottokentcpproxy.delete_public_proxy(old_proxy_id))

    asyncio.create_task(save_state())
    host = get_host()
    share_link = generate_share_link(uid, host, remark=f"EMIX-{cur_label}", protocol="mtproto")
    if not attached_link:
        attached_link = {"uuid": uid, "label": cur_label}
    log_activity(
        "link",
        f"TCP Proxy عمومی «{cur_label}» با دامنه‌ی {chosen['domain']}:{chosen['port']} تنظیم شد",
        "ok",
    )
    return {
        "ok": True,
        "result": chosen,
        "attached_link": attached_link,
        "share_link": share_link,
    }


@app.post("/api/domain-gen/start")
async def api_domain_gen_start(request: Request, _=Depends(require_auth)):
    body = await request.json()
    token = str(body.get("token", "")).strip()
    port = int(body.get("port") or CONFIG["port"])
    count = int(body.get("count") or 10)
    try:
        botgeneratedomin.start_job(token, port, target_count=count)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    log_activity("system", f"ساخت {count} دامنه آغاز شد", "info")
    return {"ok": True}

@app.post("/api/domain-gen/stop")
async def api_domain_gen_stop(_=Depends(require_auth)):
    stopped = botgeneratedomin.stop_job()
    if stopped:
        log_activity("system", "ساخت دامنه متوقف شد", "warn")
    return {"ok": True, "stopped": stopped}

@app.get("/api/domain-gen/status")
async def api_domain_gen_status(_=Depends(require_auth)):
    return botgeneratedomin.get_status()

# ── Activity Logs ─────────────────────────────────────────────────────────────
@app.get("/api/activity")
async def get_activity(_=Depends(require_auth)):
    return {"logs": list(activity_logs)[-150:]}

# ── Live connections (with IP) ────────────────────────────────────────────────
@app.get("/api/connections")
async def get_connections(_=Depends(require_auth)):
    async with LINKS_LOCK:
        snap = dict(LINKS)
    grouped: dict[str, dict] = {}
    for conn_id, c in connections.items():
        ip = c.get("ip", "نامشخص")
        link = snap.get(c.get("uuid"))
        label = link.get("label") if link else "نامشخص"
        g = grouped.get(ip)
        if g is None:
            g = {
                "ip": ip,
                "sessions": 0,
                "bytes": 0,
                "labels": set(),
                "transports": set(),
                "first_connected_at": c.get("connected_at"),
                "last_connected_at": c.get("connected_at"),
            }
            grouped[ip] = g
        g["sessions"] += 1
        g["bytes"] += c.get("bytes", 0)
        g["labels"].add(label)
        g["transports"].add(c.get("transport", "vless-ws"))
        ca = c.get("connected_at")
        if ca:
            if not g["first_connected_at"] or ca < g["first_connected_at"]:
                g["first_connected_at"] = ca
            if not g["last_connected_at"] or ca > g["last_connected_at"]:
                g["last_connected_at"] = ca
    for uid, link in snap.items():
        if link.get("protocol") == "mtproto":
            label = link.get("label", "نامشخص")
            for c in mtproto.get_instance_connections(uid):
                ip = c["ip"]
                g = grouped.get(ip)
                if g is None:
                    g = {
                        "ip": ip, "sessions": 0, "bytes": 0,
                        "labels": set(), "transports": set(),
                        "first_connected_at": None, "last_connected_at": None,
                    }
                    grouped[ip] = g
                g["sessions"] += 1
                g["labels"].add(label)
                g["transports"].add("mtproto")
    result = []
    for ip, g in grouped.items():
        result.append({
            "ip": ip,
            "sessions": g["sessions"],
            "labels": sorted(g["labels"]),
            "label": " · ".join(sorted(g["labels"])) if g["labels"] else "نامشخص",
            "transports": sorted(g["transports"]),
            "bytes": g["bytes"],
            "bytes_fmt": fmt_bytes(g["bytes"]),
            "connected_at": g["first_connected_at"],
            "last_connected_at": g["last_connected_at"],
        })
    result.sort(key=lambda x: x.get("last_connected_at") or "", reverse=True)
    return {
        "connections": result,
        "count": len(result),
        "raw_count": len(connections),
    }

# ── Link Management ───────────────────────────────────────────────────────────
# ── Idempotency-Key store (Phase 37.15) ────────────────────────────────────
# Bounded in-memory map: key → (uid, expires_at). 10-minute TTL, max 500
# entries (oldest evicted). Prevents duplicate configs from network retries.
_IDEMPOTENCY_TTL = 600.0
_IDEMPOTENCY_MAX = 500
_idempotency_map: dict = {}


def _idempotency_lookup(key: str):
    entry = _idempotency_map.get(key)
    if not entry:
        return None
    uid, exp = entry
    if time.time() > exp:
        _idempotency_map.pop(key, None)
        return None
    return uid


def _idempotency_store(key: str, uid: str) -> None:
    if not key or not uid:
        return
    if len(_idempotency_map) >= _IDEMPOTENCY_MAX:
        now = time.time()
        stale = [k for k, (_, exp) in _idempotency_map.items() if now > exp]
        for k in stale:
            _idempotency_map.pop(k, None)
        if len(_idempotency_map) >= _IDEMPOTENCY_MAX:
            _idempotency_map.pop(next(iter(_idempotency_map)))
    _idempotency_map[key] = (uid, time.time() + _IDEMPOTENCY_TTL)


async def _create_link_core(body: dict) -> dict:
    label = (body.get("label") or "لینک جدید").strip()[:60]
    try:
        lv = float(body.get("limit_value") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="limit_value باید عدد باشد")
    lu = body.get("limit_unit") or "GB"
    try:
        limit_bytes = 0 if lv <= 0 else parse_size_to_bytes(lv, lu)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"limit نامعتبر: {exc}")
    exp_days = int(body.get("expires_days") or 0)
    expires_at = (datetime.now() + timedelta(days=exp_days)).isoformat() if exp_days > 0 else None
    note = (body.get("note") or "").strip()[:200]
    sub_id = body.get("sub_id") or None
    protocol = body.get("protocol") or DEFAULT_PROTOCOL
    # [Phase 3 — Config Compiler contract] strict validation, NO silent
    # coercion to the default. Unknown/incompatible protocols get a 400
    # with an actionable message (previously they silently became vless-ws).
    _compat_check = compat.validate_fused(protocol)
    if not _compat_check.ok:
        raise HTTPException(
            status_code=400,
            detail=f"پروتکل نامعتبر: {'; '.join(_compat_check.reasons)} — پروتکل‌های معتبر: {', '.join(PROTOCOLS)}",
        )

    alpn_val = str(body.get("alpn") or "h2,http/1.1").strip()[:60]
    fp_val = str(body.get("fingerprint") or "chrome").strip()[:20]
    if fp_val not in ("chrome", "firefox", "ios"):
        fp_val = "chrome"

    # ── SNI Spoofing (per-link, opt-in, zero breaking changes) ──────────
    # Default: spoof_sni=None, spoof_sni_enabled=False → effective SNI = host
    # (identical to behavior before this feature was introduced).
    # MTProto + HTTP-Proxy skip SNI spoofing entirely (handled in generate_share_link).
    spoof_raw = (body.get("spoof_sni") or "").strip() if isinstance(body.get("spoof_sni"), str) else ""
    spoof_enabled = bool(body.get("spoof_sni_enabled", False))
    spoof_sni = None
    if spoof_enabled and spoof_raw:
        spoof_sni = _validate_sni(spoof_raw)
        if not spoof_sni:
            raise HTTPException(status_code=400, detail="دامنه‌ی SNI نامعتبر است (باید hostname معتبر، غیر IP، غیر localhost باشد)")
    # If user enabled but didn't provide a valid domain, silently disable
    spoof_enabled = spoof_enabled and bool(spoof_sni)

    # ── Endpoint & Transport Profile (Phase 25 — successor of SNI Spoofing) ──
    # New API: a link may reference a NAMED endpoint profile, strictly
    # validated (existence + protocol compatibility). Legacy spoof_sni
    # fields above keep working unchanged for existing clients.
    endpoint_profile_id = (body.get("endpoint_profile_id") or "").strip() or None
    if endpoint_profile_id:
        profile = await endpoint_profiles.get_profile(endpoint_profile_id)
        if profile is None:
            raise HTTPException(status_code=400, detail=f"پروفایل اندپوینت «{endpoint_profile_id}» وجود ندارد")
        ep_errors = endpoint_profiles.validate_profile_for_protocol(profile, protocol)
        if ep_errors:
            raise HTTPException(status_code=400, detail="; ".join(ep_errors))

    uid = generate_uuid()
    link_data = {
        "label": label,
        "limit_bytes": limit_bytes,
        "used_bytes": 0,
        "created_at": datetime.now().isoformat(),
        "alpn": alpn_val,
        "fingerprint": fp_val,
        "active": True,
        "expires_at": expires_at,
        "note": note,
        "is_default": False,
        "sub_id": sub_id,
        "protocol": protocol,
        "ad_tag": None,
        "spoof_sni": spoof_sni,
        "spoof_sni_enabled": spoof_enabled,
        # Phase 25: endpoint profile reference (None = legacy fields/standard)
        "endpoint_profile_id": endpoint_profile_id,
        # Phase 37.11: config lifecycle — born CREATED, never born HEALTHY
        "lifecycle_state": "CREATED",
        "lifecycle_reason": "compiled + stored, awaiting first probe",
    }

    if protocol == "mtproto":
        raw_port = body.get("mtproto_port")
        manual_port = int(raw_port) if raw_port not in (None, "", 0, "0") else None
        if manual_port is not None and not (1 <= manual_port <= 65535):
            raise HTTPException(status_code=400, detail="شماره پورت نامعتبر است")
        raw_domain = (body.get("mtproto_domain") or "").strip()
        domain = mtproto.sanitize_domain(raw_domain)
        try:
            inst = await mtproto.start_instance(
                uid,
                domain=domain,
                preferred_port=manual_port,
                force_port=manual_port is not None,
                ad_tag=None,
            )
        except RuntimeError as exc:
            logger.error(f"راه‌اندازی MTProto ناموفق برای {uid[:8]}: {exc}")
            raise HTTPException(status_code=409, detail=str(exc))
        except Exception as exc:
            logger.error(f"راه‌اندازی MTProto ناموفق برای {uid[:8]}: {exc}")
            raise HTTPException(status_code=502, detail=f"راه‌اندازی MTProto ناموفق: {exc}")
        link_data["mtproto_port"] = inst["port"]
        link_data["mtproto_secret"] = inst["secret"]
        link_data["mtproto_domain"] = inst["domain"]
        link_data["mtproto_manual_port"] = manual_port is not None
        _supervise_mtproto_instance(uid)  # audit fix: supervise post-boot instances

        # ── آدرس عمومی دستی ──────────────────────────────────────────────────
        # اگه کاربر TCP Proxy رو خودش از داشبورد Railway ساخته باشه، دامنه و پورت
        # عمومیش رو مستقیم اینجا وارد می‌کنه (مثل proxy.rlwy.net:12345). در این
        # حالت اصلاً سراغ ساخت خودکار/توکن نمی‌ریم.
        pub_host = (body.get("mtproto_public_host") or "").strip()
        raw_pub_port = body.get("mtproto_public_port")
        try:
            pub_port = int(raw_pub_port) if raw_pub_port not in (None, "", 0, "0") else None
        except (TypeError, ValueError):
            pub_port = None
        if pub_host and pub_port:
            link_data["mtproto_public_host"] = pub_host
            link_data["mtproto_public_port"] = pub_port
            link_data["mtproto_public_pending"] = False
        elif bottokentcpproxy.has_saved_token():
            link_data["mtproto_public_pending"] = True
            asyncio.create_task(_attach_mtproto_public_proxy(uid, inst["port"], label))
        else:
            # بدون توکن Railway هیچ TCP Proxy عمومی ساخته نمی‌شه، یعنی این لینک
            # از بیرون اصلاً قابل دسترس نیست. قبلاً این حالت بی‌صدا رد می‌شد و
            # کاربر یه لینک ظاهراً سالم ولی کاملاً مرده می‌گرفت.
            link_data["mtproto_public_pending"] = False
            logger.error(
                f"MTProto[{uid[:8]}]: توکن Railway ذخیره نشده — TCP Proxy عمومی ساخته نشد "
                f"و این لینک از بیرون قابل استفاده نیست. ابتدا از مودال «Bot TCP Proxy» "
                f"توکن Railway را وارد کنید."
            )
            log_activity(
                "link",
                f"«{label}» ساخته شد ولی TCP Proxy ندارد (توکن Railway ذخیره نشده) — لینک کار نمی‌کند",
                "err",
            )

    if protocol == "shadowsocks":
        ss_cipher = body.get("ss_cipher") or DEFAULT_CIPHER
        if ss_cipher not in CIPHERS:
            ss_cipher = DEFAULT_CIPHER
        link_data["ss_cipher"] = ss_cipher
        link_data["ss_password"] = secrets.token_urlsafe(16)
    
    async with LINKS_LOCK:
        LINKS[uid] = link_data

    if sub_id:
        async with SUBS_LOCK:
            if sub_id in SUBS:
                ids = SUBS[sub_id].setdefault("link_ids", [])
                if uid not in ids:
                    ids.append(uid)

    asyncio.create_task(save_state())
    log_activity("link", f"کانفیگ «{label}» ساخته شد", "ok")

    # [Phase 7 — per-config real testing] A fresh config is born UNKNOWN and
    # immediately gets a real protocol-level probe (non-blocking). The result
    # lands on link_data["health"] — a config is NEVER "healthy" merely
    # because it was generated.
    # Phase 38+ race fix: the born-UNKNOWN record exists SYNCHRONOUSLY so
    # /api/health/links/{uid} never 404s while the initial probe is in flight.
    network_health.ensure_record(uid, link_data)
    async def _probe_new_link():
        try:
            await network_health.probe_config(uid, link_data)
        except Exception as _exc:
            try:
                await diagnostics_mod.record_error(
                    code="HEALTH_PROBE_FAIL",
                    message=f"initial probe failed: {type(_exc).__name__}: {str(_exc)[:120]}",
                    component="health",
                    severity="WARNING",
                    context={"protocol": protocol},
                )
            except Exception:
                pass
    asyncio.create_task(_probe_new_link())

    host = get_host()
    return {
        "uuid": uid,
        **LINKS[uid],
        "expired": False,
        "vless_link": generate_share_link(uid, host, remark=f"EMIX-{label}", protocol=protocol),
        "sub_url": f"https://{host}/sub/{uid}",
    }

@app.post("/api/links")
async def create_link(request: Request, _=Depends(require_auth)):
    body = await request.json()
    # Phase 37.15 idempotency: a retried POST (network timeout / double-click
    # with the same client key) returns the ORIGINAL config instead of a
    # duplicate. Keys live in memory with a 10-minute TTL and are bounded.
    idem_key = (request.headers.get("Idempotency-Key") or "").strip()[:128]
    if idem_key:
        existing_uid = _idempotency_lookup(idem_key)
        if existing_uid is not None:
            async with LINKS_LOCK:
                link = LINKS.get(existing_uid)
            if link is not None:
                host = get_host()
                return {
                    "uuid": existing_uid,
                    **link,
                    "expired": False,
                    "idempotent_replay": True,
                    "vless_link": generate_share_link(existing_uid, host,
                                                       remark=f"EMIX-{link.get('label','EMIX')}",
                                                       protocol=link.get("protocol", DEFAULT_PROTOCOL)),
                    "sub_url": f"https://{host}/sub/{existing_uid}",
                }
        result = await _create_link_core(body)
        _idempotency_store(idem_key, result.get("uuid", ""))
        return result
    return await _create_link_core(body)

@app.post("/api/node/links")
async def node_create_link(request: Request, key_id: str = Depends(require_node_key)):
    await _require_node_manage(key_id)
    body = await request.json()
    # sub_id در اینجا به گروهِ محلیِ همین نود اشاره دارد (نه پنل مرکزی)؛ اگر معتبر نباشد نادیده گرفته می‌شود
    return await _create_link_core(body)

@app.get("/api/links")
async def list_links(_=Depends(require_auth)):
    host = get_host()
    async with LINKS_LOCK:
        snap = dict(LINKS)
    result = []
    for uid, d in snap.items():
        proto = d.get("protocol", DEFAULT_PROTOCOL)
        extra = {}
        if proto == "mtproto":
            # هر لینک MTProto حالا instance/پورت/TCP-Proxy مستقل خودش رو داره
            extra = {
                "mtproto_public_host": d.get("mtproto_public_host"),
                "mtproto_public_port": d.get("mtproto_public_port"),
                "mtproto_public_pending": bool(
                    d.get("mtproto_public_pending")
                    or (not d.get("mtproto_manual_port") and bottokentcpproxy.has_saved_token()
                        and not d.get("mtproto_public_host"))
                ),
            }
        result.append({
            "uuid": uid,
            **d,
            **extra,
            "protocol": proto,
            "expired": is_link_expired(d),
            # SNI spoofing: expose the effective SNI used in generated share-links
            # so the dashboard can show what the client will actually receive.
            "spoof_sni": d.get("spoof_sni"),
            "spoof_sni_enabled": bool(d.get("spoof_sni_enabled", False)),
            "effective_sni": _get_effective_sni(d, host),
            # CDN routing status — tells the dashboard whether SNI spoofing
            # will actually work (requires CDN domain) or will fallback to
            # panel host (safe but no disguise)
            "cdn_domain": os.environ.get("EMIX_CDN_DOMAIN", "").strip().lower() or None,
            "sni_spoof_active": bool(
                d.get("spoof_sni_enabled")
                and _validate_sni(d.get("spoof_sni"))
                and os.environ.get("EMIX_CDN_DOMAIN", "").strip()
            ),
            "vless_link": generate_share_link(uid, host, remark=f"EMIX-{d['label']}", protocol=proto),
            "sub_url": f"https://{host}/sub/{uid}",
        })
    result.sort(key=lambda x: x["created_at"], reverse=True)
    return {"links": result}

@app.patch("/api/links/{uid}")
async def update_link(uid: str, request: Request, _=Depends(require_auth)):
    body = await request.json()
    mtproto_action = None
    new_sub = "UNCHANGED"

    async with LINKS_LOCK:
        if uid not in LINKS:
            raise HTTPException(status_code=404, detail="link not found")
        link = LINKS[uid]
        old_sub = link.get("sub_id")
        label = link.get("label")

        if "active" in body:
            new_active = bool(body["active"])
            changed = new_active != link.get("active", True)
            link["active"] = new_active
            log_activity("link", f"کانفیگ «{label}» {'فعال' if new_active else 'غیرفعال'} شد", "ok" if new_active else "warn")
            if changed and link.get("protocol") == "mtproto":
                mtproto_action = ("start" if new_active else "stop", dict(link))

        if "label" in body:
            link["label"] = str(body["label"])[:60]
        # ── ویرایش دستی آدرس عمومی MTProto ────────────────────────────────────
        # برای وقتی که TCP Proxy رو خودت از داشبورد Railway ساختی و می‌خوای
        # دامنه/پورت عمومیش رو روی یک لینک موجود ست کنی، بدون ساخت دوباره.
        if "mtproto_public_host" in body:
            ph = (body.get("mtproto_public_host") or "").strip()
            link["mtproto_public_host"] = ph or None
        if "mtproto_public_port" in body:
            raw_pp = body.get("mtproto_public_port")
            try:
                link["mtproto_public_port"] = (
                    int(raw_pp) if raw_pp not in (None, "", 0, "0") else None
                )
            except (TypeError, ValueError):
                link["mtproto_public_port"] = None
        if link.get("mtproto_public_host") and link.get("mtproto_public_port"):
            link["mtproto_public_pending"] = False
        if "note" in body:
            link["note"] = str(body["note"])[:200]
        if "reset_usage" in body and body["reset_usage"]:
            link["used_bytes"] = 0
            log_activity("link", f"مصرف کانفیگ «{label}» ریست شد", "info")
        if "limit_value" in body:
            try:
                lv = float(body.get("limit_value") or 0)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="limit_value باید عدد باشد")
            lu = body.get("limit_unit") or "GB"
            try:
                link["limit_bytes"] = 0 if lv <= 0 else parse_size_to_bytes(lv, lu)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail=f"limit نامعتبر: {exc}")
        if "expires_days" in body:
            ed = int(body["expires_days"] or 0)
            link["expires_at"] = (datetime.now() + timedelta(days=ed)).isoformat() if ed > 0 else None
        if "alpn" in body:
            alpn_val = str(body["alpn"]).strip()[:60]
            if alpn_val:
                link["alpn"] = alpn_val
        if "fingerprint" in body:
            fp_val = str(body["fingerprint"]).strip()
            link["fingerprint"] = fp_val if fp_val in ("chrome", "firefox", "ios") else "chrome"
        # ── SNI Spoofing (per-link, opt-in) ──────────────────────────────────
        # PATCH semantics:
        #   - "spoof_sni": update the spoof domain (validated; None if invalid)
        #   - "spoof_sni_enabled": toggle on/off; if enabling but spoof_sni is
        #     None/invalid, reject with 400 (admin must set a valid domain first)
        # Default behavior preserved when fields absent from PATCH body.
        if "spoof_sni" in body:
            new_spoof = _validate_sni(body.get("spoof_sni"))
            link["spoof_sni"] = new_spoof
            # If spoof_sni was just cleared and the link is currently enabled, disable
            if not new_spoof and link.get("spoof_sni_enabled"):
                link["spoof_sni_enabled"] = False
        if "spoof_sni_enabled" in body:
            want_enabled = bool(body.get("spoof_sni_enabled"))
            if want_enabled and not link.get("spoof_sni"):
                raise HTTPException(status_code=400, detail="ابتدا یک دامنه‌ی SNI معتبر وارد کنید")
            link["spoof_sni_enabled"] = want_enabled
        if any(k in body for k in ("label", "note", "limit_value", "expires_days", "alpn", "fingerprint", "spoof_sni", "spoof_sni_enabled")):
            log_activity("link", f"کانفیگ «{link['label']}» ویرایش شد", "info")
        new_sub = body.get("sub_id", "UNCHANGED")
        if new_sub != "UNCHANGED":
            link["sub_id"] = new_sub or None

    if new_sub != "UNCHANGED":
        async with SUBS_LOCK:
            if old_sub and old_sub in SUBS:
                ids = SUBS[old_sub].get("link_ids", [])
                if uid in ids:
                    ids.remove(uid)
            if new_sub and new_sub in SUBS:
                ids = SUBS[new_sub].setdefault("link_ids", [])
                if uid not in ids:
                    ids.append(uid)

    if mtproto_action:
        action, snap = mtproto_action
        if action == "stop":
            await mtproto.stop_instance(uid)
        else:
            try:
                old_port = snap.get("mtproto_port")
                inst = await mtproto.start_instance(
                    uid,
                    secret=snap.get("mtproto_secret"),
                    domain=snap.get("mtproto_domain", mtproto.DEFAULT_FAKE_TLS_DOMAIN),
                    preferred_port=snap.get("mtproto_port"),
                    force_port=snap.get("mtproto_manual_port", False),
                    ad_tag=snap.get("ad_tag"),
                )
                async with LINKS_LOCK:
                    if uid in LINKS:
                        LINKS[uid]["mtproto_port"] = inst["port"]
                        LINKS[uid]["mtproto_secret"] = inst["secret"]
                _supervise_mtproto_instance(uid)  # audit fix: supervise post-boot instances
                if (snap.get("mtproto_proxy_id") and inst["port"] != old_port
                        and not snap.get("mtproto_manual_port", False)):
                    asyncio.create_task(_reattach_mtproto_public_proxy(
                        uid, inst["port"], snap.get("mtproto_proxy_id"), snap.get("label", "")
                    ))
            except Exception as exc:
                logger.error(f"روشن کردن MTProto ناموفق برای {uid[:8]}: {exc}")
                async with LINKS_LOCK:
                    if uid in LINKS:
                        LINKS[uid]["active"] = False
                log_activity("link", f"روشن کردن پروکسی تلگرام «{label}» ناموفق بود", "err")
                asyncio.create_task(save_state())
                raise HTTPException(status_code=502, detail=f"روشن کردن پروکسی تلگرام ناموفق بود: {exc}")

    asyncio.create_task(save_state())
    return {"ok": True}
    
# ===== Endpoint جدید برای به‌روزرسانی ad_tag =====
@app.patch("/api/links/{uid}/ad-tag")
async def update_ad_tag(uid: str, request: Request, _=Depends(require_auth)):
    body = await request.json()
    ad_tag = str(body.get("ad_tag", "")).strip()
    if not ad_tag:
        raise HTTPException(status_code=400, detail="ad_tag نمی‌تواند خالی باشد")

    async with LINKS_LOCK:
        if uid not in LINKS:
            raise HTTPException(status_code=404, detail="link not found")
        link = LINKS[uid]
        if link.get("protocol") != "mtproto":
            raise HTTPException(status_code=400, detail="این کانفیگ MTProto نیست")
        link["ad_tag_status"] = "pending"   # ← جدید

    asyncio.create_task(_update_mtproto_ad_tag(uid, ad_tag))
    log_activity("link", f"درخواست به‌روزرسانی ad_tag برای «{link.get('label','')}» ثبت شد", "info")
    return {"ok": True, "message": "ad_tag در حال اعمال است، پروکسی ری‌استارت می‌شود"}


# اندپوینت جدید برای پول کردن وضعیت
@app.get("/api/links/{uid}/ad-tag/status")
async def get_ad_tag_status(uid: str, _=Depends(require_auth)):
    async with LINKS_LOCK:
        link = LINKS.get(uid)
        if not link:
            raise HTTPException(status_code=404, detail="link not found")
        return {
            "status": link.get("ad_tag_status", "idle"),
            "link": link.get("ad_tag_link"),
            "ad_tag": link.get("ad_tag"),
        }

@app.delete("/api/links/{uid}")
async def delete_link(uid: str, _=Depends(require_auth)):
    async with LINKS_LOCK:
        if uid not in LINKS:
            raise HTTPException(status_code=404, detail="link not found")
        label = LINKS[uid].get("label", uid)
        sub_id = LINKS[uid].get("sub_id")
        proto = LINKS[uid].get("protocol")
        proxy_id = LINKS[uid].get("mtproto_proxy_id")
        del LINKS[uid]
    if proto == "mtproto":
        await mtproto.stop_instance(uid)
        if proxy_id:
            asyncio.create_task(bottokentcpproxy.delete_public_proxy(proxy_id))
    if sub_id:
        async with SUBS_LOCK:
            if sub_id in SUBS:
                ids = SUBS[sub_id].get("link_ids", [])
                if uid in ids:
                    ids.remove(uid)
    asyncio.create_task(save_state())
    log_activity("link", f"کانفیگ «{label}» حذف شد", "err")
    return {"ok": True, "deleted": uid}

# ══════════════════════════════════════════════════════════════════════════════
# Node linking — inbound (این پنل صادرکننده‌ی کلید است)
# احراز هویت این بخش با هدر X-RVG-Node-Key انجام می‌شود، نه کوکی سشن.
# ══════════════════════════════════════════════════════════════════════════════
def _parse_parts(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {p.strip() for p in raw.split(",") if p.strip() in NODE_SHARE_PARTS}


@app.post("/api/node/handshake")
async def node_handshake(request: Request, key_id: str = Depends(require_node_key)):
    try:
        body = await request.json()
    except Exception:
        body = {}
    async with NODE_KEYS_LOCK:
        pw_hash = (NODE_KEYS.get(key_id) or {}).get("password_hash")
    if pw_hash:
        given = str(body.get("password") or "")
        if not given:
            raise HTTPException(status_code=401, detail="PASSWORD_REQUIRED")
        if hash_password(given) != pw_hash:
            raise HTTPException(status_code=401, detail="PASSWORD_INVALID")
    peer_host = str(body.get("host") or "").strip()[:120] or client_ip(request)
    async with NODE_KEYS_LOCK:
        entry = NODE_KEYS.get(key_id)
        if entry is not None:
            first_time = not entry.get("peer_host")
            entry["peer_host"] = peer_host
            label = entry.get("label") or key_id[:8]
        else:
            first_time, label = False, key_id[:8]
    if first_time:
        log_activity("node", f"پنل «{peer_host}» با کلید «{label}» متصل شد", "ok")
    async with LINKS_LOCK:
        links_count = len(LINKS)
    async with SUBS_LOCK:
        subs_count = len(SUBS)
    return {
        "ok": True,
        "host": get_host(),
        "version": get_current_version(),
        "links_count": links_count,
        "subs_count": subs_count,
    }


@app.get("/api/node/snapshot")
async def node_snapshot(request: Request, _key_id: str = Depends(require_node_key)):
    """فقط بخش‌هایی که هم درخواست شده و هم برای این کلید مجاز است برگردانده می‌شود."""
    parts = _parse_parts(request.query_params.get("parts"))
    async with NODE_KEYS_LOCK:
        entry = NODE_KEYS.get(_key_id) or {}
        allowed = {p for p in NODE_SHARE_PARTS if (entry.get("share") or {}).get(p, p != "logs")}
    parts &= allowed
    out: dict = {"host": get_host(), "version": get_current_version(), "parts": sorted(parts)}
    if "links" in parts:
        out["links"] = (await list_links(None))["links"]
    if "subs" in parts:
        out["subs"] = (await list_subs(None))["subs"]
    if "logs" in parts:
        out["logs"] = (await get_activity(None))["logs"][-60:]
    if parts & {"usage", "requests"}:
        s = await get_stats(None)
        stats_out = {
            "uptime": s["uptime"],
            "links_count": s["links_count"],
            "active_links": s["active_links"],
            "subs_count": s["subs_count"],
        }
        if "usage" in parts:
            stats_out["total_bytes"] = stats["total_bytes"]
            stats_out["total_traffic_mb"] = s["total_traffic_mb"]
            stats_out["hourly"] = s["hourly"]
            stats_out["active_connections"] = s["active_connections"]
        if "requests" in parts:
            stats_out["total_requests"] = s["total_requests"]
            stats_out["total_errors"] = s["total_errors"]
        out["stats"] = stats_out
    return out


async def _require_node_manage(key_id: str) -> str:
    async with NODE_KEYS_LOCK:
        entry = NODE_KEYS.get(key_id) or {}
        peer = entry.get("peer_host") or "نود"
        allowed = bool(entry.get("can_manage", False))
    if not allowed:
        raise HTTPException(status_code=403, detail="این کلید اجازه‌ی ویرایش/حذف کانفیگ را ندارد")
    return peer


@app.patch("/api/node/links/{uid}")
async def node_update_link(uid: str, request: Request, key_id: str = Depends(require_node_key)):
    peer = await _require_node_manage(key_id)
    result = await update_link(uid, request, None)
    log_activity("node", f"کانفیگ {uid[:8]} از راه دور توسط «{peer}» ویرایش شد", "warn")
    return result


@app.delete("/api/node/links/{uid}")
async def node_delete_link(uid: str, key_id: str = Depends(require_node_key)):
    peer = await _require_node_manage(key_id)
    result = await delete_link(uid, None)
    log_activity("node", f"کانفیگ {uid[:8]} از راه دور توسط «{peer}» حذف شد", "err")
    return result

# ══════════════════════════════════════════════════════════════════════════════
# Node linking — outbound (این پنل به نودهای دیگر وصل می‌شود)
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/nodes/keys")
async def list_node_keys(_=Depends(require_auth)):
    host = get_host()
    async with NODE_KEYS_LOCK:
        snap = dict(NODE_KEYS)
    out = []
    for key_id, e in snap.items():
        out.append({
            "key_id": key_id,
            "label": e.get("label", ""),
            "key": build_node_key(e.get("issued_host") or host, e.get("secret", "")),
            "created_at": e.get("created_at"),
            "revoked": bool(e.get("revoked")),
            "share": {p: bool((e.get("share") or {}).get(p, p != "logs")) for p in NODE_SHARE_PARTS},
            "can_manage": bool(e.get("can_manage", False)),
            "has_password": e.get("password_hash") is not None,
            "last_used_at": e.get("last_used_at"),
            "peer_host": e.get("peer_host"),
            "use_count": int(e.get("use_count", 0)),
        })
    out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return {"keys": out, "host": host}


def _node_key_share(body_share) -> dict:
    """دسترسی‌های خواندن هر کلید؛ پیش‌فرض مثل خروجی نود: همه فعال جز لاگ‌ها."""
    src = body_share if isinstance(body_share, dict) else {}
    return {p: bool(src.get(p, p != "logs")) for p in NODE_SHARE_PARTS}


@app.post("/api/nodes/keys")
async def create_node_key(request: Request, _=Depends(require_auth)):
    try:
        body = await request.json()
    except Exception:
        body = {}
    label = (str(body.get("label") or "").strip() or f"کلید {len(NODE_KEYS) + 1}")[:60]
    share = _node_key_share(body.get("share"))
    can_manage = bool(body.get("can_manage", False))
    password = str(body.get("password") or "").strip()
    host = get_host()
    key_id = generate_uuid()
    secret = secrets.token_urlsafe(24)
    async with NODE_KEYS_LOCK:
        NODE_KEYS[key_id] = {
            "label": label,
            "secret": secret,
            "issued_host": host,
            "created_at": datetime.now().isoformat(),
            "revoked": False,
            "share": share,
            "can_manage": can_manage,
            "password_hash": hash_password(password) if password else None,
            "last_used_at": None,
            "peer_host": None,
            "use_count": 0,
        }
    asyncio.create_task(save_state())
    log_activity("node", f"کلید نود «{label}» ساخته شد", "ok")
    return {
        "ok": True, "key_id": key_id, "label": label,
        "key": build_node_key(host, secret), "share": share, "can_manage": can_manage,
    }


@app.patch("/api/nodes/keys/{key_id}")
async def update_node_key(key_id: str, request: Request, _=Depends(require_auth)):
    try:
        body = await request.json()
    except Exception:
        body = {}
    async with NODE_KEYS_LOCK:
        entry = NODE_KEYS.get(key_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="key not found")
        if "label" in body:
            entry["label"] = (str(body.get("label") or "").strip() or entry["label"])[:60]
        if "share" in body:
            cur = entry.get("share") or {}
            src = body.get("share") if isinstance(body.get("share"), dict) else {}
            entry["share"] = {p: bool(src.get(p, cur.get(p, p != "logs"))) for p in NODE_SHARE_PARTS}
        if "can_manage" in body:
            entry["can_manage"] = bool(body.get("can_manage"))
        if "password" in body:
            pw = str(body.get("password") or "").strip()
            entry["password_hash"] = hash_password(pw) if pw else None
        if "enabled" in body:
            entry["revoked"] = not bool(body.get("enabled"))
        label = entry.get("label", key_id[:8])
        revoked = entry["revoked"]
    asyncio.create_task(save_state())
    log_activity("node", f"کلید نود «{label}» {'غیرفعال شد' if revoked else 'به‌روزرسانی شد'}",
                 "warn" if revoked else "ok")
    return {"ok": True, "key_id": key_id}


@app.delete("/api/nodes/keys/{key_id}")
async def revoke_node_key(key_id: str, _=Depends(require_auth)):
    async with NODE_KEYS_LOCK:
        entry = NODE_KEYS.get(key_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="key not found")
        label = entry.get("label", key_id[:8])
        del NODE_KEYS[key_id]
    asyncio.create_task(save_state())
    log_activity("node", f"کلید نود «{label}» حذف شد", "warn")
    return {"ok": True, "revoked": key_id}


@app.get("/api/nodes/health")
async def nodes_health(_=Depends(require_auth)):
    """Phase 4.10 — circuit breaker status for all nodes."""
    from node_health import get_breaker
    return {"nodes": get_breaker().all_status()}


@app.get("/api/nodes/aggregate")
async def nodes_aggregate(request: Request, _=Depends(require_auth)):
    fresh = request.query_params.get("fresh") in ("1", "true", "yes")
    async with NODES_LOCK:
        snap = {nid: dict(n) for nid, n in NODES.items()}
    targets = [(nid, n) for nid, n in snap.items() if n.get("enabled", True)]
    results = await asyncio.gather(
        *(_fetch_node_snapshot(nid, n, fresh=fresh) for nid, n in targets),
        return_exceptions=True,
    )

    nodes_out: list[dict] = []
    for (nid, n), res in zip(targets, results):
        base = _node_public(nid, n)
        if isinstance(res, Exception):
            base.update({"online": False, "error": str(res)[:200]})
        else:
            base.update(res)
        nodes_out.append(base)
    for nid, n in snap.items():
        if not n.get("enabled", True):
            nodes_out.append({**_node_public(nid, n), "online": False, "error": None, "disabled": True})

    local = await get_stats(None)
    async with LINKS_LOCK:
        local_used = sum(l.get("used_bytes", 0) for l in LINKS.values())
    totals = {
        "local_used_bytes": local_used,
        "local_requests": local["total_requests"],
        "local_links": local["links_count"],
        "local_active_links": local["active_links"],
        "local_subs": local["subs_count"],
        "local_connections": local["active_connections"],
        "node_used_bytes": 0, "node_requests": 0, "node_links": 0,
        "node_active_links": 0, "node_subs": 0, "node_connections": 0,
        "nodes_total": len(snap), "nodes_online": 0,
    }
    for n in nodes_out:
        if not n.get("online"):
            continue
        totals["nodes_online"] += 1
        share = n.get("share") or {}
        st = n.get("stats") or {}
        if share.get("usage"):
            totals["node_used_bytes"] += int(st.get("total_bytes") or 0)
            totals["node_connections"] += int(st.get("active_connections") or 0)
        if share.get("requests"):
            totals["node_requests"] += int(st.get("total_requests") or 0)
        if share.get("links"):
            links = n.get("links") or []
            totals["node_links"] += len(links)
            totals["node_active_links"] += sum(1 for l in links if l.get("active") and not l.get("expired"))
        if share.get("subs"):
            totals["node_subs"] += len(n.get("subs") or [])
    totals["used_bytes"] = totals["local_used_bytes"] + totals["node_used_bytes"]
    totals["used_fmt"] = fmt_bytes(totals["used_bytes"])
    totals["node_used_fmt"] = fmt_bytes(totals["node_used_bytes"])
    totals["requests"] = totals["local_requests"] + totals["node_requests"]
    totals["links"] = totals["local_links"] + totals["node_links"]
    totals["active_links"] = totals["local_active_links"] + totals["node_active_links"]
    totals["subs"] = totals["local_subs"] + totals["node_subs"]
    totals["connections"] = totals["local_connections"] + totals["node_connections"]
    return {"nodes": nodes_out, "totals": totals}


async def _fetch_node_snapshot(node_id: str, node: dict, *, fresh: bool = False) -> dict:
    """اسنپ‌شات یک نود را با کش کوتاه‌مدت می‌گیرد. فقط بخش‌های تیک‌خورده منتقل می‌شوند.

    Phase 4.10 — wrapped in the node circuit breaker. If the breaker for this
    node is OPEN, the call short-circuits immediately (no network call) and
    returns an "offline" snapshot without blocking for the full timeout.
    """
    share = node.get("share") or {}
    parts = sorted(p for p in NODE_SHARE_PARTS if share.get(p))
    cache_key = f"{node_id}|{','.join(parts)}"
    cached = _NODE_CACHE.get(cache_key)
    if not fresh and cached and (time.time() - cached["at"]) < NODE_CACHE_TTL:
        return cached["data"]
    if not parts:
        return {"online": True, "error": None, "stats": {}, "links": [], "subs": [], "logs": []}

    # Phase 4.10 — check breaker state before making the network call
    try:
        from node_health import get_breaker, NodeUnavailableError
        breaker = get_breaker()
        from config_layer import CONFIG as _EMIX_CFG

        async def _do_request():
            r = await _node_request(node, "GET", "/api/node/snapshot", params={"parts": ",".join(parts)})
            if r.status_code == 401:
                raise RuntimeError("کلید نود روی پنل مقابل ابطال شده است")
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            return r.json()

        try:
            payload = await breaker.call(
                node_id,
                _do_request,
                timeout=_EMIX_CFG.node_request_timeout_seconds,
            )
        except NodeUnavailableError as exc:
            # Circuit OPEN — short-circuit, no network call
            msg = f"circuit open: {exc}"[:200]
            async with NODES_LOCK:
                if node_id in NODES:
                    NODES[node_id]["last_error"] = msg
            return {"online": False, "error": msg, "stats": {}, "links": [], "subs": [], "logs": []}
    except Exception as exc:
        msg = str(exc)[:200] or exc.__class__.__name__
        async with NODES_LOCK:
            if node_id in NODES:
                NODES[node_id]["last_error"] = msg
        return {"online": False, "error": msg, "stats": {}, "links": [], "subs": [], "logs": []}

    now_iso = datetime.now().isoformat()
    async with NODES_LOCK:
        if node_id in NODES:
            NODES[node_id]["last_sync_at"] = now_iso
            NODES[node_id]["last_error"] = None
            NODES[node_id]["peer_version"] = payload.get("version")
    data = {
        "online": True,
        "error": None,
        "last_sync_at": now_iso,
        "peer_version": payload.get("version"),
        "stats": payload.get("stats") or {},
        "links": payload.get("links") or [],
        "subs": payload.get("subs") or [],
        "logs": payload.get("logs") or [],
    }
    _NODE_CACHE[cache_key] = {"at": time.time(), "data": data}
    asyncio.create_task(schedule_save())
    return data


@app.get("/api/nodes")
async def list_nodes(_=Depends(require_auth)):
    async with NODES_LOCK:
        snap = {nid: dict(n) for nid, n in NODES.items()}
    out = [_node_public(nid, n) for nid, n in snap.items()]
    out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return {"nodes": out, "count": len(out)}


@app.post("/api/nodes/connect")
async def connect_node(request: Request, _=Depends(require_auth)):
    body = await request.json()
    key = str(body.get("key") or "").strip()
    try:
        host, _secret = parse_node_key(key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if host == get_host():
        raise HTTPException(status_code=400, detail="این کلید مربوط به همین پنل است")
    async with NODES_LOCK:
        for nid, n in NODES.items():
            if n.get("host") == host:
                raise HTTPException(status_code=409, detail=f"این پنل قبلاً به‌عنوان «{n.get('label')}» متصل شده است")

    node_password = str(body.get("password") or "").strip()
    candidate = {"host": host, "key": key}
    try:
        r = await _node_request(candidate, "POST", "/api/node/handshake",
                                json_body={"host": get_host(), "version": get_current_version(),
                                           "password": node_password})
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"اتصال به {host} برقرار نشد: {str(exc)[:160]}")
    if r.status_code == 401:
        detail = ""
        try:
            detail = r.json().get("detail") or ""
        except Exception:
            pass
        if detail == "PASSWORD_REQUIRED":
            raise HTTPException(status_code=401, detail="این نود رمز دارد؛ رمز را وارد کنید")
        if detail == "PASSWORD_INVALID":
            raise HTTPException(status_code=401, detail="رمز نود اشتباه است")
        raise HTTPException(status_code=401, detail="کلید توسط پنل مقابل پذیرفته نشد (ابطال‌شده یا نامعتبر)")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"پاسخ نامعتبر از {host}: HTTP {r.status_code}")
    info = r.json()

    label = (str(body.get("label") or "").strip() or info.get("host") or host)[:60]
    node_id = generate_uuid()
    node = _normalize_node({
        "label": label, "host": host, "key": key,
        "peer_version": info.get("version"),
        "last_sync_at": datetime.now().isoformat(),
    })
    async with NODES_LOCK:
        NODES[node_id] = node
    _NODE_CACHE.clear()
    asyncio.create_task(save_state())
    log_activity("node", f"به نود «{label}» ({host}) متصل شد", "ok")
    return {"ok": True, "node": _node_public(node_id, node), "peer": info}


@app.patch("/api/nodes/{node_id}")
async def update_node(node_id: str, request: Request, _=Depends(require_auth)):
    body = await request.json()
    async with NODES_LOCK:
        node = NODES.get(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        if "label" in body:
            node["label"] = (str(body["label"]).strip() or node["host"])[:60]
        if "enabled" in body:
            node["enabled"] = bool(body["enabled"])
        if "merge_dashboard" in body:
            node["merge_dashboard"] = bool(body["merge_dashboard"])
        share = body.get("share")
        if isinstance(share, dict):
            for p in NODE_SHARE_PARTS:
                if p in share:
                    node["share"][p] = bool(share[p])
        snap = dict(node)
    _NODE_CACHE.clear()
    asyncio.create_task(save_state())
    return {"ok": True, "node": _node_public(node_id, snap)}


@app.delete("/api/nodes/{node_id}")
async def disconnect_node(node_id: str, _=Depends(require_auth)):
    async with NODES_LOCK:
        node = NODES.pop(node_id, None)
    if node is None:
        raise HTTPException(status_code=404, detail="node not found")
    _NODE_CACHE.clear()
    asyncio.create_task(save_state())
    log_activity("node", f"اتصال نود «{node.get('label')}» قطع شد", "warn")
    return {"ok": True, "disconnected": node_id}


async def _proxy_node_link_write(node_id: str, uid: str, method: str,
                                 json_body: dict | None = None) -> dict:
    async with NODES_LOCK:
        node = NODES.get(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        snap = dict(node)
    try:
        r = await _node_request(snap, method, f"/api/node/links/{uid}", json_body=json_body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"نود پاسخ نداد: {str(exc)[:160]}")
    if r.status_code >= 400:
        detail = f"HTTP {r.status_code}"
        try:
            detail = r.json().get("detail") or detail
        except Exception:
            pass
        raise HTTPException(status_code=r.status_code, detail=detail)
    _NODE_CACHE.clear()
    return r.json() if r.content else {"ok": True}


@app.post("/api/nodes/{node_id}/subs")
async def proxy_node_create_sub(node_id: str, request: Request, _=Depends(require_auth)):
    body = await request.json()
    async with NODES_LOCK:
        node = NODES.get(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        snap = dict(node)
    try:
        r = await _node_request(snap, "POST", "/api/node/subs", json_body=body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"نود پاسخ نداد: {str(exc)[:160]}")
    if r.status_code >= 400:
        detail = f"HTTP {r.status_code}"
        try:
            detail = r.json().get("detail") or detail
        except Exception:
            pass
        raise HTTPException(status_code=r.status_code, detail=detail)
    _NODE_CACHE.clear()
    return r.json()


async def _proxy_node_sub_write(node_id: str, sub_id: str, method: str,
                                 json_body: dict | None = None) -> dict:
    async with NODES_LOCK:
        node = NODES.get(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        snap = dict(node)
    try:
        r = await _node_request(snap, method, f"/api/node/subs/{sub_id}", json_body=json_body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"نود پاسخ نداد: {str(exc)[:160]}")
    if r.status_code >= 400:
        detail = f"HTTP {r.status_code}"
        try:
            detail = r.json().get("detail") or detail
        except Exception:
            pass
        raise HTTPException(status_code=r.status_code, detail=detail)
    _NODE_CACHE.clear()
    return r.json() if r.content else {"ok": True}


@app.patch("/api/nodes/{node_id}/subs/{sub_id}")
async def proxy_node_update_sub(node_id: str, sub_id: str, request: Request, _=Depends(require_auth)):
    body = await request.json()
    return await _proxy_node_sub_write(node_id, sub_id, "PATCH", json_body=body)


@app.delete("/api/nodes/{node_id}/subs/{sub_id}")
async def proxy_node_delete_sub(node_id: str, sub_id: str, _=Depends(require_auth)):
    return await _proxy_node_sub_write(node_id, sub_id, "DELETE")


@app.post("/api/nodes/{node_id}/subs/{sub_id}/links")
async def proxy_node_assign_link_to_sub(node_id: str, sub_id: str, request: Request, _=Depends(require_auth)):
    body = await request.json()
    async with NODES_LOCK:
        node = NODES.get(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        snap = dict(node)
    try:
        r = await _node_request(snap, "POST", f"/api/node/subs/{sub_id}/links", json_body=body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"نود پاسخ نداد: {str(exc)[:160]}")
    if r.status_code >= 400:
        detail = f"HTTP {r.status_code}"
        try:
            detail = r.json().get("detail") or detail
        except Exception:
            pass
        raise HTTPException(status_code=r.status_code, detail=detail)
    _NODE_CACHE.clear()
    return r.json() if r.content else {"ok": True}


@app.post("/api/nodes/{node_id}/links")
async def proxy_node_create_link(node_id: str, request: Request, _=Depends(require_auth)):
    body = await request.json()
    async with NODES_LOCK:
        node = NODES.get(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        snap = dict(node)
    try:
        r = await _node_request(snap, "POST", "/api/node/links", json_body=body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"نود پاسخ نداد: {str(exc)[:160]}")
    if r.status_code >= 400:
        detail = f"HTTP {r.status_code}"
        try:
            detail = r.json().get("detail") or detail
        except Exception:
            pass
        raise HTTPException(status_code=r.status_code, detail=detail)
    _NODE_CACHE.clear()
    return r.json()


@app.patch("/api/nodes/{node_id}/links/{uid}")
async def proxy_node_update_link(node_id: str, uid: str, request: Request, _=Depends(require_auth)):
    body = await request.json()
    return await _proxy_node_link_write(node_id, uid, "PATCH", json_body=body)


@app.delete("/api/nodes/{node_id}/links/{uid}")
async def proxy_node_delete_link(node_id: str, uid: str, _=Depends(require_auth)):
    return await _proxy_node_link_write(node_id, uid, "DELETE")

# ══════════════════════════════════════════════════════════════════════════════
# VLESS Relay
# ══════════════════════════════════════════════════════════════════════════════
from protocol.vless.vless import (
    RELAY_BUF,
    parse_vless_header,
    check_and_use,
    relay_ws_to_tcp,
    relay_tcp_to_ws,
)
from protocol.vless.websocket import websocket_tunnel

from protocol.trojan.websocket import trojan_ws_tunnel

app.add_api_websocket_route("/ws/{uuid}", websocket_tunnel)
app.add_api_websocket_route("/trojan-ws", trojan_ws_tunnel)
from protocol.shadowsocks.shadowsocks import generate_ss_link, derive_key, CIPHERS, DEFAULT_CIPHER
from protocol.shadowsocks.websocket import shadowsocks_ws_tunnel
app.add_api_websocket_route("/ss-ws", shadowsocks_ws_tunnel)

# ══════════════════════════════════════════════════════════════════════════════
# XHTTP
# ══════════════════════════════════════════════════════════════════════════════
# نکته: مطابق نسخه‌ی مرجع (xhttp_siz10.py) مود stream-one حذف شده؛ فقط
# packet-up و stream-up فعال هستن. روترهای stream-one دیگه include نمی‌شن.
from protocol.vless.xhttpstreamon import router as xhttp_downlink_router
from protocol.vless.xhttpstreamup import router as xhttp_streamup_router
from protocol.vless.xhttshadpacketup import router as xhttp_packetup_router
app.include_router(xhttp_downlink_router)
app.include_router(xhttp_streamup_router)
app.include_router(xhttp_packetup_router)

from protocol.trojan.xhttpstreamon import router as trojan_xhttp_downlink_router
from protocol.trojan.xhttpstreamup import router as trojan_xhttp_streamup_router
from protocol.trojan.xhttshadpacketup import router as trojan_xhttp_packetup_router
app.include_router(trojan_xhttp_downlink_router)
app.include_router(trojan_xhttp_streamup_router)
app.include_router(trojan_xhttp_packetup_router)

# ── HTTP Proxy (Phase 7.14 — SSRF protection + sensitive header filter) ───────
# Hop-by-hop headers per RFC 7230 §6.1 — must not be forwarded.
_HOP = {"connection","keep-alive","proxy-authenticate","proxy-authorization",
        "te","trailers","transfer-encoding","upgrade","content-encoding","content-length"}

# Sensitive client headers that must NEVER be forwarded to the proxied target
# (could leak credentials, session, or panel-internal routing info).
_SENSITIVE = {
    "cookie", "authorization", "proxy-authorization",
    "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto",
    "x-real-ip", "x-forwarded-port", "x-forwarded-server", "forwarded",
}

# Allowlist of headers safe to forward. Anything not here is dropped.
_PROXY_ALLOWED_HEADERS = {
    "user-agent", "accept", "accept-encoding", "accept-language",
    "content-type", "content-disposition", "range", "if-modified-since",
    "if-none-match", "cache-control", "pragma", "expires",
}

# Internal/private IPv4 ranges to block (SSRF protection)
import ipaddress as _ipaddress
_PRIVATE_NETWORKS = [
    _ipaddress.ip_network("127.0.0.0/8"),       # loopback
    _ipaddress.ip_network("10.0.0.0/8"),        # private class A
    _ipaddress.ip_network("172.16.0.0/12"),    # private class B
    _ipaddress.ip_network("192.168.0.0/16"),   # private class C
    _ipaddress.ip_network("169.254.0.0/16"),   # link-local (incl. AWS metadata 169.254.169.254)
    _ipaddress.ip_network("0.0.0.0/8"),        # "this network"
    _ipaddress.ip_network("100.64.0.0/10"),    # CGNAT
    _ipaddress.ip_network("::1/128"),          # IPv6 loopback
    _ipaddress.ip_network("fc00::/7"),         # IPv6 unique-local
    _ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]


def _is_ssrf_target(host: str) -> bool:
    """Return True if the resolved host is a private/internal/loopback IP.
    Resolves DNS once via socket.getaddrinfo — protects against DNS rebinding
    for the initial request. Redirects are revalidated because we set
    follow_redirects=False below and walk the redirect chain manually."""
    import socket
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True  # unresolvable → block
    for family, _, _, _, sockaddr in infos:
        try:
            ip = _ipaddress.ip_address(sockaddr[0])
            for net in _PRIVATE_NETWORKS:
                if ip in net:
                    return True
        except ValueError:
            continue
    return False


def _validate_proxy_url(url: str) -> str:
    """Validate a proxy target URL. Raises HTTPException on SSRF or invalid URL."""
    from urllib.parse import urlparse
    if not url:
        raise HTTPException(status_code=400, detail="missing target URL")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="invalid target URL (no host)")
    # Block internal hostnames by string match (defense in depth, before DNS)
    host_lower = parsed.hostname.lower().rstrip(".")
    blocked_hosts = {"localhost", "ip6-localhost", "metadata.google.internal"}
    if host_lower in blocked_hosts:
        raise HTTPException(status_code=403, detail="target host not allowed")
    if host_lower.endswith(".internal") or host_lower.endswith(".local"):
        raise HTTPException(status_code=403, detail="internal hostnames are not allowed")
    # Block private IPs unless explicitly allowed
    allow_private = _EMIX_RUNTIME_CFG.proxy_allow_private_targets
    if not allow_private and _is_ssrf_target(parsed.hostname):
        raise HTTPException(status_code=403, detail="target host is private/internal — set EMIX_PROXY_ALLOW_PRIVATE=1 to allow")
    return url


@app.api_route("/proxy/{target_url:path}", methods=["GET","POST","PUT","DELETE","PATCH","HEAD","OPTIONS"])
async def http_proxy(target_url: str, request: Request):
    """HTTP proxy with SSRF protection + sensitive header filtering.

    Per Phase 7.14:
      - Validates target URL (rejects loopback, private, link-local, metadata)
      - Re-resolves DNS at request time (mitigates DNS rebinding)
      - Redirects are revalidated (followed manually, each hop validated)
      - Only allowlisted request headers are forwarded
      - Hop-by-hop + sensitive headers stripped
    """
    # Step 1: validate the initial target URL
    target_url = _validate_proxy_url(target_url)
    try:
        body = await request.body()
    except Exception:
        body = b""
    # Step 2: build a sanitized header set
    in_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() in _PROXY_ALLOWED_HEADERS
    }
    # Step 3: fetch without auto-redirect (we validate each redirect hop)
    try:
        max_redirects = 5
        current_url = target_url
        resp = None
        for _ in range(max_redirects + 1):
            resp = await http_client.request(
                method=request.method,
                url=current_url,
                headers=in_headers,
                content=body if request.method in ("POST","PUT","PATCH") else None,
                follow_redirects=False,  # we validate each redirect hop manually
            )
            if resp.is_redirect and resp.headers.get("location"):
                next_url = resp.headers["location"]
                # Resolve relative redirects against the current URL
                from urllib.parse import urljoin
                next_url = urljoin(current_url, next_url)
                # Revalidate the redirect target
                current_url = _validate_proxy_url(next_url)
                continue
            break
        # Step 4: filter response headers
        out_headers = {k: v for k, v in resp.headers.items() if k.lower() not in _HOP and k.lower() not in _SENSITIVE}
        stats["total_bytes"] += len(resp.content)
        stats["total_requests"] += 1
        hourly_traffic[_hourly_traffic_key()] += len(resp.content)
        return Response(content=resp.content, status_code=resp.status_code, headers=out_headers)
    except HTTPException:
        raise  # SSRF/validation errors pass through
    except Exception as exc:
        stats["total_errors"] += 1
        error_logs.append({"error": str(exc), "url": target_url, "time": datetime.now().isoformat()})
        raise HTTPException(status_code=502, detail=f"Proxy error: {exc}")

# ── Public sub page ───────────────────────────────────────────────────────────
@app.get("/p/{uuid_key}", response_class=HTMLResponse)
async def public_sub_page(uuid_key: str, request: Request):
    from pages import get_public_page_html
    async with SUBS_LOCK:
        sub = next(({"sub_id": sid, **s} for sid, s in SUBS.items() if s.get("uuid_key") == uuid_key), None)
    if not sub:
        return HTMLResponse("<h2 style='font-family:sans-serif;padding:40px'>گروه پیدا نشد</h2>", status_code=404)
    return HTMLResponse(content=get_public_page_html(uuid_key))



@app.get("/api/public/sub/{uuid_key}")
async def public_sub_data(uuid_key: str, request: Request):
    # ۱. احراز هویت و دریافت داده‌ها (همان منطق قبلی شما)
    async with SUBS_LOCK:
        sub_entry = next(((sid, s) for sid, s in SUBS.items() if s.get("uuid_key") == uuid_key), None)
    if not sub_entry:
        raise HTTPException(status_code=404, detail="not found")
    sub_id, sub = sub_entry

    has_pw = sub.get("password_hash") is not None
    if has_pw:
        pw = request.query_params.get("pw", "")
        if hash_password(pw) != sub["password_hash"]:
            return JSONResponse({"locked": True, "name": sub["name"]})

    host = get_host()
    link_ids = sub.get("link_ids", [])
    node_link_ids = sub.get("node_link_ids", [])
    async with LINKS_LOCK:
        snap = dict(LINKS)

    links_out = []
    active_conns = 0
    
    # ۲. ساخت لیست کانفیگ‌ها
    for lid in link_ids:
        link = snap.get(lid)
        if not link: continue
        allowed = is_link_allowed(link)
        conn_count = sum(1 for c in connections.values() if c.get("uuid") == lid)
        active_conns += conn_count
        proto = link.get("protocol", DEFAULT_PROTOCOL)
        links_out.append({
            "uuid": lid,
            "label": link["label"],
            "active": allowed,
            "protocol": proto,
            "used_bytes": link.get("used_bytes", 0),
            "limit_bytes": link.get("limit_bytes", 0),
            "vless_link": generate_share_link(lid, host, remark=f"EMIX-{link['label']}", protocol=proto),
        })

    # ۲.۵ کانفیگ‌های نودهای دیگر
    if node_link_ids:
        async with NODES_LOCK:
            nodes_snap = {nid: dict(n) for nid, n in NODES.items()}
        needed_nodes = list({ref.split("::", 1)[0] for ref in node_link_ids if "::" in ref})
        needed_nodes = [nid for nid in needed_nodes if nid in nodes_snap]
        snapshots = await asyncio.gather(
            *(_fetch_node_snapshot(nid, nodes_snap[nid], fresh=True) for nid in needed_nodes),
            return_exceptions=True,
        )
        snap_by_node = dict(zip(needed_nodes, snapshots))
        for ref in node_link_ids:
            if "::" not in ref:
                continue
            nid, uid = ref.split("::", 1)
            node_snap = snap_by_node.get(nid)
            if not node_snap or isinstance(node_snap, Exception):
                continue
            node_link = next((l for l in (node_snap.get("links") or []) if l.get("uuid") == uid), None)
            if not node_link or not node_link.get("vless_link"):
                continue
            lb = node_link.get("limit_bytes", 0)
            allowed = bool(node_link.get("active", True)) and not node_link.get("expired") and not (lb > 0 and node_link.get("used_bytes", 0) >= lb)
            links_out.append({
                "uuid": nid + "::" + uid,
                "label": node_link.get("label", uid),
                "active": allowed,
                "protocol": node_link.get("protocol", DEFAULT_PROTOCOL),
                "used_bytes": node_link.get("used_bytes", 0),
                "limit_bytes": node_link.get("limit_bytes", 0),
                "vless_link": node_link["vless_link"],
            })

    # ۲.۶ کانفیگ‌های ایستا (foreign_links) — مثلاً کانفیگ‌های پنل مرکزی که روی
    # یک نود اضافه شده‌اند؛ چون این نود به پنل مرکزی دسترسی برگشتی ندارد،
    # این کانفیگ‌ها به‌صورت اسنپ‌شات (لینک آماده) ذخیره و همینجا نمایش داده می‌شوند.
    for fl in sub.get("foreign_links", []):
        vl = fl.get("vless_link")
        if not vl:
            continue
        links_out.append({
            "uuid": fl.get("key") or vl,
            "label": fl.get("label", "کانفیگ"),
            "active": True,
            "protocol": fl.get("protocol", DEFAULT_PROTOCOL),
            "used_bytes": fl.get("used_bytes", 0),
            "limit_bytes": 0,
            "vless_link": vl,
        })

    # ۳. تشخیص کلاینت یا مرورگر
    user_agent = request.headers.get("User-Agent", "").lower()
    is_client = any(ua in user_agent for ua in ["v2rayng", "v2rayn", "shadowrocket", "clash", "surfboard", "nekoray"])

    if is_client:
        # اگر کلاینت است: فقط لینک‌های فعال را به صورت Base64 برگردان
        raw_links = "\n".join([l["vless_link"] for l in links_out if l["active"]])
        encoded_data = base64.b64encode(raw_links.encode("utf-8")).decode("utf-8")
        return Response(content=encoded_data, media_type="text/plain")

    # ۴. اگر مرورگر است: دیتای کامل JSON را برگردان
    return {
        "locked": False,
        "name": f"پنل: {sub['name']}",
        "desc": sub.get("desc", ""),
        "sub_url": f"https://{host}/sub-group/{uuid_key}",
        "active_connections": active_conns,
        "links": links_out, # اینجا همان لیست کامل شماست
    }

# ══════════════════════════════════════════════════════════════════════════════
# Version / Auto-Update
# ══════════════════════════════════════════════════════════════════════════════
from updater import (
    get_current_version, get_current_version_info,
    get_latest_version_info, perform_update,
    update_log, update_state, load_update_history,
    REPO, BRANCH, is_newer_version, UPDATES_DISABLED,
)

@app.get("/api/version")
async def api_version(_=Depends(require_auth)):
    current_info = get_current_version_info()
    latest_info = await get_latest_version_info()
    latest_ver = latest_info.get("version")
    update_available = is_newer_version(latest_ver, current_info["version"]) if latest_ver else False
    return {
        "repo": REPO,
        "branch": BRANCH,
        "current": current_info,
        "latest": latest_info,
        "update_available": update_available,
    }


@app.get("/api/health")
async def api_health(_=Depends(require_auth)):
    """Phase 17 — structured internal health. NO secrets logged.

    Returned shape:
      {
        "app":          version, uptime, state counts
        "persistence":  data_dir writability, last_save info
        "protocols":    per-protocol active connection count
        "nodes":        per-node circuit breaker state
        "mtproto":      instance count
      }

    Never includes: passwords, hashes, UUIDs of links, tokens, cookies.
    """
    from node_health import get_breaker
    # Count active connections per protocol
    by_proto: dict[str, int] = defaultdict(int)
    for c in connections.values():
        proto = c.get("transport") or "unknown"
        by_proto[proto] += 1
    # Persistence health
    try:
        data_dir_writable = bool(DATA_DIR.exists() and os.access(str(DATA_DIR), os.W_OK))
    except Exception:
        data_dir_writable = False
    # MTProto instances
    try:
        mtproto_count = sum(1 for d in LINKS.values() if d.get("protocol") == "mtproto" and d.get("active", True))
    except Exception:
        mtproto_count = 0
    uptime_s = int(time.time() - stats["start_time"])
    h, m, s = uptime_s // 3600, (uptime_s % 3600) // 60, uptime_s % 60
    return {
        "app": {
            "version": EMIX_VERSION,
            "build_date": EMIX_BUILD_DATE,
            "uptime_seconds": uptime_s,
            "uptime_human": f"{h:02d}:{m:02d}:{s:02d}",
            "state_counts": {
                "links": len(LINKS),
                "subs": len(SUBS),
                "nodes": len(NODES),
                "node_keys": len(NODE_KEYS),
                "active_sessions": len(SESSIONS),
                "active_connections": len(connections),
            },
            "stats": {
                "total_bytes": stats["total_bytes"],
                "total_requests": stats["total_requests"],
                "total_errors": stats["total_errors"],
            },
        },
        "persistence": {
            "data_dir": str(DATA_DIR),
            "writable": data_dir_writable,
            "save_debounce_seconds": SAVE_DEBOUNCE_SECONDS,
        },
        "protocols": dict(by_proto),
        "nodes": {
            "count": len(NODES),
            "breakers": get_breaker().all_status(),
        },
        "mtproto": {
            "active_instances": mtproto_count,
        },
    }

@app.get("/api/update-history")
async def api_update_history(_=Depends(require_auth)):
    return {"history": load_update_history()}

@app.get("/api/update-log")
async def api_update_log(_=Depends(require_auth)):
    return {"running": update_state["running"], "progress": update_state["progress"], "logs": list(update_log)[-100:]}

@app.post("/api/update")
async def api_update(_=Depends(require_auth)):
    if UPDATES_DISABLED:
        raise HTTPException(status_code=403, detail="بروزرسانی در نسخه‌ی EMIX غیرفعال است تا طراحی سفارشی حفظ شود.")
    if update_state["running"]:
        raise HTTPException(status_code=409, detail="بروزرسانی در حال اجراست")
    update_log.append({"time": time.time(), "msg": "درخواست بروزرسانی ثبت شد، در صف اجرا..."})

    async def _run():
        ok = False
        try:
            ok = await perform_update()
        except Exception as exc:
            import traceback as tb
            update_log.append({"time": time.time(), "msg": f"❌ خطای بحرانی: {exc}"})
            update_log.append({"time": time.time(), "msg": tb.format_exc()[-800:]})
            update_state["running"] = False
        try:
            await save_state()
            log_activity("system", "بروزرسانی پنل " + ("موفق" if ok else "ناموفق") + " بود", "ok" if ok else "err")
        except Exception:
            pass
        if ok:
            update_log.append({"time": time.time(), "msg": "در حال راه‌اندازی مجدد پروسه (بدون خاموش‌شدن کانتینر)..."})
            await asyncio.sleep(1.5)
            try:
                os.execv(sys.executable, [sys.executable] + sys.argv)
            except Exception as exc:
                update_log.append({"time": time.time(), "msg": f"❌ execv شکست خورد: {exc} — fallback به exit"})
                os._exit(0)

    task = asyncio.create_task(_run())

    def _on_done(t: asyncio.Task):
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            update_log.append({"time": time.time(), "msg": f"❌ Task crash: {exc}"})
            update_state["running"] = False

    task.add_done_callback(_on_done)
    log_activity("system", "درخواست بروزرسانی پنل ثبت شد", "info")
    return {"ok": True, "started": True}

# ── Settings: توقف کامل لاگ‌گیری (برای بیشترین throughput ممکن) ─────────────────
@app.get("/api/settings/logging")
async def get_logging_setting(_=Depends(require_auth)):
    return {"disabled": bool(CONFIG.get("disable_logging"))}


@app.post("/api/settings/logging")
async def set_logging_setting(request: Request, _=Depends(require_auth)):
    body = await request.json()
    disabled = bool(body.get("disabled"))
    CONFIG["disable_logging"] = disabled
    apply_logging_state()
    await save_state()
    return {"ok": True, "disabled": disabled}


# ── HTML Pages ───────────────────────────────────────────────────────────────
from pages import LOGIN_HTML, DASHBOARD_HTML

# ── Central: Announcements & Support ─────────────────────────────────────────
@app.get("/api/announcements")
async def api_announcements(_=Depends(require_auth)):
    return {"announcements": await central.fetch_announcements()}

@app.post("/api/announcements/view")
async def api_announcements_view(request: Request, _=Depends(require_auth)):
    body = await request.json()
    ids = body.get("ids", [])
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="invalid ids")
    await central.report_announcement_views([str(i) for i in ids][:100])
    return {"ok": True}

@app.get("/api/support/messages")
async def api_support_messages(_=Depends(require_auth)):
    messages, blocked = await central.fetch_support_messages()
    return {"messages": messages, "blocked": blocked}

@app.post("/api/support/send")
async def api_support_send(request: Request, _=Depends(require_auth)):
    body = await request.json()
    msg = str(body.get("message", "")).strip()[:2000]
    if not msg:
        raise HTTPException(status_code=400, detail="پیام خالی است")
    result = await central.send_support_message(msg)
    if result.get("blocked"):
        raise HTTPException(status_code=403, detail="شما توسط پشتیبانی بلاک شده‌اید")
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error") or "ارتباط با سرور مرکزی برقرار نشد")
    return {"ok": True}

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if await is_valid_session(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse(url="/dashboard")
    return HTMLResponse(content=LOGIN_HTML)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not await is_valid_session(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse(url="/login")
    await ensure_default_link()
    return HTMLResponse(content=DASHBOARD_HTML)

@app.get("/test-ws", response_class=HTMLResponse)
async def test_ws_redirect():
    return HTMLResponse(content="<script>location.href='/dashboard'</script>")


# ══════════════════════════════════════════════════════════════════════════════
# ماژول سلامت و تست پینگ (کاملاً جدا از هسته — link_health.py)
# اگر این ماژول حذف شود، پنل و همه‌ی تونل‌ها بدون تغییر کار می‌کنند.
# ══════════════════════════════════════════════════════════════════════════════
import link_health
link_health.register_routes(app)

# ══════════════════════════════════════════════════════════════════════════════
# ماژول پل ایران — مصرف داخلی + شتاب‌دهی (کاملاً جدا از هسته — bridge_boost.py)
# اگر این ماژول حذف شود، پنل و همه‌ی تونل‌ها بدون تغییر کار می‌کنند.
# ══════════════════════════════════════════════════════════════════════════════
import bridge_boost
bridge_boost.register_routes(app)

# ══════════════════════════════════════════════════════════════════════════════
# ماژول توربو — لینک‌های 0-RTT + تست A/B خودکار (کاملاً جدا از هسته — turbo_boost.py)
# اگر این ماژول حذف شود، پنل و همه‌ی تونل‌ها بدون تغییر کار می‌کنند.
# ══════════════════════════════════════════════════════════════════════════════
import turbo_boost
turbo_boost.register_routes(app)

# ══════════════════════════════════════════════════════════════════════════════
# Assets سلف‌هاست (فونت/آیکون/Chart.js محلی) + GZip — static_assets.py
# ══════════════════════════════════════════════════════════════════════════════
import static_assets
static_assets.register(app)

# ══════════════════════════════════════════════════════════════════════════════
# ماژول آی‌پی‌های تمیز — اسکن لبه‌های اروان + لینک‌های IP-دار (clean_ip_boost.py)
# ══════════════════════════════════════════════════════════════════════════════
try:
    import clean_ip_boost
    clean_ip_boost.register_routes(app)
except Exception as _exc:
    logger.error(f"[bootstrap] clean_ip_boost بارگذاری نشد (نادیده گرفته شد): {_exc}")

# ══════════════════════════════════════════════════════════════════════════════
# ماژول تنظیمات حرفه‌ای ZEUS — ISP + TLS Mask + Smart Mode + Security (zeus_features.py)
# اگر این ماژول حذف شود یا خطا بدهد، پنل و همه‌ی تونل‌ها بدون تغییر کار می‌کنند.
# این try/except تضمین می‌کند که هیچ باگ در zeus_features.py نمی‌تواند پنل را
# خراب کند — ماژول کاملاً ایزوله است.
# ══════════════════════════════════════════════════════════════════════════════
try:
    import zeus_features
    zeus_features.register_routes(app)
except Exception as _exc:
    logger.error(f"[bootstrap] zeus_features بارگذاری نشد (نادیده گرفته شد): {_exc}")


# ═════════════════════════════════════════════════════════════════════════════
# ماژول مرکز گیمینگ — اسکنر IP کلادفلر + پریست بازی + کانفیگ tuned +
# مولتی‌لوکیشن از طریق Cloudflare Worker (gaming_boost.py)
# اگر این ماژول حذف شود یا خطا بدهد، پنل و همه‌ی تونل‌ها بدون تغییر کار می‌کنند.
# ═════════════════════════════════════════════════════════════════════════════
try:
    import gaming_boost
    gaming_boost.register_routes(app)
except Exception as _exc:
    logger.error(f"[bootstrap] gaming_boost بارگذاری نشد (نادیده گرفته شد): {_exc}")


# ═════════════════════════════════════════════════════════════════════════════
# ماژول پل چندلوکیشن v2 (multiloc.py) — Worker-Terminated Egress:
#   - اسکن coloهای کلادفلر با هندشیک TLS واقعی (/cdn-cgi/trace)
#   - SNI-Trace: اثبات زنده‌ی جعل SNI ( ingress ریلوی + لبه‌ی CF)
#   - لینک‌های پل دو حالته: خروج CF (وورکر v2 /vl) یا تونل /loc
#   - سینک UUIDها به وورکر + تست خروج واقعی (/egress-test)
# اگر این ماژول حذف شود یا خطا بدهد، پنل و همه‌ی تونل‌ها بدون تغییر کار می‌کنند.
# ═════════════════════════════════════════════════════════════════════════════
try:
    import multiloc
    multiloc.register_routes(app)
    logger.info(f"[bootstrap] multiloc v{multiloc.MULTILOC_VERSION} routes registered (multi-location bridge v2 + WTE)")
except Exception as _exc:
    logger.error(f"[bootstrap] multiloc بارگذاری نشد (نادیده گرفته شد): {_exc}")


# ═════════════════════════════════════════════════════════════════════════
# موتور حقیقت خروج و مسیر (egress_engine.py) — رفع عیب تولیدی «False Egress»:
#   - CUSTOM_IP != REAL_EGRESS_IP · SNI/Hostname/TLS-server-name != ROUTING
#   - نقش‌های نود: CONTROL_PLANE / EXIT_NODE / RELAY_NODE / EDGE_NODE / HYBRID
#   - طبقه‌بندی خروج: VERIFIED_EGRESS / CONFIGURED_ONLY / UNKNOWN
#   - اعتبارسنجی مسیر ۹ مرحله‌ای (ROUTE_MISMATCH / NO_EXIT_NODE_AVAILABLE)
#   - تأخیرهای برچسب‌دار (control_plane_rtt / node_rtt / route_rtt / …)
# یک منبع حقیقت برای همه‌ی ادعاهای خروج — /api/egress/*
# ═════════════════════════════════════════════════════════════════════════
try:
    import egress_engine
    egress_engine.register_routes(app)
    logger.info(f"[bootstrap] egress_engine v{egress_engine.EGRESS_ENGINE_VERSION} routes registered (egress & route truth: roles, verification, route validation)")
except Exception as _exc:
    logger.error(f"[bootstrap] egress_engine بارگذاری نشد (نادیده گرفته شد): {_exc}")


# ═════════════════════════════════════════════════════════════════════════════
# Phase 38 / P0 — Route Engine: مسیرها به‌عنوان موجودیت درجه‌یک
# (route_id / entry / relay / exit / expected-vs-observed / health / latency)
# ═════════════════════════════════════════════════════════════════════════════
try:
    import route_engine
    route_engine.register_routes(app, require_auth)
    logger.info(f"[bootstrap] route_engine v{route_engine.ROUTE_ENGINE_VERSION} routes registered (first-class routes)")
except Exception as _exc:
    logger.error(f"[bootstrap] route_engine بارگذاری نشد (نادیده گرفته شد): {_exc}")


# ═════════════════════════════════════════════════════════════════════════════
# Phase 38 / P1 — Failover Engine: drain → explainable replacement → verify
# health → verify route → verify egress → re-point → resume
# ═════════════════════════════════════════════════════════════════════════════
try:
    import failover_engine
    failover_engine.register_routes(app, require_auth)
    logger.info(f"[bootstrap] failover_engine v{failover_engine.FAILOVER_ENGINE_VERSION} routes registered (real failover, never blind)")
except Exception as _exc:
    logger.error(f"[bootstrap] failover_engine بارگذاری نشد (نادیده گرفته شد): {_exc}")


# ═════════════════════════════════════════════════════════════════════════════
# Phase 38 / P2+P3 — Accounts / Devices / Subscriptions / Sessions
# (backend-enforced limits, PBKDF2 hashes, one-time device tokens)
# ═════════════════════════════════════════════════════════════════════════════
try:
    import account_manager
    account_manager.register_routes(app, require_auth)
    logger.info(f"[bootstrap] account_manager v{account_manager.ACCOUNT_ENGINE_VERSION} routes registered (accounts/devices/subscriptions)")
except Exception as _exc:
    logger.error(f"[bootstrap] account_manager بارگذاری نشد (نادیده گرفته شد): {_exc}")


# ═════════════════════════════════════════════════════════════════════════════
# Phase 38 / P17 — Iran Domestic Direct Routing (split tunneling)
# پیشوندهای ایرانی از RIPEstat (seed واقعی + به‌روزرسانی اتمی روزانه)
# ═════════════════════════════════════════════════════════════════════════════
try:
    import domestic_route_engine
    import domestic_rules_updater
    domestic_route_engine.register_routes(app, require_auth)
    logger.info(
        f"[bootstrap] domestic_route_engine v{domestic_route_engine.DOMESTIC_ENGINE_VERSION} "
        f"+ rules_updater registered (IR split-tunneling, {domestic_route_engine.dataset_status().get('prefix_count', 0)} prefixes)"
    )
except Exception as _exc:
    logger.error(f"[bootstrap] domestic_route_engine بارگذاری نشد (نادیده گرفته شد): {_exc}")


# ═════════════════════════════════════════════════════════════════════════════
# Phase 38+ — Capability Engine (protocol × transport × deployment × node ×
# client — ONE backend-driven capability source; frontend renders from API)
# ═════════════════════════════════════════════════════════════════════════════
try:
    import capability_engine
    capability_engine.register_routes(app, require_auth)
    logger.info(f"[bootstrap] capability_engine v{capability_engine.ENGINE_VERSION} "
                f"routes registered (/api/config-builder/capabilities, "
                f"/api/railway/validation-matrix)")
except Exception as _exc:
    logger.error(f"[bootstrap] capability_engine بارگذاری نشد (نادیده گرفته شد): {_exc}")


# ═════════════════════════════════════════════════════════════════════════════
# Phase 38+ — Unified Config Builder (canonical ConfigRequest → compiler →
# outputs + history). ONE builder; every output from the canonical compiler.
# ═════════════════════════════════════════════════════════════════════════════
try:
    import config_builder
    config_builder.register_routes(app, require_auth)
    logger.info(f"[bootstrap] config_builder v{config_builder.ENGINE_VERSION} "
                f"routes registered (preview/generate/history)")
except Exception as _exc:
    logger.error(f"[bootstrap] config_builder بارگذاری نشد (نادیده گرفته شد): {_exc}")


# ═════════════════════════════════════════════════════════════════════════════
# Phase 38+ §13 — Iran Gateway / IRAN_PROXY (REAL Iranian exit, evidence-based)
# ═════════════════════════════════════════════════════════════════════════════
try:
    import iran_gateway
    iran_gateway.register_routes(app, require_auth)
    logger.info(f"[bootstrap] iran_gateway v{iran_gateway.ENGINE_VERSION} "
                f"routes registered (IRAN_PROXY — real Iranian gateway)")
except Exception as _exc:
    logger.error(f"[bootstrap] iran_gateway بارگذاری نشد (نادیده گرفته شد): {_exc}")


# ═════════════════════════════════════════════════════════════════════════════
# Phase 38+ §29 — Structured operational events (CONFIG_GENERATED, …)
# ═════════════════════════════════════════════════════════════════════════════
try:
    import structured_events
    structured_events.register_routes(app, require_auth)
    logger.info(f"[bootstrap] structured_events v{structured_events.ENGINE_VERSION} "
                f"routes registered (/api/events)")
except Exception as _exc:
    logger.error(f"[bootstrap] structured_events بارگذاری نشد (نادیده گرفته شد): {_exc}")


# ═════════════════════════════════════════════════════════════════════════════
# ماژول زیرساخت ریلوی — volume خودکار + سلامت‌سنجی کل پنل (railway_infra.py)
# اگر این ماژول حذف شود یا خطا بدهد، پنل و همه‌ی تونل‌ها بدون تغییر کار می‌کنند.
# ═════════════════════════════════════════════════════════════════════════════
try:
    import railway_infra
    railway_infra.register_routes(app)
except Exception as _exc:
    logger.error(f"[bootstrap] railway_infra بارگذاری نشد (نادیده گرفته شد): {_exc}")


# ══════════════════════════════════════════════════════════════════════════════
# ماژول‌های آزمایشی (Experimental Modules) — toggle-based
# فعال‌سازی: EMIX_EXPERIMENTAL=1 + EMIX_ENABLE_<FEATURE>=1
# اگر فعال نشوند، هیچ اثری ندارند — پایداری اصلی حفظ می‌شود.
# هر ماژول در try/except قرار دارد تا خرابی‌اش پنل را از کار نیندازد.
# ══════════════════════════════════════════════════════════════════════════════
try:
    import experimental
    logger.info(f"[bootstrap] experimental loaded: enabled={experimental.is_experimental_enabled()}")
except Exception as _exc:
    logger.error(f"[bootstrap] experimental load failed (ignored): {_exc}")

try:
    import security_exp
    app.add_middleware(security_exp.SecurityHeadersMiddleware)
    app.add_middleware(security_exp.RateLimitMiddleware)
    logger.info("[bootstrap] security_exp middleware registered")
except Exception as _exc:
    logger.error(f"[bootstrap] security_exp load failed (ignored): {_exc}")

try:
    import link_emit
    logger.info("[bootstrap] link_emit loaded (new share-link generators)")
except Exception as _exc:
    logger.error(f"[bootstrap] link_emit load failed (ignored): {_exc}")

try:
    import exp_api
    app.include_router(exp_api.router)
    logger.info("[bootstrap] exp_api routes registered (experimental section)")
except Exception as _exc:
    logger.error(f"[bootstrap] exp_api load failed (ignored): {_exc}")

# Phase 2 — Protocol engine + adapters
try:
    import protocol_adapters  # registers all adapters via __init__.py
    import protocols_api
    app.include_router(protocols_api.router)
    from protocol_engine import list_protocols, list_protocol_names, get_enabled_protocols
    logger.info(
        f"[bootstrap] protocol_engine loaded: "
        f"{len(list_protocols())} registered "
        f"({len(get_enabled_protocols())} serving) — "
        f"names={list_protocol_names()}"
    )
except Exception as _exc:
    logger.error(f"[bootstrap] protocol_engine load failed (ignored): {_exc}")

# Phase 31-39 — Reverse proxy subsystem (opt-in)
try:
    import reverseproxy
    # Override the placeholder dependency with require_auth
    from fastapi import Depends as _Depends
    # Replace each endpoint's placeholder dependency with real auth
    for _route in reverseproxy.api.router.routes:
        # endpoints have a placeholder `_=Depends(lambda: None)` — we need
        # to re-declare them with require_auth. Simpler: just re-register
        # the same paths on the main app with require_auth.
        pass
    # Re-declare the /api/edge/* endpoints with real auth
    from reverseproxy import (
        get_proxy_config, reload_proxy_config, all_upstream_health,
        build_origin_signature, HMAC_ORIGIN_HEADER, HMAC_TIMESTAMP_HEADER,
    )
    @app.get("/api/edge/config", dependencies=[Depends(require_auth)])
    async def _edge_config():
        return get_proxy_config().to_dict()
    @app.get("/api/edge/routes", dependencies=[Depends(require_auth)])
    async def _edge_routes():
        return {"routes": [r.to_dict() for r in get_proxy_config().routes]}
    @app.get("/api/edge/upstreams/health", dependencies=[Depends(require_auth)])
    async def _edge_upstream_health():
        return {"upstreams": all_upstream_health()}
    @app.post("/api/edge/reload", dependencies=[Depends(require_auth)])
    async def _edge_reload():
        cfg = reload_proxy_config()
        log_activity("system", f"reverse-proxy reloaded: routes={len(cfg.routes)}", "info")
        return {"ok": True, "config": cfg.to_dict()}
    @app.post("/api/edge/origin/test", dependencies=[Depends(require_auth)])
    async def _edge_origin_test(request: Request):
        body = await request.json()
        method = body.get("method", "GET")
        path = body.get("path", "/")
        payload = body.get("body", "")
        if isinstance(payload, str):
            payload = payload.encode()
        cfg = get_proxy_config()
        if not cfg.origin_auth_enabled:
            return {"ok": False, "error": "origin auth not enabled (set EMIX_ORIGIN_AUTH_SECRET)"}
        sig, ts = build_origin_signature(cfg.origin_auth_secret, method, path, payload)
        return {
            "ok": True,
            "signature_header": HMAC_ORIGIN_HEADER,
            "timestamp_header": HMAC_TIMESTAMP_HEADER,
            "signature": sig,
            "timestamp": ts,
        }
    # Start background health checks if reverse proxy enabled
    cfg = get_proxy_config()
    if cfg.enabled and cfg.routes:
        reverseproxy.start_health_checks()
        logger.info(f"[bootstrap] reverseproxy enabled: {len(cfg.routes)} routes, health checks started")
    else:
        logger.info(f"[bootstrap] reverseproxy loaded (disabled by default; set EMIX_REVERSE_PROXY_ENABLED=1 + EMIX_REVERSE_PROXY_ROUTES_JSON to enable)")
except Exception as _exc:
    logger.error(f"[bootstrap] reverseproxy load failed (ignored): {_exc}")

# ── SNI Management + Security Signatures + VPN Pro (Phase SNI-Management + Security + VPN-Pro) ──
try:
    import sni_management
    import security_signatures
    import vpn_pro
    # SNI Management: CRUD + health check + ArvanCloud compat
    @app.get("/api/security/sni/profiles", dependencies=[Depends(require_auth)])
    async def _sni_list():
        return await sni_management.all_profiles_dict()
    @app.post("/api/security/sni/profiles", dependencies=[Depends(require_auth)])
    async def _sni_create(request: Request):
        body = await request.json()
        # Validate fields
        ok, val = sni_management.validate_server_name(body.get("server_name"))
        if not ok:
            raise HTTPException(status_code=400, detail=f"invalid server_name: {val}")
        ok_alpn, alpn_val = sni_management.validate_alpn(body.get("alpn") or ["h2", "http/1.1"])
        if not ok_alpn:
            raise HTTPException(status_code=400, detail=f"invalid alpn: {alpn_val}")
        ok_tls, tls_val = sni_management.validate_tls_version(body.get("min_tls_version"))
        if not ok_tls:
            raise HTTPException(status_code=400, detail=f"invalid min_tls_version: {tls_val}")
        try:
            profile = sni_management.SNIProfile(
                id=generate_uuid(),
                name=str(body.get("name") or "")[:60],
                server_name=val,
                enabled=bool(body.get("enabled", True)),
                alpn=alpn_val,
                min_tls_version=tls_val,
                verify_certificate=bool(body.get("verify_certificate", True)),
                host_header=body.get("host_header"),
                description=str(body.get("description") or "")[:500],
            )
            await sni_management.create_profile(profile)
            log_activity("system", f"SNI profile «{profile.name}» ساخته شد", "ok")
            return {"ok": True, "profile": profile.to_dict()}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    @app.put("/api/security/sni/profiles/{profile_id}", dependencies=[Depends(require_auth)])
    async def _sni_update(profile_id: str, request: Request):
        body = await request.json()
        try:
            updated = await sni_management.update_profile(profile_id, body)
            if updated is None:
                raise HTTPException(status_code=404, detail="profile not found")
            return {"ok": True, "profile": updated.to_dict()}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    @app.delete("/api/security/sni/profiles/{profile_id}", dependencies=[Depends(require_auth)])
    async def _sni_delete(profile_id: str):
        ok = await sni_management.delete_profile(profile_id)
        if not ok:
            raise HTTPException(status_code=404, detail="profile not found")
        log_activity("system", f"SNI profile deleted: {profile_id}", "warn")
        return {"ok": True, "deleted": profile_id}
    @app.post("/api/security/sni/profiles/{profile_id}/health", dependencies=[Depends(require_auth)])
    async def _sni_health(profile_id: str):
        profile = await sni_management.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="profile not found")
        result = await sni_management.health_check_profile(profile)
        return {"ok": True, "result": result}
    @app.post("/api/security/sni/profiles/{profile_id}/arvan", dependencies=[Depends(require_auth)])
    async def _sni_arvan(profile_id: str):
        profile = await sni_management.get_profile(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="profile not found")
        result = await sni_management.check_arvan_compatibility(profile)
        return {"ok": True, "result": result}
    # Security Signatures: list + health check
    @app.get("/api/security/signatures", dependencies=[Depends(require_auth)])
    async def _sig_list():
        return security_signatures.all_profiles_dict()
    # IMPORTANT: specific routes (randomized, recommend) MUST come BEFORE
    # /api/security/signatures/{profile_id} — otherwise FastAPI matches
    # "randomized" or "recommend" against the {profile_id} path parameter.
    @app.get("/api/security/signatures/randomized", dependencies=[Depends(require_auth)])
    async def _sig_randomized():
        return security_signatures.randomized_profile_dict()
    @app.post("/api/security/signatures/randomized/seed", dependencies=[Depends(require_auth)])
    async def _sig_seed(request: Request):
        body = await request.json()
        seed = body.get("seed")
        security_signatures.set_random_seed(int(seed) if seed is not None else None)
        return {"ok": True, "seed": seed, "note": "deterministic mode for testing only" if seed is not None else "secure randomness restored"}
    @app.get("/api/security/signatures/recommend", dependencies=[Depends(require_auth)])
    async def _sig_recommend(protocol: str = "", transport: str = "", client: str = ""):
        p = security_signatures.recommend_profile(protocol=protocol, transport=transport, client_capability=client)
        if p is None:
            raise HTTPException(status_code=404, detail="no recommendation for given inputs")
        return {"recommended": p.to_dict()}
    @app.get("/api/security/signatures/{profile_id}", dependencies=[Depends(require_auth)])
    async def _sig_get(profile_id: str):
        p = security_signatures.get_profile(profile_id)
        if p is None:
            raise HTTPException(status_code=404, detail="signature profile not found")
        return {"profile": p.to_dict(), "supported_in_runtime": p.is_supported_in_runtime()}
    @app.post("/api/security/signatures/{profile_id}/health", dependencies=[Depends(require_auth)])
    async def _sig_health(profile_id: str):
        p = security_signatures.get_profile(profile_id)
        if p is None:
            raise HTTPException(status_code=404, detail="signature profile not found")
        result = await security_signatures.health_check_profile(p)
        return {"ok": True, "result": result}
    # VPN Pro: nodes + preflight + config generators
    @app.get("/api/vpn/nodes", dependencies=[Depends(require_auth)])
    async def _vpn_nodes():
        return await vpn_pro.all_nodes_dict()
    @app.post("/api/vpn/nodes", dependencies=[Depends(require_auth)])
    async def _vpn_node_create(request: Request):
        body = await request.json()
        try:
            proto_str = (body.get("protocol") or "wireguard").lower()
            proto = vpn_pro.VPNProtocol(proto_str)
            node = vpn_pro.VPNNode(
                id=generate_uuid(),
                name=str(body.get("name") or "")[:60],
                provider=str(body.get("provider") or "manual")[:30],
                hostname=str(body.get("hostname") or "")[:200],
                ip=str(body.get("ip") or "")[:45],
                ssh_port=int(body.get("ssh_port") or 22),
                protocol=proto,
                region=str(body.get("region") or "")[:60],
                wg_listen_port=int(body.get("wg_listen_port") or 51820),
                wg_address_range=str(body.get("wg_address_range") or "10.8.0.0/24")[:40],
                wg_dns=str(body.get("wg_dns") or "1.1.1.1")[:60],
                wg_mtu=int(body.get("wg_mtu") or 1420),
                wg_keepalive=int(body.get("wg_keepalive") or 25),
                ovpn_port=int(body.get("ovpn_port") or 1194),
                ovpn_protocol=str(body.get("ovpn_protocol") or "udp")[:5],
                ovpn_cipher=str(body.get("ovpn_cipher") or "AES-256-GCM")[:40],
                ovpn_network=str(body.get("ovpn_network") or "10.8.0.0/24")[:40],
                ovpn_dns=str(body.get("ovpn_dns") or "1.1.1.1")[:60],
            )
            await vpn_pro.create_node(node)
            log_activity("system", f"VPN node «{node.name}» ساخته شد ({proto.value})", "ok")
            return {"ok": True, "node": node.to_dict()}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    @app.get("/api/vpn/nodes/{node_id}", dependencies=[Depends(require_auth)])
    async def _vpn_node_get(node_id: str):
        node = await vpn_pro.get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        return {"node": node.to_dict()}
    @app.delete("/api/vpn/nodes/{node_id}", dependencies=[Depends(require_auth)])
    async def _vpn_node_delete(node_id: str):
        ok = await vpn_pro.delete_node(node_id)
        if not ok:
            raise HTTPException(status_code=404, detail="node not found")
        log_activity("system", f"VPN node deleted: {node_id}", "warn")
        return {"ok": True, "deleted": node_id}
    @app.post("/api/vpn/nodes/{node_id}/preflight", dependencies=[Depends(require_auth)])
    async def _vpn_preflight(node_id: str):
        node = await vpn_pro.get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        return await vpn_pro.preflight_check(node)
    @app.post("/api/vpn/nodes/{node_id}/wireguard/server-config", dependencies=[Depends(require_auth)])
    async def _vpn_wg_server_config(node_id: str):
        node = await vpn_pro.get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        if node.protocol != vpn_pro.VPNProtocol.WIREGUARD and node.protocol.value != "wireguard":
            raise HTTPException(status_code=400, detail="node is not a WireGuard node")
        result = vpn_pro.generate_wireguard_server_config(node)
        # Store the server public key on the node for future client config generation
        await vpn_pro.update_node(node_id, {
            "wg_server_public_key": result["server_public_key"],
            "wg_server_private_key": result["server_private_key"],  # NOT exposed in to_dict()
        })
        log_activity("system", f"WireGuard server config generated for node «{node.name}»", "info")
        return result
    @app.post("/api/vpn/nodes/{node_id}/wireguard/client", dependencies=[Depends(require_auth)])
    async def _vpn_wg_client_config(node_id: str, request: Request):
        node = await vpn_pro.get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        body = await request.json()
        client_name = str(body.get("name") or "client")[:60]
        client_ip = body.get("ip") or ""
        result = vpn_pro.generate_wireguard_client_config(node, client_name, client_ip)
        # Add to node's client list (public key + name only — no private key in storage)
        node.clients.append({
            "name": client_name,
            "ip": result["client_ip"],
            "public_key": result["client_public_key"],
            "created_at": time.time(),
            "enabled": True,
        })
        log_activity("system", f"WireGuard client «{client_name}» added to node «{node.name}»", "info")
        return result
    @app.post("/api/vpn/nodes/{node_id}/openvpn/server-config", dependencies=[Depends(require_auth)])
    async def _vpn_ovpn_server_config(node_id: str):
        node = await vpn_pro.get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        if node.protocol != vpn_pro.VPNProtocol.OPENVPN and node.protocol.value != "openvpn":
            raise HTTPException(status_code=400, detail="node is not an OpenVPN node")
        result = vpn_pro.generate_openvpn_server_config(node)
        log_activity("system", f"OpenVPN server config generated for node «{node.name}»", "info")
        return result
    @app.post("/api/vpn/nodes/{node_id}/openvpn/client", dependencies=[Depends(require_auth)])
    async def _vpn_ovpn_client_config(node_id: str, request: Request):
        node = await vpn_pro.get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        body = await request.json()
        client_name = str(body.get("name") or "client")[:60]
        result = vpn_pro.generate_openvpn_client_config(node, client_name)
        node.clients.append({
            "name": client_name,
            "created_at": time.time(),
            "enabled": True,
        })
        log_activity("system", f"OpenVPN client «{client_name}» added to node «{node.name}»", "info")
        return result
    @app.get("/api/vpn/providers", dependencies=[Depends(require_auth)])
    async def _vpn_providers():
        return vpn_pro.all_providers_dict()
    logger.info("[bootstrap] SNI Management + Security Signatures + VPN Pro routes registered")
except Exception as _exc:
    logger.error(f"[bootstrap] SNI/Security/VPN-Pro load failed (ignored): {_exc}")

try:
    import gaming_health
    app.include_router(gaming_health.router)
    logger.info("[bootstrap] gaming_health routes registered")
except Exception as _exc:
    logger.error(f"[bootstrap] gaming_health load failed (ignored): {_exc}")

try:
    import smart_route
    app.include_router(smart_route.router)
    logger.info("[bootstrap] smart_route routes registered")
except Exception as _exc:
    logger.error(f"[bootstrap] smart_route load failed (ignored): {_exc}")

try:
    import isp_detect
    app.include_router(isp_detect.router)
    logger.info("[bootstrap] isp_detect routes registered")
except Exception as _exc:
    logger.error(f"[bootstrap] isp_detect load failed (ignored): {_exc}")


# ══════════════════════════════════════════════════════════════════════════════
# [Phase 3/4/25/6/9/20/21] Config Compiler + Endpoint Profiles + Network
# Health + IP Quality + Job System + Diagnostics Center
# ══════════════════════════════════════════════════════════════════════════════

# ── Compatibility matrix (frontend renders ONLY these combinations) ─────────
@app.get("/api/config-matrix", dependencies=[Depends(require_auth)])
async def api_config_matrix():
    return {"ok": True, **compat.matrix_view()}

# ── Config Compiler: compile a spec WITHOUT storing it (validation preview) ─
@app.post("/api/configs/compile", dependencies=[Depends(require_auth)])
async def api_compile_preview(request: Request):
    """Compile a config spec and return the URI + xray JSON + self-check
    result WITHOUT creating a link. Live validation for the frontend."""
    body = await request.json()
    spec = config_compiler.ConfigSpec(
        protocol=body.get("protocol", "vless"),
        transport=body.get("transport", "ws"),
        security=body.get("security", "tls"),
        credential=body.get("credential") or generate_uuid(),
        remark=(body.get("remark") or "EMIX")[:80],
        host=body.get("host") or get_host(),
        alpn=str(body.get("alpn") or "h2,http/1.1")[:60],
        fingerprint=str(body.get("fingerprint") or "chrome")[:20],
        ss_cipher=body.get("ss_cipher", ""),
        ss_password=body.get("ss_password", ""),
        requested_formats=("uri", "json") if body.get("include_json") else ("uri",),
    )
    compiled = config_compiler.compile_config(spec)
    return compiled.to_dict()

# ── Endpoint & Transport Profiles (Phase 25 — SNI Spoofing successor) ───────
@app.get("/api/endpoint-profiles", dependencies=[Depends(require_auth)])
async def api_ep_list():
    profiles = await endpoint_profiles.list_profiles()
    return {
        "ok": True,
        "profiles": [p.to_dict() for p in profiles],
        "count": len(profiles),
        "note": "Endpoint & Transport Profile Engine — replaces legacy SNI Spoofing; per-link spoof_sni fields remain supported",
    }

@app.post("/api/endpoint-profiles", dependencies=[Depends(require_auth)])
async def api_ep_create(request: Request):
    body = await request.json()
    profile = endpoint_profiles.EndpointProfile(
        id=body.get("id") or endpoint_profiles.new_profile_id(),
        name=str(body.get("name") or "")[:60],
        address=str(body.get("address") or ""),
        sni=body.get("sni"),
        host_header=body.get("host_header"),
        port=int(body.get("port") or 443),
        path_prefix=str(body.get("path_prefix") or ""),
        security=str(body.get("security") or "tls"),
        alpn=body.get("alpn") or ["h2", "http/1.1"],
        min_tls=str(body.get("min_tls") or "1.3"),
        allow_insecure=bool(body.get("allow_insecure", False)),
        ip_version=str(body.get("ip_version") or "auto"),
        dns_mode=str(body.get("dns_mode") or "auto"),
        node_id=body.get("node_id"),
        transport=body.get("transport"),
        description=str(body.get("description") or "")[:500],
    )
    try:
        created = await endpoint_profiles.create_profile(profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    asyncio.create_task(save_state())
    log_activity("system", f"Endpoint profile «{created.name}» ساخته شد", "ok")
    return {"ok": True, "profile": created.to_dict()}

@app.put("/api/endpoint-profiles/{profile_id}", dependencies=[Depends(require_auth)])
async def api_ep_update(profile_id: str, request: Request):
    body = await request.json()
    try:
        updated = await endpoint_profiles.update_profile(profile_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if updated is None:
        raise HTTPException(status_code=404, detail="profile not found")
    asyncio.create_task(save_state())
    return {"ok": True, "profile": updated.to_dict()}

@app.delete("/api/endpoint-profiles/{profile_id}", dependencies=[Depends(require_auth)])
async def api_ep_delete(profile_id: str):
    ok = await endpoint_profiles.delete_profile(profile_id)
    if not ok:
        raise HTTPException(status_code=404, detail="profile not found")
    asyncio.create_task(save_state())
    log_activity("system", f"Endpoint profile deleted: {profile_id}", "warn")
    return {"ok": True, "deleted": profile_id}

@app.post("/api/endpoint-profiles/{profile_id}/validate", dependencies=[Depends(require_auth)])
async def api_ep_validate(profile_id: str, request: Request):
    """Validate a profile against a protocol/transport combo (live check)."""
    profile = await endpoint_profiles.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")
    body = await request.json()
    fused = body.get("protocol", "vless-ws")
    errors = endpoint_profiles.validate_profile_for_protocol(profile, fused)
    c = compat.validate_fused(fused)
    return {
        "ok": not errors and c.ok,
        "profile_errors": errors,
        "compat": c.to_dict(),
    }

# ── Network Health Engine (Phase 6/7) ────────────────────────────────────────
@app.get("/api/health/summary", dependencies=[Depends(require_auth)])
async def api_health_summary():
    return {"ok": True, **network_health.summary(),
            "formula": "0.40*latency + 0.20*handshake + 0.20*reachability + 0.20*stability (real probes only)"}

@app.get("/api/health/links", dependencies=[Depends(require_auth)])
async def api_health_all():
    return {"ok": True, "records": network_health.all_health()}

@app.get("/api/health/links/{uid}", dependencies=[Depends(require_auth)])
async def api_health_one(uid: str):
    rec = network_health.get_health_dict(uid)
    if rec is None:
        # fall back to the link's persisted health field
        async with LINKS_LOCK:
            persisted = (LINKS.get(uid) or {}).get("health")
        if persisted:
            return {"ok": True, "record": persisted, "source": "persisted"}
        raise HTTPException(status_code=404, detail="no health record for this config")
    return {"ok": True, "record": rec, "source": "engine"}

@app.post("/api/health/links/{uid}/probe", dependencies=[Depends(require_auth)])
async def api_health_probe(uid: str, via: str = "direct"):
    async with LINKS_LOCK:
        link = LINKS.get(uid)
    if link is None:
        raise HTTPException(status_code=404, detail="کانفیگ یافت نشد")
    rec = await network_health.probe_config(uid, link, via=via)
    asyncio.create_task(schedule_save())
    return {"ok": True, "record": rec.to_dict()}

# ── Job System (Phase 20) ─────────────────────────────────────────────────────
@app.get("/api/jobs/status", dependencies=[Depends(require_auth)])
async def api_jobs_status():
    return {"ok": True, **job_system.status()}

@app.post("/api/jobs/{name}/run", dependencies=[Depends(require_auth)])
async def api_jobs_run(name: str):
    return await job_system.run_now(name)

# ── Diagnostics Center (Phase 21) ─────────────────────────────────────────────
@app.get("/api/diagnostics", dependencies=[Depends(require_auth)])
async def api_diagnostics():
    return await diagnostics_mod.diagnostics_overview()

# request timing + slow-request + unhandled-error capture
app.middleware("http")(diagnostics_mod.diagnostics_middleware)

# ── IP Quality Engine (Phase 9/28) ────────────────────────────────────────────
try:
    import ip_quality
    app.include_router(ip_quality.router)
    logger.info("[bootstrap] ip_quality routes registered (IP Quality Engine)")
except Exception as _exc:
    logger.error(f"[bootstrap] ip_quality load failed (ignored): {_exc}")

# ── Subscription profiles (Phase 13 + Phase 37.13) on /sub-all ───────────────
_SUB_PROFILES = ("ALL", "HEALTHY", "HEALTHIEST", "FASTEST", "REGION", "PROTOCOL", "CUSTOM")

async def _subscription_filter(items: list, profile: str, region: str = "",
                               protocol: str = "", uids: str = "") -> tuple[list, list]:
    """Phase 37.13 filter chain. Input/output: [(uid, link)] + notes.

    Respects: expiry / quota / disabled (already applied via is_link_allowed
    upstream), REVOKED (active=False → also is_link_allowed), node health
    (links whose serving node is OFFLINE are excluded with a note), and the
    requested profile. Never fabricates inclusion of unhealthy configs.
    """
    notes: list = []
    # node-health gate: serving node OFFLINE → exclude (37.13)
    def _node_ok(link: dict) -> bool:
        try:
            node_id = link.get("node_id") or "panel"
            rec = node_manager.get_node(node_id)
            if rec is None:
                return True  # unknown node — do not fabricate a verdict
            state, _reason = node_manager.derive_state(rec)
            return state != "OFFLINE"
        except Exception:
            return True

    gated = [(uid, d) for uid, d in items if _node_ok(d)]
    if len(gated) < len(items):
        notes.append(f"{len(items) - len(gated)} config(s) excluded — serving node OFFLINE")

    if profile in ("HEALTHY", "HEALTHIEST"):
        healthy = set(network_health.healthy_uids(min_score=60))
        kept = [(uid, d) for uid, d in gated if uid in healthy]
        notes.append(f"HEALTHY filter: {len(kept)}/{len(gated)} configs with fresh HEALTHY evidence")
        return kept, notes
    if profile == "FASTEST":
        probed = [(uid, d) for uid, d in gated if network_health.get_health(uid)]
        probed.sort(key=lambda kv: (
            network_health.get_health(kv[0]).latency_ms
            if network_health.get_health(kv[0]).latency_ms is not None else 10**9))
        notes.append(f"FASTEST: top 5 of {len(probed)} probed configs by real latency")
        return probed[:5], notes
    if profile == "REGION":
        region = (region or "").strip().upper()
        if not region:
            raise HTTPException(status_code=400, detail="profile=REGION requires ?region=")
        kept = []
        for uid, d in gated:
            link_region = (d.get("region") or "").upper()
            if not link_region:
                pid = d.get("endpoint_profile_id")
                if pid:
                    prof = await endpoint_profiles.get_profile(pid)
                    link_region = ((prof.region or "") if prof else "").upper()
            if link_region == region:
                kept.append((uid, d))
        notes.append(f"REGION {region}: {len(kept)}/{len(gated)} configs match "
                     f"(links without region metadata are excluded — honest)")
        return kept, notes
    if profile == "PROTOCOL":
        protocol = (protocol or "").strip().lower()
        if not protocol:
            raise HTTPException(status_code=400, detail="profile=PROTOCOL requires ?protocol=")
        kept = [(uid, d) for uid, d in gated
                if (d.get("protocol") or "").lower().startswith(protocol)]
        notes.append(f"PROTOCOL {protocol}: {len(kept)}/{len(gated)} configs match")
        return kept, notes
    if profile == "CUSTOM":
        wanted = [u.strip() for u in (uids or "").split(",") if u.strip()]
        if not wanted:
            raise HTTPException(status_code=400, detail="profile=CUSTOM requires ?uids=uid1,uid2")
        kept = [(uid, d) for uid, d in gated if uid in set(wanted)]
        missing = [u for u in wanted if u not in {uid for uid, _ in kept}]
        if missing:
            notes.append(f"CUSTOM: {len(missing)} requested uid(s) not allowed/present — excluded")
        return kept, notes
    return gated, notes


@app.get("/sub-all-v2")
async def subscription_all_v2(profile: str = "ALL", region: str = "",
                              protocol: str = "", uids: str = "",
                              _=Depends(require_auth)):
    """Subscription with profile filtering (Phase 13 + 37.13).

    ALL        — every allowed config (same as /sub-all)
    HEALTHY    — only configs with fresh HEALTHY evidence (alias: HEALTHIEST)
    FASTEST    — top 5 by latest real latency (only probed configs)
    REGION     — configs whose region metadata matches ?region= (honest: links
                 without region metadata are excluded, never guessed)
    PROTOCOL   — configs whose protocol starts with ?protocol=
    CUSTOM     — explicit ?uids=uid1,uid2 list (intersected with allowed)

    Respects: expiry, quota, disabled accounts, revoked configs, node health.
    Legacy /sub-all output format unchanged (base64 of newline-joined URIs).
    """
    profile = (profile or "ALL").upper()
    if profile not in _SUB_PROFILES:
        raise HTTPException(status_code=400, detail=f"profile must be one of {_SUB_PROFILES}")
    host = get_host()
    async with LINKS_LOCK:
        items = [(uid, dict(d)) for uid, d in LINKS.items() if is_link_allowed(d)]
    items, notes = await _subscription_filter(items, profile, region=region,
                                              protocol=protocol, uids=uids)
    lines = [
        generate_share_link(uid, host, remark=f"EMIX-{d['label']}", protocol=d.get("protocol", DEFAULT_PROTOCOL))
        for uid, d in items
    ]
    total_used = sum(d.get("used_bytes", 0) for _, d in items)
    total_limit = sum(d.get("limit_bytes", 0) for _, d in items)
    expiries = [d["expires_at"] for _, d in items if d.get("expires_at")]
    nearest_exp = min(expiries) if expiries else None
    content = base64.b64encode("\n".join(lines).encode()).decode()
    headers = build_sub_headers(f"EMIX-{profile}", total_used, total_limit, nearest_exp)
    if notes:
        # Audit fix: هدرهای HTTP فقط latin-1 هستند — em-dash و کاراکترهای
        # غیر ASCII در notes (مثل «—») باعث UnicodeEncodeError/500 می‌شدند.
        raw_notes = "; ".join(notes)[:300]
        headers["X-Emix-Filter-Notes"] = raw_notes.encode("latin-1", "replace").decode("latin-1")
    return Response(content=content, media_type="text/plain", headers=headers)

logger.info("[bootstrap] Config Compiler + Endpoint Profiles + Network Health + Jobs + Diagnostics ready")


# ══════════════════════════════════════════════════════════════════════════════
# Phase 37 — Node Manager / Runtime Supervisor / Config Lifecycle APIs
# NOTE (audit fix 2026-09): این روت‌ها از /api/nodes به /api/managed-nodes منتقل
# شدند چون /api/nodes (outbound panels, main.py:3224) آن‌را shadow می‌کرد و
# endpoint رجیستری گره‌ها در production هرگز پاسخ داده نمی‌شد.
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/managed-nodes", dependencies=[Depends(require_auth)])
async def api_nodes():
    """Node registry with runtime-gated health (37.9). No secrets.

    Audit fix: summary() هم کلید «nodes» دارد (count) — قبلاً با dict-spread
    لیست را بازنویسی می‌کرد و کلاینت به‌جای آرایه عدد می‌گرفت.
    """
    return {"ok": True, **node_manager.summary(),
            "nodes": node_manager.list_nodes()}


@app.post("/api/managed-nodes/{node_id}/heartbeat", dependencies=[Depends(require_auth)])
async def api_node_heartbeat(node_id: str, request: Request):
    """Record manual/external heartbeat evidence for a node (37.9)."""
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    rec = await node_manager.heartbeat(
        node_id, kind=body.get("kind", "manual"),
        runtime_health=body.get("runtime_health", "UNKNOWN"),
        load=body.get("load"), clients=body.get("clients"))
    if rec is None:
        raise HTTPException(status_code=404, detail=f"node {node_id!r} not registered")
    return {"ok": True, "node": rec.to_dict()}


@app.post("/api/managed-nodes/{node_id}/maintenance", dependencies=[Depends(require_auth)])
async def api_node_maintenance(node_id: str, request: Request):
    """Operator override: MAINTENANCE on/off (37.9)."""
    body = await request.json()
    on = bool(body.get("on", True))
    rec = await node_manager.set_maintenance(node_id, on, reason=body.get("reason", ""))
    if rec is None:
        raise HTTPException(status_code=404, detail=f"node {node_id!r} not registered")
    asyncio.create_task(schedule_save())
    return {"ok": True, "node": rec.to_dict()}


@app.get("/api/runtime/status", dependencies=[Depends(require_auth)])
async def api_runtime_status():
    """Supervised runtimes: state, restart counts, backoff windows (37.10)."""
    return {"ok": True, **runtime_supervisor.supervisor.status()}


@app.post("/api/runtime/{runtime_id}/restart", dependencies=[Depends(require_auth)])
async def api_runtime_restart(runtime_id: str):
    """Manual restart of a supervised runtime (counts toward the budget)."""
    result = await runtime_supervisor.supervisor.restart(runtime_id, manual=True)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "restart failed"))
    return result


@app.get("/api/lifecycle/{uid}", dependencies=[Depends(require_auth)])
async def api_config_lifecycle(uid: str):
    """Config lifecycle state + expiry bookkeeping (37.11)."""
    async with LINKS_LOCK:
        link = LINKS.get(uid)
    if link is None:
        raise HTTPException(status_code=404, detail=f"config {uid[:8]} not found")
    ann = config_lifecycle.lifecycle_annotation(uid, link, network_health.get_health_dict(uid))
    return {"ok": True, **ann, "health": network_health.get_health_dict(uid)}


# ══════════════════════════════════════════════════════════════════════════════
# Local QR generation (audit fix 2026-09 — privacy)
# قبلاً QR از api.qrserver.com (سرویس شخص ثالث) ساخته می‌شد و کل لینک
# (شامل credential) و حتی کلید خصوصی WireGuard به بیرون می‌رفت. حالا QR
# به‌صورت محلی (SVG، بدون Pillow) تولید می‌شود.
# ══════════════════════════════════════════════════════════════════════════════

_QR_SCHEME_ALLOWLIST = (
    "vless://", "trojan://", "ss://", "vmess://", "tg://", "ssh://",
    "https://", "http://", "hy2://", "tuic://", "wireguard://",
)
_QR_MAX_DATA = 2048
_QR_RATE_LIMIT = 30          # requests/min/IP
_QR_HITS: dict = {}          # (ip, minute) → count


@app.get("/api/qr")
async def api_qr(request: Request, data: str = "", size: int = 260):
    """Generate a QR code LOCALLY as SVG (no third-party service, no leak).

    Public (no auth) because the public subscription page uses it.
    Guards: scheme allowlist, 2048-char cap, 30 req/min/IP.
    """
    import io as _io
    ip = client_ip(request)
    minute = int(time.time()) // 60
    key = (ip, minute)
    hits = _QR_HITS.get(key, 0)
    _QR_HITS[key] = hits + 1
    if len(_QR_HITS) > 4096:  # bounded cleanup
        _QR_HITS.clear()
    if hits >= _QR_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="QR rate limit exceeded")
    data = (data or "").strip()
    if not data:
        raise HTTPException(status_code=400, detail="missing data parameter")
    if len(data) > _QR_MAX_DATA:
        raise HTTPException(status_code=413, detail="data too long (max 2048 chars)")
    # Allowlist: link schemes, subscription URLs, or an inline WireGuard config
    if not (data.startswith(_QR_SCHEME_ALLOWLIST) or data.startswith("BEGIN ")):
        raise HTTPException(status_code=400,
                            detail="unsupported content for QR generation")
    try:
        import qrcode
        import qrcode.image.svg
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                           border=2, box_size=10)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
        buf = _io.BytesIO()
        img.save(buf)
        svg = buf.getvalue()
    except ImportError:
        raise HTTPException(status_code=503,
                            detail="qrcode library not installed (pip install qrcode)")
    except Exception as e:
        diagnostics.record_error_sync("QR_GENERATION", str(e), "api:qr", "ERROR")
        raise HTTPException(status_code=500, detail="QR generation failed")
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "no-store"})


@app.post("/api/endpoint-profiles/migrate-legacy", dependencies=[Depends(require_auth)])
async def api_migrate_legacy_spoof():
    """Phase 37.8: build normalized profiles from legacy spoof_sni fields.

    Does NOT delete or alter legacy fields — backward compatibility is kept;
    the returned profiles are stored and can be attached to links explicitly.
    """
    host = get_host()
    cdn = CONFIG.get("cdn_domain", "")
    created, skipped = [], []
    async with LINKS_LOCK:
        targets = [(uid, dict(d)) for uid, d in LINKS.items()
                   if d.get("spoof_sni_enabled") and d.get("spoof_sni")]
    for uid, link in targets:
        profile = endpoint_profiles.migrate_legacy_link(link, host, cdn_domain=cdn)
        if profile is None:
            skipped.append(uid)
            continue
        try:
            await endpoint_profiles.create_profile(profile)
            created.append({"uid": uid, "profile_id": profile.id, "mode": "legacy-migration"})
        except ValueError:
            skipped.append(uid)  # name collision → already migrated
    if created:
        asyncio.create_task(schedule_save())
    return {
        "ok": True, "migrated": len(created), "skipped": len(skipped),
        "details": created,
        "note": "legacy spoof_sni fields remain untouched (wire compat preserved)",
        "legacy_stats": endpoint_profiles.legacy_spoof_stats(LINKS),
    }


# ══════════════════════════════════════════════════════════════════════════════
# /api/deployment-version — برای تأیید نسخه‌ی دیپلوی‌شده روی Railway
# کاربر می‌تواند با مقایسه‌ی نسخه، تأیید کند که آیا Railway کد جدید را دیپلوی
# کرده است یا هنوز روی نسخه‌ی قدیمی است. این اندپوینت بدون احراز هویت است
# تا قبل از لاگین هم قابل بررسی باشد. (از /api/version استفاده نمی‌کنیم چون
# آن مسیر قبلاً برای بررسی به‌روزرسانی در نظر گرفته شده است.)
# ══════════════════════════════════════════════════════════════════════════════
EMIX_VERSION = "11.4.0-builder"
EMIX_BUILD_DATE = "2026-09-01"

@app.get("/api/deployment-version")
async def api_deployment_version():
    """اطلاعات نسخه‌ی دیپلوی‌شده — بدون نیاز به احراز هویت.
    اگر نسخه‌ای که می‌بینید با نسخه‌ی گیت‌هاب تطابق نداشت، یعنی Railway هنوز
    روی کد قدیمی است و باید «Deploy Latest Commit» (نه Redeploy) را بزنید."""
    # خلاصه‌ی فیچرهای آزمایشی (اگر فعالند)
    exp_summary = "disabled"
    try:
        import experimental
        exp_summary = experimental.get_enabled_features_summary()
    except Exception:
        pass
    return {
        "service": "EMIX",
        "version": EMIX_VERSION,
        "build_date": EMIX_BUILD_DATE,
        "has_zeus": True,
        "has_clean_ip": True,
        "has_bridge": True,
        "has_turbo": True,
        "has_gaming": True,
        "has_infra": True,
        "experimental_section": exp_summary,
        "features_summary": "Config Compiler + Endpoint Profiles (SNI-Spoof successor) + Network Health Engine (per-config states+scores) + IP Quality Engine + Job System + Diagnostics Center + compat matrix + ISP/TLS Mask/Smart Mode/Security + Clean IPs + Bridge CDN/VPS + Turbo 0-RTT + Gaming Center + CF Gateway + Auto Volume + Experimental Section",
    }


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=CONFIG["port"],
        log_level="info",
        workers=1,
        loop="auto",         # uvloop رو در صورت نصب بودن استفاده می‌کنه، وگرنه بدون کرش fallback می‌کنه
        http="auto",
    )
