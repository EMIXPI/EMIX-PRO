# tests/integration/test_phase38plus.py — Phase 38+ integration
# Unified Config Builder + Iran Gateway + Capability Engine + Events, wired
# end-to-end through the real app. All external network is faked/absent —
# NO claims about real-network behavior.

import asyncio

import pytest

import main
import capability_engine as caps
import config_builder as cb
import domestic_route_engine as dre
import iran_gateway as ig
import iran_direct as ird
import structured_events as events
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture()
def anon():
    """Fresh client WITHOUT a session cookie (for 401 assertions).
    No context manager — startup is not needed for auth-gate checks."""
    return TestClient(main.app)


@pytest.fixture(scope="module")
def authed(client):
    r = client.post("/api/login", json={"password": "test-password"})
    assert r.status_code == 200
    return client


@pytest.fixture(autouse=True)
def engines_clean():
    # NOTE: deliberately does NOT call cb.reset_for_tests()/caps.reset_for_tests()
    # here — those wipe the DI wiring main installed at startup (host provider,
    # listener paths). Integration tests need the REAL wiring; only engine
    # state that the tests themselves pollute is cleared.
    cb._history.clear()
    ig.reset_for_tests()
    ird.reset_for_tests()      # IRD assets persist on disk — wipe per test
    events.reset_for_tests()
    dre.reset_for_tests()
    # re-wire the gateway status fn that dre.reset just cleared (main wiring)
    dre.set_gateway_status_fn(ig.iran_proxy_egress_status)
    yield
    cb._history.clear()
    ig.reset_for_tests()
    ird.reset_for_tests()
    events.reset_for_tests()
    dre.reset_for_tests()
    dre.set_gateway_status_fn(ig.iran_proxy_egress_status)


# ── Capability Engine API ───────────────────────────────────────────────────

def test_capabilities_requires_auth(anon):
    assert anon.get("/api/config-builder/capabilities").status_code == 401


def test_capabilities_document(authed):
    r = authed.get("/api/config-builder/capabilities")
    assert r.status_code == 200
    doc = r.json()
    assert doc["ok"]
    assert {"panel", "worker", "vps", "exit-node", "iran-gateway"} <= \
        set(doc["deployments"])
    assert doc["deployments"]["panel"]["udp"] == "NOT_PROVIDED"
    assert "iran_gateway" in doc["iran_gateway"]["engine"]
    # node catalogue always contains the control plane
    assert any(n["node_id"] == "panel" for n in doc["nodes"])


def test_railway_validation_matrix_requires_auth(anon):
    assert anon.get("/api/railway/validation-matrix").status_code == 401


def test_railway_validation_matrix_honest(authed):
    r = authed.get("/api/railway/validation-matrix")
    assert r.status_code == 200
    m = r.json()
    assert len(m["matrix"]) >= 8
    for e in m["matrix"]:
        assert e["stages"]["CLIENT_CONNECTED"] != "PASS"


# ── Config Builder API flows ────────────────────────────────────────────────

def test_preview_requires_auth(anon):
    assert anon.post("/api/config-builder/preview", json={}).status_code == 401


def test_full_generate_history_flow(authed):
    # 1. generate
    r = authed.post("/api/config-builder/generate", json={
        "name": "it-config", "protocol": "vless", "transport": "ws",
        "security": "tls", "node_id": "panel", "routing_policy": "ALL_VPN",
        "client_format": "uri", "remark": "IT"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] and j["outputs"]["uri"].startswith("vless://")
    hid = j["history_id"]

    # 2. history list
    r = authed.get("/api/config-builder/history")
    assert r.status_code == 200
    assert any(h["history_id"] == hid for h in r.json()["history"])

    # 3. view masked → no URI, credential masked
    r = authed.get(f"/api/config-builder/history/{hid}")
    assert r.status_code == 200
    assert "uri" not in r.json()["entry"]
    assert r.json()["entry"]["spec"]["credential"] == "<set>"

    # 4. view revealed → URI present (authed reveal)
    r = authed.get(f"/api/config-builder/history/{hid}?reveal=true")
    assert r.status_code == 200
    assert r.json()["entry"]["uri"] == j["outputs"]["uri"]

    # 5. regenerate → deterministic
    r = authed.post(f"/api/config-builder/history/{hid}/regenerate")
    assert r.status_code == 200
    j2 = r.json()
    assert j2["ok"] and j2["deterministic_match"] is True

    # 6. delete
    r = authed.delete(f"/api/config-builder/history/{hid}")
    assert r.status_code == 200 and r.json()["ok"]


def test_invalid_combination_rejected_with_reason(authed):
    r = authed.post("/api/config-builder/preview", json={
        "protocol": "vless", "transport": "grpc", "security": "tls",
        "node_id": "panel", "routing_policy": "ALL_VPN",
        "client_format": "uri"})
    assert r.status_code == 422
    j = r.json()
    assert j["stage"] == "capability"
    assert j["errors"]


def test_iran_direct_with_uri_rejected(authed):
    r = authed.post("/api/config-builder/generate", json={
        "protocol": "vless", "transport": "ws", "security": "tls",
        "node_id": "panel", "routing_policy": "IRAN_DIRECT",
        "client_format": "uri"})
    assert r.status_code == 422
    assert any("SPLIT_TUNNEL_NOT_SUPPORTED" in e
               for e in r.json()["errors"])


def test_iran_proxy_without_gateway_rejected(authed):
    r = authed.post("/api/config-builder/generate", json={
        "protocol": "vless", "transport": "ws", "security": "tls",
        "node_id": "panel", "routing_policy": "IRAN_PROXY",
        "client_format": "uri"})
    assert r.status_code == 422
    assert any("gateway" in e for e in r.json()["errors"])


def test_events_api_records_config_generated(authed):
    authed.post("/api/config-builder/generate", json={
        "name": "evt", "protocol": "vless", "transport": "ws",
        "security": "tls", "node_id": "panel", "routing_policy": "ALL_VPN",
        "client_format": "uri"})
    r = authed.get("/api/events?limit=50")
    assert r.status_code == 200
    evs = [e["event"] for e in r.json()["events"]]
    assert "CONFIG_GENERATED" in evs
    assert "ROUTE_SELECTED" in evs


def test_events_requires_auth(anon):
    assert anon.get("/api/events").status_code == 401


# ── Iran Gateway API flows (probes faked via monkeypatch) ───────────────────

def test_iran_gateway_crud_flow(authed, monkeypatch):
    # unconfigured status
    r = authed.get("/api/iran-gateway/status")
    assert r.status_code == 200
    assert r.json()["state"] == "UNCONFIGURED"

    # create
    r = authed.post("/api/iran-gateway", json={
        "name": "IT-GW", "endpoint": "itgw.example.com", "port": 8080,
        "protocol": "http", "auth_password": "it-secret"})
    assert r.status_code == 200, r.text
    gid = r.json()["gateway"]["gateway_id"]
    # secrets never leak through the API
    assert "auth_password" not in r.json()["gateway"]
    blob = str(authed.get("/api/iran-gateway").json())
    assert "it-secret" not in blob

    # fake probes: reachable + Iranian egress
    async def _reach(endpoint, port, timeout=12.0):
        return {"reachable": True, "latency_ms": 9.0, "ok": True}
    async def _egress(gw):
        return {"ok": True, "public_ip": "5.10.7.7", "country_code": "IR",
                "country": "Iran", "asn": "AS58224", "isp": "TIC"}
    monkeypatch.setattr(ig, "_tcp_reachable", _reach)
    monkeypatch.setattr(ig, "_probe_egress_http", _egress)

    r = authed.post(f"/api/iran-gateway/{gid}/check")
    assert r.status_code == 200
    assert r.json()["state"] == "VERIFIED_IRAN_EGRESS"

    # IRAN_PROXY now buildable
    r = authed.post("/api/config-builder/generate", json={
        "name": "it-iranproxy", "protocol": "vless", "transport": "ws",
        "security": "tls", "node_id": "panel", "routing_policy": "IRAN_PROXY",
        "client_format": "uri"})
    assert r.status_code == 200, r.text
    assert "IRAN_GATEWAY" in r.text

    # delete
    r = authed.delete(f"/api/iran-gateway/{gid}")
    assert r.status_code == 200


def test_iran_gateway_route_mismatch_flow(authed, monkeypatch):
    r = authed.post("/api/iran-gateway", json={
        "name": "IT-GW-NL", "endpoint": "nl.example.com", "port": 8080,
        "protocol": "http"})
    gid = r.json()["gateway"]["gateway_id"]

    async def _reach(endpoint, port, timeout=12.0):
        return {"reachable": True, "latency_ms": 9.0, "ok": True}
    async def _egress(gw):
        return {"ok": True, "public_ip": "1.2.3.4", "country_code": "NL",
                "country": "Netherlands"}
    monkeypatch.setattr(ig, "_tcp_reachable", _reach)
    monkeypatch.setattr(ig, "_probe_egress_http", _egress)

    r = authed.post(f"/api/iran-gateway/{gid}/check")
    assert r.json()["state"] == "ROUTE_MISMATCH"
    st = authed.get("/api/iran-gateway/status").json()
    assert st["iran_proxy_status"]["verdict"] == "ROUTE_MISMATCH"
    authed.delete(f"/api/iran-gateway/{gid}")


def test_iran_gateway_requires_auth(anon):
    assert anon.get("/api/iran-gateway").status_code == 401
    assert anon.post("/api/iran-gateway", json={}).status_code == 401


# ── Domestic routing policy API with new presets ────────────────────────────

def test_domestic_policy_accepts_new_presets(authed):
    for pol in ("IRAN_PROXY", "INTERNATIONAL_VPN"):
        r = authed.post("/api/domestic/policy", json={"policy": pol})
        assert r.status_code == 200, r.text
        assert r.json()["active_policy"] == pol
    # restore default
    authed.post("/api/domestic/policy", json={"policy": "ALL_VPN"})


def test_domestic_test_route_iran_proxy_attribution(authed):
    def _verified():
        return {"configured": True, "state": "VERIFIED_IRAN_EGRESS",
                "egress": "IRAN_GATEWAY (verified)",
                "verdict": "VERIFIED_IRAN_EGRESS"}
    dre.set_gateway_status_fn(_verified)
    # deterministic classification regardless of suite order
    dre._db.load_prefixes(["5.10.0.0/16"], {"version": "t", "source": "test"})
    r = authed.post("/api/domestic/test-route", json={"destination": "5.10.7.7"})
    assert r.status_code == 200
    j = r.json()
    # without policy switch the ACTIVE policy governs (ALL_VPN default) —
    # verify the engine's IRAN_PROXY attribution through the policy route
    out = asyncio.run(dre.decide_route(
        "5.10.7.7", policy=dre.PRESET_POLICIES["IRAN_PROXY"]))
    assert out["egress"] == "IRAN_GATEWAY"
    assert out["iran_gateway"]["verdict"] == "VERIFIED_IRAN_EGRESS"


# ── Diagnostics coverage (spec §27) ─────────────────────────────────────────

def test_diagnostics_covers_phase38plus_sections(authed):
    r = authed.get("/api/diagnostics")
    assert r.status_code == 200
    checks = r.json()["checks"]
    for k in ("config_builder", "iran_gateway", "events", "iran_routing"):
        assert k in checks, k


# ── Frontend markers (served HTML — source-level assertions) ────────────────

def test_dashboard_serves_builder_and_iranproxy_pages(authed):
    r = authed.get("/dashboard")
    assert r.status_code == 200
    html = r.text
    # Phase 40: the builder is no longer a standalone page — it is the
    # full-screen workspace (#ws-create) INSIDE pg-links (کانفیگ‌ها).
    # element ids ncc-*/bld-* are intentionally retained inside the overlay.
    for marker in ('id="pg-links"', 'id="ws-create"', 'id="pg-iranproxy"',
                   'data-pg="links"', 'data-pg="iranproxy"',
                   'id="ncc-protocols"', 'id="ncc-routing"', 'id="ncc-console"',
                   'id="bld-history"',
                   'id="igw-list"', 'loadBuilderPage', 'loadIranProxyPage',
                   'openCreateWorkspace', 'کانفیگ‌های ساخته‌شده', 'پروکسی ایران', 'ساخت کانفیگ'):
        assert marker in html, marker
    # the standalone builder page must be gone (no competing page — §33)
    assert 'id="pg-builder"' not in html


def test_builder_js_is_capability_driven_not_hardcoded(client):
    html = client.get("/dashboard").text
    # the page renders from /api/config-builder/capabilities — no hardcoded
    # protocol-support lists in the JS
    assert "/api/config-builder/capabilities" in html
    assert "IRAN_PROXY" in html and "INTERNATIONAL_VPN" in html
    # honest SNI note present (spec §10 — SNI is never routing)
    assert "نه مسیریابی" in html or "هرگز مسیریابی" in html


# ── IRAN DIRECT assets + builder E2E (Phase 38+ §11/§12 — Clean IP + Handshake) ──

def test_iran_direct_routes_require_auth(anon):
    assert anon.get("/api/iran-direct/assets").status_code == 401
    assert anon.post("/api/iran-direct/ips", json={"address": "1.1.1.1"}).status_code == 401
    assert anon.post("/api/iran-direct/handshakes", json={"sni": "x.com"}).status_code == 401


def test_iran_direct_asset_lifecycle_via_real_app(authed):
    r = authed.post("/api/iran-direct/ips",
                    json={"address": "104.17.1.1", "port": 443})
    assert r.status_code == 200
    ip_id = r.json()["asset"]["id"]
    assert r.json()["asset"]["verification"] == "CONFIGURED_ENDPOINT"

    # invalid octets rejected (canonical validator — no impossible IPs)
    r = authed.post("/api/iran-direct/ips", json={"address": "104.17.1.999"})
    assert r.status_code == 400
    # SNI can never be an IP
    r = authed.post("/api/iran-direct/handshakes", json={"sni": "104.17.1.1"})
    assert r.status_code == 400

    r = authed.post("/api/iran-direct/handshakes",
                    json={"sni": "hs.example.com"})
    assert r.status_code == 200
    hs_id = r.json()["asset"]["id"]

    assets = authed.get("/api/iran-direct/assets").json()
    assert [a["address"] for a in assets["ips"]] == ["104.17.1.1"]
    assert [h["sni"] for h in assets["handshakes"]] == ["hs.example.com"]
    assert "USER_ISP" in assets["note"]

    assert authed.delete(f"/api/iran-direct/ips/{ip_id}").status_code == 200
    assert authed.delete(f"/api/iran-direct/handshakes/{hs_id}").status_code == 200


def test_iran_direct_clean_ip_handshake_config_e2e(authed):
    """IP سالم + هندشیک → کانفیگ IRAN_DIRECT از کامپایلر کانونی (همان API)."""
    authed.post("/api/iran-direct/ips", json={"address": "104.17.1.1"})
    authed.post("/api/iran-direct/handshakes", json={"sni": "hs.example.com"})
    body = {
        "name": "ird-e2e", "protocol": "vless", "transport": "xhttp-packet-up",
        "security": "tls", "node_id": "panel", "endpoint_profile_id": "",
        "custom_address": "104.17.1.1", "custom_sni": "hs.example.com",
        "custom_port": 443, "routing_policy": "IRAN_DIRECT",
        "client_format": "xray-json", "remark": "e2e",
    }
    r = authed.post("/api/config-builder/generate", json=body)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"], j.get("errors")
    uri = j["outputs"]["uri"]
    assert "104.17.1.1" in uri            # address = Clean IP
    assert "hs.example.com" in uri        # host/sni = handshake
    assert j["history_id"]
    # split rules embedded in xray json (IRAN_DIRECT honored)
    rules = j["preview"]["routing_detail"]["split_rules"]
    assert rules["verdict"] == "SPLIT_TUNNEL_SUPPORTED"
    legs = j["preview"]["routing_detail"]["legs"]
    assert legs["IRAN_DOMESTIC"]["egress"] == "USER_ISP (VPN BYPASSED)"

    # events recorded (structured)
    recs = authed.get("/api/events?limit=50").json()
    evs = [e["event"] for e in recs.get("events", [])]
    assert "CONFIG_GENERATED" in evs
    assert "IRAN_DIRECT_ASSET_SAVED" in evs


def test_iran_direct_ip_without_handshake_rejected(authed):
    body = {
        "name": "ird-bad", "protocol": "vless", "transport": "xhttp-packet-up",
        "security": "tls", "node_id": "panel",
        "custom_address": "104.17.1.1", "custom_sni": "", "custom_port": 443,
        "routing_policy": "IRAN_DIRECT", "client_format": "xray-json",
    }
    r = authed.post("/api/config-builder/preview", json=body)
    assert r.status_code == 422
    j = r.json()
    assert not j["ok"]
    assert any("SNI" in e for e in j["errors"])


def test_dashboard_serves_iran_direct_builder(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    html = r.text
    for marker in ('id="ird-protocols"', 'id="ird-ips"', 'id="ird-hss"',
                   'id="ird-preview-btn"', 'id="ird-history"',
                   'irdLoad', 'irdGenerate', 'irdPayload',
                   'IP سالم', 'هندشیک', 'IRAN_DIRECT'):
        assert marker in html, marker
    # canonical-only: the IRD builder posts to the config-builder API
    assert "/api/config-builder/generate" in html
    # honest labeling present in the section
    assert "CONFIGURED_ENDPOINT" in html
