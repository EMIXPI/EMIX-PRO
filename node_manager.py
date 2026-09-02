# node_manager.py — Node Manager (Phase 37.9)
#
# Every node that carries EMIX traffic is a first-class managed object:
#
#   identity     — id, name, kind (panel / worker / vps / exit)
#   runtime      — what actually serves traffic on this node and HOW
#                  (in-panel relays, subprocess binaries, worker JS, …)
#   capabilities — protocol/transport combos this node can serve (compat truth)
#   health       — REGISTER → ONLINE → DEGRADED → OFFLINE (+ MAINTENANCE /
#                  DRAINING / QUARANTINED / UNKNOWN — Phase 38 / P1)
#   load         — 0-100 estimate from active connections / quota pressure
#   traffic      — bytes served through this node
#   clients      — active client connections
#   heartbeat    — last evidence timestamp (NOT just HTTP ping)
#
# Honesty rules:
#   * A node is ONLINE only when its RELEVANT RUNTIME is healthy — an HTTP
#     200 from a co-hosted web UI says nothing about protocol relays.
#     runtime_health_fn (injected, no main import) supplies that evidence.
#   * Heartbeats expire: OFFLINE after heartbeat_ttl without evidence.
#   * REGISTER (never heartbeated) is never shown as healthy.
#   * MAINTENANCE is an operator override — traffic is excluded while set.

from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Dict, List

NODE_STATES = ("REGISTER", "ONLINE", "DEGRADED", "DRAINING", "MAINTENANCE",
               "OFFLINE", "QUARANTINED", "UNKNOWN")
# Phase 38 note: REGISTER (never heartbeated) is the concrete sub-case of
# spec state UNKNOWN; kept for backward compatibility with v11 snapshots.
KINDS = ("panel", "worker", "vps", "exit", "external")

HEARTBEAT_TTL = 180.0        # seconds — evidence older than this = OFFLINE
HEARTBEAT_DEGRADED = 90.0    # seconds — stale but not dead → DEGRADED


@dataclass
class NodeRecord:
    id: str
    name: str
    kind: str = "external"                  # panel | worker | vps | exit | external
    region: str = ""                        # optional geo hint (e.g. "AMS", "CF-HKG")
    address: str = ""                       # public address (hostname/ip; never secret)
    runtime: str = "unknown"                # "in-panel-relays" | "mtproto-subprocess" | ...
    capabilities: List[str] = field(default_factory=list)   # fused protocols served
    state: str = "REGISTER"
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: Optional[float] = None
    last_heartbeat_kind: str = ""           # "runtime-health" | "probe" | "manual"
    runtime_health: str = "UNKNOWN"         # OK | DEGRADED | DOWN | UNKNOWN
    load: Optional[float] = None            # 0-100 when known
    traffic_bytes: int = 0
    clients: int = 0
    restart_count: int = 0
    draining: bool = False                   # Phase 38: no NEW assignments
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["last_heartbeat_iso"] = (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.last_heartbeat))
            if self.last_heartbeat else None)
        d["registered_at_iso"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.registered_at))
        d["heartbeat_age_s"] = (round(time.time() - self.last_heartbeat, 1)
                                if self.last_heartbeat else None)
        d["effective_state"] = derive_state(self)[0]
        return d


# ── Pure state derivation (unit-testable) ──────────────────────────────────

def derive_state(rec: NodeRecord, now: Optional[float] = None,
                 heartbeat_ttl: float = HEARTBEAT_TTL,
                 heartbeat_degraded: float = HEARTBEAT_DEGRADED
                 ) -> tuple[str, str]:
    """(state, reason). QUARANTINED/MAINTENANCE override > drain > runtime
    health > heartbeat age. DRAINING keeps existing traffic but blocks new
    assignments (failover_engine drives it)."""
    if rec.state == "QUARANTINED":
        return "QUARANTINED", "operator quarantine — egress/behavior under investigation"
    if rec.state == "MAINTENANCE":
        return "MAINTENANCE", "operator override"
    now = time.time() if now is None else now
    if rec.last_heartbeat is None:
        return "REGISTER", "registered but never heartbeated"
    age = now - rec.last_heartbeat
    if age > heartbeat_ttl:
        return "OFFLINE", f"no heartbeat for {int(age)}s (ttl {int(heartbeat_ttl)}s)"
    # runtime gate: heartbeat fresh but the runtime itself is down → OFFLINE
    if rec.runtime_health == "DOWN":
        return "OFFLINE", "runtime health reported DOWN"
    if age > heartbeat_degraded:
        return "DEGRADED", f"stale heartbeat ({int(age)}s)"
    if rec.runtime_health == "DEGRADED":
        return "DEGRADED", "runtime health reported DEGRADED"
    if rec.runtime_health in ("UNKNOWN",):
        return "REGISTER", "heartbeat fresh but runtime health unknown"
    if rec.draining:
        return "DRAINING", "draining — existing traffic continues, no new assignments"
    return "ONLINE", "runtime healthy + fresh heartbeat"


# ── Manager (process-local registry; persisted via snapshot bridge) ────────

_nodes: Dict[str, NodeRecord] = {}
_lock = asyncio.Lock()
# runtime health probe injectors: node kind → async fn(NodeRecord) → (health, load, clients)
_runtime_health_fns: Dict[str, Callable] = {}


def register_runtime_health_fn(kind: str, fn: Callable) -> None:
    """Register the runtime-health evaluator for a node kind (DI — no main import)."""
    _runtime_health_fns[kind] = fn


async def register_node(rec: NodeRecord) -> NodeRecord:
    """Idempotent registration: existing records keep their heartbeat history."""
    async with _lock:
        existing = _nodes.get(rec.id)
        if existing is not None:
            # refresh mutable identity fields, keep observed state
            existing.name = rec.name or existing.name
            existing.kind = rec.kind
            existing.region = rec.region or existing.region
            existing.address = rec.address or existing.address
            existing.runtime = rec.runtime or existing.runtime
            existing.capabilities = rec.capabilities or existing.capabilities
            return existing
        _nodes[rec.id] = rec
    return rec


async def heartbeat(node_id: str, kind: str = "probe", runtime_health: str = "UNKNOWN",
                    load: Optional[float] = None, clients: Optional[int] = None,
                    traffic_delta: int = 0) -> Optional[NodeRecord]:
    """Record fresh evidence for a node (called by probes/jobs/supervisor)."""
    async with _lock:
        rec = _nodes.get(node_id)
        if rec is None:
            return None
        rec.last_heartbeat = time.time()
        rec.last_heartbeat_kind = kind
        if runtime_health in ("OK", "DEGRADED", "DOWN", "UNKNOWN"):
            rec.runtime_health = runtime_health
        if load is not None:
            rec.load = max(0.0, min(100.0, float(load)))
        if clients is not None:
            rec.clients = max(0, int(clients))
        if traffic_delta > 0:
            rec.traffic_bytes += int(traffic_delta)
        state, _reason = derive_state(rec)
        rec.state = state
        return rec


async def set_maintenance(node_id: str, on: bool, reason: str = "") -> Optional[NodeRecord]:
    async with _lock:
        rec = _nodes.get(node_id)
        if rec is None:
            return None
        if on:
            rec.state = "MAINTENANCE"
            rec.notes = [n for n in rec.notes if not n.startswith("maintenance:")]
            rec.notes.append(f"maintenance:{reason or 'operator'}")
        else:
            rec.state = "REGISTER"
            rec.notes = [n for n in rec.notes if not n.startswith("maintenance:")]
        return rec


async def set_draining(node_id: str, on: bool,
                       reason: str = "") -> Optional[NodeRecord]:
    """Phase 38: DRAINING — existing traffic continues, NEW assignments stop.
    Driven by failover_engine (step 1+2 of the failover pipeline)."""
    async with _lock:
        rec = _nodes.get(node_id)
        if rec is None:
            return None
        rec.draining = on
        if on:
            rec.notes = [n for n in rec.notes if not n.startswith("drain:")]
            rec.notes.append(f"drain:{reason or 'operator'}")
        else:
            rec.notes = [n for n in rec.notes if not n.startswith("drain:")]
        state, _reason = derive_state(rec)
        rec.state = state
        return rec


async def set_quarantine(node_id: str, on: bool,
                         reason: str = "") -> Optional[NodeRecord]:
    """Phase 38: QUARANTINED — traffic fully excluded while egress/behavior
    is under investigation (e.g. ROUTE_MISMATCH evidence)."""
    async with _lock:
        rec = _nodes.get(node_id)
        if rec is None:
            return None
        if on:
            rec.state = "QUARANTINED"
            rec.notes = [n for n in rec.notes if not n.startswith("quarantine:")]
            rec.notes.append(f"quarantine:{reason or 'operator'}")
        else:
            rec.state = "REGISTER"
            rec.notes = [n for n in rec.notes if not n.startswith("quarantine:")]
            state, _r = derive_state(rec)
            rec.state = state
        return rec


async def record_restart(node_id: str) -> None:
    async with _lock:
        rec = _nodes.get(node_id)
        if rec is not None:
            rec.restart_count += 1


async def evaluate_runtime_health(node_id: str) -> Optional[dict]:
    """Run the injected runtime-health evaluator for a node (the gate that
    makes 'HTTP ping is not enough' real). Returns the evaluated record."""
    rec = _nodes.get(node_id)
    if rec is None:
        return None
    fn = _runtime_health_fns.get(rec.kind)
    if fn is None:
        # no evaluator registered for this kind — keep UNKNOWN, never fake
        return rec.to_dict()
    try:
        result = await fn(rec)
        # evaluator returns (runtime_health, load, clients) or a dict
        if isinstance(result, tuple):
            rh, load, clients = result
        elif isinstance(result, dict):
            rh = result.get("runtime_health", "UNKNOWN")
            load = result.get("load")
            clients = result.get("clients")
        else:
            rh, load, clients = "UNKNOWN", None, None
    except Exception:
        rh, load, clients = "DOWN", None, None
    updated = await heartbeat(node_id, kind="runtime-health", runtime_health=rh,
                              load=load, clients=clients)
    return updated.to_dict() if updated is not None else rec.to_dict()


async def check_all(now: Optional[float] = None) -> dict:
    """Re-derive states for all nodes (stateless sweep, cheap)."""
    out = {}
    async with _lock:
        for nid, rec in _nodes.items():
            state, reason = derive_state(rec, now=now)
            rec.state = state
            out[nid] = {"state": state, "reason": reason}
    return out


def get_node(node_id: str) -> Optional[NodeRecord]:
    return _nodes.get(node_id)


def list_nodes() -> List[dict]:
    return [rec.to_dict() for rec in _nodes.values()]


def summary() -> dict:
    by_state = {s: 0 for s in NODE_STATES}
    for rec in _nodes.values():
        state, _ = derive_state(rec)
        by_state[state] = by_state.get(state, 0) + 1
    return {"nodes": len(_nodes), "by_state": by_state,
            "heartbeat_ttl_s": HEARTBEAT_TTL, "engine": "node_manager/1.0"}


def node_load(node_id: str) -> Optional[float]:
    rec = _nodes.get(node_id)
    return rec.load if rec else None


def online_nodes(capability: Optional[str] = None) -> List[str]:
    """Node ids ONLINE (runtime-gated). Optional capability (fused protocol) filter.
    DRAINING / QUARANTINED / MAINTENANCE / OFFLINE nodes are NEVER returned —
    they do not accept new assignments."""
    out = []
    for nid, rec in _nodes.items():
        state, _ = derive_state(rec)
        if state == "ONLINE" and not rec.draining \
                and (capability is None or capability in rec.capabilities):
            out.append(nid)
    return out


# ── Persistence bridge (wired into main.save_state / load_state) ───────────

def persist_snapshot() -> dict:
    return {"nodes": [
        {k: v for k, v in rec.__dict__.items() if k != "state"}
        | {"state": rec.state}
        for rec in _nodes.values()
    ]}


def restore_snapshot(data: dict) -> None:
    _nodes.clear()
    for d in (data or {}).get("nodes", []):
        try:
            d = {k: v for k, v in d.items() if k in NodeRecord.__dataclass_fields__}
            _nodes[d["id"]] = NodeRecord(**d)
        except Exception:
            continue


def reset_for_tests() -> None:
    _nodes.clear()
    _runtime_health_fns.clear()
