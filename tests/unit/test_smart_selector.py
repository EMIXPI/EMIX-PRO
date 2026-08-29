"""Unit tests for protocol_engine smart selector (Batch 8).

Verifies:
  - score_protocol returns 0 for unknown/DEFERRED
  - score_protocol returns >0 for healthy stable adapter
  - select_best returns the highest-scoring protocol
  - rank_protocols sorts by score descending
  - profiles exist + 'stable' is the default
  - SelectorWeights reads from env vars
"""
import os
import asyncio
import time
import pytest

from protocol_engine import (
    ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
    HealthResult, LinkResult,
    score_protocol, select_best, rank_protocols,
    get_profile, list_profiles, SelectorWeights,
    register_protocol, get_protocol, unregister_protocol,
    get_registry,
)
from protocol_engine.health import get_health, Sample


class _HealthyAdapter(ProtocolAdapter):
    """Test adapter that reports successful health checks."""
    def __init__(self, name="healthy"):
        super().__init__()
        self.name = name
        self.version = "1.0.0"
        self.description = "test"
        self._caps = Capabilities(
            transports=(Transport.TCP,),
            supports_tcp=True,
            supports_ipv4=True,
            supports_link_generation=True,
            supports_health_check=True,
            supports_inbound=True,
            status=ProtocolStatus.STABLE,
            maturity="stable",
        )

    def capabilities(self): return self._caps
    def validate_config(self, c): return True, []
    def configure(self, c): pass
    def generate_link(self, p): return LinkResult(ok=True, link="test://link", protocol=self.name)
    async def health_check(self): return HealthResult(ok=True, rtt_ms=10.0)
    async def start(self): return True
    async def stop(self): return True


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    """Use a fresh registry for each test so we don't pollute the global one."""
    # Save the original global registry
    import protocol_engine.registry as reg_mod
    original = reg_mod._registry
    new_reg = reg_mod.ProtocolRegistry()
    monkeypatch.setattr(reg_mod, "_registry", new_reg)
    # Patch the top-level functions too
    import protocol_engine as pe
    monkeypatch.setattr(pe, "list_protocols", new_reg.list_protocols)
    monkeypatch.setattr(pe, "get_protocol", new_reg.get_protocol)
    monkeypatch.setattr(pe, "get_enabled_protocols", new_reg.get_enabled_protocols)
    monkeypatch.setattr(pe, "register_protocol", new_reg.register_protocol)
    monkeypatch.setattr(pe, "unregister_protocol", new_reg.unregister_protocol)
    # Also patch selector module which imports get_enabled_protocols at call-time
    import protocol_engine.selector as sel_mod
    monkeypatch.setattr(sel_mod, "get_enabled_protocols", new_reg.get_enabled_protocols)
    yield
    # Restore
    monkeypatch.setattr(reg_mod, "_registry", original)


def _record_sample(name, ok, rtt_ms=10.0):
    get_health(name).record(Sample(
        timestamp=time.time(), ok=ok, rtt_ms=rtt_ms,
    ))


def test_score_protocol_unknown_returns_zero():
    s = score_protocol("nonexistent")
    assert s["score"] == 0.0


def test_score_protocol_no_health_data_returns_low_score():
    register_protocol(_HealthyAdapter("test-no-data"))
    s = score_protocol("test-no-data")
    # No health data → success_rate=0, avg_rtt=None → low score but not error
    assert s["score"] >= 0
    assert "error" not in s  # adapter is registered + STABLE


def test_score_protocol_with_success_has_high_score():
    register_protocol(_HealthyAdapter("healthy"))
    _record_sample("healthy", ok=True, rtt_ms=20.0)
    s = score_protocol("healthy")
    assert s["score"] > 0.5
    assert s["success_rate"] == 1.0


def test_score_protocol_with_failures_has_lower_score():
    register_protocol(_HealthyAdapter("flaky"))
    _record_sample("flaky", ok=True, rtt_ms=20.0)
    _record_sample("flaky", ok=False)
    _record_sample("flaky", ok=False)
    s = score_protocol("flaky")
    assert s["success_rate"] < 1.0
    assert s["consecutive_failures"] == 2


def test_select_best_returns_highest_scoring():
    register_protocol(_HealthyAdapter("slow"))
    register_protocol(_HealthyAdapter("fast"))
    _record_sample("slow", ok=True, rtt_ms=400.0)
    _record_sample("fast", ok=True, rtt_ms=10.0)
    best = select_best()
    assert best is not None
    assert best["name"] == "fast"


def test_select_best_returns_none_when_no_candidates():
    best = select_best()
    assert best is None


def test_rank_protocols_sorts_by_score_descending():
    register_protocol(_HealthyAdapter("slow"))
    register_protocol(_HealthyAdapter("fast"))
    _record_sample("slow", ok=True, rtt_ms=400.0)
    _record_sample("fast", ok=True, rtt_ms=10.0)
    ranked = rank_protocols()
    assert len(ranked) >= 2
    assert ranked[0]["score"] >= ranked[1]["score"]
    assert ranked[0]["name"] == "fast"


def test_profiles_list_includes_defaults():
    profiles = list_profiles()
    assert "stable" in profiles
    assert "mobile" in profiles
    assert "high_latency" in profiles
    assert "udp_friendly" in profiles
    assert "restricted" in profiles


def test_get_profile_returns_stable_for_unknown():
    p = get_profile("nonexistent")
    assert p == get_profile("stable")


def test_get_profile_returns_prefer_transports():
    p = get_profile("mobile")
    assert "prefer_transports" in p
    assert "tcp" in p["prefer_transports"]


def test_selector_weights_reads_env(monkeypatch):
    monkeypatch.setenv("EMIX_SELECTOR_W_RELIABILITY", "0.5")
    monkeypatch.setenv("EMIX_SELECTOR_W_LATENCY", "0.3")
    w = SelectorWeights()
    assert w.reliability == 0.5
    assert w.latency == 0.3
