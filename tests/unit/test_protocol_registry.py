"""Unit tests for the protocol_engine registry (Batch 8).

Verifies:
  - register_protocol() accepts a valid adapter
  - duplicate registration raises ValueError
  - unregister removes an adapter
  - get_protocol returns the registered adapter or None
  - list_protocols preserves registration order
  - get_enabled_protocols filters out DEFERRED + UNAVAILABLE
  - safe_register swallows errors without crashing
"""
import pytest

from protocol_engine import (
    ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
    ProtocolRegistry, HealthResult, LinkResult,
)


class _FakeAdapter(ProtocolAdapter):
    """A minimal adapter for tests."""
    def __init__(self, name="fake", status=ProtocolStatus.STABLE, enabled=True):
        super().__init__()
        self.name = name
        self.version = "1.0.0"
        self.description = "test adapter"
        self._caps = Capabilities(status=status)
        self.status.enabled = enabled

    def capabilities(self) -> Capabilities:
        return self._caps

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        return True, []

    def configure(self, config: dict) -> None:
        pass

    def generate_link(self, params: dict) -> LinkResult:
        return LinkResult(ok=True, link="fake://link", protocol=self.name)

    async def health_check(self) -> HealthResult:
        return HealthResult(ok=True)

    async def start(self) -> bool:
        return True

    async def stop(self) -> bool:
        return True


def test_register_and_get():
    r = ProtocolRegistry()
    a = _FakeAdapter("vless-ws")
    r.register_protocol(a)
    assert r.get_protocol("vless-ws") is a
    assert len(r.list_protocols()) == 1


def test_duplicate_registration_rejected():
    r = ProtocolRegistry()
    r.register_protocol(_FakeAdapter("vless-ws"))
    with pytest.raises(ValueError):
        r.register_protocol(_FakeAdapter("vless-ws"))


def test_unregister():
    r = ProtocolRegistry()
    a = _FakeAdapter("vless-ws")
    r.register_protocol(a)
    assert r.unregister_protocol("vless-ws") is True
    assert r.get_protocol("vless-ws") is None
    assert r.unregister_protocol("vless-ws") is False  # already gone


def test_list_protocols_preserves_order():
    r = ProtocolRegistry()
    r.register_protocol(_FakeAdapter("a"))
    r.register_protocol(_FakeAdapter("b"))
    r.register_protocol(_FakeAdapter("c"))
    names = [a.name for a in r.list_protocols()]
    assert names == ["a", "b", "c"]


def test_get_enabled_protocols_excludes_deferred_and_unavailable():
    r = ProtocolRegistry()
    r.register_protocol(_FakeAdapter("stable", status=ProtocolStatus.STABLE))
    r.register_protocol(_FakeAdapter("experimental", status=ProtocolStatus.EXPERIMENTAL))
    r.register_protocol(_FakeAdapter("deferred", status=ProtocolStatus.DEFERRED))
    r.register_protocol(_FakeAdapter("unavailable", status=ProtocolStatus.UNAVAILABLE))
    enabled = [a.name for a in r.get_enabled_protocols()]
    # STABLE and EXPERIMENTAL are enabled; DEFERRED and UNAVAILABLE are not
    assert "stable" in enabled
    assert "experimental" in enabled
    assert "deferred" not in enabled
    assert "unavailable" not in enabled


def test_get_enabled_protocols_excludes_disabled():
    r = ProtocolRegistry()
    r.register_protocol(_FakeAdapter("disabled", status=ProtocolStatus.STABLE, enabled=False))
    enabled = [a.name for a in r.get_enabled_protocols()]
    assert "disabled" not in enabled


def test_safe_register_swallows_errors():
    r = ProtocolRegistry()

    class _BrokenAdapter:
        name = "broken"
        # Not a ProtocolAdapter — should be rejected by safe_register
        def capabilities(self): return None

    # safe_register catches the error and returns False
    result = r.safe_register(lambda: _BrokenAdapter())
    assert result is False
    assert r.get_protocol("broken") is None


def test_safe_register_succeeds_for_valid():
    r = ProtocolRegistry()
    result = r.safe_register(lambda: _FakeAdapter("ok"))
    assert result is True
    assert r.get_protocol("ok") is not None


def test_to_dict_no_secrets():
    r = ProtocolRegistry()
    r.register_protocol(_FakeAdapter("test"))
    d = r.to_dict()
    assert "protocols" in d
    assert d["count"] == 1
    assert d["protocols"][0]["name"] == "test"
    # No actual secret values in the public view.
    # `supports_password_auth` is a capability flag name, not a secret —
    # check that no actual password VALUE leaks.
    s = str(d)
    forbidden = ["password_hash", "client_private_key", "secret_key", "auth_token", "session_token"]
    for f in forbidden:
        assert f not in s, f"registry.to_dict() leaked {f!r}"
