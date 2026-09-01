# tests/unit/test_egress_engine.py — Egress & Route Truth Engine (pure logic)
#
# Regression evidence for the FALSE-EGRESS production defect:
#   configured custom IP 185.164.73.192 != actual egress 208.77.244.84.
#
# Proves (spec §REGRESSION TESTS):
#   * configured IP is never reported as actual egress
#   * SNI change      → egress classification unchanged
#   * hostname change → egress classification unchanged
#   * country selection without exit node → NO_EXIT_NODE_AVAILABLE
#   * country selection with real exit node → route uses that node
#   * expected country != observed country → ROUTE_MISMATCH (never HEALTHY)
#   * Railway control plane cannot masquerade as an arbitrary exit node
#   * every latency is labeled with WHAT it measured
import time

import pytest

import egress_engine as ee


@pytest.fixture(autouse=True)
def _clean():
    ee.reset_for_tests()
    yield
    ee.reset_for_tests()


# ── helpers ─────────────────────────────────────────────────────────────────

def _store(target, ip="208.77.244.84", cc="NL", country="Netherlands",
            isp="Railway", asn="AS198204", ok=True, age=0.0):
    ev = ee.EgressEvidence(
        target_id=target, ok=ok, public_ip=ip, asn=asn, isp=isp,
        country=country, country_code=cc, city="Amsterdam",
        ip_family=ee.ip_family(ip), timestamp=time.time() - age,
        measurement_source="test")
    ee._evidence[target] = ev
    return ev


# ── 1. configured IP != actual egress — never reported as egress ────────────

def test_configured_ip_is_never_reported_as_verified_egress():
    """Production case: custom IP 185.164.73.192 configured; egress measured
    208.77.244.84. The VERIFIED egress must be the MEASURED one only."""
    _store("loc:tr", ip="208.77.244.84", cc="NL")
    res = ee.classify_egress("loc:tr", configured={
        "upstream": "vps.example.com",
        "advertised_ip": "185.164.73.192",   # the "Custom IP" the user typed
    })
    assert res["classification"] == "VERIFIED_EGRESS"
    assert res["egress"]["public_ip"] == "208.77.244.84"
    assert res["egress"]["public_ip"] != "185.164.73.192"
    # the configured value is surfaced only as a clearly-labelled preference
    assert res.get("configured_address") == "vps.example.com"
    assert "does NOT" in res["configured_note"]


def test_unverified_target_is_configured_only_never_verified():
    res = ee.classify_egress("loc:tr", configured={"upstream": "vps.example.com"})
    assert res["classification"] == "CONFIGURED_ONLY"
    assert "egress" not in res or not res.get("egress", {}).get("public_ip")
    assert res["verified"] is False


def test_nothing_configured_and_nothing_measured_is_unknown():
    res = ee.classify_egress("loc:xx")
    assert res["classification"] == "UNKNOWN"
    assert res["verified"] is False


def test_stale_evidence_degrades_not_verified():
    _store("panel", age=ee.EGRESS_EVIDENCE_TTL + 60)
    res = ee.classify_egress("panel", configured={"upstream": "panel"})
    assert res["classification"] != "VERIFIED_EGRESS"
    assert res.get("egress", {}).get("stale") is True


# ── 2. SNI / hostname / TLS server name do NOT affect egress ────────────────

def _classify_with_endpoint_layer(**endpoint_values):
    _store("loc:tr", ip="208.77.244.84", cc="NL")
    cfg = {"upstream": "vps.example.com", **endpoint_values}
    res = ee.classify_egress("loc:tr", configured=cfg)
    # strip volatile timestamps so only semantics are compared
    if "egress" in res:
        for k in ("checked_at", "expires_at", "age_s", "timestamp"):
            res["egress"].pop(k, None)
    return res


def test_sni_change_does_not_change_egress():
    a = _classify_with_endpoint_layer(sni="www.microsoft.com")
    b = _classify_with_endpoint_layer(sni="irancell.ir")
    c = _classify_with_endpoint_layer(spoof_sni="fakesni.example.org")
    assert a == b == c
    assert a["egress"]["public_ip"] == "208.77.244.84"


def test_hostname_change_does_not_change_egress():
    a = _classify_with_endpoint_layer(hostname="one.example.com")
    b = _classify_with_endpoint_layer(hostname="two.example.com",
                                      http_host="three.example.com")
    assert a == b
    assert a["egress"]["public_ip"] == "208.77.244.84"


def test_tls_server_name_change_does_not_change_egress():
    a = _classify_with_endpoint_layer(tls_server_name="a.tls")
    b = _classify_with_endpoint_layer(server_name="b.tls", alpn="h2,http/1.1")
    assert a == b


# ── 3. country selection ────────────────────────────────────────────────────

def test_country_selection_without_exit_node_is_no_exit_node_available():
    targets = [
        {"name": "tr", "role": "RELAY_NODE",
         "upstream": "emix-pro-production.up.railway.app", "egress": {}},
        {"name": "de", "role": "CONTROL_PLANE", "egress": {}},
    ]
    res = ee.select_exit_country("TR", targets)
    assert res["ok"] is False
    assert res["route_health"] == "NO_EXIT_NODE_AVAILABLE"
    assert "not faked" in res["reason"]
    assert res["targets"] == []


def test_country_selection_with_real_verified_exit_node_uses_that_node():
    targets = [
        {"name": "tr", "role": "EXIT_NODE", "upstream": "vps-tr.example.com",
         "egress": {"ok": True, "country_code": "TR", "public_ip": "1.2.3.4"}},
    ]
    res = ee.select_exit_country("TR", targets)
    assert res["ok"] is True
    assert res["route_health"] == "HEALTHY"
    assert res["targets"][0]["name"] == "tr"
    assert res["targets"][0]["upstream"] == "vps-tr.example.com"


def test_unverified_exit_node_is_not_proof_for_country_selection():
    targets = [{"name": "tr", "role": "EXIT_NODE",
                "upstream": "vps-tr.example.com", "egress": {}}]
    res = ee.select_exit_country("TR", targets)
    assert res["ok"] is False
    assert res["route_health"] == "NO_EXIT_NODE_AVAILABLE"


# ── 4. expected != observed → ROUTE_MISMATCH ───────────────────────────────

def test_expected_country_mismatch_is_route_mismatch_never_healthy():
    observed = {"ok": True, "public_ip": "208.77.244.84",
                "country_code": "NL", "country": "Netherlands"}
    res = ee.compare_route_expectations("TR", observed)
    assert res["route_health"] == "ROUTE_MISMATCH"
    assert any("expected country TR" in r for r in res["reasons"])


def test_expected_country_match_is_healthy():
    observed = {"ok": True, "public_ip": "1.2.3.4",
                "country_code": "TR", "country": "Türkiye"}
    res = ee.compare_route_expectations("TR", observed)
    assert res["route_health"] == "HEALTHY"


def test_country_name_instead_of_code_still_matches():
    observed = {"ok": True, "public_ip": "1.2.3.4", "country": "Türkiye"}
    res = ee.compare_route_expectations("türkiye", observed)
    assert res["route_health"] == "HEALTHY"


def test_expected_ip_mismatch_reports_reason():
    observed = {"ok": True, "public_ip": "208.77.244.84", "country_code": "NL"}
    res = ee.compare_route_expectations("NL", observed, expected_ip="185.164.73.192")
    assert res["route_health"] == "ROUTE_MISMATCH"
    assert any("185.164.73.192" in r for r in res["reasons"])


def test_no_observation_is_unknown_not_mismatch():
    res = ee.compare_route_expectations("TR", None)
    assert res["route_health"] == "UNKNOWN"
    assert "nothing was verified" in res["reason"]


# ── 5. Railway control plane can never masquerade as an exit node ───────────

def test_railway_addresses_are_control_plane():
    for host in ("emix-pro-production.up.railway.app",
                 "something.railway.app", "x.up.railway.internal"):
        assert ee.is_control_plane_address(host), host


def test_railway_masquerade_via_role_derivation():
    """A worker location whose upstream is Railway is a RELAY into the control
    plane — never an EXIT_NODE, whatever its label claims."""
    role = ee.derive_node_role(kind="worker",
                               upstream="emix-pro-production.up.railway.app")
    assert role == "RELAY_NODE"
    assert role != "EXIT_NODE"


def test_railway_masquerade_via_route_mismatch():
    """Panel (Railway) egress measured NL; claiming TR must stay ROUTE_MISMATCH —
    the control plane cannot pretend to emit from an arbitrary country."""
    _store("panel", ip="208.77.244.84", cc="NL", country="Netherlands")
    ev = ee._evidence["panel"].to_dict()
    res = ee.compare_route_expectations("TR", ev)
    assert res["route_health"] == "ROUTE_MISMATCH"


def test_panel_kind_is_control_plane_role():
    assert ee.derive_node_role(kind="panel") == "CONTROL_PLANE"
    assert ee.control_plane_info()["role"] == "CONTROL_PLANE"


# ── 6. node role taxonomy ───────────────────────────────────────────────────

def test_node_roles_derivation():
    assert ee.derive_node_role(kind="panel") == "CONTROL_PLANE"
    assert ee.derive_node_role(kind="worker", upstream="",
                               terminates_tunnel=True) == "EDGE_NODE"
    assert ee.derive_node_role(kind="worker", upstream="vps.example.com") == "EXIT_NODE"
    assert ee.derive_node_role(kind="vps", upstream="") == "RELAY_NODE"
    assert set(ee.NODE_ROLES) == {"CONTROL_PLANE", "EXIT_NODE", "RELAY_NODE",
                                  "EDGE_NODE", "HYBRID"}


def test_route_status_chips():
    assert ee.route_status_for("CONTROL_PLANE", False) == "DIRECT"
    assert ee.route_status_for("CONTROL_PLANE", True) == "VERIFIED"
    assert ee.route_status_for("RELAY_NODE", False) == "RELAY"
    assert ee.route_status_for("EDGE_NODE", True) == "VERIFIED"
    assert ee.route_status_for("weird", False) == "UNKNOWN"


# ── 7. latency labels ───────────────────────────────────────────────────────

def test_every_latency_is_labeled():
    lat = ee.labeled_latency("control_plane_rtt", 12.34)
    assert lat["measure"] == "control_plane_rtt"
    assert lat["ms"] == 12.3
    for m in ("control_plane_rtt", "node_rtt", "route_rtt",
              "protocol_handshake_rtt"):
        assert m in ee.LATENCY_MEASURES


def test_unknown_latency_measure_falls_back_labeled():
    lat = ee.labeled_latency("ping", 5)
    assert lat["measure"] == "route_rtt"  # still labeled, never anonymous


def test_latency_none_ms_is_allowed():
    lat = ee.labeled_latency("node_rtt", None)
    assert lat["ms"] is None and lat["measure"] == "node_rtt"


# ── 8. evidence bookkeeping ─────────────────────────────────────────────────

def test_ip_family_detection():
    assert ee.ip_family("185.164.73.192") == "IPv4"
    assert ee.ip_family("2606:4700::6810:84e5") == "IPv6"
    assert ee.ip_family("") is None
    assert ee.ip_family("not-an-ip") is None


def test_evidence_expiry_metadata():
    _store("panel")
    d = ee.evidence_for("panel")
    assert d["valid"] is True
    assert d["expires_at"] > d["checked_at"]


def test_health_layers_split():
    layers = ee.egress_health_layers()
    assert set(layers.keys()) == set(ee.HEALTH_LAYERS)
    # APPLICATION_HEALTH (panel API up) must be separate from EGRESS_HEALTH —
    # a healthy Railway API says NOTHING about VPN egress health.
    assert layers["APPLICATION_HEALTH"] == "HEALTHY"


def test_worker_topology_roles_from_upstream_reality():
    """worker_topology with an injected provider: railway upstream → RELAY_NODE,
    real upstream → EXIT_NODE, no upstream → EDGE_NODE."""
    async def fake_status(cfg):
        return {"ok": True, "wte": True, "version": "2.2.0-egress",
                "locations": [
                    {"name": "auto", "label": "auto",
                     "upstream": "emix-pro-production.up.railway.app"},
                    {"name": "tr", "label": "ترکیه", "flag": "🇹🇷",
                     "upstream": "vps-tr.example.com"},
                    {"name": "wte", "label": "edge", "upstream": ""},
                ]}
    ee.set_provider("worker_status", fake_status)
    import asyncio
    topo = asyncio.run(ee.worker_topology())
    roles = {l["name"]: l["role"] for l in topo["locations"]}
    assert roles["auto"] == "RELAY_NODE"
    assert roles["tr"] == "EXIT_NODE"
    assert roles["wte"] == "EDGE_NODE"
    cp = {l["name"]: l["is_control_plane"] for l in topo["locations"]}
    assert cp["auto"] is True and cp["tr"] is False
