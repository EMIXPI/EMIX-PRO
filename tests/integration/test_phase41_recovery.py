# tests/integration/test_phase41_recovery.py — Phase 41:
# REAL NETWORK TEST RECOVERY + CONFIG BUILDER DATA-INTEGRITY FIX + MOBILE UX
#
# Coverage (user spec Phase 41):
#   §6  backend request-integrity boundary: an empty required field NEVER
#       reaches the capability engine — it fails at stage "request" with
#       INVALID_REQUEST (the exact production bug: transport '(empty)').
#   §30 transport integrity: for every (protocol, transport) combination the
#       capability engine itself reports as SUPPORTED, the canonical
#       ConfigRequest validates+previews WITHOUT any empty/None transport —
#       the generated request carries the exact canonical transport value.
#   §31 real config tests: VLESS+XHTTP+TLS (validate→preview→generate, live
#       link created), VLESS+WS+TLS, Trojan+WS, Shadowsocks+WS, MTProto+TCP.
#   §32 real ping contract: network quick-test against a REAL reachable
#       endpoint returns real latency (ok=True → total_ms is a positive
#       number) or an honest failure (ok=False → error_code/detail) — never a
#       fabricated value. Link E2E ping: success → ms, failure → reason.
#   §33/§34 UI acceptance (structural): frontend boundary validation exists
#       (builderPreview/guard), capability-driven auto-select keeps
#       visual selection == ConfigRequest value, mobile workspace has sticky
#       actions + compact one-column CSS + collapsed advanced sections.

import pytest
from fastapi.testclient import TestClient

import main  # the real app — same boot path as Railway
import capability_engine as caps
import pages


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app) as c:
        c.post("/api/login", json={"password": "test-password"})
        _before = {l["uuid"] for l in c.get("/api/links").json()["links"]}
        yield c
        for l in c.get("/api/links").json()["links"]:
            if l["uuid"] not in _before:
                c.delete(f"/api/links/{l['uuid']}")


# ── §6 request-integrity boundary (the EXACT production bug) ───────────────

def test_s6_empty_transport_is_request_stage_not_capability(client):
    """The exact user-reported payload: protocol selected, transport ''."""
    r = client.post("/api/config-builder/preview", json={
        "name": "", "remark": "EMIX", "protocol": "vless",
        "transport": "", "security": "tls", "node_id": "panel",
        "endpoint_profile_id": "", "routing_policy": "ALL_VPN",
        "client_format": "xray-json",
    })
    body = r.json()
    assert r.status_code == 422
    assert body["stage"] == "request", (
        "empty transport must be caught at the request boundary, "
        f"not passed to the capability engine (got stage={body.get('stage')!r})")
    assert any("INVALID_REQUEST" in e and "'transport'" in e
               for e in body["errors"])


def test_s6_empty_protocol_is_request_stage(client):
    r = client.post("/api/config-builder/preview", json={
        "protocol": "", "transport": "ws", "security": "tls",
        "node_id": "panel", "routing_policy": "ALL_VPN",
        "client_format": "xray-json"})
    body = r.json()
    assert r.status_code == 422
    assert body["stage"] == "request"
    assert any("'protocol'" in e for e in body["errors"])


def test_s6_generate_boundary_too(client):
    r = client.post("/api/config-builder/generate", json={
        "protocol": "vless", "transport": None, "security": "tls",
        "node_id": "panel", "routing_policy": "ALL_VPN",
        "client_format": "xray-json"})
    body = r.json()
    assert r.status_code == 422
    if "detail" in body:
        # pydantic rejects null at the API boundary (never reaches engines)
        assert any(d.get("loc") == ["body", "transport"] for d in body["detail"])
    else:
        assert body["stage"] == "request"
        assert any("'transport'" in e for e in body["errors"])


def test_s6_nonempty_invalid_transport_is_still_capability_stage(client):
    """A *filled but unsupported* value (legacy 'xhttp') is a capability
    verdict, NOT a request bug — the boundary must not swallow it."""
    r = client.post("/api/config-builder/preview", json={
        "protocol": "vless", "transport": "xhttp", "security": "tls",
        "node_id": "panel", "routing_policy": "ALL_VPN",
        "client_format": "xray-json"})
    body = r.json()
    assert r.status_code == 422
    assert body["stage"] == "capability"
    assert any("not supported" in e and "xhttp-packet-up" in e
               for e in body["errors"]), "error must list canonical values"


# ── §30 transport integrity across the capability surface ─────────────────

def _panel_supported_combos(client):
    # SAME source the UI renders from: the capability API (§4 — the engine is
    # the single source of truth, not a test-local reimplementation).
    doc = client.get("/api/config-builder/capabilities").json()
    combos = []
    for node in doc.get("nodes", []):
        if node.get("node_id") != "panel":
            continue
        for pr in node.get("protocols") or []:
            if pr.get("status") == "SUPPORTED":
                combos.append((pr["protocol"], pr["transport"], pr["security"]))
    return combos


def test_s30_every_supported_combo_previews_with_canonical_transport(client):
    combos = _panel_supported_combos(client)
    assert combos, "capability engine must report supported panel combos"
    seen = set()
    for proto, tr, sec in combos:
        key = (proto, tr)
        if key in seen:
            continue
        seen.add(key)
        payload = {
            "protocol": proto, "transport": tr, "security": sec,
            "node_id": "panel", "routing_policy": "ALL_VPN",
            "client_format": "xray-json"}
        if proto == "mtproto":
            # honest engine rule: mtproto needs its real secret up-front
            payload["credential"] = "dd" + "0123456789abcdef" * 2
        r = client.post("/api/config-builder/preview", json=payload)
        body = r.json()
        assert body["ok"] is True, (
            f"SUPPORTED combo {proto}/{tr}/{sec} failed: {body.get('errors')}")
        assert body["preview"]["transport"] == tr, (
            "preview must echo the exact canonical transport, "
            f"got {body['preview']['transport']!r} for {tr!r}")
    # the canonical transport names actually used by the engine
    assert {"ws", "xhttp-packet-up"} <= {t for _, t in seen}


def test_s30_transport_values_are_never_empty_in_request_model():
    """ConfigRequest defaults are canonical (never '') — an explicit empty
    string only ever comes from a broken frontend, which §6 catches."""
    import config_builder as cb
    req = cb.ConfigRequest()
    assert req.protocol and req.transport and req.security and req.node_id
    assert req.transport in ("ws", "xhttp-packet-up", "xhttp-stream-up", "tcp")


# ── §31 real config tests (validate → preview → generate) ──────────────────

def test_s31_vless_xhttp_tls_full_chain(client):
    # validate (preview — no side effects)
    p = client.post("/api/config-builder/preview", json={
        "protocol": "vless", "transport": "xhttp-packet-up", "security": "tls",
        "node_id": "panel", "routing_policy": "ALL_VPN",
        "client_format": "xray-json"}).json()
    assert p["ok"] and p["preview"]["transport"] == "xhttp-packet-up"
    assert p["outputs"]["uri"].startswith("vless://")
    # generate — live link (link-factory seam, Phase 40 §25)
    links_before = len(client.get("/api/links").json()["links"])
    g = client.post("/api/config-builder/generate", json={
        "name": "phase41-e2e", "protocol": "vless",
        "transport": "xhttp-packet-up", "security": "tls",
        "node_id": "panel", "routing_policy": "ALL_VPN",
        "client_format": "xray-json", "persist_link": True}).json()
    assert g["ok"], g.get("errors")
    assert g["link"]["created"], "panel-node generation must create a live link"
    links_after = len(client.get("/api/links").json()["links"])
    assert links_after == links_before + 1
    # the card is retestable: /api/links carries the new config (fused name
    # for vless+xhttp is legacy-bare: "xhttp-packet-up" — compat.compose)
    card = [l for l in client.get("/api/links").json()["links"]
            if l["uuid"] == g["link"]["uuid"]]
    assert card and card[0]["protocol"] == "xhttp-packet-up"


@pytest.mark.parametrize("proto,transport,security,extra", [
    ("vless", "ws", "tls", {}),
    ("vless", "xhttp-stream-up", "tls", {}),
    ("trojan", "ws", "tls", {}),
    ("trojan", "xhttp-packet-up", "tls", {}),
    ("shadowsocks", "ws", "tls", {}),
    ("mtproto", "tcp", "none", {"credential": "dd0123456789abcdef0123456789abcdef"}),
])
def test_s31_genuinely_supported_protocols(client, proto, transport, security, extra):
    body = client.post("/api/config-builder/preview", json={
        "protocol": proto, "transport": transport, "security": security,
        "node_id": "panel", "routing_policy": "ALL_VPN",
        "client_format": "xray-json", **extra}).json()
    assert body["ok"] is True, (
        f"{proto}/{transport}/{security}: {body.get('errors')}")


# ── §32 real ping contract — real latency or honest failure ────────────────

def test_s32_quick_test_real_latency(client):
    """Real socket test against a reachable public endpoint (cloudflare)."""
    r = client.post("/api/network/test/quick", json={
        "address": "cloudflare.com", "port": 443, "sni": "", "tls": True})
    d = r.json()
    if d.get("ok"):
        assert d.get("total_ms") is not None and d["total_ms"] > 0, (
            "success without a real latency is a fabricated result")
        assert d.get("stages_ms", {}).get("tcp") is not None
    else:
        assert d.get("error_code"), "failure without an honest error_code"
        assert d.get("error_detail") is not None


def test_s32_blocked_hosts_are_honestly_rejected(client):
    """SSRF posture: loopback targets never masquerade as VPN latency —
    they are rejected with an explicit error (no fake ms, no panel-ping)."""
    r = client.post("/api/network/test/quick", json={
        "address": "127.0.0.1", "port": 8000, "sni": "", "tls": False})
    d = r.json()
    assert r.status_code in (400, 422)
    assert not d.get("ok") or d.get("total_ms") is None


def test_s32_link_ping_contract(client):
    """E2E tunnel ping on a generated link: success → ms fields, failure →
    a reason string. Never ok=True with all-null measurements."""
    g = client.post("/api/config-builder/generate", json={
        "name": "phase41-ping", "protocol": "vless", "transport": "ws",
        "security": "tls", "node_id": "panel", "routing_policy": "ALL_VPN",
        "client_format": "xray-json", "persist_link": True}).json()
    assert g["ok"] and g["link"]["created"]
    uuid = g["link"]["uuid"]
    d = client.post(f"/api/links/{uuid}/ping").json()
    if d.get("ok"):
        assert (d.get("e2e_ms") is not None or d.get("ws_ms") is not None), (
            "ok=True with no measurement is fabricated")
    else:
        assert d.get("detail"), "failure must carry an honest reason"
    client.delete(f"/api/links/{uuid}")


# ── §33/§34 UI acceptance (structural — the browser gate runs separately) ──

def test_s33_frontend_boundary_guard_exists():
    src = pages.DASHBOARD_HTML
    # builderPreview/generate must refuse to send incomplete requests
    assert "bldValidateSelection()" in src
    assert "if(!bldValidateSelection())return;" in src
    # the exact Persian message demanded by §5
    assert "ابتدا نوع انتقال را انتخاب کنید" in src


def test_s33_state_machine_capability_driven():
    src = pages.DASHBOARD_HTML
    # auto-select only picks capability-SUPPORTED transports (§4/§5)
    assert "x.status==='SUPPORTED'" in src
    assert "nccAutoTransport" in src
    # node change re-syncs transport+security renders (§8 — the stale-.sel bug)
    assert "nccAutoTransport();nccRenderTransports();" in src
    # transport display labels keep canonical internal values (§4)
    assert "NCC_TR_FA" in src
    assert "'xhttp-packet-up':'XHTTP Packet-up'" in src


def test_s33_backend_boundary_message_reaches_ui():
    src = pages.DASHBOARD_HTML
    assert 'j.stage||' in src  # INVALID — مرحله: <stage> renders the boundary


def test_s34_mobile_workspace_css():
    src = pages.DASHBOARD_HTML
    # §16 sticky bottom bar: base rule BEFORE the media query (the CSS order
    # bug that kept .ws-sticky hidden on every mobile viewport is fixed by
    # having @media's display:flex come after the base display:none)
    base = src.index(".ws-sticky{display:none")
    media = src.index(".ws-sticky{display:flex}")
    assert base < media, "sticky base rule must precede its media override"
    # §16 one column on mobile
    assert 'grid-template-areas:"build" "test" "out"' in src
    # §20 compact summary always visible
    assert 'id="ws-summary"' in src and "nccSummaryUpdate" in src
    # §21 advanced settings collapsed by default
    assert 'details class="ncc-step ncc-fold" id="ncc-ep-fold"' in src
    assert 'details class="ncc-step ncc-fold" id="ncc-adv-fold"' in src
    # §22 quick test + more-tests disclosure
    assert 'id="ncc-test-extra"' in src and "nccToggleMoreTests" in src
    # §12/§13 ping failure shows a visible reason, not a bare "قطع"
    assert "RUNTIME FAILED" in src


def test_s34_no_horizontal_overflow_guard():
    src = pages.DASHBOARD_HTML
    assert ".ncc-build,.ncc-live,.ncc-out{min-width:0;max-width:100%;box-sizing:border-box}" in src
    assert "@media(max-width:400px)" in src, "320-400px viewport support"
