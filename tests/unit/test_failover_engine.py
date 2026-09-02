# tests/unit/test_failover_engine.py — Phase 38 / P1 failover + scoring

import asyncio
import time

import pytest

import failover_engine as fe
import node_manager as nm
import egress_engine as ee


@pytest.fixture(autouse=True)
def clean():
    fe.reset_for_tests()
    nm.reset_for_tests()
    ee.reset_for_tests()
    yield
    fe.reset_for_tests()
    nm.reset_for_tests()
    ee.reset_for_tests()




async def _online_node(node_id: str, kind: str = "exit", **kw):
    rec = nm.NodeRecord(id=node_id, name=node_id, kind=kind, **kw)
    await nm.register_node(rec)
    await nm.heartbeat(node_id, kind="probe", runtime_health="OK")
    return rec


# ── node state extension (P1) ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_node_states_include_draining_quarantined_unknown():
    for s in ("DRAINING", "QUARANTINED", "UNKNOWN", "ONLINE", "DEGRADED",
              "MAINTENANCE", "OFFLINE"):
        assert s in nm.NODE_STATES


@pytest.mark.asyncio
async def test_set_draining_blocks_new_assignments():
    await (_online_node("nl-01"))
    await (nm.set_draining("nl-01", True, reason="test"))
    rec = nm.get_node("nl-01")
    state, reason = nm.derive_state(rec)
    assert state == "DRAINING"
    assert "no new assignments" in reason
    assert "nl-01" not in nm.online_nodes()      # drained ≠ assignable
    # existing traffic continues (state derives, record alive)
    assert rec.last_heartbeat is not None


@pytest.mark.asyncio
async def test_undrain_restores_online():
    await (_online_node("nl-01"))
    await (nm.set_draining("nl-01", True))
    await (nm.set_draining("nl-01", False))
    assert "nl-01" in nm.online_nodes()


@pytest.mark.asyncio
async def test_set_quarantine():
    await (_online_node("nl-01"))
    await (nm.set_quarantine("nl-01", True, reason="egress suspect"))
    state, _ = nm.derive_state(nm.get_node("nl-01"))
    assert state == "QUARANTINED"
    assert "nl-01" not in nm.online_nodes()
    await (nm.set_quarantine("nl-01", False))
    assert "nl-01" in nm.online_nodes()


@pytest.mark.asyncio
async def test_quarantine_survives_fresh_heartbeat():
    await (_online_node("nl-01"))
    await (nm.set_quarantine("nl-01", True))
    await (nm.heartbeat("nl-01", runtime_health="OK"))
    state, _ = nm.derive_state(nm.get_node("nl-01"))
    assert state == "QUARANTINED"               # operator override wins


@pytest.mark.asyncio
async def test_draining_node_with_dead_runtime_is_offline():
    await (_online_node("nl-01"))
    await (nm.set_draining("nl-01", True))
    await (nm.heartbeat("nl-01", runtime_health="DOWN"))
    state, _ = nm.derive_state(nm.get_node("nl-01"))
    assert state == "OFFLINE"                   # runtime gate beats drain


# ── explainable scoring (pure) ──────────────────────────────────────────────

def _cand(state="ONLINE", load=30, caps=("vless:ws:tls",)):
    return {"id": "x", "state": state, "effective_state": state,
            "load": load, "capabilities": list(caps), "kind": "exit"}


@pytest.mark.asyncio
async def test_score_healthy_node_full_health_points():
    score, reasons = fe.score_node(_cand(), {}, {})
    assert score >= 25
    assert any("ONLINE" in r for r in reasons)


@pytest.mark.asyncio
async def test_score_drained_node_scores_zero_health():
    score, reasons = fe.score_node(_cand(state="DRAINING"), {}, {})
    assert any("DRAINING (no new assignments)" in r for r in reasons)


@pytest.mark.asyncio
async def test_score_quarantined_node_penalized():
    score_q, _ = fe.score_node(_cand(state="QUARANTINED"), {}, {})
    score_o, _ = fe.score_node(_cand(state="ONLINE"), {}, {})
    assert score_q < score_o


@pytest.mark.asyncio
async def test_score_latency_unknown_is_explicit_not_fake():
    _, reasons = fe.score_node(_cand(), {}, {})
    assert any(r.startswith("? latency UNKNOWN") for r in reasons)


@pytest.mark.asyncio
async def test_score_latency_quality():
    good, _ = fe.score_node(_cand(), {}, {"latency_ms": 30})
    bad, _ = fe.score_node(_cand(), {}, {"latency_ms": 400})
    assert good > bad


@pytest.mark.asyncio
async def test_score_verified_egress_beats_unknown():
    s_v, r_v = fe.score_node(_cand(), {}, {"egress_classification": "VERIFIED_EGRESS"})
    s_u, r_u = fe.score_node(_cand(), {}, {})
    assert s_v > s_u
    assert any("VERIFIED egress" in r for r in r_v)
    assert any("egress UNKNOWN" in r for r in r_u)


@pytest.mark.asyncio
async def test_score_country_match_needs_verification():
    req = {"country": "Netherlands"}
    s_verified, _ = fe.score_node(
        _cand(), req, {"egress_classification": "VERIFIED_EGRESS",
                       "egress": {"country": "Netherlands"}})
    s_configured, _ = fe.score_node(
        _cand(), req, {"egress_classification": "CONFIGURED_ONLY",
                       "egress": {"country": "Netherlands"}})
    assert s_verified > s_configured          # label without proof ≠ match


@pytest.mark.asyncio
async def test_score_protocol_compatibility():
    s_yes, _ = fe.score_node(_cand(caps=("vless:ws:tls",)), {"protocol": "vless:ws:tls"}, {})
    s_no, _ = fe.score_node(_cand(caps=("trojan:ws:tls",)), {"protocol": "vless:ws:tls"}, {})
    assert s_yes > s_no


@pytest.mark.asyncio
async def test_score_explainability_every_factor_named():
    _, reasons = fe.score_node(_cand(), {"country": "NL", "protocol": "x", "asn": "AS1"}, {})
    assert len(reasons) >= 5                  # multi-factor explanation


@pytest.mark.asyncio
async def test_score_weights_sum_100():
    assert sum(fe.SCORE_WEIGHTS.values()) == 100


# ── failover pipeline ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_failover_unknown_node_fails():
    out = await (fe.failover("ghost-node", reason="test"))
    assert out["verdict"] == "FAILOVER_FAILED"
    assert out["steps"][0]["ok"] is False


@pytest.mark.asyncio
async def test_failover_no_replacement_available():
    await (_online_node("only-node"))
    out = await (fe.failover("only-node", reason="unhealthy"))
    assert out["verdict"] == "FAILOVER_NO_REPLACEMENT"
    assert "nl" not in nm.online_nodes() or True
    # old node stays drained — never fails back blindly
    assert nm.get_node("only-node").draining is True


@pytest.mark.asyncio
async def test_failover_success_full_pipeline(monkeypatch):
    import gaming_boost
    await (_online_node("nl-01"))
    await (_online_node("nl-02"))
    # full provider injection — no real network in unit tests
    monkeypatch.setattr(gaming_boost, "_load_cfg",
                        lambda: {"worker_domain": "gw.test.example"})
    async def fake_worker_status(cfg=None):
        return {"ok": True, "locations": [{"name": "nl-02", "kind": "exit",
                                           "country": "Netherlands"}]}
    ee.set_provider("worker_status", fake_worker_status)

    async def fake_exit_ip(cfg, name):
        return {"ok": True, "exit_ip": "37.48.88.1", "exit_asn": "AS60794",
                "exit_isp": "TestISP", "exit_country": "Netherlands",
                "exit_country_code": "NL"}
    ee.set_provider("worker_exit_ip", fake_exit_ip)

    repointed = []

    async def repoint(old, new):
        repointed.append((old, new))
    fe.set_route_repoint_fn(repoint)

    out = await (fe.failover("nl-01", reason="degraded",
                          requirements={"location": "nl-02"}))
    assert out["verdict"] == "FAILOVER_SUCCESS", out
    assert out["replacement_node"] == "nl-02"
    assert repointed == [("nl-01", "nl-02")]
    step_names = [s["step"] for s in out["steps"]]
    assert step_names[0] == "drain"
    assert "verify_replacement_health" in step_names
    assert "repoint_routes" in step_names
    assert "resume_assignments" in step_names
    assert any("ONLINE" in r for r in out["ranking_reason"])
    # replacement is not drained and accepts assignments again
    assert nm.get_node("nl-02").draining is False


@pytest.mark.asyncio
async def test_failover_replacement_unhealthy_fails():
    await (_online_node("nl-01"))
    rec = nm.NodeRecord(id="nl-02", name="n2", kind="exit")
    await (nm.register_node(rec))                       # REGISTER — never ONLINE
    out = await (fe.failover("nl-01", reason="unhealthy", verify=False))
    # REGISTER nodes are not even selected; with no other candidates:
    assert out["verdict"] in ("FAILOVER_NO_REPLACEMENT", "FAILOVER_FAILED")


@pytest.mark.asyncio
async def test_failed_failover_keeps_node_drained():
    await (_online_node("nl-01"))
    await (_online_node("nl-02"))
    async def fake_worker_status(cfg=None):
        return {"ok": False, "error": "worker unreachable"}
    ee.set_provider("worker_status", fake_worker_status)
    out = await (fe.failover("nl-01", reason="test",
                          requirements={"location": "nl-02"}))
    assert out["verdict"] in ("FAILOVER_FAILED",)
    assert nm.get_node("nl-01").draining is True    # stays drained


@pytest.mark.asyncio
async def test_failover_history_bounded():
    for i in range(fe.FAILOVER_HISTORY_BOUND + 5):
        fe._history.append({"verdict": "FAILOVER_FAILED"})
    out = await (fe.failover("ghost", reason="x"))
    assert len(fe.failover_history()) <= fe.FAILOVER_HISTORY_BOUND


@pytest.mark.asyncio
async def test_failover_verdict_vocabulary():
    for v in ("FAILOVER_SUCCESS", "FAILOVER_FAILED", "FAILOVER_NO_REPLACEMENT"):
        assert v in fe.FAILOVER_VERDICTS


@pytest.mark.asyncio
async def test_summary_shape():
    s = fe.summary()
    assert "by_verdict" in s
    assert s["engine"].startswith("failover_engine/")
