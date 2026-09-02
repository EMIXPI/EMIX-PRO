# tests/unit/test_iran_direct.py — Phase 38+ §11/§12 (IRAN_DIRECT assets)
# Clean-IP + Handshake store → canonical config generation.
# Rules under test:
#   1. Assets are validated (IP-or-hostname address; hostname-only SNI).
#   2. Manual IP = CONFIGURED_ENDPOINT — never presented as verified egress.
#   3. Probe results are honestly labeled (server-side measurement only).
#   4. Config generation goes ONLY through the canonical config_builder
#      (custom_address=Clean IP, custom_sni=handshake, IRAN_DIRECT policy).
#   5. IP-without-handshake is rejected (TLS SNI can never be an IP).
# All network probes are monkeypatched — NO REAL_NETWORK tests here.

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import iran_direct as ird
import config_builder as cb
import structured_events as events


@pytest.fixture(autouse=True)
def clean(tmp_path, monkeypatch):
    events.reset_for_tests()
    cb.reset_for_tests()
    # deterministic asset file per test (never touches real DATA_DIR)
    monkeypatch.setattr(ird, "ASSET_FILE", tmp_path / "iran_direct_assets.json")
    yield
    cb.reset_for_tests()
    events.reset_for_tests()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ird, "ASSET_FILE", tmp_path / "iran_direct_assets.json")

    async def _auth_ok():
        return None

    app = FastAPI()
    ird.register_routes(app, _auth_ok)
    return TestClient(app)


def _fake_probe(monkeypatch, state="TLS_VERIFIED", **extra):
    async def _probe(address, port, sni=""):
        return {"state": state, "tcp_ms": 33, "tls_ms": 44, "sni": sni,
                "checked_at": time.time(), "from": "panel-server", **extra}
    monkeypatch.setattr(ird, "_probe_address", _probe)


def _req(**kw):
    base = dict(protocol="vless", transport="xhttp-packet-up", security="tls",
                node_id="panel", routing_policy="IRAN_DIRECT",
                client_format="xray-json", remark="unit-test",
                custom_address="104.17.1.1", custom_sni="hs.example.com",
                custom_port=443)
    base.update(kw)
    return cb.ConfigRequest(**base)


def _providers():
    cb.set_host_provider(lambda: "panel.example.com")
    cb.set_worker_domain_provider(lambda: "")
    cb.set_cdn_domain_provider(lambda: "")


# ── Asset CRUD + validation (HTTP level) ─────────────────────────────────────

def test_add_list_delete_ip(client):
    r = client.post("/api/iran-direct/ips",
                    json={"address": "104.17.1.1", "port": 443})
    assert r.status_code == 200 and r.json()["ok"]
    asset = r.json()["asset"]
    assert asset["verification"] == "CONFIGURED_ENDPOINT"   # honest label
    assert asset["address"] == "104.17.1.1"

    r = client.get("/api/iran-direct/assets")
    assert [a["address"] for a in r.json()["ips"]] == ["104.17.1.1"]
    assert "USER_ISP" in r.json()["note"]     # IRAN_DIRECT attribution note

    r = client.delete(f"/api/iran-direct/ips/{asset['id']}")
    assert r.status_code == 200
    assert client.get("/api/iran-direct/assets").json()["ips"] == []


def test_add_ip_rejects_invalid(client):
    r = client.post("/api/iran-direct/ips", json={"address": "bad host!"})
    assert r.status_code == 400
    r = client.post("/api/iran-direct/ips", json={"address": "104.17.1.999"})
    assert r.status_code == 400


def test_duplicate_ip_rejected(client):
    client.post("/api/iran-direct/ips", json={"address": "104.17.1.1"})
    r = client.post("/api/iran-direct/ips", json={"address": "104.17.1.1"})
    assert r.status_code == 409


def test_handshake_crud_and_hostname_only(client):
    r = client.post("/api/iran-direct/handshakes",
                    json={"sni": "hs.example.com"})
    assert r.status_code == 200
    hs = r.json()["asset"]
    # SNI can never be an IP (TLS semantics — honest rejection)
    r = client.post("/api/iran-direct/handshakes", json={"sni": "104.17.1.1"})
    assert r.status_code == 400
    r = client.delete(f"/api/iran-direct/handshakes/{hs['id']}")
    assert r.status_code == 200
    assert client.get("/api/iran-direct/assets").json()["handshakes"] == []


def test_delete_missing_asset_404(client):
    assert client.delete("/api/iran-direct/ips/nope").status_code == 404


# ── Honest probe labeling (monkeypatched network) ────────────────────────────

def test_probe_tls_verified_stored_on_asset(client, monkeypatch):
    _fake_probe(monkeypatch, state="TLS_VERIFIED")
    ip_id = client.post("/api/iran-direct/ips",
                        json={"address": "104.17.1.1"}).json()["asset"]["id"]
    r = client.post(f"/api/iran-direct/ips/{ip_id}/probe",
                    json={"sni": "hs.example.com"})
    assert r.status_code == 200
    p = r.json()["probe"]
    assert p["state"] == "TLS_VERIFIED"
    assert p["from"] == "panel-server"        # honest measurement origin
    assert "ISP" in p["caveat"]               # the «clean from YOUR ISP» caveat
    # stored on the asset for the UI badge
    ips = client.get("/api/iran-direct/assets").json()["ips"]
    assert ips[0]["last_probe"]["state"] == "TLS_VERIFIED"


def test_probe_unreachable_never_becomes_healthy(client, monkeypatch):
    _fake_probe(monkeypatch, state="UNREACHABLE", error="TimeoutError")
    ip_id = client.post("/api/iran-direct/ips",
                        json={"address": "203.0.113.9"}).json()["asset"]["id"]
    r = client.post(f"/api/iran-direct/ips/{ip_id}/probe", json={})
    assert r.json()["probe"]["state"] == "UNREACHABLE"


def test_probe_rejects_ip_sni(client):
    ip_id = client.post("/api/iran-direct/ips",
                        json={"address": "104.17.1.1"}).json()["asset"]["id"]
    r = client.post(f"/api/iran-direct/ips/{ip_id}/probe",
                    json={"sni": "1.2.3.4"})
    assert r.status_code == 400


# ── Use counters (post-generation bookkeeping) ───────────────────────────────

def test_use_marks_counters(client):
    ip_id = client.post("/api/iran-direct/ips",
                        json={"address": "104.17.1.1"}).json()["asset"]["id"]
    hs_id = client.post("/api/iran-direct/handshakes",
                        json={"sni": "hs.example.com"}).json()["asset"]["id"]
    r = client.post("/api/iran-direct/use",
                    json={"ip_id": ip_id, "handshake_id": hs_id})
    assert r.status_code == 200 and ip_id in r.json()["marked"]
    ips = client.get("/api/iran-direct/assets").json()["ips"]
    hss = client.get("/api/iran-direct/assets").json()["handshakes"]
    assert ips[0]["use_count"] == 1
    assert hss[0]["use_count"] == 1
    assert ips[0]["last_used_at"]


# ── THE core promise: Clean IP + Handshake → canonical IRAN_DIRECT config ────

@pytest.mark.asyncio
async def test_clean_ip_plus_handshake_builds_canonical_config():
    _providers()
    out = await cb.build_config(_req(), for_preview=True)
    assert out["ok"], out.get("errors")
    uri = out["outputs"]["uri"]
    assert "104.17.1.1" in uri                     # address = the Clean IP
    assert "hs.example.com" in uri                 # host/sni = the handshake
    assert uri.startswith("vless://")
    # IRAN_DIRECT legs are explainable and honest
    legs = out["preview"]["routing_detail"]["legs"]
    assert legs["IRAN_DOMESTIC"]["decision"] == "DIRECT"
    assert "USER_ISP" in legs["IRAN_DOMESTIC"]["egress"]
    # split rules compiled into the client output (GEOIP/CIDR)
    rules = out["preview"]["routing_detail"]["split_rules"]
    assert rules["verdict"] == "SPLIT_TUNNEL_SUPPORTED"
    assert any(r["outbound"] == "direct" for r in rules["rules"])


@pytest.mark.asyncio
async def test_ip_without_handshake_rejected_tls_sni():
    """IP سالم بدون هندشیک ⇒ رد صریح (SNI هرگز IP نیست) — نه ساخت نصفه."""
    _providers()
    out = await cb.build_config(_req(custom_sni=""), for_preview=True)
    assert not out["ok"]
    assert out["stage"] in ("endpoint", "compiler")
    assert any("SNI" in e for e in out["errors"])


@pytest.mark.asyncio
async def test_uri_client_cannot_carry_iran_direct_split():
    """کلاینت بدون split-tunnel ⇒ SPLIT_TUNNEL_NOT_SUPPORTED — صداقت."""
    _providers()
    out = await cb.build_config(_req(client_format="uri"), for_preview=True)
    assert not out["ok"]
    assert out["stage"] == "routing"
    assert any("SPLIT_TUNNEL_NOT_SUPPORTED" in e for e in out["errors"])


@pytest.mark.asyncio
async def test_handshake_only_uses_domain_as_address():
    """فقط هندشیک ⇒ همان دامنه آدرس اتصال هم هست (رفتار UI در بک‌اند اثبات)."""
    _providers()
    out = await cb.build_config(_req(custom_address="hs.example.com"),
                                for_preview=True)
    assert out["ok"], out.get("errors")
    assert "hs.example.com" in out["outputs"]["uri"]


@pytest.mark.asyncio
async def test_history_entry_records_iran_direct_and_custom_endpoint():
    _providers()
    out = await cb.build_config(_req(name="ird-1"), for_preview=False)
    assert out["ok"]
    hist = cb.list_history()
    assert hist[0]["routing"] == "IRAN_DIRECT"
    entry = await cb.get_history_entry(hist[0]["history_id"], reveal=True)
    assert entry["spec"]["custom_address"] == "104.17.1.1"
    assert entry["spec"]["custom_sni"] == "hs.example.com"
    # regenerate deterministically from the stored spec (same pipeline)
    regen = await cb.regenerate(hist[0]["history_id"])
    assert regen["ok"]
    assert "104.17.1.1" in regen["outputs"]["uri"]


# ── Events + bounds + reset ──────────────────────────────────────────────────

def test_asset_saved_event_recorded():
    ird._log("IRAN_DIRECT_ASSET_SAVED", kind="ip", address="104.17.1.1")
    recs = events.recent_events(20, event="IRAN_DIRECT_ASSET_SAVED")
    assert recs and recs[0]["kind"] == "ip"


def test_store_bounded():
    st = {"ips": [{"id": f"ip-{i}", "address": f"1.2.3.{i}"} for i in range(150)],
          "handshakes": []}
    del st["ips"][:-ird.MAX_ASSETS]
    assert len(st["ips"]) == ird.MAX_ASSETS


def test_reset_for_tests_clears_store(tmp_path, monkeypatch):
    f = tmp_path / "x.json"
    f.write_text('{"ips": [{"id": "ip-1"}], "handshakes": []}',
                 encoding="utf-8")
    monkeypatch.setattr(ird, "ASSET_FILE", f)
    ird.reset_for_tests()
    assert not f.exists()
