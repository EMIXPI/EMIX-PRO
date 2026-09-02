# tests/unit/test_phase38plus_routing.py — Phase 38+ §11-§13 (policy extensions)
# IRAN_PROXY / INTERNATIONAL_VPN policies in the domestic engine + failover
# transport gates + event emission from existing engines.

import asyncio
import time

import pytest

import domestic_route_engine as dre
import failover_engine as fe
import node_manager as nm
import structured_events as events


@pytest.fixture(autouse=True)
def clean():
    dre.reset_for_tests()
    fe.reset_for_tests()
    nm.reset_for_tests()
    events.reset_for_tests()
    dre._db.load_prefixes(["5.10.0.0/16", "2.144.0.0/14"],
                          {"version": 7, "source": "test"})
    yield
    dre.reset_for_tests()
    fe.reset_for_tests()
    nm.reset_for_tests()
    events.reset_for_tests()


# ── Policy vocabulary (spec §11) ────────────────────────────────────────────

def test_policy_presets_include_new_policies():
    assert set(dre.POLICY_PRESETS) >= {"ALL_VPN", "IRAN_DIRECT", "IRAN_PROXY",
                                       "INTERNATIONAL_VPN", "CUSTOM"}


def test_international_vpn_blocks_iran_leg():
    p = dre.PRESET_POLICIES["INTERNATIONAL_VPN"]
    assert p.iran == "BLOCK"
    assert p.international == "VPN"


# ── IRAN_PROXY attribution (spec §13) ───────────────────────────────────────

@pytest.mark.asyncio
async def test_iran_proxy_iranian_destination_attributes_iran_gateway():
    def _unverified():
        return {"configured": True, "state": "CONFIGURED",
                "egress": "IRAN_GATEWAY (state CONFIGURED)",
                "verdict": "NO_VERIFIED_IRAN_GATEWAY"}
    dre.set_gateway_status_fn(_unverified)
    out = await dre.decide_route("5.10.7.7",
                                 policy=dre.PRESET_POLICIES["IRAN_PROXY"])
    assert out["decision"] == "VPN"
    assert out["egress"] == "IRAN_GATEWAY"
    assert "NO_VERIFIED_IRAN_GATEWAY" in out["egress_note"]
    assert out["iran_gateway"]["verdict"] == "NO_VERIFIED_IRAN_GATEWAY"
    assert "warning" in out["iran_gateway"]


@pytest.mark.asyncio
async def test_iran_proxy_with_verified_gateway():
    def _verified():
        return {"configured": True, "state": "VERIFIED_IRAN_EGRESS",
                "egress": "IRAN_GATEWAY (verified)",
                "verdict": "VERIFIED_IRAN_EGRESS"}
    dre.set_gateway_status_fn(_verified)
    out = await dre.decide_route("5.10.7.7",
                                 policy=dre.PRESET_POLICIES["IRAN_PROXY"])
    assert out["egress"] == "IRAN_GATEWAY"
    assert "VERIFIED_IRAN_EGRESS" in out["egress_note"]
    assert "warning" not in (out["iran_gateway"] or {})


@pytest.mark.asyncio
async def test_iran_proxy_international_destination_uses_emix_route():
    def _verified():
        return {"configured": True, "verdict": "VERIFIED_IRAN_EGRESS"}
    dre.set_gateway_status_fn(_verified)
    out = await dre.decide_route("8.8.8.8",
                                 policy=dre.PRESET_POLICIES["IRAN_PROXY"])
    assert out["decision"] == "VPN"
    assert out["egress"] == "EMIX_ROUTE"


@pytest.mark.asyncio
async def test_gateway_not_wired_is_explicit():
    out = await dre.decide_route("5.10.7.7",
                                 policy=dre.PRESET_POLICIES["IRAN_PROXY"])
    assert out["egress"] == "IRAN_GATEWAY"
    assert out["iran_gateway"]["verdict"] == "IRAN_GATEWAY_UNCONFIGURED"


# ── INTERNATIONAL_VVPN BLOCK decision ───────────────────────────────────────

@pytest.mark.asyncio
async def test_international_vpn_blocks_iranian_destination():
    out = await dre.decide_route(
        "5.10.7.7", policy=dre.PRESET_POLICIES["INTERNATIONAL_VPN"])
    assert out["decision"] == "BLOCK"
    assert out["egress"] == "NONE"
    assert "refused" in out["egress_note"]
    assert out["vpn_bypassed"] is True


@pytest.mark.asyncio
async def test_international_vpn_international_still_vpn():
    out = await dre.decide_route(
        "8.8.8.8", policy=dre.PRESET_POLICIES["INTERNATIONAL_VPN"])
    assert out["decision"] == "VPN"


# ── Split-tunnel compilation for BLOCK leg (spec §26) ───────────────────────

def test_block_policy_compiles_blackhole_rules():
    rules = dre.compile_split_tunnel_rules(
        dre.PRESET_POLICIES["INTERNATIONAL_VPN"],
        "xray-json", use_geoip=False)
    assert rules["verdict"] == "SPLIT_TUNNEL_SUPPORTED"
    assert any(r["outbound"] == "blackhole" for r in rules["rules"])
    assert all(r["outbound"] == "blackhole" for r in rules["rules"])


def test_iran_proxy_compiles_no_client_rules():
    rules = dre.compile_split_tunnel_rules(
        dre.PRESET_POLICIES["IRAN_PROXY"], "xray-json")
    assert rules["verdict"] == "SPLIT_TUNNEL_NOT_APPLICABLE"
    assert "server-side" in rules["reason"]


# ── Active policy switching includes new presets ───────────────────────────

def test_set_active_policy_accepts_new_presets():
    dre.set_active_policy("INTERNATIONAL_VPN")
    assert dre.get_active_policy_name() == "INTERNATIONAL_VPN"
    dre.set_active_policy("IRAN_PROXY")
    assert dre.get_active_policy_name() == "IRAN_PROXY"


# ── Failover capability gates (spec §15) ────────────────────────────────────

@pytest.mark.asyncio
async def test_transport_incompatible_node_never_selected():
    # nl-01 carries only vless-ws; a trojan-xhttp requirement must skip it
    await nm.register_node(nm.NodeRecord(
        id="nl-01", name="NL-01", kind="exit", region="NL",
        address="nl01.example.com", runtime="node",
        capabilities=["vless-ws"], state="ONLINE",
        last_heartbeat=time.time(),
        runtime_health="OK"))
    rep = await fe.select_replacement(
        "failing-node", {"protocol": "trojan", "transport": "xhttp-packet-up"})
    assert rep is None, "incompatible node must never be selected"


@pytest.mark.asyncio
async def test_transport_compatible_node_selected():
    await nm.register_node(nm.NodeRecord(
        id="nl-02", name="NL-02", kind="exit", region="NL",
        address="nl02.example.com", runtime="node",
        capabilities=["trojan-xhttp-packet-up"], state="ONLINE",
        last_heartbeat=time.time(),
        runtime_health="OK"))
    rep = await fe.select_replacement(
        "failing-node", {"protocol": "trojan", "transport": "xhttp-packet-up"})
    assert rep is not None and rep["node_id"] == "nl-02"


@pytest.mark.asyncio
async def test_exit_role_requires_verified_egress():
    await nm.register_node(nm.NodeRecord(
        id="nl-03", name="NL-03", kind="exit", region="NL",
        address="nl03.example.com", runtime="node",
        capabilities=["vless-ws"], state="ONLINE",
        last_heartbeat=time.time(),
        runtime_health="OK"))
    # no egress evidence injected → EXIT_NODE requirement filters it out
    rep = await fe.select_replacement(
        "failing-node", {"protocol": "vless", "transport": "ws",
                         "role": "EXIT_NODE"})
    assert rep is None


# ── Event emission from existing engines (spec §29) ─────────────────────────

@pytest.mark.asyncio
async def test_quarantine_emits_event():
    await nm.register_node(nm.NodeRecord(id="q1", name="Q1", kind="vps"))
    await nm.set_quarantine("q1", True, reason="route-mismatch")
    evs = [e for e in events.recent_events(20)
           if e["event"] == "NODE_QUARANTINED"]
    assert evs and evs[0]["node"] == "q1"
    assert evs[0]["reason"] == "route-mismatch"
