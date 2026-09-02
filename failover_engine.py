# failover_engine.py — Real Failover with Drain / Verify / Explain (Phase 38 / P1)
# ══════════════════════════════════════════════════════════════════════════════
# A failover is ONLY successful when the replacement route is actually usable.
#
# Pipeline (never blind):
#   1. stop assigning NEW configs/connections to the failing node
#   2. node enters DRAINING (existing traffic continues, new traffic stops)
#   3. select a replacement via EXPLAINABLE scoring (ranking_reason[])
#   4. verify replacement health     (node_manager: ONLINE, runtime-gated)
#   5. verify the route              (egress_engine 9-step validation)
#   6. verify egress where possible  (VERIFIED_EGRESS classification)
#   7. re-point routes and resume new assignments → FAILOVER_SUCCESS
#
# Verdicts: FAILOVER_SUCCESS | FAILOVER_FAILED | FAILOVER_NO_REPLACEMENT
#           (a failed failover KEEPS the old node drained — never fails back
#            silently to a bad node)
#
# Node scoring is pure and unit-testable; metric providers are injectable.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Callable

import node_manager as nm
import egress_engine as ee
import route_engine as re_eng

FAILOVER_ENGINE_VERSION = "1.0.0"

FAILOVER_VERDICTS = ("FAILOVER_SUCCESS", "FAILOVER_FAILED", "FAILOVER_NO_REPLACEMENT")

FAILOVER_HISTORY_BOUND = 50            # bounded memory of failover records

# Weights for explainable scoring (sum = 100)
SCORE_WEIGHTS = {
    "health": 25,
    "latency": 15,
    "jitter": 5,
    "packet_loss": 10,
    "load": 10,
    "egress_quality": 15,
    "country_match": 8,
    "asn_match": 4,
    "protocol_compatibility": 5,
    "historical_stability": 3,
}


@dataclass
class FailoverRecord:
    failed_node: str
    reason: str
    verdict: str = "FAILOVER_FAILED"
    replacement_node: Optional[str] = None
    ranking_reason: List[str] = field(default_factory=list)
    steps: List[dict] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["duration_s"] = (round(self.finished_at - self.started_at, 2)
                           if self.finished_at else None)
        return d


_history: List[dict] = []
_lock = asyncio.Lock()
_route_repoint_fn: Optional[Callable] = None      # DI seam for re-pointing routes


def set_route_repoint_fn(fn: Callable) -> None:
    """Inject the function that re-points live routes to a new exit node."""
    global _route_repoint_fn
    _route_repoint_fn = fn


def failover_history() -> List[dict]:
    return list(_history)


def reset_for_tests() -> None:
    _history.clear()
    global _route_repoint_fn
    _route_repoint_fn = None


# ── Explainable node scoring (pure) ─────────────────────────────────────────

def score_node(candidate: dict, requirements: Optional[dict] = None,
               metrics: Optional[dict] = None) -> tuple[float, List[str]]:
    """Score a candidate node 0-100 with human-readable ranking reasons.

    candidate : node_manager.to_dict() shape (state, load, capabilities, kind…)
    requirements: {country, asn, protocol, node_id_exclude}
    metrics  : {latency_ms, jitter_ms, packet_loss_pct, stability_0_100}
               — when absent, the factor scores 0 with an explicit reason
               (UNKNOWN never masquerades as good).
    """
    requirements = requirements or {}
    metrics = metrics or {}
    reasons: List[str] = []
    score = 0.0

    state = candidate.get("effective_state") or candidate.get("state") or "UNKNOWN"
    if state == "ONLINE":
        score += SCORE_WEIGHTS["health"]; reasons.append("+ ONLINE (runtime-verified)")
    elif state == "DEGRADED":
        score += SCORE_WEIGHTS["health"] * 0.4; reasons.append("+ DEGRADED (partial credit)")
    elif state == "DRAINING":
        reasons.append("- DRAINING (no new assignments)")
    elif state == "MAINTENANCE":
        reasons.append("- MAINTENANCE (operator override)")
    elif state == "QUARANTINED":
        reasons.append("- QUARANTINED (suspicious egress/behavior)")
    else:
        reasons.append(f"- state {state} (not eligible)")

    lat = metrics.get("latency_ms")
    if lat is None:
        reasons.append("? latency UNKNOWN")
    elif lat <= 0:
        pass
    else:
        # 30ms→full credit, 300ms→0
        pts = SCORE_WEIGHTS["latency"] * max(0.0, min(1.0, (300 - lat) / 270))
        score += pts; reasons.append(f"+ {int(lat)}ms latency")

    jit = metrics.get("jitter_ms")
    if jit is not None and jit >= 0:
        pts = SCORE_WEIGHTS["jitter"] * max(0.0, min(1.0, (50 - jit) / 50))
        score += pts; reasons.append(f"+ {jit:.1f}ms jitter")

    loss = metrics.get("packet_loss_pct")
    if loss is None:
        reasons.append("? packet loss UNKNOWN")
    else:
        pts = SCORE_WEIGHTS["packet_loss"] * max(0.0, min(1.0, (5 - loss) / 5))
        score += pts; reasons.append(f"+ {loss:.2f}% packet loss")

    load = candidate.get("load")
    if load is None:
        reasons.append("? load UNKNOWN")
    else:
        pts = SCORE_WEIGHTS["load"] * max(0.0, (100 - float(load)) / 100)
        score += pts; reasons.append(f"+ load {int(load)}%")

    # egress quality from MEASURED evidence only
    ev = metrics.get("egress") or {}
    cls = metrics.get("egress_classification") or ev.get("classification")
    if cls == "VERIFIED_EGRESS":
        score += SCORE_WEIGHTS["egress_quality"]
        reasons.append("+ VERIFIED egress evidence")
    elif cls == "CONFIGURED_ONLY":
        score += SCORE_WEIGHTS["egress_quality"] * 0.3
        reasons.append("+ CONFIGURED_ONLY egress (unverified, partial credit)")
    else:
        reasons.append("? egress UNKNOWN")

    want_country = (requirements.get("country") or "").strip().lower()
    if want_country:
        obs = (ev.get("country") or "").strip().lower()
        if obs == want_country and cls == "VERIFIED_EGRESS":
            score += SCORE_WEIGHTS["country_match"]
            reasons.append(f"+ country match {want_country} (verified)")
        else:
            reasons.append(f"- country {want_country} not verified for this node")

    want_asn = (requirements.get("asn") or "").strip()
    if want_asn:
        obs = (ev.get("asn") or "").strip()
        if obs == want_asn:
            score += SCORE_WEIGHTS["asn_match"]
            reasons.append(f"+ ASN match {want_asn}")

    proto = requirements.get("protocol")
    if proto:
        caps = candidate.get("capabilities") or []
        if proto in caps or any(c.startswith(proto) for c in caps):
            score += SCORE_WEIGHTS["protocol_compatibility"]
            reasons.append(f"+ compatible with {proto}")
        else:
            reasons.append(f"- no capability {proto}")

    # Phase 38+ §15: transport compatibility — never silently switch to a node
    # that cannot carry the required transport (explicit UNSUPPORTED reason).
    want_transport = (requirements.get("transport") or "").strip()
    if want_transport:
        import compat as _compat
        served_transports = set()
        for fused in (candidate.get("capabilities") or []):
            _p, _t = _compat.decompose(fused)
            if _t:
                served_transports.add(_t)
        if want_transport in served_transports:
            reasons.append(f"+ serves transport {want_transport}")
        else:
            reasons.append(f"UNSUPPORTED_NODE_TRANSPORT: node carries "
                           f"{sorted(served_transports) or 'no relevant capability'} — "
                           f"required {want_transport}")

    stab = metrics.get("stability_0_100")
    if stab is None:
        reasons.append("? historical stability UNKNOWN")
    else:
        score += SCORE_WEIGHTS["historical_stability"] * max(0.0, min(1.0, stab / 100))
        reasons.append(f"+ stability {int(stab)}/100")

    return round(max(0.0, min(100.0, score)), 1), reasons


async def select_replacement(exclude_node: str,
                             requirements: Optional[dict] = None) -> Optional[dict]:
    """Pick the best replacement among ONLINE (or DEGRADED) nodes.

    Returns {"node_id", "score", "ranking_reason[]", "candidate"} or None."""
    requirements = dict(requirements or {})
    requirements["node_id_exclude"] = exclude_node
    scored = []
    for cand in nm.list_nodes():
        if cand.get("id") == exclude_node:
            continue
        state = cand.get("effective_state") or cand.get("state")
        if state not in ("ONLINE", "DEGRADED"):
            continue
        # Phase 38+ §15 hard gates — incompatible nodes are NEVER selected
        # (no amount of health/latency score can override capability reality)
        want_proto = (requirements.get("protocol") or "").strip()
        caps = cand.get("capabilities") or []
        if want_proto and not any(
                c == want_proto or c.startswith(want_proto + "-")
                or want_proto in c for c in caps):
            continue        # UNSUPPORTED_NODE_PROTOCOL — silently incompatible
        want_transport = (requirements.get("transport") or "").strip()
        if want_transport:
            import compat as _compat
            served = {_compat.decompose(c)[1] for c in caps}
            served.discard("")
            if want_transport not in served:
                continue    # UNSUPPORTED_NODE_TRANSPORT
        want_role = (requirements.get("role") or "").strip()
        if want_role and want_role == "EXIT_NODE":
            # only nodes with verified egress may serve as exit replacements
            _nid = cand.get("id")
            _ev = ee.evidence_for(f"node:{_nid}") or ee.evidence_for(f"loc:{_nid}")
            if not (_ev and _ev.get("valid")):
                continue    # NO_VERIFIED_EGRESS
        node_id = cand.get("id")
        metrics: Dict[str, object] = {}
        ev = ee.evidence_for(f"node:{node_id}") or ee.evidence_for(f"loc:{node_id}")
        if ev:
            metrics["egress"] = ev
            metrics["egress_classification"] = (
                "VERIFIED_EGRESS" if ev.get("valid") else "CONFIGURED_ONLY")
        score, reasons = score_node(cand, requirements, metrics)
        scored.append({"node_id": node_id, "score": score,
                       "ranking_reason": reasons, "candidate": cand})
    if not scored:
        return None
    scored.sort(key=lambda s: -s["score"])
    return scored[0]


# ── The failover pipeline (7 steps, never blind) ────────────────────────────

async def failover(node_id: str, reason: str = "unhealthy",
                   requirements: Optional[dict] = None,
                   verify: bool = True) -> dict:
    """Execute the full failover pipeline. Returns a FailoverRecord dict."""
    requirements = requirements or {}
    rec = FailoverRecord(failed_node=node_id, reason=reason)
    step = lambda n, ok, detail: rec.steps.append(
        {"step": n, "ok": ok, "detail": detail, "at": time.time()})
    try:
        import structured_events as events
        events.log_event("FAILOVER_TRIGGERED", severity="WARNING",
                         node=node_id, reason=reason,
                         protocol=requirements.get("protocol", ""),
                         transport=requirements.get("transport", ""))
    except Exception:
        pass

    # 1+2. stop NEW assignments → DRAINING
    drained = await nm.set_draining(node_id, True, reason=f"failover: {reason}")
    step("drain", drained is not None,
         "node DRAINING — no new configs/connections assigned" if drained else "node not registered")
    if drained is None:
        rec.verdict = "FAILOVER_FAILED"
        rec.finished_at = time.time()
        await _record(rec)
        return rec.to_dict()

    # 3. select replacement (explainable)
    replacement = await select_replacement(node_id, requirements)
    if replacement is None:
        step("select_replacement", False, "no eligible replacement node")
        rec.verdict = "FAILOVER_NO_REPLACEMENT"
        rec.finished_at = time.time()
        await _record(rec)
        return rec.to_dict()
    rec.replacement_node = replacement["node_id"]
    rec.ranking_reason = replacement["ranking_reason"]
    step("select_replacement", True,
         f"{replacement['node_id']} selected (score {replacement['score']})")

    rep_id = replacement["node_id"]
    rep_cand = replacement["candidate"]

    # 4. verify replacement health (runtime-gated state)
    healthy = (rep_cand.get("effective_state") or rep_cand.get("state")) == "ONLINE"
    if verify:
        re_eval = await nm.evaluate_runtime_health(rep_id)
        healthy = bool(re_eval and (re_eval.get("state") == "ONLINE"))
    step("verify_replacement_health", healthy,
         "replacement ONLINE (runtime-verified)" if healthy
         else f"replacement state {rep_cand.get('state')}")

    # 5+6. verify route + egress where possible
    route_usable = healthy
    if healthy and verify:
        target = requirements.get("location") or rep_id
        verdict = await ee.validate_route(location=str(target))
        rh = verdict.get("route_health", "UNKNOWN")
        cls = verdict.get("egress", {}).get("classification", "UNKNOWN")
        route_usable = rh in ("HEALTHY", "DEGRADED") and cls != "UNKNOWN"
        step("verify_route", route_usable, f"route health={rh}, egress={cls}")
    else:
        step("verify_route", False, "skipped (replacement unhealthy)")

    # 7. re-point routes + resume
    if route_usable and _route_repoint_fn is not None:
        try:
            await _route_repoint_fn(node_id, rep_id)
            step("repoint_routes", True, f"routes re-pointed {node_id} → {rep_id}")
        except Exception as exc:
            route_usable = False
            step("repoint_routes", False, f"re-point error: {exc}")

    if route_usable:
        await nm.set_draining(node_id, False, reason="failover complete — recovered")
        await nm.set_draining(rep_id, False, reason="replacement active")
        rec.verdict = "FAILOVER_SUCCESS"
        step("resume_assignments", True, "new assignments resumed on replacement")
    else:
        # failed failover: old node stays drained, replacement NOT activated
        rec.verdict = "FAILOVER_FAILED"
        step("resume_assignments", False,
             "replacement route NOT usable — node stays drained (no blind failback)")

    rec.finished_at = time.time()
    await _record(rec)
    return rec.to_dict()


async def _record(rec: FailoverRecord) -> None:
    async with _lock:
        _history.append(rec.to_dict())
        del _history[:-FAILOVER_HISTORY_BOUND]


def summary() -> dict:
    verdicts: Dict[str, int] = {}
    for h in _history:
        verdicts[h.get("verdict", "?")] = verdicts.get(h.get("verdict", "?"), 0) + 1
    return {"failovers": len(_history), "by_verdict": verdicts,
            "history_bound": FAILOVER_HISTORY_BOUND,
            "engine": f"failover_engine/{FAILOVER_ENGINE_VERSION}"}


# ── API surface ─────────────────────────────────────────────────────────────

def register_routes(app, require_auth) -> None:
    from fastapi import Depends, Query
    from fastapi.responses import JSONResponse

    @app.post("/api/failover/{node_id}", dependencies=[Depends(require_auth)])
    async def api_failover(node_id: str, reason: str = Query("manual failover")):
        return await failover(node_id, reason=reason)

    @app.get("/api/failover/history", dependencies=[Depends(require_auth)])
    async def api_failover_history():
        return {"history": failover_history(), "summary": summary()}

    @app.get("/api/failover/summary", dependencies=[Depends(require_auth)])
    async def api_failover_summary():
        return summary()
