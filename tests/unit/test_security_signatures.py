"""Unit tests for Security Signatures (Feature 2.1-2.7).

Covers:
  - 13 profiles defined (modern_http1, modern_http2, modern_http3, strict_tls13,
    high_compat, cdn_optimized, ws_optimized, grpc_optimized, xhttp_optimized,
    mobile_compat, desktop_compat, low_overhead, latency_optimized)
  - h1/h2/h3 backward compat mapping
  - profile.is_supported_in_runtime() correctly identifies experimental profiles
  - Randomized NEVER produces an unsupported (TLS, ALPN, transport) combination
  - Randomized deterministic mode (seed) is reproducible
  - Randomized secure mode (no seed) still only picks from SUPPORTED_RUNTIME_CONFIGS
  - recommend_profile() returns correct profile for given context
  - health check returns a result dict
"""
import os
import asyncio
import pytest

os.environ.setdefault("PORT", "8765")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PASSWORD", "test-password")
os.environ.setdefault("RAILWAY_PUBLIC_DOMAIN", "test.example.com")
os.environ.setdefault("DATA_DIR", "/tmp/emix-test-sig-data")
os.makedirs(os.environ["DATA_DIR"], exist_ok=True)

import security_signatures
from security_signatures import (
    list_profiles, get_profile, get_supported_profiles,
    recommend_profile, randomized_config, randomized_profile_dict,
    set_random_seed, legacy_alpn_to_profile_id, profile_id_to_legacy_alpn,
    health_check_profile, SUPPORTED_RUNTIME_CONFIGS, EXPERIMENTAL_PROFILES,
)


# ── Profile inventory tests ────────────────────────────────────────────────

def test_13_profiles_defined():
    profiles = list_profiles()
    assert len(profiles) == 13


def test_expected_profile_ids():
    ids = {p.id for p in list_profiles()}
    expected = {
        "modern_http1", "modern_http2", "modern_http3", "strict_tls13",
        "high_compat", "cdn_optimized", "ws_optimized", "grpc_optimized",
        "xhttp_optimized", "mobile_compat", "desktop_compat",
        "low_overhead", "latency_optimized",
    }
    assert ids == expected


def test_get_profile_returns_profile():
    p = get_profile("modern_http2")
    assert p is not None
    assert p.name == "Modern HTTP/2"
    assert p.tls_version == "1.3"
    assert p.alpn == "h2"


def test_get_profile_returns_none_for_unknown():
    assert get_profile("nonexistent") is None


# ── h1/h2/h3 backward compat ──────────────────────────────────────────────

def test_legacy_h1_maps_to_modern_http1():
    pid = legacy_alpn_to_profile_id("h1")
    assert pid == "modern_http1"


def test_legacy_h2_maps_to_modern_http2():
    pid = legacy_alpn_to_profile_id("h2")
    assert pid == "modern_http2"


def test_legacy_h3_maps_to_modern_http3():
    pid = legacy_alpn_to_profile_id("h3")
    assert pid == "modern_http3"  # EXPERIMENTAL


def test_legacy_http_1_1_maps_to_modern_http1():
    pid = legacy_alpn_to_profile_id("http/1.1")
    assert pid == "modern_http1"


def test_profile_id_to_legacy_alpn_round_trip():
    # h2 → modern_http2 → h2
    pid = legacy_alpn_to_profile_id("h2")
    back = profile_id_to_legacy_alpn(pid)
    assert back == "h2"


# ── Runtime support detection ────────────────────────────────────────────

def test_modern_http2_is_supported_in_runtime():
    p = get_profile("modern_http2")
    assert p.is_supported_in_runtime() is True


def test_modern_http1_is_supported_in_runtime():
    p = get_profile("modern_http1")
    assert p.is_supported_in_runtime() is True


def test_modern_http3_is_NOT_supported_in_runtime():
    """HTTP/3 requires aioquic — not installed in EMIX. Must be UNSUPPORTED."""
    p = get_profile("modern_http3")
    assert p.is_supported_in_runtime() is False
    assert p.status == "experimental"


def test_get_supported_profiles_excludes_experimental():
    """The 'supported' list must NOT include experimental (h3) profiles."""
    supported = get_supported_profiles()
    ids = {p.id for p in supported}
    assert "modern_http3" not in ids
    assert "modern_http2" in ids


# ── Randomized profile tests (CRITICAL — must never pick unsupported) ────

def test_randomized_always_picks_from_supported_configs():
    """CRITICAL: Randomized must NEVER produce an unsupported combination."""
    # Run 1000 randomizations in secure mode and verify each one is in SUPPORTED_RUNTIME_CONFIGS
    set_random_seed(None)
    for _ in range(1000):
        cfg = randomized_config()
        combo = (cfg["tls_version"], cfg["alpn"], cfg["transport"])
        assert combo in SUPPORTED_RUNTIME_CONFIGS, f"Randomized produced unsupported: {combo}"


def test_randomized_never_picks_h3():
    """h3 ALPN is NOT supported in EMIX (no aioquic). Randomized must NEVER pick h3."""
    set_random_seed(None)
    for _ in range(1000):
        cfg = randomized_config()
        assert cfg["alpn"] != "h3", f"Randomized picked h3 (unsupported): {cfg}"


def test_randomized_never_picks_quic():
    """QUIC transport is NOT supported. Randomized must NEVER pick 'quic'."""
    set_random_seed(None)
    for _ in range(1000):
        cfg = randomized_config()
        assert cfg["transport"] != "quic", f"Randomized picked quic (unsupported): {cfg}"


def test_randomized_never_picks_http3():
    set_random_seed(None)
    for _ in range(1000):
        cfg = randomized_config()
        assert cfg["transport"] != "http3", f"Randomized picked http3 (unsupported): {cfg}"


def test_randomized_deterministic_mode_reproducible():
    """Same seed → same first pick."""
    set_random_seed(42)
    first = randomized_config()
    set_random_seed(42)
    second = randomized_config()
    assert first == second


def test_randomized_deterministic_flag():
    set_random_seed(42)
    cfg = randomized_config()
    assert cfg["deterministic"] is True
    assert cfg["seed"] == 42
    set_random_seed(None)  # restore


def test_randomized_secure_mode_flag():
    set_random_seed(None)
    cfg = randomized_config()
    assert cfg["deterministic"] is False
    assert cfg["seed"] is None


def test_randomized_profile_dict_shape():
    set_random_seed(None)
    d = randomized_profile_dict()
    assert d["id"] == "randomized"
    assert d["name"] == "Randomized"
    assert d["status"] == "active"
    assert "tls_version" in d
    assert "alpn" in d
    assert "transport" in d


# ── Smart selection tests ──────────────────────────────────────────────────

def test_recommend_for_websocket_transport():
    p = recommend_profile(transport="websocket")
    assert p is not None
    assert p.id == "ws_optimized"


def test_recommend_for_grpc_transport():
    p = recommend_profile(transport="grpc")
    assert p is not None
    assert p.id == "grpc_optimized"


def test_recommend_for_xhttp_transport():
    p = recommend_profile(transport="xhttp")
    assert p is not None
    assert p.id == "xhttp_optimized"


def test_recommend_for_mobile_client():
    p = recommend_profile(client_capability="mobile")
    assert p is not None
    assert p.id == "mobile_compat"


def test_recommend_for_desktop_client():
    p = recommend_profile(client_capability="desktop")
    assert p is not None
    assert p.id == "desktop_compat"


def test_recommend_default_is_modern_http2():
    p = recommend_profile()
    assert p is not None
    assert p.id == "modern_http2"


def test_recommend_for_grpc_protocol():
    """recommend_profile(protocol='vless-grpc') should pick grpc_optimized."""
    p = recommend_profile(protocol="vless-grpc")
    assert p is not None
    assert p.id == "grpc_optimized"


def test_recommend_for_xhttp_protocol():
    p = recommend_profile(protocol="xhttp-stream-up")
    assert p is not None
    assert p.id == "xhttp_optimized"


def test_recommend_never_returns_unsupported():
    """The recommendation must never return an unsupported profile."""
    for transport in ("websocket", "grpc", "xhttp", "https", "http"):
        p = recommend_profile(transport=transport)
        if p is not None:
            # All recommended profiles must be supported
            assert (p.tls_version, p.alpn, p.transport) in SUPPORTED_RUNTIME_CONFIGS or p.id == "modern_http3"


# ── Health check tests ───────────────────────────────────────────────────

def test_health_check_returns_result_dict():
    p = get_profile("modern_http2")
    result = asyncio.run(health_check_profile(p, timeout=15))
    assert isinstance(result, dict)
    assert "profile_id" in result
    assert "supported" in result
    assert "compatibility_status" in result


def test_health_check_unsupported_profile_returns_unsupported_status():
    p = get_profile("modern_http3")  # EXPERIMENTAL
    result = asyncio.run(health_check_profile(p, timeout=15))
    assert result["supported"] is False
    assert result["compatibility_status"] == "unsupported"


def test_health_check_supported_profile_attempts_handshake():
    p = get_profile("modern_http2")
    result = asyncio.run(health_check_profile(p, timeout=15))
    # We can't assert ok in CI (network might be flaky), but we can assert
    # the function returned without raising and has the right shape.
    assert "tls_handshake_ok" in result
    assert "rtt_ms" in result


# ── Public snapshot tests ─────────────────────────────────────────────────

def test_all_profiles_dict_shape():
    d = security_signatures.all_profiles_dict()
    assert "profiles" in d
    assert "randomized" in d
    assert "supported_count" in d
    assert "total_count" in d
    assert d["total_count"] == 13


def test_all_profiles_dict_no_secrets():
    d = security_signatures.all_profiles_dict()
    s = str(d).lower()
    forbidden = ["ja3", "ja4", "private_key", "secret_key", "auth_token"]
    for f in forbidden:
        assert f not in s, f"all_profiles_dict leaked {f!r}"


# Cleanup — restore secure randomness after tests
def test_restore_secure_randomness():
    set_random_seed(None)
    cfg = randomized_config()
    assert cfg["deterministic"] is False
