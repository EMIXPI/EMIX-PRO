# route_engine.py — First-class Route & Egress Abstraction (Phase 38 / P0)
# ══════════════════════════════════════════════════════════════════════════════
# Routing model, made explicit and inspectable:
#
#     Client → Entry node → [Relay node, …] → Exit node → Internet → Egress
#
# Every route is a first-class object with:
#     route_id, entry_node, relay_nodes[], exit_node,
#     expected_country / observed_country,
#     expected_asn / observed_asn,
#     health, latency (labeled measures), packet_loss, jitter,
#     last_verified, verification_state, route_policy
#
# HONESTY RULES (same as egress_engine — this module CONSUMES that engine,
# it never re-probes and never invents):
#   * observed_* fields come ONLY from measured evidence (egress_engine).
#   * expected != observed ⇒ ROUTE_MISMATCH (never masked as HEALTHY).
#   * No exit node ⇒ NO_EXIT_NODE_AVAILABLE.
#   * DIRECT domestic egress is labeled USER_ISP, never a panel/exit IP.
#   * Unknown stays UNKNOWN. Health expires (STALE → revalidation).
#
# Bounded memory: ROUTE_REGISTRY_BOUND routes max (oldest evicted).
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Callable

import egress_engine as ee

ROUTE_ENGINE_VERSION = "1.0.0"

ROUTE_REGISTRY_BOUND = 500          # bounded memory — no unbounded route store
ROUTE_STALE_AFTER_S = 900.0         # routes unverified this long → STALE

# Route policies (public contract; domestic engine extends semantics)
ROUTE_POLICIES = ("ALL_VPN", "IRAN_DIRECT", "CUSTOM")

# Verification states reuse the egress engine taxonomy — never re-invented.
VERIFICATION_STATES = ee.EGRESS_CLASSIFICATIONS          # VERIFIED_EGRESS / CONFIGURED_ONLY / UNKNOWN

# Egress attribution for the DIRECT leg (domestic split tunneling)
DIRECT_EGRESS = "USER_ISP"


def _now() -> float:
    return time.time()


# ── Route object ────────────────────────────────────────────────────────────

@dataclass
class Route:
    route_id: str
    entry_node: str                             # node id (e.g. "railway-control")
    relay_nodes: List[str] = field(default_factory=list)
    exit_node: Optional[str] = None             # None ⇒ no real exit node
    expected_country: Optional[str] = None      # country name (Route expectation)
    observed_country: Optional[str] = None      # MEASURED only (never configured)
    expected_asn: Optional[str] = None
    observed_asn: Optional[str] = None
    health: str = "UNKNOWN"                     # ROUTE_HEALTH_STATES
    latency: Dict[str, Optional[float]] = field(default_factory=dict)  # labeled measures
    packet_loss: Optional[float] = None         # percent 0-100 when known
    jitter: Optional[float] = None              # ms when known
    last_verified: Optional[float] = None
    verification_state: str = "UNKNOWN"
    route_policy: str = "ALL_VPN"
    notes: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=_now)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["last_verified_iso"] = (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.last_verified))
            if self.last_verified else None)
        d["age_s"] = round(_now() - (self.last_verified or self.created_at), 1)
        d["stale"] = (self.last_verified is None
                      or (_now() - self.last_verified) > ROUTE_STALE_AFTER_S)
        d["latency_labeled"] = {
            k: ee.labeled_latency(k, v) for k, v in (self.latency or {}).items()}
        return d


# ── Registry (bounded, process-local) ───────────────────────────────────────

_routes: Dict[str, Route] = {}
_routes_lock = asyncio.Lock()
_route_metrics_fns: Dict[str, Callable] = {}    # injectable metric providers


def set_metrics_provider(name: str, fn: Callable) -> None:
    """DI seam — tests inject latency/loss/jitter providers; never main import."""
    _route_metrics_fns[name] = fn


async def register_route(route: Route) -> Route:
    async with _routes_lock:
        if route.route_id in _routes:
            _routes[route.route_id] = route      # idempotent update
            return route
        if len(_routes) >= ROUTE_REGISTRY_BOUND:
            # evict oldest by created_at — bounded memory, never unbounded
            oldest = min(_routes.values(), key=lambda r: r.created_at)
            _routes.pop(oldest.route_id, None)
        _routes[route.route_id] = route
    return route


async def remove_route(route_id: str) -> bool:
    async with _routes_lock:
        return _routes.pop(route_id, None) is not None


def get_route(route_id: str) -> Optional[dict]:
    r = _routes.get(route_id)
    return r.to_dict() if r else None


def list_routes(verification_state: Optional[str] = None) -> List[dict]:
    out = [r.to_dict() for r in _routes.values()]
    if verification_state:
        out = [r for r in out if r["verification_state"] == verification_state]
    return out


def reset_for_tests() -> None:
    _routes.clear()
    _route_metrics_fns.clear()


# ── Route assessment (pure — consumes egress_engine evidence only) ──────────

def assess_route(route: Route, evidence: Optional[dict] = None) -> Route:
    """Fill observed_* / verification_state / health from MEASURED evidence.

    evidence: an egress_engine evidence dict for the exit target
              (evidence_for() / classify_egress()["evidence"]). When absent,
              the route degrades to UNKNOWN — it never fabricates.
    """
    if route.exit_node is None:
        route.health = "NO_EXIT_NODE_AVAILABLE"
        route.verification_state = "UNKNOWN"
        route.observed_country = None
        route.observed_asn = None
        return route

    ev = evidence or {}
    valid = bool(ev.get("valid", ev.get("ok")))
    route.observed_country = ev.get("country") if valid else None
    route.observed_asn = ev.get("asn") if valid else None
    if valid:
        route.verification_state = "VERIFIED_EGRESS"
        route.last_verified = ev.get("checked_at") or _now()
    else:
        route.verification_state = "UNKNOWN" if not ev else "CONFIGURED_ONLY"

    route.health = _route_health(route)
    return route


def _route_health(route: Route) -> str:
    """Expected vs observed comparison — mismatch is NEVER masked.
    Only VERIFIED_EGRESS routes are comparable; CONFIGURED_ONLY / UNKNOWN
    stay UNKNOWN (never healthy, per spec)."""
    if route.exit_node is None:
        return "NO_EXIT_NODE_AVAILABLE"
    if route.verification_state != "VERIFIED_EGRESS":
        return "UNKNOWN"
    observed = {"ok": True, "country": route.observed_country,
                "asn": route.observed_asn}
    verdict = ee.compare_route_expectations(
        route.expected_country, observed, route.expected_asn)
    return verdict.get("route_health", "UNKNOWN")


def route_status_label(route: Route) -> str:
    """DIRECT / RELAY / VERIFIED / UNKNOWN (public ROUTE_STATUSES)."""
    return ee.route_status_for(_role_of(route), route.verification_state == "VERIFIED_EGRESS")


def _role_of(route: Route) -> str:
    if route.exit_node is None:
        return "CONTROL_PLANE"
    if route.relay_nodes and route.exit_node not in route.relay_nodes:
        return "RELAY_NODE"
    return "EXIT_NODE"


# ── Metrics (labeled; injectable providers; honest defaults) ────────────────

async def measure_route_metrics(route: Route) -> Route:
    """Attach labeled latency/loss/jitter when a provider is registered.
    No provider ⇒ fields stay None (UNKNOWN), never invented numbers."""
    for measure, key in (("control_plane_rtt", "control_plane_rtt"),
                         ("node_rtt", "node_rtt"),
                         ("route_rtt", "route_rtt"),
                         ("protocol_handshake_rtt", "protocol_handshake_rtt")):
        fn = _route_metrics_fns.get(key)
        if fn is None:
            route.latency.setdefault(measure, None)
            continue
        try:
            route.latency[measure] = await _maybe_await(fn(route))
        except Exception:
            route.latency[measure] = None            # provider failure ⇒ UNKNOWN
    fn = _route_metrics_fns.get("packet_loss")
    if fn:
        try:
            route.packet_loss = await _maybe_await(fn(route))
        except Exception:
            route.packet_loss = None
    fn = _route_metrics_fns.get("jitter")
    if fn:
        try:
            route.jitter = await _maybe_await(fn(route))
        except Exception:
            route.jitter = None
    return route


async def _maybe_await(v):
    return await v if hasattr(v, "__await__") else v


# ── Inventory sync (single source of truth stays egress_engine) ─────────────

async def sync_inventory() -> List[dict]:
    """Rebuild the route inventory view from egress_engine topology +
    live registry. Routes here are READ-ONLY projections of measured truth."""
    topo = await ee.worker_topology()
    out: List[dict] = []
    for loc in topo.get("locations", []):
        name = loc.get("name", "")
        ev = ee.evidence_for(f"loc:{name}") or {}
        cls = ee.classify_egress(f"loc:{name}")
        out.append({
            "route_id": f"worker:{name}",
            "entry_node": "cf-edge",
            "relay_nodes": [],
            "exit_node": name if loc.get("kind") == "exit" else None,
            "expected_country": (loc.get("country") or {}).get("name")
            if isinstance(loc.get("country"), dict) else loc.get("country"),
            "observed_country": ev.get("country") if ev.get("valid") else None,
            "observed_asn": ev.get("asn") if ev.get("valid") else None,
            "verification_state": cls.get("classification"),
            "health": cls.get("route_health", "UNKNOWN"),
            "source": "worker_topology",
        })
    # registry routes take precedence (they carry policy + metrics)
    for r in _routes.values():
        d = r.to_dict()
        d["source"] = "route_registry"
        out.append(d)
    return out


def summary() -> dict:
    by_health: Dict[str, int] = {}
    by_verification: Dict[str, int] = {}
    for r in _routes.values():
        by_health[r.health] = by_health.get(r.health, 0) + 1
        by_verification[r.verification_state] = \
            by_verification.get(r.verification_state, 0) + 1
    return {
        "routes": len(_routes),
        "by_health": by_health,
        "by_verification": by_verification,
        "registry_bound": ROUTE_REGISTRY_BOUND,
        "stale_after_s": ROUTE_STALE_AFTER_S,
        "engine": f"route_engine/{ROUTE_ENGINE_VERSION}",
    }


# ── API surface (registered from main; auth applied there) ──────────────────

def register_routes(app, require_auth) -> None:
    from fastapi import Depends, Query
    from fastapi.responses import JSONResponse

    @app.get("/api/routes", dependencies=[Depends(require_auth)])
    async def api_routes(verification: Optional[str] = Query(None)):
        return {"routes": list_routes(verification) or await sync_inventory(),
                "summary": summary()}

    @app.get("/api/routes/summary", dependencies=[Depends(require_auth)])
    async def api_routes_summary():
        return summary()

    @app.get("/api/routes/{route_id}", dependencies=[Depends(require_auth)])
    async def api_route(route_id: str):
        r = get_route(route_id)
        if r is None:
            return JSONResponse({"error": "route not found"}, status_code=404)
        return r
