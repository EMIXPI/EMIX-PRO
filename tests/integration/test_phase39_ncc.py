# tests/integration/test_phase39_ncc.py — Phase 39: Network Control Center
#
# Integration + REAL-network tests:
#   §A quick/tls/sni/diagnostic against a REAL public target (cloudflare.com)
#      — every number in the response must come from a real measurement.
#   §B honest failures (DNS_ERROR) and blocked-host posture.
#   §C canonical compiler chain still healthy (preview + generate vless-ws).
#   §D structured events emitted for real tests.
#   §E migration acceptance: nav «ساخت کانفیگ» → pg-builder → NCC markers;
#      old create modal stays on the links page (management quick-add);
#      command palette routes ساخت کانفیگ جدید to the unified builder.
#
# Uses the real FastAPI app (same boot path as Railway: import main).

import asyncio
import json
import re

import pytest
from fastapi.testclient import TestClient

import main  # the real app — same as `python main.py`
import network_test
import structured_events


@pytest.fixture(scope="module")
def client():
    main.reset_for_tests() if hasattr(main, "reset_for_tests") else None
    with TestClient(main.app) as c:
        c.post("/api/login", json={"password": "test-password"})
        yield c


REAL_TARGET = {"address": "cloudflare.com", "port": 443, "sni": "cloudflare.com"}


# ── §A real network tests (a unit test is NOT a real network test) ──────────

def test_a1_quick_real_network(client):
    r = client.post("/api/network/test/quick", json=REAL_TARGET)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True, f"real probe failed: {d.get('error_detail')}"
    s = d["stages_ms"]
    # every stage measured for real — non-None, non-negative, plausible
    assert s["dns"] is not None and s["dns"] >= 0
    assert s["tcp"] is not None and s["tcp"] >= 0
    assert s["tls"] is not None and s["tls"] >= 0
    assert d["total_ms"] == round(s["dns"] + s["tcp"] + s["tls"], 1)
    assert d["resolved_ips"], "real DNS resolution must produce addresses"
    assert d["engine"].startswith("network_test/")


def test_a2_tls_real_cert(client):
    r = client.post("/api/network/test/tls", json=REAL_TARGET)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    cert = d["cert"]
    # real certificate info from a real handshake
    assert cert["subject_cn"] or cert["sans"]
    assert cert["days_left"] is not None and cert["days_left"] > 0
    assert cert["verify_mode"] == "verified"


def test_a3_sni_real_match(client):
    r = client.post("/api/network/test/sni", json=REAL_TARGET)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    sa = d["sni_analysis"]
    assert sa["requested"] == "cloudflare.com"
    assert sa["match"] is True
    assert "SNI فقط معنای TLS" in sa["note"]  # semantics guardrail text


def test_a4_diagnostic_composite(client):
    r = client.post("/api/network/test/diagnostic", json=REAL_TARGET)
    assert r.status_code == 200
    d = r.json()
    assert d["endpoint"]["ok"] is True
    # composite parts present (each honest: OK / UNAVAILABLE — never faked)
    assert d["panel_egress"]["status"] in ("OK", "UNAVAILABLE")
    assert d["panel_health"]["status"] in ("OK", "UNAVAILABLE", "SKIPPED")
    assert isinstance(d["browser_targets"], list)


def test_a5_targets_real_panel_host(client):
    r = client.get("/api/network/test/targets")
    assert r.status_code == 200
    d = r.json()
    # the real panel host (from RAILWAY_PUBLIC_DOMAIN in test env) must appear
    assert any(t["address"] == "test.example.com" for t in d["targets"])


# ── §B honest failures ───────────────────────────────────────────────────────

def test_b1_dns_error_is_honest(client):
    r = client.post("/api/network/test/quick",
                    json={"address": "nonexistent-zzz.invalid", "port": 443})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is False
    assert d["error_code"] == "DNS_ERROR"
    assert d["total_ms"] is None  # never a fake number on failure


def test_b2_blocked_host_refused(client):
    r = client.post("/api/network/test/quick", json={"address": "127.0.0.1"})
    assert r.status_code == 400


def test_b3_bad_sni_refused(client):
    r = client.post("/api/network/test/sni",
                    json={"address": "example.com", "sni": "1.2.3.4"})
    assert r.status_code == 400


# ── §C canonical compiler chain unaffected ──────────────────────────────────

def test_c1_preview_generate_vless_ws(client):
    body = {"name": "p39-it", "protocol": "vless", "transport": "ws",
            "security": "tls", "node_id": "panel", "routing_policy": "ALL_VPN",
            "client_format": "xray-json", "remark": "p39"}
    r = client.post("/api/config-builder/preview", json=body)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert "uri" in (d.get("outputs") or {})
    r = client.post("/api/config-builder/generate", json=body)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True, d.get("errors")


def test_c2_capabilities_shape(client):
    r = client.get("/api/config-builder/capabilities")
    assert r.status_code == 200
    d = r.json()
    protos = {p["protocol"]: p for p in d["protocols"]}
    for must in ("vless", "trojan", "shadowsocks", "mtproto"):
        assert must in protos, f"{must} missing from capabilities"
        assert protos[must]["readiness"] == "PRODUCTION"
    policies = {p["policy"] for p in d["routing_policies"]}
    assert {"ALL_VPN", "IRAN_DIRECT", "IRAN_PROXY"} <= policies
    # the NCC routing gate needs the gateway state
    assert "iran_gateway" in d and "state" in d["iran_gateway"]


# ── §D structured events for real tests ─────────────────────────────────────

def test_d1_events_emitted(client):
    client.post("/api/network/test/quick", json=REAL_TARGET)
    evts = structured_events.recent_events(limit=20, event="network_test")
    assert evts, "network_test events must be recorded"
    e = evts[0] if isinstance(evts, list) else evts
    blob = json.dumps(e, ensure_ascii=False)
    assert "cloudflare.com" in blob
    assert ("success" in blob or "DNS_ERROR" in blob or "failed" in blob)


# ── §E migration acceptance (the REAL user flow) ─────────────────────────────

def test_e1_nav_and_ncc_markers(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    html = r.text
    # the existing «ساخت کانفیگ» nav item must open pg-builder…
    assert re.search(r'data-pg="builder"[^>]*>\s*<i[^>]*></i>\s*✨?\s*ساخت کانفیگ', html) or \
           ('data-pg="builder"' in html and 'ساخت کانفیگ' in html)
    # …and pg-builder IS the Network Control Center now
    assert 'id="pg-builder"' in html
    assert "مرکز کنترل شبکه EMIX" in html          # NCC header title
    assert 'id="ncc-console"' in html              # live test panel
    assert 'id="ncc-routing"' in html              # routing cards
    assert 'id="ncc-protocols"' in html            # protocol cards
    assert "nccTestQuick" in html                  # real quick test wired
    assert "nccTestTunnel" in html                 # real E2E tunnel test wired
    assert "nccTestDiagnostic" in html             # full diagnostic wired


def test_e2_old_create_modal_remains_for_management(client):
    """The old quick-add modal stays ONLY as part of the links management page."""
    r = client.get("/dashboard")
    html = r.text
    assert 'id="modal-create-link"' in html        # management quick-add kept
    assert "createLink" in html                     # links page flow intact


def test_e3_palette_routes_to_unified_builder(client):
    r = client.get("/dashboard")
    html = r.text
    m = re.search(r"\{t:'ساخت کانفیگ جدید',s:'([^']*)'", html)
    assert m, "palette entry missing"
    assert "مرکز کنترل شبکه" in m.group(1)          # now describes the NCC
    assert "navTo('builder')" in html


def test_e4_no_second_config_page_created(client):
    """No new competing page was added — the NCC replaced pg-builder in place."""
    r = client.get("/dashboard")
    html = r.text
    # pg-builder is unique: exactly one section carries the NCC console
    assert html.count('id="pg-builder"') == 1
    assert html.count('id="ncc-console"') == 1
