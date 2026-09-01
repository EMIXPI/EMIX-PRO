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


# ══════════════════════════════════════════════════════════════════════════════
# Smart Route v3 — health-weighted CONFIG ranking (Phase 8 + Phase 37.12)
#
# v1 ranks manually-registered upstreams. v2 ranked configs by health score.
# v3 is EXPLAINABLE and multi-factor:
#
#   rank = composite of
#     health state       (HEALTHY 100 / DEGRADED 60 / UNKNOWN 30 / … 0)
#     health score       (network_health v2 weighted formula)
#     latency            (real probe e2e_ms, capped)
#     jitter             (real probe stdev)
#     loss               (real probe loss_pct)
#     node state         (node_manager: ONLINE/DEGRADED/OFFLINE/…)
#     node load          (0-100 when known)
#     protocol capability(PRODUCTION protocol = full weight; others demoted)
#     reliability        (probe sample count — more evidence = more trust)
#
# Every row carries `ranking_reason` with the ACTUAL numbers behind the
# decision — never a generic string. Expired health evidence downgrades to
# UNKNOWN (never stale-HEALTHY). Pure function rank_rows() is unit-tested.
# ══════════════════════════════════════════════════════════════════════════════

import network_health as _nh

_HEALTH_WEIGHT = {"HEALTHY": 100.0, "DEGRADED": 60.0, "UNKNOWN": 30.0,
                  "UNREACHABLE": 5.0, "INVALID": 0.0}
_NODE_WEIGHT = {"ONLINE": 1.0, "REGISTER": 0.6, "DEGRADED": 0.5,
                "OFFLINE": 0.0, "MAINTENANCE": 0.0}
_LAT_CAP = 2000.0
_JITTER_CAP = 300.0


def _factor_health(row):
    state = row.get("health_state") or "UNKNOWN"
    return _HEALTH_WEIGHT.get(state, 30.0), state


def _factor_latency(row):
    lat = row.get("latency_ms")
    if lat is None:
        return 0.0, None
    return max(0.0, 1.0 - min(lat, _LAT_CAP) / _LAT_CAP) * 100.0, lat


def _factor_jitter(row):
    j = row.get("jitter_ms")
    if j is None:
        return 0.0, None
    return max(0.0, 1.0 - min(j, _JITTER_CAP) / _JITTER_CAP) * 100.0, j


def _factor_loss(row):
    l = row.get("loss_pct")
    if l is None:
        return 0.0, None
    return max(0.0, 100.0 - min(l, 100.0)), l


def _factor_reliability(row):
    n = row.get("samples") or 0
    return min(100.0, n * 20.0), n  # 5+ samples = full reliability weight


def _factor_capability(row):
    protocol = row.get("protocol", "")
    p = protocol.split("-")[0]
    readiness = {"vless": "PRODUCTION", "trojan": "PRODUCTION",
                 "shadowsocks": "PRODUCTION", "mtproto": "PRODUCTION"}.get(p, "")
    return (100.0 if readiness == "PRODUCTION" else 40.0), readiness or "UNKNOWN"


def rank_rows(rows):
    """PURE: compute composite score + explainable ranking_reason per row.

    weights: health 0.30, score 0.20, latency 0.15, jitter 0.10, loss 0.10,
    node 0.10, reliability 0.05, capability ×node_factor (multiplicative gate)
    """
    out = []
    for row in rows:
        health_f, state = _factor_health(row)
        lat_f, lat = _factor_latency(row)
        jit_f, jit = _factor_jitter(row)
        loss_f, loss = _factor_loss(row)
        rel_f, samples = _factor_reliability(row)
        cap_f, readiness = _factor_capability(row)
        node_state = row.get("node_state") or "UNKNOWN"
        node_factor = _NODE_WEIGHT.get(node_state, 0.5)
        node_load = row.get("node_load")
        load_f = 100.0
        if node_load is not None:
            if node_load >= 85:
                load_f = 60.0
            elif node_load >= 70:
                load_f = 85.0
        score_f = row.get("score") if row.get("score") is not None else 0.0

        composite = (0.30 * health_f + 0.20 * score_f + 0.15 * lat_f +
                     0.10 * jit_f + 0.10 * loss_f + 0.10 * (load_f * node_factor) +
                     0.05 * rel_f) * node_factor * (cap_f / 100.0)

        parts = [f"Health {state}", f"score {score_f:.0f}" if row.get("score") is not None else "score n/a"]
        if lat is not None:
            parts.append(f"latency {lat:.0f}ms")
        if loss is not None:
            parts.append(f"loss {loss:.0f}%")
        if jit is not None:
            parts.append(f"jitter {jit:.0f}ms")
        if node_state != "UNKNOWN":
            parts.append(f"node {node_state}")
        if node_load is not None:
            parts.append(f"load {node_load:.0f}%")
        parts.append(f"{samples} samples" if samples else "never probed")
        reason = " · ".join(parts) + (f" — {readiness}" if readiness != "PRODUCTION" else "")
        base_reason = (row.get("rank_reason") or "").strip()
        if base_reason:
            reason = f"{base_reason} — {reason}"

        r = dict(row)
        r["composite_score"] = round(composite, 1)
        r["ranking_reason"] = reason
        out.append(r)

    order = {"HEALTHY": 0, "DEGRADED": 1, "UNKNOWN": 2, "UNREACHABLE": 3, "INVALID": 4}
    out.sort(key=lambda r: (
        -r["composite_score"],
        order.get(r.get("health_state"), 5),
        r["latency_ms"] if r.get("latency_ms") is not None else 99999,
    ))
    return out


def _node_context(uid: str, link: dict) -> tuple[str, Optional[float]]:
    """Node state + load for a link's serving node (defaults to the panel node)."""
    try:
        import node_manager
        node_id = link.get("node_id") or "panel"
        rec = node_manager.get_node(node_id)
        if rec is None:
            return "UNKNOWN", None
        state, _ = node_manager.derive_state(rec)
        return state, rec.load
    except Exception:
        return "UNKNOWN", None


@router.get("/api/exp/route/configs/ranked")
async def ranked_configs(_limit: int = 20):
    """All allowed configs ranked by composite health factors (v3, explainable).

    Response rows:
      uid, label, protocol, health_state, score, latency_ms, handshake_ms,
      jitter_ms, loss_pct, samples, node_state, node_load,
      composite_score, rank_reason
    """
    from main import LINKS, LINKS_LOCK, is_link_allowed  # late import — no cycle

    async with LINKS_LOCK:
        targets = {uid: dict(d) for uid, d in LINKS.items()}

    rows = []
    for uid, link in targets.items():
        allowed = is_link_allowed(link)
        rec = _nh.get_health(uid)
        node_state, node_load = _node_context(uid, link)
        if rec is None:
            rows.append({
                "uid": uid, "label": link.get("label", uid[:8]),
                "protocol": link.get("protocol", "vless-ws"),
                "health_state": "INVALID" if not allowed else "UNKNOWN",
                "score": None, "latency_ms": None, "handshake_ms": None,
                "jitter_ms": None, "loss_pct": None, "samples": 0,
                "node_state": node_state, "node_load": node_load,
                "rank_reason": "not allowed" if not allowed else "never probed",
            })
            continue
        if not allowed and rec.state != "INVALID":
            _nh.mark_invalid(uid, link, "config not allowed")
            rec = _nh.get_health(uid)
        rows.append({
            "uid": uid, "label": link.get("label", uid[:8]),
            "protocol": link.get("protocol", "vless-ws"),
            "health_state": rec.effective_state(),
            "score": rec.score, "latency_ms": rec.latency_ms,
            "handshake_ms": rec.handshake_ms, "jitter_ms": rec.jitter_ms,
            "loss_pct": rec.loss_pct, "samples": rec.samples,
            "node_state": node_state, "node_load": node_load,
            "rank_reason": "",
        })

    rows = rank_rows(rows)
    return {
        "ok": True,
        "total": len(rows),
        "ranking": rows[:max(1, _limit)],
        "formula": ("composite = 0.30·health + 0.20·score + 0.15·latency + "
                    "0.10·jitter + 0.10·loss + 0.10·node(load×state) + "
                    "0.05·reliability, ×node_factor ×capability (real probes only)"),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


@router.post("/api/exp/route/configs/probe-all")
async def probe_all_configs():
    """Probe every allowed config through the health engine, then rank."""
    from main import LINKS, LINKS_LOCK, is_link_allowed
    import network_health

    async with LINKS_LOCK:
        targets = [(uid, dict(d)) for uid, d in LINKS.items() if is_link_allowed(d)]
    sem = asyncio.Semaphore(4)

    async def _one(uid: str, link: dict):
        async with sem:
            return await network_health.probe_config(uid, link)

    await asyncio.gather(*[_one(u, d) for u, d in targets]) if targets else None
    return await ranked_configs()
