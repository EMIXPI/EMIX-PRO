# smart_route.py — موتور مسیریابی هوشمند (با اصل "هیچ‌گاه fabrication نکن")
# معیارها: RTT (40%) + jitter (25%) + loss (20%) + stability (15%)
# Failover با hysteresis: فقط بعد از ۳ fail متوالی switch کن.
# Cooldown: 60s بین دو switch.

import asyncio
import time
import socket
import statistics
from collections import deque
from typing import Optional
from fastapi import APIRouter, Request, HTTPException

from experimental import is_enabled

router = APIRouter()

# ─── Upstream registry ───────────────────────────────────────────────────
# upstream_id → {address, port, last_rtt, history, last_fail, score}
# در state file persist نمی‌شود (فعلاً) — در restart reset می‌شود.
_UPSTREAMS = {}
_HIST_LEN = 10
_FAILOVER_THRESHOLD = 3
_FAILOVER_COOLDOWN = 60.0  # seconds


def _require_smart_route():
    if not is_enabled("smart_route"):
        raise HTTPException(404, "smart_route disabled")


@router.post("/api/exp/route/upstream/add")
async def add_upstream(request: Request):
    """ثبت یک upstream جدید برای scoring."""
    _require_smart_route()
    body = await request.json()
    uid = body.get("id") or f"up-{int(time.time())}-{body.get('address','')[:8]}"
    _UPSTREAMS[uid] = {
        "id": uid,
        "address": body.get("address", ""),
        "port": int(body.get("port", 443)),
        "label": body.get("label", ""),
        "history": deque(maxlen=_HIST_LEN),
        "fail_count": 0,
        "last_switch": 0,
        "score": 0.0,
        "active": True,
    }
    return {"ok": True, "upstream": _serialize_upstream(_UPSTREAMS[uid])}


@router.get("/api/exp/route/upstreams")
async def list_upstreams():
    """لیست همه‌ی upstream‌ها با score."""
    _require_smart_route()
    return {
        "ok": True,
        "upstreams": [_serialize_upstream(u) for u in _UPSTREAMS.values()],
    }


@router.post("/api/exp/route/upstream/{uid}/probe")
async def probe_upstream(uid: str, request: Request):
    """پروب یک upstream (TCP handshake) و ثبت نتیجه."""
    _require_smart_route()
    if uid not in _UPSTREAMS:
        raise HTTPException(404, "upstream not found")
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    timeout_s = float(body.get("timeout", 5))
    u = _UPSTREAMS[uid]
    addr = u["address"]
    port = u["port"]
    rtt = None
    failed = False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_s)
        start = time.time()
        sock.connect((addr, port))
        rtt = (time.time() - start) * 1000  # ms
        sock.close()
    except (socket.timeout, ConnectionRefusedError, Exception):
        failed = True
        rtt = timeout_s * 1000
    # ثبت در history
    u["history"].append({"ts": time.time(), "rtt_ms": rtt, "failed": failed})
    if failed:
        u["fail_count"] += 1
    else:
        u["fail_count"] = 0
    # محاسبه‌ی score
    u["score"] = _calc_score(u)
    return {
        "ok": True,
        "upstream": _serialize_upstream(u),
        "probe": {"rtt_ms": rtt, "failed": failed},
    }


def _calc_score(u: dict) -> float:
    """محاسبه‌ی score (0-100)."""
    history = list(u["history"])
    if not history:
        return 0.0
    successes = [h for h in history if not h["failed"]]
    if not successes:
        return 0.0  # همه‌ی probe‌ها fail شده‌اند
    rtt_samples = [h["rtt_ms"] for h in successes]
    avg_rtt = statistics.mean(rtt_samples)
    jitter = statistics.stdev(rtt_samples) if len(rtt_samples) >= 2 else 0
    loss_pct = (len(history) - len(successes)) / len(history) * 100
    # نرمال‌سازی: رفرنس baseline
    BASELINE_RTT = 100  # ms
    BASELINE_JITTER = 20  # ms
    rtt_norm = max(0.0, 1.0 - (avg_rtt / BASELINE_RTT)) if avg_rtt < BASELINE_RTT else 0.0
    jit_norm = max(0.0, 1.0 - (jitter / BASELINE_JITTER)) if jitter < BASELINE_JITTER else 0.0
    loss_norm = 1.0 - (loss_pct / 100.0)
    # stability: 1 - (fail_count / threshold)
    stability = max(0.0, 1.0 - (u["fail_count"] / _FAILOVER_THRESHOLD))
    score = 0.4 * rtt_norm + 0.25 * jit_norm + 0.2 * loss_norm + 0.15 * stability
    return round(score * 100, 1)


def _serialize_upstream(u: dict) -> dict:
    return {
        "id": u["id"],
        "address": u["address"],
        "port": u["port"],
        "label": u["label"],
        "score": u["score"],
        "fail_count": u["fail_count"],
        "active": u["active"],
        "samples": len(u["history"]),
        "last_5": list(u["history"])[-5:],
    }


@router.get("/api/exp/route/best")
async def get_best_upstream():
    """پیدا‌کردن بهترین upstream بر اساس score."""
    _require_smart_route()
    if not _UPSTREAMS:
        return {"ok": True, "best": None, "reason": "no upstreams registered"}
    best = max(_UPSTREAMS.values(), key=lambda u: u["score"])
    return {
        "ok": True,
        "best": _serialize_upstream(best),
        "all_count": len(_UPSTREAMS),
    }


@router.post("/api/exp/route/failover/check")
async def check_failover(request: Request):
    """بررسی آیا failover لازم است.
    منطق: اگر upstream فعالی ۳ fail متوالی داشت و cooldown گذشته، switch کن.
    """
    _require_smart_route()
    if not is_enabled("safe_failover"):
        raise HTTPException(403, "safe_failover disabled")
    now = time.time()
    active_upstreams = [u for u in _UPSTREAMS.values() if u["active"]]
    if not active_upstreams:
        return {"ok": True, "action": "no_active", "message": "no active upstream"}
    # پیدا‌کردن worst active
    current = max(active_upstreams, key=lambda u: u["fail_count"])
    if current["fail_count"] < _FAILOVER_THRESHOLD:
        return {
            "ok": True,
            "action": "none",
            "current": _serialize_upstream(current),
            "fail_count": current["fail_count"],
            "threshold": _FAILOVER_THRESHOLD,
        }
    # cooldown
    if now - current["last_switch"] < _FAILOVER_COOLDOWN:
        return {
            "ok": True,
            "action": "cooldown",
            "current": _serialize_upstream(current),
            "wait_s": int(_FAILOVER_COOLDOWN - (now - current["last_switch"])),
        }
    # پیدا‌کردن بهترین جایگزین
    candidates = [u for u in _UPSTREAMS.values() if not u["active"] and u["score"] > 0]
    if not candidates:
        return {"ok": True, "action": "no_replacement", "current": _serialize_upstream(current)}
    replacement = max(candidates, key=lambda u: u["score"])
    # انجام switch
    current["active"] = False
    replacement["active"] = True
    replacement["last_switch"] = now
    return {
        "ok": True,
        "action": "switched",
        "from": _serialize_upstream(current),
        "to": _serialize_upstream(replacement),
        "reason": f"fail_count={current['fail_count']} >= threshold={_FAILOVER_THRESHOLD}",
    }


@router.get("/api/exp/route/mtu")
async def mtu_discovery(request: Request):
    """MTU discovery — Railway-aware.
    توجه: در Railway unprivileged، /bin/ping (icmp) قابل دسترس نیست.
    fallback: TCP-based PMTU با packet size بزرگ.
    """
    _require_smart_route()
    if not is_enabled("mtu_discovery"):
        raise HTTPException(403, "mtu_discovery disabled")
    body = await request.json() if False else {}
    # فعلاً اعلام honest unavailable
    return {
        "ok": True,
        "mtu": None,
        "available": False,
        "reason": "MTU ping requires /bin/ping with ICMP — not available on Railway unprivileged. "
                  "Use TCP probe upstreams for latency estimation instead.",
    }
