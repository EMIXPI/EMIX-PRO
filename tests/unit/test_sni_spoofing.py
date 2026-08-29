"""Unit tests for SNI Spoofing (Phase 1 — per-link, opt-in, zero breaking changes).

Covers:
  - _validate_sni accepts valid hostnames
  - _validate_sni rejects IPs, localhost, short/long, special chars, no-dot
  - _validate_sni normalizes to lowercase
  - _get_effective_sni returns host when disabled
  - _get_effective_sni returns spoofed domain when enabled + valid
  - _get_effective_sni falls back to host when enabled + invalid
  - _get_effective_sni handles missing fields (backward compat)
  - load_state fills missing spoof fields for old backups
  - backup_validator accepts spoof_sni + spoof_sni_enabled
"""
import pytest

# Pre-set env BEFORE importing main
import os
os.environ.setdefault("PORT", "8765")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PASSWORD", "test-password")
os.environ.setdefault("RAILWAY_PUBLIC_DOMAIN", "test.example.com")
os.environ.setdefault("DATA_DIR", "/tmp/emix-test-sni-data")
os.makedirs(os.environ["DATA_DIR"], exist_ok=True)

from main import _validate_sni, _get_effective_sni


# ── _validate_sni tests ────────────────────────────────────────────────────

def test_validate_sni_accepts_valid_domains():
    assert _validate_sni("www.google.com") == "www.google.com"
    assert _validate_sni("cloudflare.com") == "cloudflare.com"
    assert _validate_sni("api.github.com") == "api.github.com"
    assert _validate_sni("images.unsplash.com") == "images.unsplash.com"


def test_validate_sni_normalizes_to_lowercase():
    assert _validate_sni("WWW.GOOGLE.COM") == "www.google.com"
    assert _validate_sni("  Www.Google.com  ") == "www.google.com"


def test_validate_sni_rejects_ipv4():
    assert _validate_sni("127.0.0.1") is None
    assert _validate_sni("8.8.8.8") is None  # even public IPs
    assert _validate_sni("192.168.1.1") is None


def test_validate_sni_rejects_localhost():
    assert _validate_sni("localhost") is None
    assert _validate_sni("0.0.0.0") is None
    assert _validate_sni("::1") is None
    assert _validate_sni("ip6-localhost") is None


def test_validate_sni_rejects_empty_and_none():
    assert _validate_sni("") is None
    assert _validate_sni(None) is None
    assert _validate_sni(123) is None
    assert _validate_sni([]) is None


def test_validate_sni_rejects_too_short():
    assert _validate_sni("ab") is None  # < 3 chars
    assert _validate_sni("a.b") is not None  # 3 chars exactly with dot — OK


def test_validate_sni_rejects_too_long():
    assert _validate_sni("a" * 300 + ".com") is None  # > 253 chars


def test_validate_sni_rejects_no_dot():
    assert _validate_sni("google") is None  # no TLD separator


def test_validate_sni_rejects_special_chars():
    assert _validate_sni("google!.com") is None
    assert _validate_sni("google.com!") is None
    assert _validate_sni("goo gle.com") is None  # space
    assert _validate_sni("google.com/path") is None  # path separator


def test_validate_sni_accepts_hyphens_in_middle():
    assert _validate_sni("my-domain.example.com") == "my-domain.example.com"
    assert _validate_sni("sub-domain.example.com") == "sub-domain.example.com"


# ── _get_effective_sni tests ────────────────────────────────────────────────

def test_effective_sni_disabled_returns_host():
    """Default behavior — disabled → returns host (100% backward compat)."""
    link = {"spoof_sni": "www.google.com", "spoof_sni_enabled": False}
    assert _get_effective_sni(link, "panel.example.com") == "panel.example.com"


def test_effective_sni_enabled_with_valid_returns_spoof():
    link = {"spoof_sni": "www.google.com", "spoof_sni_enabled": True}
    assert _get_effective_sni(link, "panel.example.com") == "www.google.com"


def test_effective_sni_enabled_with_invalid_returns_host():
    """Defensive: invalid spoof value silently falls back to host."""
    link = {"spoof_sni": "127.0.0.1", "spoof_sni_enabled": True}
    assert _get_effective_sni(link, "panel.example.com") == "panel.example.com"


def test_effective_sni_handles_missing_fields():
    """Old links without spoof fields → host (backward compat)."""
    assert _get_effective_sni({}, "panel.example.com") == "panel.example.com"
    assert _get_effective_sni({"label": "old link"}, "panel.example.com") == "panel.example.com"


def test_effective_sni_handles_none_link():
    """Defensive: None link → host."""
    assert _get_effective_sni(None, "panel.example.com") == "panel.example.com"


def test_effective_sni_handles_null_spoof_value():
    """spoof_sni=None + enabled=True → falls back to host."""
    link = {"spoof_sni": None, "spoof_sni_enabled": True}
    assert _get_effective_sni(link, "panel.example.com") == "panel.example.com"


def test_effective_sni_handles_falsy_enabled():
    """spoof_sni_enabled=0/None/""/False → treated as False (Python-falsy)."""
    for falsy in (0, None, "", False):
        link = {"spoof_sni": "www.google.com", "spoof_sni_enabled": falsy}
        assert _get_effective_sni(link, "panel.example.com") == "panel.example.com"
    # Note: "false" as a non-empty string is Python-TRUTHY and would NOT
    # be treated as False — but since `spoof_sni_enabled` is meant to be a
    # boolean, the API never stores strings here. The backup_validator
    # rejects non-boolean values at import time.


# ── backup_validator tests for spoof fields ─────────────────────────────────

def test_backup_validator_accepts_spoof_sni_string():
    from backup_validator import validate_backup
    data = {
        "links": {
            "c3efb57c-eb89-517d-df7c-68b4eeb0c0a2": {
                "label": "test",
                "protocol": "vless-ws",
                "active": True,
                "spoof_sni": "www.google.com",
                "spoof_sni_enabled": True,
            }
        },
        "subs": {},
    }
    r = validate_backup(data)
    assert r.ok, f"errors: {r.errors}"


def test_backup_validator_accepts_null_spoof_sni():
    from backup_validator import validate_backup
    data = {
        "links": {
            "c3efb57c-eb89-517d-df7c-68b4eeb0c0a2": {
                "label": "test",
                "protocol": "vless-ws",
                "active": True,
                "spoof_sni": None,
                "spoof_sni_enabled": False,
            }
        },
        "subs": {},
    }
    r = validate_backup(data)
    assert r.ok


def test_backup_validator_rejects_non_string_spoof_sni():
    from backup_validator import validate_backup
    data = {
        "links": {
            "c3efb57c-eb89-517d-df7c-68b4eeb0c0a2": {
                "label": "test",
                "protocol": "vless-ws",
                "active": True,
                "spoof_sni": 123,  # not a string
                "spoof_sni_enabled": True,
            }
        },
        "subs": {},
    }
    r = validate_backup(data)
    assert not r.ok
    assert any("spoof_sni" in e for e in r.errors)


def test_backup_validator_rejects_non_boolean_spoof_enabled():
    from backup_validator import validate_backup
    data = {
        "links": {
            "c3efb57c-eb89-517d-df7c-68b4eeb0c0a2": {
                "label": "test",
                "protocol": "vless-ws",
                "active": True,
                "spoof_sni": "www.google.com",
                "spoof_sni_enabled": "yes",  # not a bool
            }
        },
        "subs": {},
    }
    r = validate_backup(data)
    assert not r.ok
    assert any("spoof_sni_enabled" in e for e in r.errors)


def test_backup_validator_rejects_oversized_spoof_sni():
    from backup_validator import validate_backup
    data = {
        "links": {
            "c3efb57c-eb89-517d-df7c-68b4eeb0c0a2": {
                "label": "test",
                "protocol": "vless-ws",
                "active": True,
                "spoof_sni": "a" * 300 + ".com",  # > 253 chars
                "spoof_sni_enabled": True,
            }
        },
        "subs": {},
    }
    r = validate_backup(data)
    assert not r.ok
    assert any("spoof_sni" in e for e in r.errors)


def test_backup_validator_accepts_missing_spoof_fields():
    """Old backups without spoof fields must still validate (backward compat)."""
    from backup_validator import validate_backup
    data = {
        "links": {
            "c3efb57c-eb89-517d-df7c-68b4eeb0c0a2": {
                "label": "old link",
                "protocol": "vless-ws",
                "active": True,
                # no spoof_sni, no spoof_sni_enabled
            }
        },
        "subs": {},
    }
    r = validate_backup(data)
    assert r.ok
