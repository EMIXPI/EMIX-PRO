# tests/integration/test_phase40_workspace.py — Phase 40: کانفیگ‌ها = ورک‌اسپیس واحد شبکه
#
# Coverage (user spec Phase 40):
#   §A boot profile: config-creation chain is ALWAYS_ON under EMIX_PROFILE=core
#      (the "enable another profile" wall is GONE — §32).
#   §B ONE canonical pipeline: generate creates a LIVE link via the real
#      link-factory (_create_link_core) → the config appears as a card
#      (GET /api/links carries routing_policy/builder metadata) → retestable.
#      preview NEVER creates a link (same compiler, no side effects).
#   §C honest output-only paths: custom endpoint / non-panel node → created=false
#      with a reason; regenerate never duplicates the live link.
#   §D routing honesty: IRAN_DIRECT needs a split-tunnel client (blocked for
#      client_format=uri with SPLIT_TUNNEL_NOT_SUPPORTED); IRAN_PROXY blocked
#      without a verified gateway (honest Persian reason, no fake egress).
#   §E UI migration acceptance (§33): nav has NO visible competing builder page;
#      «+ ساخت کانفیگ» opens the workspace INSIDE کانفیگ‌ها (openCreateWorkspace);
#      the standalone pg-builder section is gone; palette routes to the workspace;
#      the old create modal is no longer the links-page primary action; the
#      profile-wall text is gone; premium card renderer + two-state chips exist.
#   §F history: link_uuid recorded; list view exposes it.

import re

import pytest
from fastapi.testclient import TestClient

import main  # the real app — same boot path as Railway
import boot_profile
import config_builder
import pages


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app) as c:
        c.post("/api/login", json={"password": "test-password"})
        _before = {l["uuid"] for l in c.get("/api/links").json()["links"]}
        yield c
        # hygiene: remove links created by this module so later test modules
        # (e.g. gaming_wte worker-sync exact-set assertions) see a clean LINKS
        for l in c.get("/api/links").json()["links"]:
            if l["uuid"] not in _before:
                c.delete(f"/api/links/{l['uuid']}")


# ── §A config-creation chain is core (the profile wall is gone) ─────────────

def test_a1_always_on_engines(monkeypatch):
    # production default profile (core) — the conftest runs full; emulate core
    monkeypatch.setenv("EMIX_PROFILE", "core")
    boot_profile.reset_for_tests()
    try:
        assert boot_profile.enabled("config_builder"), "config_builder must be ALWAYS_ON"
        assert boot_profile.enabled("capability_engine")
        assert boot_profile.enabled("iran_gateway")
        assert boot_profile.enabled("iran_direct")
        assert boot_profile.enabled("structured_events")
        assert boot_profile.enabled("turbo_boost")
        assert boot_profile.enabled("account_manager")
        # optional engines stay optional — the sidebar-simplified pages keep
        # their engines opt-in (nothing else silently became core)
        assert not boot_profile.enabled("gaming_boost")
        assert not boot_profile.enabled("zeus_features")
    finally:
        boot_profile.reset_for_tests()


def test_a2_core_surface_routes_registered(client):
    paths = {r.path for r in main.app.routes}
    for p in ("/api/config-builder/capabilities", "/api/config-builder/preview",
              "/api/config-builder/generate", "/api/config-builder/history",
              "/api/network/test/quick"):
        assert p in paths, f"core-surface route missing: {p}"
    assert "/api/network/test/quick" in [
        p for p, _ in boot_profile.CORE_SURFACE]


def test_a3_link_factory_wired(client):
    assert config_builder._link_factory is not None, \
        "main must wire config_builder.set_link_factory(_create_link_core)"


# ── §B ONE canonical pipeline: generate = live link + card + retest ─────────

def _gen(client, **over):
    body = {
        "name": "p40-test", "protocol": "vless", "transport": "xhttp-packet-up",
        "security": "tls", "node_id": "panel", "routing_policy": "ALL_VPN",
        "client_format": "xray-json", "persist": True,
    }
    body.update(over)
    return client.post("/api/config-builder/generate", json=body)


def test_b1_generate_creates_live_link(client):
    r = _gen(client, name="p40-vless-xhttp")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True, d.get("errors")
    # the LIVE link block (Phase 40 §34)
    L = d["link"]
    assert L["created"] is True
    assert L["uuid"] and L["share_link"].startswith("vless://")
    assert L["sub_url"].endswith(f"/sub/{L['uuid']}")
    assert L["routing_policy"] == "ALL_VPN"
    # the compiled credential IS the live link uuid (relay-authentic)
    assert d["request"]["credential"] == "<set>"  # masked server-side
    assert L["uuid"] in d["outputs"]["uri"]
    # history recorded with the link uuid (§F)
    assert d["history_id"]
    # the card sees it: GET /api/links carries builder metadata
    lr = client.get("/api/links")
    links = {l["uuid"]: l for l in lr.json()["links"]}
    assert L["uuid"] in links
    card = links[L["uuid"]]
    assert card["routing_policy"] == "ALL_VPN"
    assert card["node_id"] == "panel"
    assert card["transport"] == "xhttp-packet-up"
    assert card["built_by"] == "config_builder"
    assert card["protocol"] == "xhttp-packet-up"  # fused storage name


def test_b2_preview_never_creates_links(client):
    before = {l["uuid"] for l in client.get("/api/links").json()["links"]}
    r = client.post("/api/config-builder/preview", json={
        "name": "p40-preview", "protocol": "vless", "transport": "xhttp-packet-up",
        "security": "tls", "node_id": "panel", "routing_policy": "ALL_VPN",
        "client_format": "xray-json"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["link"]["created"] is False
    assert "preview" in d["link"]["reason"]
    assert d["credential_placeholder"] is True  # no invented credential
    after = {l["uuid"] for l in client.get("/api/links").json()["links"]}
    assert before == after  # zero side effects


def test_b3_generated_link_is_retestable_structure(client):
    # the generated link must carry everything the E2E ping needs
    # (uuid + protocol) and must NOT be born healthy (Phase 37.11 lifecycle)
    r = _gen(client, name="p40-retest")
    L = r.json()["link"]
    lr = client.get("/api/links").json()["links"]
    card = [l for l in lr if l["uuid"] == L["uuid"]][0]
    assert card["lifecycle_state"] == "CREATED"  # born UNKNOWN, never HEALTHY
    # the ping endpoint exists for this uuid (route-level)
    paths = {route.path for route in main.app.routes}
    assert "/api/links/{uid}/ping" in paths


# ── §C honest output-only paths ─────────────────────────────────────────────

def test_c1_custom_endpoint_is_output_only(client):
    r = _gen(client, name="p40-custom-ep", custom_address="example.com",
             custom_sni="example.com", custom_port=443)
    d = r.json()
    assert d["ok"] is True
    assert d["link"]["created"] is False
    assert "custom endpoint" in d["link"]["reason"].lower()


def test_c2_regenerate_never_duplicates_link(client):
    r = _gen(client, name="p40-regen")
    d = r.json()
    hid = d["history_id"]
    before = len(client.get("/api/links").json()["links"])
    rr = client.post(f"/api/config-builder/history/{hid}/regenerate")
    assert rr.status_code == 200
    rd = rr.json()
    assert rd["ok"] is True
    assert rd["link"]["created"] is False  # outputs-only — no duplicate
    after = len(client.get("/api/links").json()["links"])
    assert after == before


# ── §D routing honesty (no fake egress, no fake split-tunnel) ───────────────

def test_d1_iran_direct_requires_split_tunnel_client(client):
    r = _gen(client, name="p40-ird-uri", routing_policy="IRAN_DIRECT",
             client_format="uri")
    d = r.json()
    assert d["ok"] is False
    assert any("SPLIT_TUNNEL_NOT_SUPPORTED" in e for e in d["errors"])
    assert d["stage"] == "routing"
    # no link was created for the blocked request
    assert d.get("link", {}).get("created") is not True


def test_d2_iran_direct_with_xray_json_works(client):
    r = _gen(client, name="p40-ird-ok", routing_policy="IRAN_DIRECT",
             client_format="xray-json")
    d = r.json()
    assert d["ok"] is True, d.get("errors")
    assert d["link"]["created"] is True
    assert d["link"]["routing_policy"] == "IRAN_DIRECT"
    # the delivered client config carries the split rules (dataset-backed)
    assert d["outputs"].get("split_rules"), "IRAN_DIRECT must embed split rules"


def test_d3_iran_proxy_blocked_without_verified_gateway(client):
    r = _gen(client, name="p40-irproxy", routing_policy="IRAN_PROXY",
             client_format="xray-json")
    d = r.json()
    assert d["ok"] is False
    assert any("گیت‌وی" in e or "gateway" in e.lower() for e in d["errors"]), \
        "honest Persian gateway-missing reason required"
    assert d["stage"] == "routing"


# ── §E UI migration acceptance (the REAL active UI replaced) ────────────────

DASH = pages.DASHBOARD_HTML


def test_e1_no_visible_competing_builder_nav():
    # the «✨ ساخت کانفیگ» nav item must be HIDDEN (not a competing page)
    m = re.search(r'<div class="nav-it"[^>]*data-pg="builder"[^>]*>', DASH)
    assert m, "builder nav item must still exist as hidden deep-link target"
    assert "display:none" in m.group(0), "builder nav item must be hidden"


def test_e2_links_header_opens_workspace():
    # «+ ساخت کانفیگ» on the کانفیگ‌ها page opens the unified workspace
    m = re.search(r'id="ncw-add-btn"[^>]*onclick="openCreateWorkspace\(\)"', DASH)
    assert m, "links header button must call openCreateWorkspace()"
    # NOT the old modal — the old modal is no longer the primary create action
    pg_links = DASH.split('id="pg-links"')[1].split('id="pg-bridge"')[0]
    assert "openModal('modal-create-link')" not in pg_links


def test_e3_workspace_overlay_inside_links_page():
    pg_links = DASH.split('id="pg-links"')[1].split('id="pg-bridge"')[0]
    assert 'id="ws-create"' in pg_links, "workspace overlay must live INSIDE pg-links"
    assert 'closeCreateWorkspace()' in DASH
    assert 'builderGenerate' in pg_links and 'builderPreview' in pg_links
    # the 10-step progressive structure (§8)
    for s in range(1, 11):
        assert f'data-s="{s}"' in pg_links, f"step {s} missing"


def test_e4_standalone_builder_section_gone():
    assert '<section class="pg" id="pg-builder">' not in DASH, \
        "the standalone builder page must NOT exist (content moved to overlay)"


def test_e5_navto_builder_redirects_to_links_workspace():
    m = re.search(
        r"function navTo\(name\)\{.*?if\(name==='builder'\)\{.*?\n\s*\}",
        DASH, re.S)
    assert m, "navTo('builder') must redirect into the links workspace"
    assert "openCreateWorkspace" in m.group(0)
    assert "navTo('links')" in m.group(0)


def test_e6_palette_routes_to_workspace():
    assert "openCreateWorkspace" in DASH
    # the old quick-modal palette entry is replaced
    assert "مودال سریع" not in DASH


def test_e7_profile_wall_text_gone():
    # §32: no "enable EMIX_PROFILE=full to use this" wall in the builder path
    bld_js = DASH.split("loadBuilderPage")[1][:2000] if "loadBuilderPage" in DASH else ""
    assert "EMIX_PROFILE=full" not in bld_js, \
        "the builder fallback must not instruct users to switch profiles"


def test_e8_premium_cards_two_state_model():
    assert "function ncwCardHtml" in DASH
    assert "CONFIG ✓" in DASH and "RUNTIME" in DASH  # two-state chips
    assert "ncwRuntime" in DASH  # real ping-driven state
    # cards render from the real links list (routing line for builder links)
    assert "routing_policy" in DASH
    # CSS for the new design exists
    assert ".ncw-card" in DASH and ".ws-overlay" in DASH


def test_e9_mobile_sticky_action_bar():
    ws = DASH.split('id="ws-create"')[1].split("</section>")[0]
    assert 'class="ws-sticky"' in ws, "mobile sticky Generate bar (§29)"
    assert ".ws-sticky{display:none" in DASH  # desktop hidden, mobile shown
    assert "builderGenerate(this)" in ws


def test_e10_hidden_pages_keep_their_engines():
    # §31: hiding ≠ deleting — every hidden page section still exists
    for pg in ("bridge", "zeus", "gaming", "multiloc", "vpn", "routing",
               "iranproxy", "subscriptions", "traffic", "connections", "nodes",
               "experimental", "unified-configs"):
        assert f'id="pg-{pg}"' in DASH, f"pg-{pg} section must remain (hidden, not deleted)"


# ── §F history carries the link uuid ────────────────────────────────────────

def test_f1_history_list_exposes_link_uuid(client):
    r = client.get("/api/config-builder/history?limit=50")
    d = r.json()
    assert d["ok"] is True
    entries = [e for e in d["history"] if e.get("link_uuid")]
    assert entries, "at least one history entry must reference its live link"
    uuids = {l["uuid"] for l in client.get("/api/links").json()["links"]}
    for e in entries[:5]:
        assert e["link_uuid"] in uuids
