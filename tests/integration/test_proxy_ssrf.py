"""Integration tests for /proxy SSRF protection (Phase 7.14).

These tests exercise the _validate_proxy_url helper directly. They do NOT
need a running FastAPI app — the function is pure-Python and self-contained.

Covers:
  - localhost rejected
  - 127.0.0.1 rejected
  - private IPv4 ranges (10.x, 172.16.x, 192.168.x) rejected
  - link-local 169.254.x rejected (incl. AWS metadata 169.254.169.254)
  - IPv6 loopback ::1 rejected
  - public IP / public hostname accepted
  - .internal / .local hostnames rejected
  - explicit EMIX_PROXY_ALLOW_PRIVATE=1 allows private
"""
import os
import pytest
import sys

# Force-test env BEFORE importing main (which builds the CORS middleware at
# import time and reads config_layer at import time).
os.environ.pop("EMIX_PROXY_ALLOW_PRIVATE", None)

from main import _validate_proxy_url, _PROXY_ALLOWED_HEADERS, _SENSITIVE, _HOP  # noqa: E402


def test_localhost_rejected():
    with pytest.raises(Exception):
        _validate_proxy_url("http://localhost:8000/")


def test_ipv4_loopback_rejected():
    with pytest.raises(Exception):
        _validate_proxy_url("http://127.0.0.1/")


def test_aws_metadata_rejected():
    """169.254.169.254 is in link-local range — AWS metadata endpoint."""
    with pytest.raises(Exception):
        _validate_proxy_url("http://169.254.169.254/latest/meta-data/")


def test_private_class_a_rejected():
    with pytest.raises(Exception):
        _validate_proxy_url("http://10.0.0.1/")


def test_private_class_b_rejected():
    with pytest.raises(Exception):
        _validate_proxy_url("http://172.16.0.1/")


def test_private_class_c_rejected():
    with pytest.raises(Exception):
        _validate_proxy_url("http://192.168.1.1/")


def test_ipv6_loopback_rejected():
    with pytest.raises(Exception):
        _validate_proxy_url("http://[::1]/")


def test_internal_hostname_rejected():
    with pytest.raises(Exception):
        _validate_proxy_url("http://my-service.internal/")


def test_local_hostname_rejected():
    with pytest.raises(Exception):
        _validate_proxy_url("http://my-laptop.local/")


def test_public_ip_accepted():
    """8.8.8.8 is a public Google DNS — should pass."""
    url = _validate_proxy_url("http://8.8.8.8/")
    assert url.startswith("http://8.8.8.8")


def test_public_hostname_accepted():
    """example.com should pass (DNS resolves to public IPs)."""
    url = _validate_proxy_url("https://example.com/")
    assert url == "https://example.com/"


def test_protocol_prefix_added():
    """URLs without protocol should get https:// prepended."""
    url = _validate_proxy_url("example.com/")
    assert url == "https://example.com/"


def test_empty_url_rejected():
    with pytest.raises(Exception):
        _validate_proxy_url("")


def test_allow_private_when_env_set(monkeypatch):
    """EMIX_PROXY_ALLOW_PRIVATE=1 should allow private IPs."""
    # Reload config_layer with the env set
    monkeypatch.setenv("EMIX_PROXY_ALLOW_PRIVATE", "1")
    # The validation function reads _EMIX_RUNTIME_CFG (already imported).
    # We need to rebuild the config + reimport the function. For test
    # simplicity, we monkey-patch the config object directly.
    import main as _main
    original = _main._EMIX_RUNTIME_CFG
    from config_layer import EmixConfig
    new_cfg = EmixConfig(proxy_allow_private_targets=True)
    _main._EMIX_RUNTIME_CFG = new_cfg
    try:
        # Now private IPs should pass
        url = _main._validate_proxy_url("http://10.0.0.1/")
        assert "10.0.0.1" in url
    finally:
        _main._EMIX_RUNTIME_CFG = original


def test_sensitive_headers_set_includes_critical_names():
    """Defensive: ensure Cookie, Authorization, X-Forwarded-* are in _SENSITIVE."""
    for h in ("cookie", "authorization", "proxy-authorization",
              "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto",
              "forwarded"):
        assert h in _SENSITIVE, f"{h!r} missing from _SENSITIVE set"


def test_proxy_allowed_headers_does_not_include_sensitive():
    """Defensive: _PROXY_ALLOWED_HEADERS must not include any sensitive header."""
    for h in _SENSITIVE:
        assert h not in _PROXY_ALLOWED_HEADERS, (
            f"{h!r} should NOT be in _PROXY_ALLOWED_HEADERS"
        )
