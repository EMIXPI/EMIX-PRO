"""Unit tests for network_health.py — Network Health Engine (Phases 6/7).

Covers the PURE classification/scoring functions (no network) plus the
recording engine with an injected fake probe function:
  - classify(): UNKNOWN / INVALID / UNREACHABLE / DEGRADED / HEALTHY
  - compute_score(): weighted formula, bounds, monotonicity
  - record_probe(): state transitions + consecutive counters + loss/jitter
  - mark_invalid()
  - probe_config() with unwired engine → honest INVALID
  - sweep() with injected links provider
  - healthy_uids() for subscription filtering
"""
import asyncio
import time

import pytest

import network_health as nh


def _sample(ok=True, ws=120.0, e2e=400.0):
    return nh.ProbeSample(ts=time.time(), ok=ok, ws_ms=ws, e2e_ms=e2e)


# ── classify() — pure state machine ────────────────────────────────────────

def test_classify_unknown_when_no_samples():
    state, score, err = nh.classify(True, [])
    assert state == "UNKNOWN" and score is None

def test_classify_invalid_when_not_allowed():
    state, score, err = nh.classify(False, [_sample()])
    assert state == "INVALID" and score is None

def test_classify_unreachable_when_last_probe_failed():
    state, score, err = nh.classify(True, [_sample(ok=True), _sample(ok=False)])
    assert state == "UNREACHABLE"

def test_classify_healthy_when_fast_and_stable():
    samples = [_sample(ok=True, ws=80, e2e=200) for _ in range(5)]
    state, score, err = nh.classify(True, samples)
    assert state == "HEALTHY"
    assert score is not None and score >= 70

def test_classify_degraded_when_flaky():
    samples = [_sample(ok=True), _sample(ok=False), _sample(ok=True), _sample(ok=False), _sample(ok=True)]
    state, *_ = nh.classify(True, samples)
    assert state == "DEGRADED"

def test_classify_degraded_when_slow_but_ok():
    samples = [_sample(ok=True, ws=700, e2e=1900) for _ in range(4)]
    state, score, *_ = nh.classify(True, samples)
    assert state == "DEGRADED" and score < 70


# ── compute_score() ─────────────────────────────────────────────────────────

def test_score_none_without_successes():
    assert nh.compute_score([_sample(ok=False) for _ in range(3)]) == 0

def test_score_bounds_0_100():
    fast = nh.compute_score([_sample(ok=True, ws=10, e2e=50) for _ in range(5)])
    slow = nh.compute_score([_sample(ok=True, ws=700, e2e=5000) for _ in range(5)])
    assert 0 <= fast <= 100 and 0 <= slow <= 100
    assert fast > slow

def test_score_penalizes_loss():
    clean = nh.compute_score([_sample(ok=True) for _ in range(6)])
    lossy = nh.compute_score([_sample(ok=True) for _ in range(4)] + [_sample(ok=False), _sample(ok=False)])
    assert clean > lossy

def test_score_zero_when_all_fail():
    assert nh.compute_score([_sample(ok=False)]) == 0


# ── record_probe() with injected probe fn ──────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_engine():
    nh._records.clear()
    nh._history.clear()
    nh._probe_fn = None
    nh._allowed_fn = None
    yield
    nh._records.clear()
    nh._history.clear()
    nh._probe_fn = None
    nh._allowed_fn = None


@pytest.mark.asyncio
async def test_record_probe_healthy_transition():
    link = {"protocol": "vless-ws", "active": True}
    for _ in range(3):
        rec = await nh.record_probe("uid-1", link,
                                    {"ok": True, "ws_ms": 90, "e2e_ms": 260, "checked_at": "now"})
    assert rec.state == "HEALTHY"
    assert rec.samples == 3
    assert rec.consecutive_ok == 3
    assert "health" in link  # attached for persistence

@pytest.mark.asyncio
async def test_record_probe_unreachable_then_recover():
    link = {"protocol": "vless-ws", "active": True}
    rec = await nh.record_probe("uid-2", link, {"ok": False, "detail": "TLS fail"})
    assert rec.state == "UNREACHABLE"
    assert rec.consecutive_fail == 1
    rec = await nh.record_probe("uid-2", link, {"ok": True, "ws_ms": 100, "e2e_ms": 300})
    assert rec.state in ("HEALTHY", "DEGRADED")  # recovered but 50% history loss → DEGRADED
    assert rec.loss_pct == 50.0

@pytest.mark.asyncio
async def test_record_probe_not_allowed_marks_invalid():
    nh.set_allowed_fn(lambda link: False)
    link = {"protocol": "vless-ws", "active": False}
    rec = await nh.record_probe("uid-3", link, {"ok": True, "ws_ms": 50, "e2e_ms": 100})
    assert rec.state == "INVALID"

def test_mark_invalid():
    rec = nh.mark_invalid("uid-4", {"protocol": "mtproto"}, "expired")
    assert rec.state == "INVALID" and "expired" in rec.error

@pytest.mark.asyncio
async def test_probe_config_unwired_engine_is_honest():
    # no probe fn injected → INVALID with explicit reason, never fake ok
    rec = await nh.probe_config("uid-5", {"protocol": "vless-ws", "active": True})
    assert rec.state == "INVALID"
    assert "not wired" in (rec.error or "")

@pytest.mark.asyncio
async def test_probe_config_with_fake_executor():
    async def fake_probe(uid, link, via="direct"):
        return {"ok": True, "ws_ms": 80, "e2e_ms": 220, "checked_at": "t"}
    nh.set_probe_fn(fake_probe)
    link = {"protocol": "vless-ws", "active": True}
    for _ in range(2):
        rec = await nh.probe_config("uid-6", link)
    assert rec.state == "HEALTHY"

@pytest.mark.asyncio
async def test_sweep_with_injected_provider():
    async def fake_probe(uid, link, via="direct"):
        return {"ok": True, "ws_ms": 80, "e2e_ms": 220}
    nh.set_probe_fn(fake_probe)
    async def provider():
        return [("uid-a", {"protocol": "vless-ws", "active": True})]
    result = await nh.sweep(links_provider=provider)
    assert result["ok"] and result["total"] == 1
    assert result["by_state"].get("HEALTHY") == 1

@pytest.mark.asyncio
async def test_sweep_unwired_returns_not_ok():
    async def provider():
        return []
    result = await nh.sweep(links_provider=provider)
    assert not result["ok"]


# ── Subscription filtering ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_healthy_uids_filter():
    link = {"protocol": "vless-ws", "active": True}
    for _ in range(3):
        await nh.record_probe("good-1", link, {"ok": True, "ws_ms": 70, "e2e_ms": 200})
    await nh.record_probe("bad-1", link, {"ok": False})
    healthy = set(nh.healthy_uids())
    assert "good-1" in healthy and "bad-1" not in healthy


def test_summary_shape():
    s = nh.summary()
    assert s["tracked"] == len(nh._records)
    assert set(s["by_state"].keys()) == set(nh.STATES)
