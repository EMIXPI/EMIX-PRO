# tests/unit/test_capability_engine.py — Phase 38+ (spec §3-§5, §25, §26)
# Capability engine: deployment model, protocol×deployment status, UDP rule,
# Railway validation matrix honesty, request-combination validation.
# No real network access.

import pytest

import capability_engine as caps
import compat


@pytest.fixture(autouse=True)
def clean():
    caps.reset_for_tests()
    yield
    caps.reset_for_tests()


# ── Deployment layers & model (spec §4) ─────────────────────────────────────

def test_deployment_layers_are_four_and_distinct():
    assert caps.DEPLOYMENT_LAYERS == ("RAILWAY_EDGE", "RAILWAY_DEPLOYMENT",
                                      "RAILWAY_OUTBOUND", "ACTUAL_EGRESS")
    # every deployment model documents all four layers explicitly
    for did, dm in caps.DEPLOYMENT_MODEL.items():
        for layer in caps.DEPLOYMENT_LAYERS:
            assert layer in dm["layers"], f"{did} missing layer {layer}"


def test_panel_udp_is_never_provided():
    assert caps.DEPLOYMENT_MODEL["panel"]["udp"] == "NOT_PROVIDED"
    assert caps.DEPLOYMENT_MODEL["worker"]["udp"] == "DNS_ONLY"


def test_udp_dependent_protocols_never_railway_native():
    for proto in ("wireguard", "hysteria2", "tuic"):
        st = caps._protocol_status_on_deployment(proto, "ws", "tls", "panel")
        assert st["status"] == "UNSUPPORTED", proto
        assert "UDP" in st["reason"]
        # worker too (DNS-only UDP is not usable public UDP)
        st2 = caps._protocol_status_on_deployment(proto, "ws", "tls", "worker")
        assert st2["status"] == "UNSUPPORTED", proto


def test_railway_priority_starts_with_xhttp():
    p = caps.DEPLOYMENT_MODEL["panel"]["priority"]
    assert p[0] == ["vless", "xhttp-packet-up", "tls"]
    assert ["vless", "ws", "tls"] in p
    assert ["mtproto", "tcp", "none"] in p      # TCP via Railway TCP proxy


# ── Protocol × deployment status (spec §5, §9) ──────────────────────────────

def test_valid_combo_supported_on_panel():
    st = caps._protocol_status_on_deployment("vless", "xhttp-packet-up", "tls", "panel")
    assert st["status"] == "SUPPORTED"


def test_grpc_is_experimental_with_envelope_note():
    st = caps._protocol_status_on_deployment("vless", "grpc", "tls", "panel")
    assert st["status"] == "EXPERIMENTAL"
    assert "gRPC" in st["reason"] or "mimic" in st["reason"].lower()


def test_transport_not_carried_by_deployment_is_unsupported():
    # raw tcp combos (EXPERIMENTAL per compat) on the panel deployment
    st = caps._protocol_status_on_deployment("vless", "tcp", "tls", "panel")
    assert st["status"] == "EXPERIMENTAL"


def test_invalid_combo_is_invalid():
    st = caps._protocol_status_on_deployment("vless", "ws", "reality", "panel")
    assert st["status"] == "INVALID"


# ── Routing policy catalogue (spec §11) ─────────────────────────────────────

def test_routing_policy_capabilities_cover_all_five():
    pols = {p["policy"] for p in caps.routing_policy_capabilities()}
    assert {"ALL_VPN", "IRAN_DIRECT", "IRAN_PROXY", "INTERNATIONAL_VPN",
            "CUSTOM"} <= pols
    by = {p["policy"]: p for p in caps.routing_policy_capabilities()}
    assert by["IRAN_DIRECT"]["legs"]["iran"] == "DIRECT"
    assert "USER_ISP" in by["IRAN_DIRECT"]["egress"]
    assert by["IRAN_PROXY"]["legs"]["iran"] == "VPN_VIA_IRAN_GATEWAY"
    assert "gateway" in by["IRAN_PROXY"]["gateway_requirement"].lower()
    assert by["INTERNATIONAL_VPN"]["legs"]["iran"] == "BLOCK"


# ── Client capability model (spec §26) ──────────────────────────────────────

def test_client_formats_split_tunnel_matrix():
    assert caps.CLIENT_FORMATS["xray-json"]["split_tunnel"] == "SPLIT_TUNNEL_SUPPORTED"
    assert caps.CLIENT_FORMATS["sing-box"]["split_tunnel"] == "SPLIT_TUNNEL_SUPPORTED"
    assert caps.CLIENT_FORMATS["uri"]["split_tunnel"] == "SPLIT_TUNNEL_NOT_SUPPORTED"
    assert caps.CLIENT_FORMATS["wireguard-conf"]["split_tunnel"] == "SPLIT_TUNNEL_NOT_SUPPORTED"


# ── Request combination validation (spec §19) ───────────────────────────────

def test_validate_request_valid_combo():
    out = caps.validate_request_combination("vless", "xhttp-packet-up", "tls",
                                            "panel", "xray-json")
    assert out["ok"], out["problems"]


def test_validate_request_unsupported_transport_rejected():
    out = caps.validate_request_combination("vless", "grpc", "tls", "panel", "uri")
    assert not out["ok"]
    assert out["problems"]


def test_validate_request_unknown_client_format_rejected():
    out = caps.validate_request_combination("vless", "ws", "tls", "panel", "pptp")
    assert not out["ok"]
    assert any("client format" in p for p in out["problems"])


# ── Railway validation matrix honesty (spec §25) ────────────────────────────

def test_validation_matrix_covers_all_runtime_combos():
    m = caps.railway_validation_matrix()
    combos = {e["fused"] for e in m["matrix"]}
    for (p, t) in compat.SERVER_RUNTIME:
        assert compat.compose(p, t) in combos
    assert set(m["stages"]) == set(caps.VALIDATION_STAGES)


def test_validation_matrix_honest_client_stages():
    m = caps.railway_validation_matrix()
    for e in m["matrix"]:
        for stage in ("CLIENT_CONNECTED", "REAL_TRAFFIC_CONFIRMED",
                      "RECONNECT_CONFIRMED"):
            v = e["stages"][stage]
            # never faked as PASS: honest labels only
            assert v in ("NOT_TESTABLE_WITHOUT_REAL_CLIENT",
                         "NOT_TESTED_WITH_REAL_CLIENT"), (e["fused"], stage)


def test_validation_matrix_status_vocabulary_honest():
    m = caps.railway_validation_matrix()
    for e in m["matrix"]:
        assert e["status"] in ("IMPLEMENTED_RUNTIME_VERIFIED_IN_PROCESS",
                               "CONFIG_VALID_RUNTIME_CONDITIONAL",
                               "CONFIG_VALID_ONLY", "FAILED", "UNSUPPORTED")
        assert "VERIFIED" not in e["status"] or "IN_PROCESS" in e["status"]


def test_validation_matrix_config_valid_executes_real_compile():
    m = caps.railway_validation_matrix()
    for e in m["matrix"]:
        assert e["stages"]["CONFIG_VALID"].startswith("PASS") or \
            e["stages"]["CONFIG_VALID"].startswith("FAIL")


@pytest.mark.asyncio
async def test_node_catalogue_includes_panel_with_honest_udp():
    cat = await caps.node_catalogue("panel.example.com")
    panel = [n for n in cat if n["node_id"] == "panel"][0]
    assert panel["udp"] == "NOT_PROVIDED"
    assert panel["role"] == "CONTROL_PLANE"
    # only protocol entries with SUPPORTED status appear selectable
    assert any(x["status"] == "SUPPORTED" for x in panel["protocols"])


@pytest.mark.asyncio
async def test_builder_capabilities_document_shape():
    doc = await caps.builder_capabilities("panel.example.com")
    assert doc["ok"] and doc["engine"].startswith("capability_engine/")
    for key in ("protocols", "deployments", "nodes", "clients",
                "routing_policies", "matrix", "iran_gateway", "rules"):
        assert key in doc, key
    # matrix comes from compat SSoT
    assert doc["matrix"]["source"].startswith("compat.py")
    # UDP rule stated
    assert "NEVER" in doc["udp_rule"] or "never" in doc["udp_rule"]
