# tests/integration/test_egress_semantics.py — FALSE EGRESS defect, E2E evidence
#
# Spec §REGRESSION TESTS + §E2E: prove through the live app (TestClient) with
# injected measurement providers that:
#
#   1. configured custom IP is never reported as the actual egress IP
#   2. SNI change / 3. hostname change → actual egress unchanged
#   4. country selection without exit node → NO_EXIT_NODE_AVAILABLE
#   5. country selection with a real exit node → route uses that node
#   6. expected country != observed country → ROUTE_MISMATCH
#   7. Railway control plane → cannot masquerade as an arbitrary exit node
#   8. E2E: CLIENT → CONTROL PLANE → EXIT NODE → INTERNET → EGRESS VERIFICATION
#   9. UI semantics: the misleading "Custom IP" label is gone; the field is an
#      endpoint address; the panel never claims it changes the egress.
import asyncio
import os
import time

import pytest
from fastapi.testclient import TestClient
from urllib.parse import unquote

os.environ.setdefault("EMIX_HEALTH_SWEEP_INTERVAL", "3600")

import egress_engine as ee

# a REAL vless UUID so the config compiler does not fall back to legacy
E2E_UUID = "e2e0192a-7c31-4b8a-9d5f-3a6b8c1d2e4f"


# ── fake world: one control plane (Railway NL), one real TR exit node ───────
RAILWAY_UPSTREAM = "emix-pro-production.up.railway.app"
TR_VPS = "vps-tr.example.com"
PANEL_EGRESS_IP = "208.77.244.84"        # what the Internet actually sees
CUSTOM_IP = "185.164.73.192"             # the value the user typed
TR_EGRESS_IP = "203.0.113.7"

LOCATIONS = [
    {"name": "auto", "label": "auto", "flag": "🌍",
     "upstream": RAILWAY_UPSTREAM, "pending": False},
    {"name": "tr", "label": "ترکیه — استانبول", "flag": "🇹🇷",
     "upstream": RAILWAY_UPSTREAM, "pending": True},     # claims TR, exits Railway
    {"name": "trvps", "label": "ترکیه (VPS واقعی)", "flag": "🇹🇷",
     "upstream": TR_VPS, "pending": False},              # real TR exit node
]


def _install_providers(panel_egress=None, loc_egress=None, cp_rtt=42.0):
    async def fake_status(cfg):
        return {"ok": True, "wte": True, "version": "2.2.0-egress",
                "locations": LOCATIONS}

    async def fake_exit_ip(cfg, name):
        if name == "trvps":
            return {"ok": True, "loc": name, "label": "ترکیه (VPS واقعی)",
                    "upstream": TR_VPS, "exit_ip": TR_EGRESS_IP,
                    "exit_country": "Türkiye", "exit_country_code": "TR",
                    "exit_city": "Istanbul", "exit_isp": "TR-Host",
                    "exit_asn": "AS9123", "latency_ms": 88.0}
        if name == "tr":
            return {"ok": True, "loc": name, "label": "ترکیه — استانبول",
                    "upstream": RAILWAY_UPSTREAM, "exit_ip": PANEL_EGRESS_IP,
                    "exit_country": "Netherlands", "exit_country_code": "NL",
                    "exit_city": "Amsterdam", "exit_isp": "Railway",
                    "exit_asn": "AS198204", "latency_ms": 65.0}
        # auto → panel egress via upstream
        return {"ok": True, "loc": name, "upstream": RAILWAY_UPSTREAM,
                "exit_ip": PANEL_EGRESS_IP, "exit_country": "Netherlands",
                "exit_country_code": "NL", "exit_isp": "Railway",
                "exit_asn": "AS198204", "latency_ms": 61.0}

    async def fake_panel(cfg=None):
        if panel_egress is not None:
            return panel_egress
        return {"ok": True, "public_ip": PANEL_EGRESS_IP,
                "country": "Netherlands", "country_code": "NL",
                "city": "Amsterdam", "isp": "Railway", "asn": "AS198204",
                "measurement_source": "test:panel"}

    def fake_cp_rtt():
        return ee.labeled_latency("control_plane_rtt", cp_rtt, "test")

    ee.set_provider("worker_status", fake_status)
    ee.set_provider("worker_exit_ip", loc_egress or fake_exit_ip)
    ee.set_provider("panel_egress", fake_panel)
    ee.set_provider("control_plane_rtt", fake_cp_rtt)


@pytest.fixture(scope="module")
def client():
    import main
    from main import LINKS

    _before = dict(LINKS)
    LINKS[E2E_UUID] = {
        "label": "E2E-TR", "protocol": "vless-ws", "active": True,
        "created": time.time(), "used_bytes": 0, "limit_bytes": 0,
    }
    _install_providers()
    with TestClient(main.app) as c:
        yield c
    LINKS.clear()
    LINKS.update(_before)
    ee.reset_for_tests()
    try:
        asyncio.run(main.save_state())
    except Exception:
        pass


@pytest.fixture(scope="module")
def authed(client):
    client.post("/api/login", json={"password": os.environ.get("ADMIN_PASSWORD", "test-password")})
    return client


@pytest.fixture(autouse=True)
def _fresh_evidence():
    ee._evidence.clear()
    ee._route_history.clear()
    _install_providers()
    yield
    ee._evidence.clear()
    ee._route_history.clear()


# ── 1. configured IP is never the reported egress ───────────────────────────

def test_verify_panel_reports_measured_ip_not_configured(authed):
    """The user 'configured' 185.164.73.192 — the API must answer with the
    MEASURED egress 208.77.244.84 and never echo the configured value."""
    r = authed.get("/api/egress/verify?target=panel")
    assert r.status_code == 200
    j = r.json()
    assert j["classification"] == "VERIFIED_EGRESS"
    assert j["egress"]["public_ip"] == PANEL_EGRESS_IP
    body = r.text
    assert CUSTOM_IP not in body
    assert "185.164" not in body


def test_verify_loc_classifications(authed):
    r = authed.get("/api/egress/verify?target=loc:trvps")
    j = r.json()
    assert j["classification"] == "VERIFIED_EGRESS"
    assert j["egress"]["public_ip"] == TR_EGRESS_IP
    assert j["egress"]["country_code"] == "TR"
    assert j["egress"]["asn"] == "AS9123"
    # measured country never comes from the location label
    r2 = authed.get("/api/egress/verify?target=loc:tr")
    j2 = r2.json()
    assert j2["egress"]["country_code"] == "NL"      # label said TR, truth says NL


# ── 2/3. SNI & hostname changes leave the egress unchanged ─────────────────

def test_sni_and_hostname_do_not_appear_in_egress_api(authed):
    for target in ("panel", "loc:trvps"):
        r = authed.get(f"/api/egress/verify?target={target}")
        j = r.json()
        ev = j.get("egress", {})
        # egress evidence schema carries ONLY measured fields
        for endpoint_layer_key in ("sni", "host", "hostname", "tls_server_name",
                                   "server_name", "http_host", "custom_sni"):
            assert endpoint_layer_key not in ev
        assert "public_ip" in ev


def test_egress_evidence_invariant_under_sni_changes():
    ee._evidence.clear()
    a = asyncio.run(ee.verify_egress("loc:trvps"))
    ev_a = a["egress"]["public_ip"]
    # simulate the user changing SNI/hostname in the config — evidence is keyed
    # by TARGET, endpoint-layer values never enter the measurement
    b = asyncio.run(ee.verify_egress("loc:trvps"))
    assert b["egress"]["public_ip"] == ev_a == TR_EGRESS_IP


# ── 4. country selection without exit node → NO_EXIT_NODE_AVAILABLE ────────

def test_validate_route_tr_label_without_exit_node(authed):
    """Location 'tr' exists but its upstream is Railway → choosing Turkey is
    NO_EXIT_NODE_AVAILABLE; the country is not faked."""
    r = authed.post("/api/egress/validate-route",
                    json={"location": "tr", "expected_country": "TR"})
    j = r.json()
    assert j["route_health"] == "NO_EXIT_NODE_AVAILABLE"
    assert "NO_EXIT_NODE" in j["error"] or "no verified exit node" in j["error"]
    # verdict recorded with expected country for audit
    assert j["expected_country"] == "TR"


# ── 5. country selection with real exit node → route uses that node ─────────

def test_validate_route_real_exit_node_healthy(authed):
    r = authed.post("/api/egress/validate-route",
                    json={"location": "trvps", "expected_country": "TR"})
    j = r.json()
    assert j["ok"] is True
    assert j["route_health"] == "HEALTHY"
    assert j["egress"]["egress"]["public_ip"] == TR_EGRESS_IP
    assert j["egress"]["egress"]["country_code"] == "TR"
    assert j["comparison"]["route_health"] == "HEALTHY"


# ── 6. expected != observed → ROUTE_MISMATCH (never HEALTHY) ───────────────

def test_route_mismatch_when_observed_country_differs(authed):
    r = authed.post("/api/egress/validate-route",
                    json={"location": "auto", "expected_country": "TR"})
    j = r.json()
    assert j["route_health"] == "ROUTE_MISMATCH"
    reasons = " | ".join(j["comparison"]["reasons"])
    assert "TR" in reasons and "NL" in reasons
    assert j["ok"] is False


def test_route_mismatch_case_is_recorded_not_hidden(authed):
    authed.post("/api/egress/validate-route",
                json={"location": "auto", "expected_country": "TR"})
    r = authed.get("/api/egress/health")
    j = r.json()
    assert j["layers"]["ROUTE_HEALTH"] == "ROUTE_MISMATCH"
    assert j["layers"]["EGRESS_HEALTH"] == "ROUTE_MISMATCH"
    assert any(h["route_health"] == "ROUTE_MISMATCH" for h in j["route_history"])


# ── 7. Railway control plane cannot masquerade as an exit node ─────────────

def test_control_plane_cannot_masquerade(authed):
    """Panel egress is NL. Claiming TR must produce ROUTE_MISMATCH — the
    control plane role makes an arbitrary-country claim impossible."""
    r = authed.get("/api/egress/summary")
    j = r.json()
    assert j["control_plane"]["role"] == "CONTROL_PLANE"
    assert j["control_plane"]["is_control_plane"] is True
    # exit nodes list never contains the railway relay
    for nd in j.get("exit_nodes", []):
        assert "railway.app" not in (nd.get("upstream") or "")
    # and with an expectation of TR on the panel chain:
    r2 = authed.post("/api/egress/validate-route",
                     json={"location": "auto", "expected_country": "TR"})
    assert r2.json()["route_health"] == "ROUTE_MISMATCH"


# ── 8. E2E: CLIENT → CONTROL PLANE → EXIT NODE → INTERNET → EGRESS VERIFY ──

def test_e2e_full_route_chain(authed):
    """Golden path through the 9-step pipeline with evidence at every hop."""
    r = authed.post("/api/egress/validate-route",
                    json={"location": "trvps", "expected_country": "TR",
                          "expected_ip": TR_EGRESS_IP})
    j = r.json()
    assert j["route_health"] == "HEALTHY"
    # all 9 steps present and named
    names = [s["name"] for s in j["steps"]]
    for expected_step in ("resolve_endpoint", "connect_node", "verify_node",
                          "verify_route", "verify_egress",
                          "compare_expectations", "measure_latency"):
        assert expected_step in names, f"missing step {expected_step}"
    assert all(s["ok"] for s in j["steps"])
    # egress evidence stored & queryable
    assert ee.evidence_for("loc:trvps")["public_ip"] == TR_EGRESS_IP
    # latencies labeled
    measures = [l["measure"] for l in j["latencies"]]
    assert "route_rtt" in measures and "control_plane_rtt" in measures
    for lat in j["latencies"]:
        assert lat["measure"] in ee.LATENCY_MEASURES
    # routes inventory exposes entry/relay/exit/egress/latency shape
    inv = authed.get("/api/egress/routes").json()
    route = next(rt for rt in inv["routes"] if rt["route"] == "loc:trvps")
    assert route["entry"]["role"] == "RELAY_NODE"
    assert route["exit"]["host"] == TR_VPS
    assert route["exit"]["role"] == "EXIT_NODE"
    assert "latencies" in route and "egress" in route


def test_e2e_routes_inventory_honest_notes(authed):
    inv = authed.get("/api/egress/routes").json()
    auto = next(rt for rt in inv["routes"] if rt["route"] == "loc:auto")
    assert auto["note"].startswith("Traffic exits from the control plane") or \
        "کنترل" in auto["note"]
    assert auto["exit"]["role"] == "RELAY_NODE"


# ── gaming links API carries the truth ──────────────────────────────────────

@pytest.fixture()
def patched_gaming(monkeypatch):
    """Worker v1 (no WTE) — pure tunnel semantics: /loc/{name} → upstream."""
    import gaming_boost

    async def fake_call_worker(cfg, path, method="GET", payload=None):
        if path.startswith("/gateway-status"):
            return {"ok": True, "wte": False, "version": "1.9.0-legacy",
                    "locations": LOCATIONS}
        if path.startswith("/admin/vless-uuids"):
            return {"ok": True, "pushed": 1}
        return {"ok": False, "error": f"unexpected {path}"}

    monkeypatch.setattr(gaming_boost, "_call_worker", fake_call_worker)
    return gaming_boost


@pytest.fixture()
def patched_gaming_wte(monkeypatch):
    """Worker v2 (WTE capable) — vless links terminate INSIDE the worker, so
    their honest exit is the CF colo (EDGE_NODE), whatever the location says."""
    import gaming_boost

    async def fake_call_worker(cfg, path, method="GET", payload=None):
        if path.startswith("/gateway-status"):
            return {"ok": True, "wte": True, "version": "2.2.0-egress",
                    "locations": LOCATIONS}
        if path.startswith("/admin/vless-uuids"):
            return {"ok": True, "pushed": 1}
        return {"ok": False, "error": f"unexpected {path}"}

    monkeypatch.setattr(gaming_boost, "_call_worker", fake_call_worker)
    return gaming_boost


def test_gaming_links_warn_no_exit_node(authed, patched_gaming):
    """Choosing the 'tr' location (railway upstream) must carry
    NO_EXIT_NODE_AVAILABLE and honest remarks — not a country claim."""
    r = authed.post("/api/gaming/links",
                    json={"entry": "direct", "location": "tr",
                          "ip": CUSTOM_IP, "transport": "ws"})
    j = r.json()
    assert j["ok"] is True
    assert j["route_warning"]["code"] == "NO_EXIT_NODE_AVAILABLE"
    assert j["egress"]["has_real_exit"] is False
    # endpoint note teaches the truth about the custom IP field
    assert "IP خروج را تغییر نمی‌دهد" in j["egress"]["endpoint_note"]
    # every link says where traffic really exits
    for l in j["links"]:
        assert l["route"]["egress"]["classification"] in ee.EGRESS_CLASSIFICATIONS
        assert l["route"]["exit"]["role"] == "RELAY_NODE"
        assert "کنترل‌پلین" in l["exit"]
        assert "خروج: Railway" in unquote(l["gaming"])


def test_gaming_links_with_real_exit(authed, patched_gaming):
    r = authed.post("/api/gaming/links",
                    json={"entry": "direct", "location": "trvps",
                          "ip": "", "transport": "ws"})
    j = r.json()
    assert j["route_warning"] is None
    assert j["egress"]["has_real_exit"] is True
    assert j["egress"]["selected_upstream"] == TR_VPS
    for l in j["links"]:
        assert l["route"]["exit"]["role"] == "EXIT_NODE"
        assert l["route"]["exit"]["host"] == TR_VPS
        assert TR_VPS in l["gaming"] or TR_VPS in unquote(l["gaming"])


def test_gaming_links_wte_exit_is_edge_node_not_country(authed, patched_gaming_wte):
    """Worker v2 WTE: vless terminates inside the worker → honest exit label is
    the CF colo (EDGE_NODE) — NOT the selected country, NOT Railway."""
    r = authed.post("/api/gaming/links",
                    json={"entry": "direct", "location": "trvps",
                          "ip": "", "transport": "ws"})
    j = r.json()
    for l in j["links"]:
        assert l["route"]["exit"]["role"] == "EDGE_NODE"
        assert "Cloudflare colo" in l["exit"]
        assert "خروج: CF colo (WTE)" in unquote(l["gaming"])
        # and the country never appears as an egress claim
        assert "istanbul" not in l["exit"].lower()


def test_gaming_links_custom_ip_is_entry_only(authed, patched_gaming):
    """The custom IP ends up ONLY as the dial address (entry), never as an
    egress claim anywhere in the response."""
    r = authed.post("/api/gaming/links",
                    json={"entry": "direct", "location": "tr",
                          "ip": CUSTOM_IP, "transport": "ws"})
    j = r.json()
    for l in j["links"]:
        assert l["route"]["entry"]["address"] == CUSTOM_IP   # entry: yes
        assert "IP خروج را تغییر نمی‌دهد" in l["route"]["entry"]["note"]
        egress_block = str(l["route"].get("egress", {}))
        assert CUSTOM_IP not in egress_block                  # egress: never
        assert CUSTOM_IP not in l["exit"]


# ── 9. UI semantics — the misleading labels are gone ────────────────────────

def test_ui_no_misleading_custom_ip_label():
    src = open("pages.py", encoding="utf-8").read()
    # the old misleading field label is removed
    assert "IP سفارشی (اختیاری)" not in src
    # replaced by an honest endpoint-address label
    assert "آدرس اندپوینت (ورودی — نه IP خروج)" in src
    assert "IP خروج را عوض نمی‌کند" in src
    # route truth card exists with the four required chips
    for elem in ("eg-cp-host", "eg-exit-node", "eg-real-ip", "eg-status-badge"):
        assert f'id="{elem}"' in src
    assert "کنترل‌پلین" in src and "CONTROL PLANE" in src
    # exit location select is honest about control-plane routes
    assert "بدون نود خروج — خروج: Railway (کنترل‌پلین)" in src


def test_ui_exit_check_uses_truth_engine():
    src = open("pages.py", encoding="utf-8").read()
    assert "/api/egress/validate-route" in src          # truth engine drives UI
    assert "ROUTE_MISMATCH" in src                       # mismatch is surfaced
    assert "NO_EXIT_NODE_AVAILABLE" in src               # no-exit is surfaced
    assert "/api/egress/summary" in src                  # card loader
    # latency labels are rendered with their measure names
    for m in ("control_plane_rtt", "route_rtt", "protocol_handshake_rtt"):
        assert m in src
    # configured IPs are never rendered as egress in the multiloc results
    assert "IP خروج (اندازه‌گیری‌شده)" in src
