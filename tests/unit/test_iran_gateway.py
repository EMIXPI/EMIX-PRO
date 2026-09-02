# tests/unit/test_iran_gateway.py — Phase 38+ §13 (Iran Gateway / IRAN_PROXY)
# Gateway registry, state machine, evidence-based egress verification.
# All network probes are monkeypatched — NO REAL_NETWORK tests here.

import asyncio
import time

import pytest

import iran_gateway as ig
import structured_events as events


@pytest.fixture(autouse=True)
def clean():
    ig.reset_for_tests()
    events.reset_for_tests()
    yield
    ig.reset_for_tests()
    events.reset_for_tests()


async def _add_gw(name="Tehran-GW", protocol="http", endpoint="gw.example.com",
                  port=8080, **kw):
    out = await ig.upsert_gateway(name=name, endpoint=endpoint, port=port,
                                  protocol=protocol, **kw)
    assert out["ok"], out.get("errors")
    return out["gateway"]


def _fake_probes(monkeypatch, reachable=True, egress=None):
    async def _reach(endpoint, port, timeout=ig.PROBE_TIMEOUT_S):
        return ({"reachable": True, "latency_ms": 12.5, "ok": True}
                if reachable else {"reachable": False, "error": "refused", "ok": False})
    async def _egress(gw):
        if egress is None:
            return {"ok": False, "error": "not probed"}
        return {"ok": True, "timestamp": time.time(), **egress}
    monkeypatch.setattr(ig, "_tcp_reachable", _reach)
    monkeypatch.setattr(ig, "_probe_egress_http", _egress)
    monkeypatch.setattr(ig, "_geo_lookup", _egress)  # never used for http path


# ── Registry CRUD + validation ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_and_list():
    gw = await _add_gw()
    assert gw["gateway_id"].startswith("gw-")
    assert gw["state"] == "CONFIGURED"      # never VERIFIED without evidence
    assert ig.list_gateways()[0]["name"] == "Tehran-GW"


@pytest.mark.asyncio
async def test_validation_rejects_bad_input():
    out = await ig.upsert_gateway(name="x", endpoint="bad host!", port=99999)
    assert not out["ok"]
    assert out["errors"]


@pytest.mark.asyncio
async def test_endpoint_change_invalidates_evidence(monkeypatch):
    _fake_probes(monkeypatch, egress={"public_ip": "5.10.7.7",
                                      "country_code": "IR", "country": "Iran"})
    g = await _add_gw()
    await ig.check_gateway(g["gateway_id"])
    assert ig.gateway_state(ig.get_gateway(g["gateway_id"])) == "VERIFIED_IRAN_EGRESS"
    # operator changes the endpoint → previous verification no longer applies
    out = await ig.upsert_gateway(gateway_id=g["gateway_id"], name="Tehran-GW",
                                  endpoint="other.example.com", port=8080,
                                  protocol="http")
    assert out["ok"]
    gw = ig.get_gateway(g["gateway_id"])
    assert gw.last_egress is None
    assert gw.last_check is None


@pytest.mark.asyncio
async def test_delete():
    g = await _add_gw()
    out = await ig.delete_gateway(g["gateway_id"])
    assert out["ok"]
    assert ig.list_gateways() == []


# ── State machine (evidence-based, never optimistic) ────────────────────────

@pytest.mark.asyncio
async def test_verified_iran_egress_requires_measured_ir(monkeypatch):
    _fake_probes(monkeypatch, egress={"public_ip": "5.10.7.7",
                                      "country_code": "IR", "country": "Iran"})
    g = await _add_gw()
    out = await ig.check_gateway(g["gateway_id"])
    assert out["state"] == "VERIFIED_IRAN_EGRESS"
    assert out["egress"]["public_ip"] == "5.10.7.7"


@pytest.mark.asyncio
async def test_non_ir_egress_is_route_mismatch_never_masked(monkeypatch):
    _fake_probes(monkeypatch, egress={"public_ip": "1.2.3.4",
                                      "country_code": "NL", "country": "Netherlands"})
    g = await _add_gw()
    out = await ig.check_gateway(g["gateway_id"])
    assert out["state"] == "ROUTE_MISMATCH"
    assert "NOT Iranian" in out["state_reason"] or "expected IR" in out["state_reason"]


@pytest.mark.asyncio
async def test_unreachable_gateway_is_unreachable(monkeypatch):
    _fake_probes(monkeypatch, reachable=False)
    g = await _add_gw()
    out = await ig.check_gateway(g["gateway_id"])
    assert out["state"] == "UNREACHABLE"
    # unreachable invalidates stale egress evidence
    assert ig.get_gateway(g["gateway_id"]).last_egress is None


@pytest.mark.asyncio
async def test_custom_protocol_gateway_is_unsupported_for_egress(monkeypatch):
    _fake_probes(monkeypatch, reachable=True)
    g = await _add_gw(protocol="custom")
    out = await ig.check_gateway(g["gateway_id"])
    assert out["state"] == "UNSUPPORTED"
    assert "no probeable" in out["state_reason"]


@pytest.mark.asyncio
async def test_stale_evidence_degrades(monkeypatch):
    _fake_probes(monkeypatch, egress={"public_ip": "5.10.7.7",
                                      "country_code": "IR", "country": "Iran"})
    g = await _add_gw()
    await ig.check_gateway(g["gateway_id"])
    gw = ig.get_gateway(g["gateway_id"])
    # age the evidence beyond TTL
    gw.last_egress["timestamp"] = time.time() - (ig.EGRESS_TTL_S + 10)
    gw.last_check["at"] = time.time() - (ig.REACH_TTL_S + 10)
    assert ig.gateway_state(gw) in ("DEGRADED", "UNREACHABLE")


# ── IRAN_PROXY attribution (consumed by domestic engine) ────────────────────

@pytest.mark.asyncio
async def test_unconfigured_gateway_iran_proxy_verdict():
    st = ig.iran_proxy_egress_status()
    assert st["configured"] is False
    assert st["verdict"] == "IRAN_GATEWAY_UNCONFIGURED"


@pytest.mark.asyncio
async def test_verified_gateway_iran_proxy_verdict(monkeypatch):
    _fake_probes(monkeypatch, egress={"public_ip": "5.10.7.7",
                                      "country_code": "IR", "country": "Iran"})
    g = await _add_gw()
    await ig.check_gateway(g["gateway_id"])
    st = ig.iran_proxy_egress_status()
    assert st["verdict"] == "VERIFIED_IRAN_EGRESS"
    assert st["egress_ip"] == "5.10.7.7"
    assert st["country_code"] == "IR"


@pytest.mark.asyncio
async def test_route_mismatch_gateway_never_counts_as_verified(monkeypatch):
    _fake_probes(monkeypatch, egress={"public_ip": "1.2.3.4",
                                      "country_code": "DE"})
    g = await _add_gw()
    await ig.check_gateway(g["gateway_id"])
    st = ig.iran_proxy_egress_status()
    assert st["verdict"] == "ROUTE_MISMATCH"


@pytest.mark.asyncio
async def test_disabled_gateway_excluded(monkeypatch):
    _fake_probes(monkeypatch, egress={"public_ip": "5.10.7.7",
                                      "country_code": "IR"})
    g = await _add_gw()
    await ig.check_gateway(g["gateway_id"])
    ig.get_gateway(g["gateway_id"]).enabled = False
    st = ig.iran_proxy_egress_status()
    assert st["verdict"] != "VERIFIED_IRAN_EGRESS"


# ── Secrets discipline ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gateway_secrets_masked_in_listing():
    g = await _add_gw(auth_username="user", auth_password="s3cret-pass")
    listing = ig.list_gateways()[0]
    assert "auth_password" not in listing
    assert listing.get("auth_configured") is True
    # the engine itself keeps the secret for probes (server-side trust domain)
    assert ig.get_gateway(g["gateway_id"]).auth_password == "s3cret-pass"


@pytest.mark.asyncio
async def test_check_emits_structured_event_without_secrets(monkeypatch):
    _fake_probes(monkeypatch, egress={"public_ip": "5.10.7.7",
                                      "country_code": "IR"})
    g = await _add_gw(auth_password="s3cret-pass")
    await ig.check_gateway(g["gateway_id"])
    evs = [e for e in events.recent_events(20)
           if e["event"] == "IRAN_GATEWAY_CHECK"]
    assert evs, "IRAN_GATEWAY_CHECK event must be recorded"
    blob = str(evs)
    assert "s3cret-pass" not in blob


# ── Persistence round-trip ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_persist_restore_roundtrip():
    await _add_gw(name="GW1")
    snap = ig.persist_snapshot()
    ig.reset_for_tests()
    ig.restore_snapshot(snap)
    assert len(ig.list_gateways()) == 1
    assert ig.list_gateways()[0]["name"] == "GW1"
    # auth secrets survive the roundtrip (server-side storage)
    snap2 = ig.persist_snapshot()
    assert snap2["gateways"][0]["auth_password"] == ""
