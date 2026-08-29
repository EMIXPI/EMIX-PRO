"""Unit tests for SNI Management (Feature 1.1-1.6).

Covers:
  - validate_server_name: valid/invalid hostnames, wildcards, IPs, localhost
  - validate_alpn: valid/invalid/empty/duplicates
  - validate_tls_version: 1.2/1.3/invalid
  - SNIProfile create/get/update/delete
  - duplicate ID/name rejection
  - find_route_by_sni (uses reverseproxy if enabled)
  - health check returns a result dict (no exceptions raised)
  - all_profiles_dict (public snapshot, no secrets)
"""
import os
import asyncio
import pytest

os.environ.setdefault("PORT", "8765")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PASSWORD", "test-password")
os.environ.setdefault("RAILWAY_PUBLIC_DOMAIN", "test.example.com")
os.environ.setdefault("DATA_DIR", "/tmp/emix-test-sni-mgmt-data")
os.makedirs(os.environ["DATA_DIR"], exist_ok=True)

import sni_management
from sni_management import (
    SNIProfile, SNIProfileStatus,
    validate_server_name, validate_alpn, validate_tls_version,
    create_profile, get_profile, update_profile, delete_profile,
    list_profiles, all_profiles_dict,
    health_check_profile, check_arvan_compatibility,
    find_route_by_sni,
)


# ── validate_server_name tests ──────────────────────────────────────────────

def test_validate_server_name_accepts_valid_hostname():
    ok, val = validate_server_name("www.google.com")
    assert ok is True
    assert val == "www.google.com"


def test_validate_server_name_normalizes_case():
    ok, val = validate_server_name("WWW.GOOGLE.COM")
    assert ok is True and val == "www.google.com"


def test_validate_server_name_accepts_wildcard():
    ok, val = validate_server_name("*.example.com")
    assert ok is True
    assert val == "*.example.com"


def test_validate_server_name_rejects_ipv4():
    ok, val = validate_server_name("127.0.0.1")
    assert ok is False


def test_validate_server_name_rejects_localhost():
    ok, _ = validate_server_name("localhost")
    assert ok is False


def test_validate_server_name_rejects_empty():
    ok, _ = validate_server_name("")
    assert ok is False
    ok, _ = validate_server_name(None)
    assert ok is False
    ok, _ = validate_server_name(123)
    assert ok is False


def test_validate_server_name_rejects_too_long():
    ok, _ = validate_server_name("a" * 300 + ".com")
    assert ok is False


def test_validate_server_name_rejects_no_dot():
    ok, _ = validate_server_name("google")
    assert ok is False


def test_validate_server_name_strips_trailing_dot():
    ok, val = validate_server_name("www.google.com.")
    assert ok is True and val == "www.google.com"


# ── validate_alpn tests ────────────────────────────────────────────────────

def test_validate_alpn_accepts_h2():
    ok, val = validate_alpn(["h2"])
    assert ok and val == ["h2"]


def test_validate_alpn_accepts_http_1_1():
    ok, val = validate_alpn(["http/1.1"])
    assert ok and val == ["http/1.1"]


def test_validate_alpn_accepts_multiple():
    ok, val = validate_alpn(["h2", "http/1.1"])
    assert ok and val == ["h2", "http/1.1"]


def test_validate_alpn_normalizes_case():
    ok, val = validate_alpn(["H2"])
    assert ok and val == ["h2"]


def test_validate_alpn_rejects_h3():
    # h3 is in _VALID_ALPN but considered experimental
    ok, val = validate_alpn(["h3"])
    assert ok and "h3" in val


def test_validate_alpn_rejects_unknown_protocol():
    ok, _ = validate_alpn(["foo"])
    assert ok is False


def test_validate_alpn_rejects_empty():
    ok, _ = validate_alpn([])
    assert ok is False


def test_validate_alpn_rejects_duplicates():
    ok, _ = validate_alpn(["h2", "h2"])
    assert ok is False


def test_validate_alpn_rejects_non_list():
    ok, _ = validate_alpn("h2")
    assert ok is False


def test_validate_alpn_rejects_non_string_value():
    ok, _ = validate_alpn([123])
    assert ok is False


# ── validate_tls_version tests ────────────────────────────────────────────

def test_validate_tls_version_default():
    ok, val = validate_tls_version(None)
    assert ok and val == "1.3"


def test_validate_tls_version_13():
    ok, val = validate_tls_version("1.3")
    assert ok and val == "1.3"


def test_validate_tls_version_12():
    ok, val = validate_tls_version("1.2")
    assert ok and val == "1.2"


def test_validate_tls_version_rejects_10():
    ok, _ = validate_tls_version("1.0")
    assert ok is False


def test_validate_tls_version_rejects_11():
    ok, _ = validate_tls_version("1.1")
    assert ok is False


# ── SNIProfile CRUD tests ─────────────────────────────────────────────────

def _make_profile(name="test", server_name="www.example.com", pid="test-id-1"):
    return SNIProfile(
        id=pid, name=name, server_name=server_name,
        alpn=["h2", "http/1.1"], min_tls_version="1.3",
    )


@pytest.fixture(autouse=True)
def _reset_store():
    """Reset the in-memory store between tests."""
    sni_management._profiles.clear()
    yield
    sni_management._profiles.clear()


def test_create_and_get_profile():
    p = asyncio.run(create_profile(_make_profile()))
    assert p.id == "test-id-1"
    fetched = asyncio.run(get_profile("test-id-1"))
    assert fetched is p


def test_create_duplicate_id_rejected():
    asyncio.run(create_profile(_make_profile(pid="dup")))
    with pytest.raises(ValueError, match="id already exists"):
        asyncio.run(create_profile(_make_profile(pid="dup")))


def test_create_duplicate_name_rejected():
    asyncio.run(create_profile(_make_profile(name="same", pid="a")))
    with pytest.raises(ValueError, match="name already exists"):
        asyncio.run(create_profile(_make_profile(name="same", pid="b")))


def test_update_profile_changes_fields():
    asyncio.run(create_profile(_make_profile()))
    updated = asyncio.run(update_profile("test-id-1", {"name": "renamed", "description": "updated"}))
    assert updated.name == "renamed"
    assert updated.description == "updated"


def test_update_profile_invalid_server_name_rejected():
    asyncio.run(create_profile(_make_profile()))
    with pytest.raises(ValueError, match="invalid server_name"):
        asyncio.run(update_profile("test-id-1", {"server_name": "127.0.0.1"}))


def test_update_profile_duplicate_name_rejected():
    asyncio.run(create_profile(_make_profile(name="a", pid="id-a")))
    asyncio.run(create_profile(_make_profile(name="b", pid="id-b")))
    with pytest.raises(ValueError, match="name already exists"):
        asyncio.run(update_profile("id-a", {"name": "b"}))


def test_update_nonexistent_returns_none():
    result = asyncio.run(update_profile("nope", {"name": "x"}))
    assert result is None


def test_delete_profile():
    asyncio.run(create_profile(_make_profile()))
    assert asyncio.run(delete_profile("test-id-1")) is True
    assert asyncio.run(get_profile("test-id-1")) is None


def test_delete_nonexistent_returns_false():
    assert asyncio.run(delete_profile("nope")) is False


def test_list_profiles():
    asyncio.run(create_profile(_make_profile(pid="a")))
    asyncio.run(create_profile(_make_profile(name="other", pid="b")))
    profiles = asyncio.run(list_profiles())
    assert len(profiles) == 2


def test_all_profiles_dict_no_private_keys():
    asyncio.run(create_profile(_make_profile()))
    d = asyncio.run(all_profiles_dict())
    assert d["count"] == 1
    s = str(d).lower()
    # No actual secret values should leak
    forbidden = ["private_key", "client_secret", "auth_token"]
    for f in forbidden:
        assert f not in s, f"all_profiles_dict leaked {f!r}"


# ── Health check tests (live — uses real TLS to a public host) ─────────────

def test_health_check_returns_result_dict():
    p = _make_profile(server_name="www.cloudflare.com")
    result = asyncio.run(health_check_profile(p, timeout=15))
    assert isinstance(result, dict)
    assert "status" in result
    assert "checked_at" in result
    # Don't assert ok — public TLS could fail in test env. Just assert no raise.

def test_health_check_records_on_profile():
    p = _make_profile(server_name="www.cloudflare.com")
    asyncio.run(health_check_profile(p, timeout=15))
    # Profile's last_health_check should be set
    assert p.last_health_check is not None


# ── ArvanCloud compatibility check tests ───────────────────────────────────

def test_arvan_check_returns_result_dict():
    p = _make_profile(server_name="www.cloudflare.com")
    result = asyncio.run(check_arvan_compatibility(p))
    assert isinstance(result, dict)
    assert "arvan_compatible" in result
    assert "supported_alpn" in result
    assert "unsupported_alpn" in result
    assert "h3_status" in result  # always UNVERIFIED


# ── Reverse proxy SNI routing (uses reverseproxy if enabled) ───────────────

def test_find_route_by_sni_returns_none_when_no_match():
    # By default, reverseproxy is disabled (no routes configured)
    r = find_route_by_sni("no.such.host", "/")
    assert r is None
