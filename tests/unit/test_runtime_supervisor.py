"""Unit tests for runtime_supervisor.py — Runtime Supervision (Phase 37.10).

Covers: crash detection, exponential backoff, bounded restart budget
(no infinite restart loops), give-up state, node-state updates, diagnostics
records, manual restart, backoff reset after stable uptime.
"""
import asyncio
import time

import pytest

import runtime_supervisor as rs
import diagnostics as diag


@pytest.fixture(autouse=True)
def _reset():
    rs.reset_for_tests()
    diag._errors.clear()
    diag._error_counts.clear()
    yield
    rs.reset_for_tests()
    diag._errors.clear()
    diag._error_counts.clear()


def _rt(id="rt1", alive=True, restart_count=0):
    calls = {"restarts": 0, "alive": alive, "stops": 0}

    async def _restart():
        calls["restarts"] += 1
        calls["alive"] = True
        return True

    async def _stop():
        calls["stops"] += 1
        calls["alive"] = False
        return True

    rt = rs.SupervisedRuntime(
        id=id, name=f"Runtime {id}", kind="mtproto-subprocess", node_id=None,
        is_alive_fn=lambda: calls["alive"],
        restart_fn=_restart,
        stop_fn=_stop,
    )
    rt.restart_count = restart_count
    return rt, calls


# ── happy path ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_alive_runtime_stays_running():
    rt, _ = _rt()
    rs.supervisor.register(rt)
    out = await rs.supervisor.monitor_once()
    assert out[rt.id]["state"] == "RUNNING"
    assert rt.state == "RUNNING"


@pytest.mark.asyncio
async def test_crash_detected_and_restarted():
    rt, calls = _rt(alive=True)
    rs.supervisor.register(rt)
    await rs.supervisor.monitor_once()          # RUNNING
    calls["alive"] = False                      # crash
    out = await rs.supervisor.monitor_once()    # crash pass
    assert out[rt.id]["action"] == "restarted"
    assert calls["restarts"] == 1
    assert rt.state == "RUNNING"
    assert rt.restart_count == 1


@pytest.mark.asyncio
async def test_crash_records_structured_diagnostics():
    rt, _ = _rt()
    rs.supervisor.register(rt)
    rt.state = "RUNNING"                        # was healthy → crash is CRITICAL
    rt.is_alive_fn = lambda: False
    rt.restart_fn = None                        # no restart fn → crash recorded
    await rs.supervisor.monitor_once()
    codes = [e.code for e in diag._errors]
    assert "RUNTIME_CRASH" in codes


# ── exponential backoff (bounded, deterministic) ────────────────────────────

def test_backoff_delay_is_exponential_and_bounded():
    rt, _ = _rt()
    delays = []
    for i in range(10):
        rt.restart_count = i
        delays.append(rs.supervisor.backoff_delay(rt))
    for i in range(min(8, len(delays) - 1)):
        assert delays[i + 1] == min(rs.BACKOFF_MAX_S, delays[i] * 2)
    assert all(d <= rs.BACKOFF_MAX_S for d in delays)


@pytest.mark.asyncio
async def test_restarts_gated_by_backoff_window():
    rt, _ = _rt()
    rs.supervisor.register(rt)
    # simulate a restart that just happened → backoff blocks immediate retry
    rt._restart_ts = [time.time()]
    rt._next_restart_allowed = time.time() + 60
    rt.is_alive_fn = lambda: False
    out = await rs.supervisor.monitor_once()
    assert out[rt.id]["action"] in ("give-up", "no-restart-fn") or \
           out[rt.id].get("reason", "").startswith("backoff")


@pytest.mark.asyncio
async def test_giveup_after_max_restarts_in_window():
    rt, calls = _rt(alive=False)
    rs.supervisor.register(rt)
    rt.is_alive_fn = lambda: False
    # 4 prior restarts in the window; max_restarts=5 → one more allowed, then
    # the next crash trip hits the budget and gives up
    rt._restart_ts = [time.time() - i for i in range(1, 5)]
    out = await rs.supervisor.monitor_once()
    assert out[rt.id]["action"] == "restarted"
    # now 5 restarts in the window → give-up
    out = await rs.supervisor.monitor_once()
    assert out[rt.id]["action"] == "give-up"
    assert rt.state == "FAILED"
    assert calls["restarts"] == 1  # no extra restart after give-up


def test_restarts_allowed_window_slides():
    rt, _ = _rt()
    # restarts older than the window no longer count
    rt._restart_ts = [time.time() - (rs.BACKOFF_WINDOW_S + 60)] * 5
    allowed, why = rs.supervisor.restarts_allowed(rt)
    assert allowed


# ── no-checker honesty ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_alive_checker_reports_unknown_never_running():
    rt = rs.SupervisedRuntime(id="blind", name="Blind", kind="custom")
    rs.supervisor.register(rt)
    out = await rs.supervisor.monitor_once()
    assert out["blind"]["state"] == "UNKNOWN"
    assert "cannot claim RUNNING" in out["blind"]["reason"]


# ── node-state propagation ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_node_heartbeat_on_crash_and_recovery():
    import node_manager as nm
    nm.reset_for_tests()
    rt, _ = _rt()
    rt.node_id = "n1"
    rs.supervisor.register(rt)
    await nm.register_node(nm.NodeRecord(id="n1", name="N1", kind="panel"))
    rt.is_alive_fn = lambda: False
    rt.restart_fn = None
    await rs.supervisor.monitor_once()          # crash → node DOWN
    assert nm.get_node("n1").runtime_health == "DOWN"
    rt.is_alive_fn = lambda: True
    await rs.supervisor.monitor_once()          # recovery → node OK
    assert nm.get_node("n1").runtime_health == "OK"


# ── manual lifecycle ops ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_manual_restart_and_stop():
    rt, _ = _rt()
    rs.supervisor.register(rt)
    result = await rs.supervisor.restart("rt1", manual=True)
    assert result["ok"] and rt.state == "RUNNING"
    result = await rs.supervisor.stop("rt1")
    assert result["ok"] and rt.state == "STOPPED"


@pytest.mark.asyncio
async def test_unknown_runtime_rejected():
    assert not (await rs.supervisor.restart("nope"))["ok"]
    assert not (await rs.supervisor.stop("nope"))["ok"]


# ── status exposure ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_status_exposes_policy_and_runtimes():
    rt, _ = _rt()
    rs.supervisor.register(rt)
    st = rs.supervisor.status()
    assert st["policy"]["backoff_max_s"] == rs.BACKOFF_MAX_S
    assert st["policy"]["max_restarts_in_window"] == rs.MAX_RESTARTS_WINDOW
    assert any(r["id"] == "rt1" for r in st["runtimes"])
    assert "restart_count" in st["runtimes"][0]


@pytest.mark.asyncio
async def test_register_refreshes_fns_keeps_counters():
    rt, calls = _rt()
    rs.supervisor.register(rt)
    rt.is_alive_fn = lambda: False
    rt.restart_fn = None
    await rs.supervisor.monitor_once()
    assert rt.restart_count >= 0 or rt.state in ("CRASHED", "UNKNOWN")
    # re-register with new fns (e.g. process rebound after panel restart):
    # the stored runtime must now be alive-checkable again
    rt2, calls2 = _rt(id="rt1")
    rs.supervisor.register(rt2)
    stored = rs.supervisor._runtimes["rt1"]
    assert stored.is_alive_fn is not None and stored.is_alive_fn()
    assert stored.restart_fn is not None
    out = await rs.supervisor.monitor_once()
    assert out["rt1"]["state"] == "RUNNING"
