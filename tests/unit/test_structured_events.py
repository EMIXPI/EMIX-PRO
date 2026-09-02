# tests/unit/test_structured_events.py — Phase 38+ §29 (structured event log)
# Event recording, secret scrubbing, filtering, bounded memory.

import time

import pytest

import structured_events as se


@pytest.fixture(autouse=True)
def clean():
    se.reset_for_tests()
    yield
    se.reset_for_tests()


def test_basic_event_recording():
    rec = se.log_event("CONFIG_GENERATED", protocol="vless", node="panel")
    assert rec["event"] == "CONFIG_GENERATED"
    assert rec["severity"] == "INFO"
    evs = se.recent_events(10)
    assert evs[0]["event"] == "CONFIG_GENERATED"


def test_severity_filtering():
    se.log_event("ROUTE_MISMATCH", severity="WARNING", location="x")
    se.log_event("EGRESS_VERIFIED", severity="INFO", target="panel")
    warns = se.recent_events(10, min_severity="WARNING")
    assert [e["event"] for e in warns] == ["ROUTE_MISMATCH"]


def test_event_name_filtering():
    se.log_event("EGRESS_VERIFIED", target="panel")
    se.log_event("ROUTE_MISMATCH", location="x")
    only = se.recent_events(10, event="ROUTE_MISMATCH")
    assert len(only) == 1 and only[0]["location"] == "x"


def test_password_fields_never_recorded():
    rec = se.log_event("ACCOUNT_GATE_DECISION", password="hunter2",
                       token="abc123", account="ali")
    assert rec["password"] == "<redacted>"
    assert rec["token"] == "<redacted>"
    assert rec["account"] == "ali"


def test_secretish_field_names_redacted():
    rec = se.log_event("X", private_key="KEYKEYKEY", server_private_key="k2",
                       api_key="k3", subscription_secret="s")
    for k in ("private_key", "server_private_key", "api_key",
              "subscription_secret"):
        assert rec[k] == "<redacted>", k


def test_uuids_redacted_in_values():
    rec = se.log_event("X", note="user 12345678-1234-5678-8901-123456789012 connected")
    assert "12345678" not in str(rec["note"])
    assert "<uuid-redacted>" in rec["note"]


def test_nested_dict_scrubbing():
    rec = se.log_event("X", ctx={"credential": "sec", "node": "n1"})
    assert rec["ctx"]["credential"] == "<redacted>"
    assert rec["ctx"]["node"] == "n1"


def test_bound_enforced():
    for i in range(se.EVENT_BOUND + 50):
        se.log_event("X", i=i)
    assert len(se._events) == se.EVENT_BOUND


def test_stats():
    se.log_event("CONFIG_GENERATED")
    se.log_event("CONFIG_GENERATED")
    st = se.event_stats()
    assert st["events_total"] == 2
    assert st["by_event"]["CONFIG_GENERATED"] == 2


def test_never_raises():
    # event logging failure must never break the operation
    out = se.log_event(None, **{"bad field": 1})
    assert out is not None or True  # must not raise


def test_listener_sink_receives_events():
    got = []
    se.add_listener(got.append)
    se.log_event("FAILOVER_TRIGGERED", node="n1")
    assert got and got[0]["event"] == "FAILOVER_TRIGGERED"
