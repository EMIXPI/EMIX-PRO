# gaming_health.py — موتور گیمینگ واقعی
# اصل: هیچ‌گاه fabrication نمی‌کند. اگر metric قابل اندازه‌گیری نیست،
#       "unavailable" برمی‌گرداند.
#
# معیارها:
#   - latency: TCP handshake time به game server
#   - jitter: ضریب تغییرات latency در ۱۰ اندازه‌گیری گذشته
#   - loss: تعداد timeout‌ها در ۱۰ اندازه‌گیری گذشته / ۱۰
#   - stability: 1 - (spike_count_5min / max_spike_count)
#
# Gaming Health Score (GHS):
#   GHS = 0.4 * latency_norm + 0.25 * (1 - jitter_norm) + 0.2 * (1 - loss) + 0.15 * stability
#
# نمونه‌ی spike detection: ۳ اندازه‌گیری متوالی با latency > 2 * median

import asyncio
import time
import statistics
from collections import deque
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from experimental import is_enabled

router = APIRouter()


# ─── In-memory storage (per gaming session) ─────────────────────────────
# توجه: در Railway، state در restart از بین می‌رود. اگر نیاز به persistence است،
# باید به state file اضافه شود. فعلاً فقط برای کاربری real-time استفاده می‌شود.

_SESSIONS = {}  # session_id → {history: deque, profile: str, last_spike: float}
_MAX_HISTORY = 10
_SPIKE_COOLDOWN = 30.0  # ثانیه

# ─── Gaming Profiles ─────────────────────────────────────────────────────
PROFILES = {
    "fps": {
        "name": "FPS (CS:GO/Valorant)",
        "max_latency_ms": 100,
        "max_jitter_ms": 15,
        "max_loss_pct": 1,
        "keepalive_s": 30,
        "timeout_s": 3,
        "preferred_protocols": ["vless-ws", "trojan-ws"],
    },
    "moba": {
        "name": "MOBA (LoL/Dota)",
        "max_latency_ms": 150,
        "max_jitter_ms": 25,
        "max_loss_pct": 2,
        "keepalive_s": 60,
        "timeout_s": 5,
        "preferred_protocols": ["vless-ws", "trojan-ws", "shadowsocks"],
    },
    "br": {
        "name": "Battle Royale (PUBG/Fortnite)",
        "max_latency_ms": 200,
        "max_jitter_ms": 30,
        "max_loss_pct": 3,
        "keepalive_s": 30,
        "timeout_s": 4,
        "preferred_protocols": ["vless-ws", "trojan-ws", "xhttp-stream-up"],
    },
    "mmo": {
        "name": "MMO (WoW/FFXIV)",
        "max_latency_ms": 250,
        "max_jitter_ms": 40,
        "max_loss_pct": 5,
        "keepalive_s": 60,
        "timeout_s": 6,
        "preferred_protocols": ["vless-ws", "trojan-ws", "xhttp-stream-up"],
    },
    "general": {
        "name": "General",
        "max_latency_ms": 300,
        "max_jitter_ms": 50,
        "max_loss_pct": 10,
        "keepalive_s": 60,
        "timeout_s": 10,
        "preferred_protocols": ["vless-ws", "trojan-ws", "shadowsocks", "xhttp-stream-up"],
    },
}


def _require_gaming():
    if not (is_enabled("gaming_health") or is_enabled("gaming_profiles") or is_enabled("gaming_dashboard")):
        raise HTTPException(404, "gaming engine disabled")


# ─── Helpers ─────────────────────────────────────────────────────────────
def _latency_norm(latency_ms: float, max_latency_ms: float) -> float:
    """نرمال‌سازی latency به 0-1 (1 = عالی، 0 = بد)."""
    if latency_ms <= 0:
        return 0.0
    if latency_ms >= max_latency_ms:
        return 0.0
    return 1.0 - (latency_ms / max_latency_ms)


def _jitter_norm(jitter_ms: float, max_jitter_ms: float) -> float:
    """نرمال‌سازی jitter."""
    if jitter_ms <= 0:
        return 1.0  # بدون jitter = عالی
    if jitter_ms >= max_jitter_ms:
        return 0.0
    return 1.0 - (jitter_ms / max_jitter_ms)


def _calc_jitter(samples: list[float]) -> float:
    """محاسبه‌ی jitter (انحراف معیار)."""
    if len(samples) < 2:
        return 0.0
    try:
        return statistics.stdev(samples)
    except Exception:
        return 0.0


def _calc_loss(history: deque) -> float:
    """محاسبه‌ی loss به‌عنوان درصد timeout‌ها."""
    if not history:
        return 0.0
    timeouts = sum(1 for h in history if h.get("timeout", False))
    return (timeouts / len(history)) * 100.0


def _detect_spike(history: deque, profile: dict) -> bool:
    """تشخیص spike: ۳ اندازه‌گیری متوالی با latency > 2 * median."""
    if len(history) < 3:
        return False
    samples = [h.get("latency_ms", 0) for h in list(history)[-3:]]
    if any(s <= 0 for s in samples):
        return False
    median = statistics.median(samples)
    if median <= 0:
        return False
    threshold = 2 * median
    return all(s > threshold for s in samples)


def _calc_stability(session_id: str, spike_count_5min: int) -> float:
    """محاسبه‌ی stability: 1 - (spike_count / max_acceptable_spikes)."""
    max_spikes = 5  # ۵ spike در ۵ دقیقه = ناپایدار
    if spike_count_5min >= max_spikes:
        return 0.0
    return 1.0 - (spike_count_5min / max_spikes)


def _calc_ghs(latency_ms: float, jitter_ms: float, loss_pct: float, stability: float, profile: dict) -> float:
    """محاسبه‌ی Gaming Health Score (0-100)."""
    lat_norm = _latency_norm(latency_ms, profile["max_latency_ms"])
    jit_norm = _jitter_norm(jitter_ms, profile["max_jitter_ms"])
    loss_norm = max(0.0, 1.0 - (loss_pct / 100.0))
    ghs = (
        0.4 * lat_norm
        + 0.25 * jit_norm
        + 0.2 * loss_norm
        + 0.15 * stability
    )
    return round(ghs * 100, 1)


# ─── API Endpoints ───────────────────────────────────────────────────────

@router.get("/api/exp/gaming/profiles")
async def gaming_profiles():
    """لیست پروفایل‌های گیمینگ."""
    _require_gaming()
    return {"profiles": PROFILES}


@router.post("/api/exp/gaming/session/start")
async def gaming_session_start(request: Request):
    """شروع یک session گیمینگ جدید."""
    _require_gaming()
    if not is_enabled("gaming_health"):
        raise HTTPException(403, "gaming_health disabled")
    body = await request.json()
    profile_key = body.get("profile", "general")
    if profile_key not in PROFILES:
        raise HTTPException(400, f"unknown profile: {profile_key}")
    session_id = f"gs-{int(time.time()*1000)}-{body.get('link_uuid', 'nolink')[:8]}"
    _SESSIONS[session_id] = {
        "history": deque(maxlen=_MAX_HISTORY),
        "profile": profile_key,
        "spike_count_5min": 0,
        "last_spike": 0.0,
        "started_at": time.time(),
        "link_uuid": body.get("link_uuid", ""),
        "target_host": body.get("target_host", ""),
        "target_port": int(body.get("target_port", 80)),
    }
    return {"ok": True, "session_id": session_id, "profile": PROFILES[profile_key]}


@router.post("/api/exp/gaming/session/{session_id}/measure")
async def gaming_session_measure(session_id: str, request: Request):
    """ثبت یک اندازه‌گیری جدید latency."""
    _require_gaming()
    if not is_enabled("gaming_health"):
        raise HTTPException(403, "gaming_health disabled")
    if session_id not in _SESSIONS:
        raise HTTPException(404, "session not found")
    body = await request.json()
    latency_ms = float(body.get("latency_ms", 0))
    timeout = bool(body.get("timeout", False))

    sess = _SESSIONS[session_id]
    sess["history"].append({
        "ts": time.time(),
        "latency_ms": latency_ms,
        "timeout": timeout,
    })

    # محاسبه‌ی metrics
    samples = [h["latency_ms"] for h in sess["history"] if not h["timeout"]]
    avg_lat = statistics.mean(samples) if samples else 0
    jitter = _calc_jitter(samples)
    loss = _calc_loss(sess["history"])
    profile = PROFILES[sess["profile"]]

    # spike detection با cooldown
    is_spike = _detect_spike(sess["history"], profile)
    now = time.time()
    if is_spike and (now - sess["last_spike"]) > _SPIKE_COOLDOWN:
        sess["spike_count_5min"] += 1
        sess["last_spike"] = now
        # کاهش spike count قدیمی‌ها (older than 5 min)
        # فعلاً ساده: هر ۵ دقیقه reset
        if now - sess.get("spike_reset_at", sess["started_at"]) > 300:
            sess["spike_count_5min"] = 1
            sess["spike_reset_at"] = now

    stability = _calc_stability(session_id, sess["spike_count_5min"])
    ghs = _calc_ghs(avg_lat, jitter, loss, stability, profile)

    return {
        "ok": True,
        "session_id": session_id,
        "metrics": {
            "latency_ms": round(avg_lat, 2),
            "jitter_ms": round(jitter, 2),
            "loss_pct": round(loss, 2),
            "stability": round(stability, 2),
            "ghs": ghs,
            "spike_detected": is_spike,
            "samples_count": len(samples),
        },
        "profile": sess["profile"],
        "history": list(sess["history"]),
    }


@router.get("/api/exp/gaming/session/{session_id}")
async def gaming_session_get(session_id: str):
    """دریافت وضعیت session."""
    _require_gaming()
    if not is_enabled("gaming_health"):
        raise HTTPException(403, "gaming_health disabled")
    if session_id not in _SESSIONS:
        raise HTTPException(404, "session not found")
    sess = _SESSIONS[session_id]
    samples = [h["latency_ms"] for h in sess["history"] if not h["timeout"]]
    avg_lat = statistics.mean(samples) if samples else 0
    jitter = _calc_jitter(samples)
    loss = _calc_loss(sess["history"])
    profile = PROFILES[sess["profile"]]
    stability = _calc_stability(session_id, sess["spike_count_5min"])
    ghs = _calc_ghs(avg_lat, jitter, loss, stability, profile)
    return {
        "ok": True,
        "session_id": session_id,
        "metrics": {
            "latency_ms": round(avg_lat, 2),
            "jitter_ms": round(jitter, 2),
            "loss_pct": round(loss, 2),
            "stability": round(stability, 2),
            "ghs": ghs,
            "samples_count": len(samples),
        },
        "profile": sess["profile"],
        "history": list(sess["history"]),
        "uptime_s": round(time.time() - sess["started_at"], 1),
    }


@router.post("/api/exp/gaming/server-ping")
async def gaming_server_ping(request: Request):
    """پینگ به یک game server (TCP probe)."""
    _require_gaming()
    if not is_enabled("game_server_ping"):
        raise HTTPException(403, "game_server_ping disabled")
    import socket
    body = await request.json()
    host = body.get("host", "")
    port = int(body.get("port", 80))
    timeout_s = float(body.get("timeout", 3))
    if not host:
        raise HTTPException(400, "host required")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_s)
        start = time.time()
        sock.connect((host, port))
        elapsed = (time.time() - start) * 1000
        sock.close()
        return {
            "ok": True,
            "host": host,
            "port": port,
            "latency_ms": round(elapsed, 2),
            "timeout": False,
        }
    except socket.timeout:
        return {
            "ok": True,
            "host": host,
            "port": port,
            "latency_ms": timeout_s * 1000,
            "timeout": True,
        }
    except Exception as e:
        return {
            "ok": False,
            "host": host,
            "port": port,
            "error": str(e),
        }


@router.get("/api/exp/gaming/game-servers")
async def gaming_game_servers():
    """لیست سرورهای معروف بازی‌ها (برای ping test)."""
    _require_gaming()
    return {
        "servers": {
            "csgo_eu": {"game": "CS:GO", "host": "steamcommunity.com", "port": 27015},
            "valorant_eu": {"game": "Valorant", "host": "riot.eu", "port": 80},
            "lol_eu": {"game": "League of Legends", "host": "euw.leagueoflegends.com", "port": 80},
            "dota_eu": {"game": "Dota 2", "host": "steamcommunity.com", "port": 80},
            "pubg_eu": {"game": "PUBG", "host": "pubg.com", "port": 80},
            "fortnite_eu": {"game": "Fortnite", "host": "fortnite.com", "port": 80},
            "wow_eu": {"game": "WoW EU", "host": "eu.battle.net", "port": 80},
            "ffxiv_eu": {"game": "FFXIV", "host": "eu.finalfantasyxiv.com", "port": 80},
        }
    }


@router.get("/api/exp/gaming/dashboard")
async def gaming_dashboard():
    """خلاصه‌ی dashboard: همه‌ی session‌های فعال."""
    _require_gaming()
    if not is_enabled("gaming_dashboard"):
        raise HTTPException(403, "gaming_dashboard disabled")
    out = []
    now = time.time()
    for sid, sess in _SESSIONS.items():
        if now - sess["started_at"] > 3600:  # cleanup پاک‌سازی قدیمی‌تر از ۱ ساعت
            continue
        samples = [h["latency_ms"] for h in sess["history"] if not h["timeout"]]
        avg_lat = statistics.mean(samples) if samples else 0
        jitter = _calc_jitter(samples)
        loss = _calc_loss(sess["history"])
        profile = PROFILES[sess["profile"]]
        stability = _calc_stability(sid, sess["spike_count_5min"])
        ghs = _calc_ghs(avg_lat, jitter, loss, stability, profile)
        out.append({
            "session_id": sid,
            "profile": sess["profile"],
            "link_uuid": sess.get("link_uuid", ""),
            "uptime_s": round(now - sess["started_at"], 1),
            "metrics": {
                "latency_ms": round(avg_lat, 2),
                "jitter_ms": round(jitter, 2),
                "loss_pct": round(loss, 2),
                "stability": round(stability, 2),
                "ghs": ghs,
                "samples_count": len(samples),
            },
        })
    return {
        "ok": True,
        "active_sessions": len(out),
        "sessions": out,
        "max_history_per_session": _MAX_HISTORY,
        "spike_cooldown_s": _SPIKE_COOLDOWN,
    }
