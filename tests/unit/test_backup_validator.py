"""Unit tests for backup_validator (Phase 3.9).

Covers:
  - valid backup passes
  - top-level not dict → fail
  - missing required fields → warning/error
  - invalid UUID format → error
  - invalid protocol name → error
  - negative limits → error
  - invalid timestamps → error
  - nested malformed data → error
  - password_hash non-sha256 format → warning (but still ok)
"""
import pytest
from backup_validator import validate_backup, is_valid_backup


def _valid_link(uid="c3efb57c-eb89-517d-df7c-68b4eeb0c0a2", **overrides):
    base = {
        "label": "test link",
        "protocol": "vless-ws",
        "limit_bytes": 0,
        "used_bytes": 0,
        "active": True,
        "expires_at": None,
        "created_at": "2026-08-29T10:00:00",
    }
    base.update(overrides)
    return {uid: base}


def test_valid_backup_passes():
    data = {
        "kind": "rvg-backup",
        "version": "9.2",
        "links": _valid_link(),
        "subs": {},
        "node_keys": {},
        "nodes": {},
        "password_hash": "a" * 64,  # 64-char hex
    }
    r = validate_backup(data)
    assert r.ok, f"expected ok, got errors: {r.errors}"
    assert r.data is data


def test_non_dict_root_fails():
    assert not is_valid_backup([])
    assert not is_valid_backup("string")
    assert not is_valid_backup(None)
    assert not is_valid_backup(123)


def test_invalid_uuid_fails():
    data = {"links": {"not-a-uuid": {"label": "x", "protocol": "vless-ws", "active": True}}}
    r = validate_backup(data)
    assert not r.ok
    assert any("UUID" in e for e in r.errors)


def test_invalid_protocol_fails():
    data = {"links": _valid_link(protocol="invalid-proto")}
    r = validate_backup(data)
    assert not r.ok
    assert any("unknown protocol" in e for e in r.errors)


def test_negative_limit_bytes_fails():
    data = {"links": _valid_link(limit_bytes=-100)}
    r = validate_backup(data)
    assert not r.ok
    assert any("negative" in e for e in r.errors)


def test_negative_used_bytes_fails():
    data = {"links": _valid_link(used_bytes=-1)}
    r = validate_backup(data)
    assert not r.ok
    assert any("negative" in e for e in r.errors)


def test_invalid_timestamp_fails():
    data = {"links": _valid_link(expires_at="not-a-date")}
    r = validate_backup(data)
    assert not r.ok
    assert any("expires_at" in e for e in r.errors)


def test_active_must_be_boolean():
    data = {"links": _valid_link(active="yes")}
    r = validate_backup(data)
    assert not r.ok
    assert any("active" in e for e in r.errors)


def test_missing_links_warning():
    r = validate_backup({"subs": {}})
    assert not r.ok  # missing links is still an error


def test_password_hash_warning_for_non_sha256():
    """Non-sha256 hash is a warning, not an error (load_state ignores it)."""
    data = {
        "links": _valid_link(),
        "subs": {},
        "password_hash": "pbkdf2$210000$abcd$1234",
    }
    r = validate_backup(data)
    assert r.ok, f"non-sha256 hash should be warning not error: {r.errors}"
    assert any("password_hash" in w for w in r.warnings)


def test_node_keys_must_be_dict():
    data = {
        "links": _valid_link(),
        "subs": {},
        "node_keys": ["not", "a", "dict"],
    }
    r = validate_backup(data)
    assert not r.ok
    assert any("node_keys" in e for e in r.errors)


def test_unknown_fields_preserved():
    """Unknown top-level fields must not cause errors (they're preserved)."""
    data = {
        "links": _valid_link(),
        "subs": {},
        "unknown_future_field": {"anything": "goes"},
        "schema_version": 1,
    }
    r = validate_backup(data)
    assert r.ok, f"unknown fields should be tolerated: {r.errors}"


def test_subs_must_be_dict():
    data = {"links": _valid_link(), "subs": "not a dict"}
    r = validate_backup(data)
    assert not r.ok


def test_sub_link_ids_must_be_list_of_strings():
    data = {
        "links": _valid_link(),
        "subs": {
            "c3efb57c-eb89-517d-df7c-68b4eeb0c0a2": {
                "name": "test sub",
                "link_ids": [123, 456],  # not strings
            }
        },
    }
    r = validate_backup(data)
    assert not r.ok
    assert any("link_ids" in e for e in r.errors)
