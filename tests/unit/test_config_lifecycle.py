"""Unit tests for config_lifecycle.py — Config Lifecycle Engine (Phase 37.11).

PURE derivation tests: policy states (EXPIRED/REVOKED) override network
evidence; health evidence expiry downgrades HEALTHY → VALIDATING; a config
is never permanently HEALTHY.
"""
import time

from datetime import datetime, timedelta

import config_lifecycle as cl


def _link(**kw):
    base = {"active": True, "limit_bytes": 0, "used_bytes": 0, "expires_at": None}
    base.update(kw)
    return base


def _health(state="HEALTHY", age_s=0.0, **kw):
    h = {"state": state, "checked_at": datetime.now().isoformat(),
         "checked_ts": time.time() - age_s}
    h.update(kw)
    return h


# ── policy layers override network evidence ────────────────────────────────

def test_disabled_link_is_revoked():
    state, reason = cl.derive_lifecycle(_link(active=False), _health())
    assert state == "REVOKED" and "disabled" in reason


def test_quota_exhausted_is_revoked():
    state, reason = cl.derive_lifecycle(_link(limit_bytes=100, used_bytes=100), _health())
    assert state == "REVOKED" and "quota" in reason


def test_time_expired_is_expired():
    state, reason = cl.derive_lifecycle(
        _link(expires_at=(datetime.now() - timedelta(hours=1)).isoformat()), _health())
    assert state == "EXPIRED" and "expiry" in reason


def test_future_expiry_not_expired():
    state, _ = cl.derive_lifecycle(
        _link(expires_at=(datetime.now() + timedelta(days=7)).isoformat()),
        _health())
    assert state == "HEALTHY"


# ── network evidence interpretation ────────────────────────────────────────

def test_no_evidence_is_validating():
    state, reason = cl.derive_lifecycle(_link(), None)
    assert state == "VALIDATING" and "no probe" in reason


def test_fresh_healthy_evidence_is_healthy():
    state, reason = cl.derive_lifecycle(_link(), _health("HEALTHY", age_s=0))
    assert state == "HEALTHY" and "fresh" in reason


def test_degraded_evidence_is_degraded():
    state, _ = cl.derive_lifecycle(_link(), _health("DEGRADED"))
    assert state == "DEGRADED"


def test_unreachable_evidence_is_failed():
    state, _ = cl.derive_lifecycle(_link(), _health("UNREACHABLE"))
    assert state == "FAILED"


def test_invalid_health_is_revoked():
    state, _ = cl.derive_lifecycle(_link(), _health("INVALID"))
    assert state == "REVOKED"


# ── health expiry (the core 37.11 rule) ────────────────────────────────────

def test_stale_healthy_evidence_downgrades_to_validating():
    # health older than the TTL is UNKNOWN until revalidated — never healthy
    state, reason = cl.derive_lifecycle(_link(), _health("HEALTHY", age_s=3600.0))
    assert state == "VALIDATING" and "expired" in reason


def test_stale_unreachable_also_requires_revalidation():
    state, _ = cl.derive_lifecycle(_link(), _health("UNREACHABLE", age_s=3600.0))
    assert state == "VALIDATING"


def test_custom_ttl_respected():
    state, _ = cl.derive_lifecycle(_link(), _health("HEALTHY", age_s=120.0),
                                   health_ttl=60.0)
    assert state == "VALIDATING"
    state, _ = cl.derive_lifecycle(_link(), _health("HEALTHY", age_s=30.0),
                                   health_ttl=60.0)
    assert state == "HEALTHY"


def test_invalid_never_expires():
    # INVALID is policy-derived, not network-derived — no TTL applies
    state, _ = cl.derive_lifecycle(_link(), _health("INVALID", age_s=99999.0))
    assert state == "REVOKED"


# ── annotation shape ───────────────────────────────────────────────────────

def test_annotation_shape():
    ann = cl.lifecycle_annotation("uid-1", _link(), _health())
    assert ann["uid"] == "uid-1"
    assert ann["lifecycle_state"] == "HEALTHY"
    assert ann["health_checked_at"]
    assert "health_expires_at" in ann


def test_all_states_reachable():
    seen = set()
    seen.add(cl.derive_lifecycle(_link(), None)[0])                       # VALIDATING
    seen.add(cl.derive_lifecycle(_link(), _health())[0])                  # HEALTHY
    seen.add(cl.derive_lifecycle(_link(), _health("DEGRADED"))[0])        # DEGRADED
    seen.add(cl.derive_lifecycle(_link(), _health("UNREACHABLE"))[0])     # FAILED
    seen.add(cl.derive_lifecycle(_link(active=False), _health())[0])      # REVOKED
    seen.add(cl.derive_lifecycle(
        _link(expires_at=(datetime.now() - timedelta(days=1)).isoformat()),
        _health())[0])                                                    # EXPIRED
    seen.add(cl.derive_lifecycle(_link(), _health("HEALTHY", age_s=10**6))[0])  # VALIDATING
    assert seen <= set(cl.LIFECYCLE_STATES)
    assert "HEALTHY" in seen and "VALIDATING" in seen
