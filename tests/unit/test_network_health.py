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


# ═════════════════════════════════════════════════════════════════════════════
# Phase 37.5 — Layered health model (CONFIG→DNS→TCP→TLS→TRANSPORT→PROTOCOL
# →APPLICATION→LATENCY→LOSS→QUALITY). A layer without evidence is
# NOT_TESTABLE — never PASS.
# ═════════════════════════════════════════════════════════════════════════════

def test_layers_all_not_testable_by_default():
    # empty probe: CONFIG is checkable from the link record alone (PASS for a
    # valid default protocol) — every network layer stays NOT_TESTABLE
    layers = nh.derive_layers(True, {})
    assert set(layers.keys()) == set(nh.LAYERS)
    assert layers["config"] == "PASS"
    for layer in ("dns", "tcp", "tls", "transport", "protocol", "application"):
        assert layers[layer] == "NOT_TESTABLE", layer


def test_layers_config_fail_when_not_allowed():
    layers = nh.derive_layers(False, {"ok": False})
    assert layers["config"] == "FAIL"
    assert layers["dns"] == "NOT_TESTABLE"


def test_layers_config_fail_on_unknown_protocol():
    link = {"protocol": "not-a-protocol"}
    layers = nh.derive_layers(True, {"ok": False, "detail": "x"}, link)
    assert layers["config"] == "FAIL"


def test_layers_full_tunnel_success_certifies_all_layers():
    probe = {"ok": True, "ws_ms": 90.0, "e2e_ms": 250.0, "test": "ws-tunnel"}
    layers = nh.derive_layers(True, probe, {"protocol": "vless-ws"})
    for layer in ("config", "dns", "tcp", "tls", "transport", "protocol", "application"):
        assert layers[layer] == "PASS", layer
    assert layers["latency"] == "PASS"


def test_layers_tcp_only_probe_leaves_deeper_layers_not_testable():
    # MTProto probe: raw TCP only — TLS/transport/protocol/application are
    # honestly NOT_TESTABLE, never assumed PASS
    probe = {"ok": True, "ws_ms": 31.2, "e2e_ms": 31.2, "test": "tcp-connect"}
    layers = nh.derive_layers(True, probe, {"protocol": "mtproto"})
    assert layers["tcp"] == "PASS"
    for layer in ("tls", "transport", "protocol", "application"):
        assert layers[layer] == "NOT_TESTABLE", layer


def test_layers_dns_failure_located():
    probe = {"ok": False, "detail": "gaierror: name resolution failed"}
    layers = nh.derive_layers(True, probe, {"protocol": "vless-ws"})
    assert layers["dns"] == "FAIL"
    assert layers["tcp"] == "NOT_TESTABLE"


def test_layers_tcp_failure_located():
    probe = {"ok": False, "detail": "ConnectionRefusedError: [Errno 111]"}
    layers = nh.derive_layers(True, probe, {"protocol": "vless-ws"})
    assert layers["dns"] == "PASS" and layers["tcp"] == "FAIL"
    assert layers["tls"] == "NOT_TESTABLE"


def test_layers_tls_failure_located():
    probe = {"ok": False, "detail": "ssl.SSLError: handshake_failure"}
    layers = nh.derive_layers(True, probe, {"protocol": "vless-ws"})
    assert layers["dns"] == "PASS" and layers["tcp"] == "PASS"
    assert layers["tls"] == "FAIL"


def test_layers_protocol_failure_with_handshake_ok():
    # ws_ms present → TLS + transport channel came up; failure at protocol
    probe = {"ok": False, "ws_ms": 88.0, "detail": "unexpected reply"}
    layers = nh.derive_layers(True, probe, {"protocol": "trojan-ws"})
    assert layers["tls"] == "PASS" and layers["transport"] == "PASS"
    assert layers["protocol"] == "FAIL"


def test_finalize_layers_latency_loss_quality():
    samples = [nh.ProbeSample(ts=1, ok=True, ws_ms=50, e2e_ms=200),
               nh.ProbeSample(ts=2, ok=True, ws_ms=50, e2e_ms=220)]
    layers = nh.finalize_layers(nh._empty_layers(), samples, 90)
    assert layers["latency"] == "PASS" and layers["loss"] == "PASS"
    assert layers["quality"] == "PASS"
    layers = nh.finalize_layers(nh._empty_layers(), samples, 40)
    assert layers["quality"] == "FAIL"


@pytest.mark.asyncio
async def test_record_probe_attaches_layers():
    link = {"protocol": "vless-ws", "active": True}
    rec = await nh.record_probe("uid-l", link,
                                {"ok": True, "ws_ms": 70, "e2e_ms": 200,
                                 "test": "ws-tunnel", "ts": time.time()})
    assert rec.layers["protocol"] == "PASS"
    assert link["health"]["layers"]["tls"] == "PASS"


# ═════════════════════════════════════════════════════════════════════════════
# Phase 37.6 — score audit: deterministic formula + the six node archetypes
# ═════════════════════════════════════════════════════════════════════════════

def test_score_formula_documented():
    f = nh.score_formula()
    assert "availability" in f and "jitter" in f and "deterministic" in f


def test_score_deterministic():
    samples = [nh.ProbeSample(ts=i, ok=True, ws_ms=100 + i, e2e_ms=300 + 10 * i)
               for i in range(5)]
    assert nh.compute_score(samples) == nh.compute_score(list(samples))


def test_archetype_excellent_node():
    samples = [nh.ProbeSample(ts=i, ok=True, ws_ms=60, e2e_ms=180)
               for i in range(6)]
    score = nh.compute_score(samples)
    state, score, _ = nh.classify(True, samples)
    assert state == "HEALTHY" and score >= 90


def test_archetype_high_latency_node():
    samples = [nh.ProbeSample(ts=i, ok=True, ws_ms=300, e2e_ms=1900)
               for i in range(6)]
    state, score, _ = nh.classify(True, samples)
    # hard latency gate: DEGRADED even though stability keeps the score up —
    # a 1.9s-mean tunnel is never HEALTHY regardless of numeric score
    assert state == "DEGRADED"
    assert score is not None and score < 90


def test_archetype_high_loss_node():
    samples = ([nh.ProbeSample(ts=i, ok=True, ws_ms=100, e2e_ms=400)
                for i in range(4)] +
               [nh.ProbeSample(ts=10 + i, ok=False) for i in range(4)])
    state, score, _ = nh.classify(True, samples)
    assert state in ("DEGRADED", "UNREACHABLE") and score < 70


def test_archetype_unstable_node():
    # alternating ok/fail ENDING ON OK — flaky history while currently up
    samples = [nh.ProbeSample(ts=i, ok=(i % 2 == 1), ws_ms=100, e2e_ms=400)
               for i in range(8)]
    state, score, _ = nh.classify(True, samples)
    assert state == "DEGRADED" and score < 90


def test_archetype_offline_node():
    # all probes fail + runtime OFFLINE context → score 0
    samples = [nh.ProbeSample(ts=i, ok=False) for i in range(3)]
    state, score, _ = nh.classify(True, samples, runtime_state="OFFLINE")
    assert state == "UNREACHABLE" and score == 0


def test_archetype_unknown_node():
    state, score, err = nh.classify(True, [])
    assert state == "UNKNOWN" and score is None and err is None


def test_runtime_state_context_penalty():
    samples = [nh.ProbeSample(ts=i, ok=True, ws_ms=60, e2e_ms=180)
               for i in range(5)]
    base = nh.compute_score(samples)
    degraded = nh.compute_score(samples, runtime_state="DEGRADED")
    offline = nh.compute_score(samples, runtime_state="OFFLINE")
    assert offline == 0
    assert degraded < base


def test_node_load_context_penalty():
    samples = [nh.ProbeSample(ts=i, ok=True, ws_ms=60, e2e_ms=180)
               for i in range(5)]
    base = nh.compute_score(samples)
    loaded = nh.compute_score(samples, node_load=90)
    mid = nh.compute_score(samples, node_load=75)
    assert loaded < mid < base


def test_jitter_component_counts():
    steady = [nh.ProbeSample(ts=i, ok=True, ws_ms=60, e2e_ms=200)
              for i in range(4)]
    jumpy = [nh.ProbeSample(ts=i, ok=True, ws_ms=60, e2e_ms=200 + (300 if i % 2 else 0))
             for i in range(4)]
    assert nh.compute_score(steady) > nh.compute_score(jumpy)


# ═════════════════════════════════════════════════════════════════════════════
# Phase 37.11 — health expiry (fresh evidence only)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_health_expires_to_unknown():
    link = {"protocol": "vless-ws", "active": True}
    rec = await nh.record_probe("uid-e", link,
                                {"ok": True, "ws_ms": 70, "e2e_ms": 200,
                                 "ts": time.time()})
    assert rec.effective_state() == "HEALTHY"
    # age the evidence past the TTL
    rec.checked_ts = time.time() - (nh.HEALTH_TTL_SECONDS + 1)
    assert rec.is_expired()
    assert rec.effective_state() == "UNKNOWN"
    d = rec.to_dict()
    assert d["effective_state"] == "UNKNOWN" and d["expired"] is True
    # healthy_uids must not include expired evidence (37.13)
    assert "uid-e" not in nh.healthy_uids()


@pytest.mark.asyncio
async def test_health_expires_at_exposed():
    link = {"protocol": "vless-ws", "active": True}
    rec = await nh.record_probe("uid-e2", link,
                                {"ok": True, "ws_ms": 70, "e2e_ms": 200,
                                 "ts": time.time()})
    assert rec.health_expires_at is not None
    assert "health_expires_at" in rec.to_dict()


def test_summary_reports_expired_count_and_ttl():
    s = nh.summary()
    assert "expired" in s and s["health_ttl_s"] == nh.HEALTH_TTL_SECONDS
    assert s["engine"] == "network_health/2.0"
