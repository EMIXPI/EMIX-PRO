"""Unit tests for node_manager.py — Node Manager (Phase 37.9).

Covers: REGISTER/ONLINE/DEGRADED/OFFLINE/MAINTENANCE, heartbeat expiry,
runtime-gated health (HTTP ping is NOT enough), persistence snapshot,
idempotent registration, load/traffic/clients bookkeeping.
"""
import asyncio
import time

import pytest

import node_manager as nm


@pytest.fixture(autouse=True)
def _reset():
    nm.reset_for_tests()
    yield
    nm.reset_for_tests()


def _rec(**kw):
    base = dict(id="n1", name="Node 1", kind="panel", runtime="in-panel-relays")
    base.update(kw)
    return nm.NodeRecord(**base)


# ── pure state derivation ──────────────────────────────────────────────────

def test_registered_never_heartbeated_is_register():
    state, reason = nm.derive_state(_rec())
    assert state == "REGISTER" and "never" in reason


def test_fresh_heartbeat_and_healthy_runtime_is_online():
    rec = _rec(last_heartbeat=time.time(), runtime_health="OK")
    state, reason = nm.derive_state(rec)
    assert state == "ONLINE" and "runtime healthy" in reason


def test_fresh_heartbeat_but_runtime_down_is_offline():
    # THE core 37.9 rule: heartbeat (HTTP 200) alone is NOT health
    rec = _rec(last_heartbeat=time.time(), runtime_health="DOWN")
    state, reason = nm.derive_state(rec)
    assert state == "OFFLINE" and "DOWN" in reason


def test_stale_heartbeat_is_degraded_then_offline():
    rec = _rec(last_heartbeat=time.time() - nm.HEARTBEAT_DEGRADED - 1,
               runtime_health="OK")
    assert nm.derive_state(rec)[0] == "DEGRADED"
    rec = _rec(last_heartbeat=time.time() - nm.HEARTBEAT_TTL - 1,
               runtime_health="OK")
    assert nm.derive_state(rec)[0] == "OFFLINE"


def test_runtime_degraded_is_degraded():
    rec = _rec(last_heartbeat=time.time(), runtime_health="DEGRADED")
    assert nm.derive_state(rec)[0] == "DEGRADED"


def test_runtime_health_unknown_is_register_not_online():
    # fresh heartbeat but no runtime evidence → honest REGISTER, not ONLINE
    rec = _rec(last_heartbeat=time.time(), runtime_health="UNKNOWN")
    assert nm.derive_state(rec)[0] == "REGISTER"


def test_maintenance_overrides_everything():
    rec = _rec(state="MAINTENANCE", last_heartbeat=time.time(), runtime_health="OK")
    assert nm.derive_state(rec)[0] == "MAINTENANCE"


# ── manager operations ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_idempotent_keeps_history():
    await nm.register_node(_rec())
    await nm.heartbeat("n1", runtime_health="OK")
    # re-register (e.g. restart) must NOT wipe observed state
    await nm.register_node(_rec(name="Node 1 updated"))
    rec = nm.get_node("n1")
    assert rec.name == "Node 1 updated"
    assert rec.last_heartbeat is not None


@pytest.mark.asyncio
async def test_heartbeat_updates_state_and_load():
    await nm.register_node(_rec())
    rec = await nm.heartbeat("n1", runtime_health="OK", load=42.0, clients=7)
    assert rec.state == "ONLINE"
    assert rec.load == 42.0 and rec.clients == 7
    assert nm.node_load("n1") == 42.0


@pytest.mark.asyncio
async def test_maintenance_toggle():
    await nm.register_node(_rec())
    rec = await nm.set_maintenance("n1", True, reason="kernel upgrade")
    assert rec.state == "MAINTENANCE"
    assert any(n.startswith("maintenance:") for n in rec.notes)
    rec = await nm.set_maintenance("n1", False)
    assert rec.state == "REGISTER"
    assert not any(n.startswith("maintenance:") for n in rec.notes)


@pytest.mark.asyncio
async def test_evaluate_runtime_health_with_injected_fn():
    async def evaluator(rec):
        return {"runtime_health": "OK", "load": 30.0, "clients": 3}
    nm.register_runtime_health_fn("panel", evaluator)
    await nm.register_node(_rec())
    result = await nm.evaluate_runtime_health("n1")
    assert result["state"] == "ONLINE"
    assert nm.get_node("n1").runtime_health == "OK"


@pytest.mark.asyncio
async def test_evaluate_runtime_health_fn_error_is_down():
    async def evaluator(rec):
        raise RuntimeError("probe exploded")
    nm.register_runtime_health_fn("panel", evaluator)
    await nm.register_node(_rec())
    await nm.evaluate_runtime_health("n1")
    rec = nm.get_node("n1")
    assert rec.runtime_health == "DOWN"
    assert nm.derive_state(rec)[0] == "OFFLINE"


@pytest.mark.asyncio
async def test_evaluate_without_fn_stays_unknown():
    # no evaluator registered for the kind → UNKNOWN, never fake ONLINE
    await nm.register_node(_rec())
    await nm.evaluate_runtime_health("n1")
    assert nm.get_node("n1").runtime_health == "UNKNOWN"


@pytest.mark.asyncio
async def test_record_restart():
    await nm.register_node(_rec())
    await nm.record_restart("n1")
    await nm.record_restart("n1")
    assert nm.get_node("n1").restart_count == 2


@pytest.mark.asyncio
async def test_online_nodes_with_capability_filter():
    await nm.register_node(_rec(id="a", capabilities=["vless-ws"]))
    await nm.heartbeat("a", runtime_health="OK")
    await nm.register_node(_rec(id="b", capabilities=["trojan-ws"]))
    await nm.heartbeat("b", runtime_health="DOWN")
    assert nm.online_nodes() == ["a"]
    assert nm.online_nodes(capability="vless-ws") == ["a"]
    assert nm.online_nodes(capability="trojan-ws") == []


@pytest.mark.asyncio
async def test_check_all_recomputes_states():
    await nm.register_node(_rec(id="x"))
    await nm.heartbeat("x", runtime_health="OK")
    # simulate time passing beyond TTL
    nm.get_node("x").last_heartbeat = time.time() - (nm.HEARTBEAT_TTL + 10)
    out = await nm.check_all()
    assert out["x"]["state"] == "OFFLINE"


# ── persistence snapshot ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_persist_restore_roundtrip():
    await nm.register_node(_rec(id="keep", region="AMS", load=55.5))
    await nm.heartbeat("keep", runtime_health="OK", load=55.5, clients=12)
    snap = nm.persist_snapshot()
    nm.reset_for_tests()
    nm.restore_snapshot(snap)
    rec = nm.get_node("keep")
    assert rec is not None
    assert rec.region == "AMS" and rec.load == 55.5 and rec.clients == 12
    assert rec.last_heartbeat is not None


def test_restore_ignores_garbage():
    nm.restore_snapshot({"nodes": [{"id": "ok", "name": "N"}, {"broken": True}, "junk"]})
    assert nm.get_node("ok") is not None
    assert len(nm.list_nodes()) == 1


def test_summary_shape():
    s = nm.summary()
    assert s["nodes"] == 0
    assert set(s["by_state"].keys()) == set(nm.NODE_STATES)
    assert s["engine"] == "node_manager/1.0"
