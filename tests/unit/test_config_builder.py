# tests/unit/test_config_builder.py — Phase 38+ (spec §6-§7, §18-§21)
# Canonical ConfigRequest → validation → compiler → outputs + history.
# Every output must originate from the canonical compiler (no new emitter).

import asyncio

import pytest

import config_builder as cb
import structured_events as events


@pytest.fixture(autouse=True)
def clean():
    cb.reset_for_tests()
    events.reset_for_tests()
    # deterministic host provider (no main import in unit tests)
    cb.set_host_provider(lambda: "builder.example.com")
    cb.set_worker_domain_provider(lambda: "")
    cb.set_cdn_domain_provider(lambda: "")
    yield
    cb.reset_for_tests()
    events.reset_for_tests()


def _req(**kw):
    base = dict(protocol="vless", transport="xhttp-packet-up", security="tls",
                node_id="panel", routing_policy="ALL_VPN",
                client_format="xray-json", remark="unit-test")
    base.update(kw)
    return cb.ConfigRequest(**base)


# ── Validation BEFORE generation (spec §19) ─────────────────────────────────

@pytest.mark.asyncio
async def test_valid_request_compiles_via_canonical_compiler():
    out = await cb.build_config(_req(), for_preview=True)
    assert out["ok"], out.get("errors")
    assert out["validation"] == "VALID"
    assert out["outputs"]["uri"].startswith("vless://")
    assert out["outputs"]["uri"].count("@") == 1


@pytest.mark.asyncio
async def test_invalid_transport_never_generates():
    out = await cb.build_config(_req(transport="grpc"), for_preview=True)
    assert not out["ok"]
    assert out["stage"] == "capability"
    assert out["errors"]


@pytest.mark.asyncio
async def test_iran_direct_with_uri_client_rejected_split_tunnel():
    out = await cb.build_config(_req(routing_policy="IRAN_DIRECT",
                                     client_format="uri"), for_preview=True)
    assert not out["ok"]
    assert out["stage"] == "routing"
    assert any("SPLIT_TUNNEL_NOT_SUPPORTED" in e for e in out["errors"])


@pytest.mark.asyncio
async def test_iran_direct_with_xray_json_compiles_split_rules():
    out = await cb.build_config(_req(routing_policy="IRAN_DIRECT",
                                     client_format="xray-json"),
                                for_preview=True)
    assert out["ok"], out.get("errors")
    rules = (out["preview"]["routing_detail"] or {}).get("split_rules") or {}
    assert rules.get("verdict") == "SPLIT_TUNNEL_SUPPORTED"
    assert any(r["outbound"] == "direct" for r in rules.get("rules", []))


@pytest.mark.asyncio
async def test_iran_proxy_without_gateway_rejected():
    out = await cb.build_config(_req(routing_policy="IRAN_PROXY",
                                     client_format="uri"), for_preview=True)
    assert not out["ok"]
    assert out["stage"] == "routing"
    assert any("Iranian gateway" in e for e in out["errors"])


@pytest.mark.asyncio
async def test_iran_proxy_with_verified_gateway_builds():
    import domestic_route_engine as dre
    import iran_gateway

    def _fake_status():
        return {"configured": True, "state": "VERIFIED_IRAN_EGRESS",
                "egress": "IRAN_GATEWAY (verified)", "verdict": "VERIFIED_IRAN_EGRESS"}
    dre.set_gateway_status_fn(_fake_status)
    out = await cb.build_config(_req(routing_policy="IRAN_PROXY",
                                     client_format="uri"), for_preview=True)
    assert out["ok"], out.get("errors")
    gw = out["preview"]["routing_detail"]["iran_gateway"]
    assert gw["verdict"] == "VERIFIED_IRAN_EGRESS"
    legs = out["preview"]["routing_detail"]["legs"]
    assert "IRAN_GATEWAY" in legs["IRAN_DOMESTIC"]["egress"]


@pytest.mark.asyncio
async def test_unknown_node_rejected():
    out = await cb.build_config(_req(node_id="no-such-node"), for_preview=True)
    assert not out["ok"]
    # the node problem is reported with the node id (stage: node or capability)
    assert any("no-such-node" in e for e in out["errors"])


@pytest.mark.asyncio
async def test_preview_uses_placeholder_credential_not_invented():
    out = await cb.build_config(_req(), for_preview=True)
    assert out["ok"]
    assert out.get("credential_placeholder") is True
    assert "00000000-0000-0000-0000-00000000c0de" in out["outputs"]["uri"]


# ── History lifecycle (spec §21) ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_persists_history_and_events():
    out = await cb.build_config(_req(name="hist-1", client_format="uri"))
    assert out["ok"]
    hid = out["history_id"]
    hist = cb.list_history()
    assert any(h["history_id"] == hid for h in hist)
    evs = [e["event"] for e in events.recent_events(50)]
    assert "CONFIG_GENERATED" in evs
    assert "ROUTE_SELECTED" in evs
    # the event must NOT carry the credential (scrubbed centrally)
    gen = [e for e in events.recent_events(50) if e["event"] == "CONFIG_GENERATED"][0]
    assert "credential" not in gen


@pytest.mark.asyncio
async def test_history_view_masks_credential_reveal_shows_uri():
    out = await cb.build_config(_req(name="hist-2", client_format="uri"))
    hid = out["history_id"]
    masked = await cb.get_history_entry(hid, reveal=False)
    assert masked["spec"]["credential"] == "<set>"
    assert "uri" not in masked
    revealed = await cb.get_history_entry(hid, reveal=True)
    assert revealed["uri"] == out["outputs"]["uri"]
    assert revealed["spec"]["credential"] == out["outputs"]["uri"].split("://", 1)[1].split("@", 1)[0]


@pytest.mark.asyncio
async def test_regenerate_is_deterministic():
    out = await cb.build_config(_req(name="hist-3", client_format="uri"))
    regen = await cb.regenerate(out["history_id"])
    assert regen["ok"]
    assert regen["deterministic_match"] is True
    assert regen["outputs"]["uri"] == out["outputs"]["uri"]
    assert regen["checksum"] == out["checksum"]


@pytest.mark.asyncio
async def test_delete_history():
    out = await cb.build_config(_req(name="hist-4", client_format="uri"))
    hid = out["history_id"]
    res = await cb.delete_history(hid)
    assert res["ok"]
    assert await cb.get_history_entry(hid) is None


@pytest.mark.asyncio
async def test_history_bound_is_enforced():
    for i in range(12):
        await cb.build_config(_req(name=f"bulk-{i}", client_format="uri"))
    assert len(cb._history) == 12
    assert cb.history_summary()["bound"] == cb.HISTORY_BOUND


# ── Output formats (spec §18) ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subscription_output_is_base64_of_uri():
    import base64
    out = await cb.build_config(_req(client_format="subscription"))
    assert out["ok"]
    sub = out["outputs"]["subscription"]
    assert base64.b64decode(sub).decode() == out["outputs"]["uri"]


@pytest.mark.asyncio
async def test_xray_json_output_present_for_xray_client():
    out = await cb.build_config(_req(client_format="xray-json"))
    assert out["ok"]
    xj = out["outputs"]["xray_json"]
    assert xj and xj["outbounds"][0]["protocol"] == "vless"


# ── Validation-failure events (spec §29) ────────────────────────────────────

@pytest.mark.asyncio
async def test_protocol_validation_failed_event_emitted():
    await cb.build_config(_req(transport="grpc"), for_preview=True)
    evs = [e["event"] for e in events.recent_events(50)]
    assert "PROTOCOL_VALIDATION_FAILED" in evs
