"""Unit tests for protocol_engine fallback chain (Batch 8)."""
import asyncio
import pytest

from protocol_engine import (
    ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
    HealthResult, LinkResult,
    register_protocol, get_protocol, unregister_protocol,
    run_with_fallback,
)
from protocol_engine.health import get_health, Sample
import time


class _SuccessAdapter(ProtocolAdapter):
    """Adapter whose operation always succeeds."""
    def __init__(self, name="success", delay=0.0, raises=None):
        super().__init__()
        self.name = name
        self.version = "1.0.0"
        self.description = "test"
        self._delay = delay
        self._raises = raises
        self._caps = Capabilities(
            transports=(Transport.TCP,),
            supports_tcp=True,
            supports_ipv4=True,
            supports_inbound=True,
            status=ProtocolStatus.STABLE,
            maturity="stable",
        )

    def capabilities(self): return self._caps
    def validate_config(self, c): return True, []
    def configure(self, c): pass
    def generate_link(self, p): return LinkResult(ok=True, link="test://x", protocol=self.name)
    async def health_check(self): return HealthResult(ok=True, rtt_ms=10.0)
    async def start(self): return True
    async def stop(self): return True


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    import protocol_engine.registry as reg_mod
    original = reg_mod._registry
    new_reg = reg_mod.ProtocolRegistry()
    monkeypatch.setattr(reg_mod, "_registry", new_reg)
    import protocol_engine as pe
    monkeypatch.setattr(pe, "list_protocols", new_reg.list_protocols)
    monkeypatch.setattr(pe, "get_protocol", new_reg.get_protocol)
    monkeypatch.setattr(pe, "get_enabled_protocols", new_reg.get_enabled_protocols)
    monkeypatch.setattr(pe, "register_protocol", new_reg.register_protocol)
    monkeypatch.setattr(pe, "unregister_protocol", new_reg.unregister_protocol)
    import protocol_engine.selector as sel_mod
    monkeypatch.setattr(sel_mod, "get_enabled_protocols", new_reg.get_enabled_protocols)
    # Record success samples so selector ranks them
    yield


def _record_success(name, rtt_ms=10.0):
    get_health(name).record(Sample(timestamp=time.time(), ok=True, rtt_ms=rtt_ms))


def test_fallback_succeeds_on_first_protocol():
    register_protocol(_SuccessAdapter("p1"))
    _record_success("p1", rtt_ms=10.0)

    async def op(name):
        return f"ok-{name}"

    result = asyncio.run(run_with_fallback(op, max_protocols=3))
    assert result.ok is True
    assert result.protocol_used == "p1"
    assert result.total_attempts == 1
    assert result.fallback_count == 0


def test_fallback_to_second_when_first_fails():
    register_protocol(_SuccessAdapter("p1-fail"))
    register_protocol(_SuccessAdapter("p2-ok"))
    _record_success("p1-fail", rtt_ms=10.0)
    _record_success("p2-ok", rtt_ms=20.0)

    async def op(name):
        if "p1" in name:
            raise RuntimeError("p1 always fails")
        return f"ok-{name}"

    result = asyncio.run(run_with_fallback(op, max_protocols=3, max_retries_per_protocol=0))
    assert result.ok is True
    assert result.protocol_used == "p2-ok"
    assert result.fallback_count == 1
    assert result.total_attempts == 2


def test_fallback_all_fail_returns_failure():
    register_protocol(_SuccessAdapter("p1"))
    register_protocol(_SuccessAdapter("p2"))
    _record_success("p1", rtt_ms=10.0)
    _record_success("p2", rtt_ms=20.0)

    async def op(name):
        raise RuntimeError(f"{name} always fails")

    result = asyncio.run(run_with_fallback(op, max_protocols=2, max_retries_per_protocol=0))
    assert result.ok is False
    assert result.protocol_used is None
    assert result.fallback_count == 1
    assert len(result.attempts) == 2


def test_fallback_respects_max_protocols():
    register_protocol(_SuccessAdapter("p1"))
    register_protocol(_SuccessAdapter("p2"))
    register_protocol(_SuccessAdapter("p3"))
    for n in ("p1", "p2", "p3"):
        _record_success(n, rtt_ms=10.0)

    async def op(name):
        raise RuntimeError(f"{name} fails")

    # max_protocols=1 → only try p1 (first ranked)
    result = asyncio.run(run_with_fallback(op, max_protocols=1, max_retries_per_protocol=0))
    assert result.ok is False
    assert result.total_attempts == 1


def test_fallback_attempts_has_per_protocol_detail():
    register_protocol(_SuccessAdapter("p1"))
    _record_success("p1", rtt_ms=10.0)

    async def op(name):
        return f"ok-{name}"

    result = asyncio.run(run_with_fallback(op))
    assert len(result.attempts) == 1
    a = result.attempts[0]
    assert a["protocol"] == "p1"
    assert a["ok"] is True
    assert "latency_ms" in a
