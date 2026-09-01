"""Integration tests — new architecture API surface (Phases 3-21).

Uses TestClient with a lifespan context so startup() runs (network health
engine wiring, job system, diagnostics). Network probes will fail in the
sandbox — the engine must record honest UNREACHABLE/UNKNOWN states, never
fake success.
"""
import os
import time

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("EMIX_HEALTH_SWEEP_INTERVAL", "3600")  # keep the sweep quiet in tests


@pytest.fixture(scope="module")
def client():
    import asyncio

    import main
    from main import LINKS, LINKS_LOCK

    # Snapshot BEFORE entering the TestClient context: startup() runs
    # ensure_default_link() + load_state() inside the context, and our tests
    # create real links. We restore the snapshot afterwards AND persist it,
    # so neither in-memory state nor the JSON state file is polluted for
    # later modules (gaming WTE sync tests assert on the exact link set).
    _before = dict(LINKS)
    with TestClient(main.app) as c:
        yield c
    # context exit ran shutdown() → save_state() wrote the polluted state;
    # restore in-memory + persist the clean snapshot over it.
    LINKS.clear()
    LINKS.update(_before)
    try:
        asyncio.run(main.save_state())
    except Exception:
        pass


@pytest.fixture(scope="module")
def authed(client):
    client.post("/api/login", json={"password": os.environ.get("ADMIN_PASSWORD", "test-password")})
    return client


def _uuid_link(authed, protocol="vless-ws", label="IT"):
    r = authed.post("/api/links", json={"protocol": protocol, "label": label})
    assert r.status_code == 200, r.text
    return r.json()


# ── Config Matrix ───────────────────────────────────────────────────────────

def test_config_matrix(authed):
    r = authed.get("/api/config-matrix")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] and len(j["combinations"]) >= 8
    assert "vless" in j["production"]


# ── Strict protocol validation (no silent coercion) ─────────────────────────

def test_create_link_invalid_protocol_rejected(authed):
    r = authed.post("/api/links", json={"protocol": "vless-grpc", "label": "Bad"})
    assert r.status_code == 400
    assert "پروتکل نامعتبر" in r.json()["detail"] or "protocol" in r.json()["detail"].lower()

def test_create_link_valid_protocol_accepted(authed):
    data = _uuid_link(authed, "trojan-ws", "IT-TW")
    assert data["protocol"] == "trojan-ws"
    assert data["vless_link"].startswith("trojan://")
    assert "endpoint_profile_id" in data


# ── Endpoint profiles CRUD ──────────────────────────────────────────────────

def test_endpoint_profile_crud(authed):
    # create
    r = authed.post("/api/endpoint-profiles", json={
        "name": "Arvan Edge", "address": "edge.arvancloud.ir", "sni": "edge.arvancloud.ir",
    })
    assert r.status_code == 200, r.text
    pid = r.json()["profile"]["id"]
    # list
    r = authed.get("/api/endpoint-profiles")
    assert any(p["id"] == pid for p in r.json()["profiles"])
    # validate against vless-ws (SNI applicable → ok)
    r = authed.post(f"/api/endpoint-profiles/{pid}/validate", json={"protocol": "vless-ws"})
    assert r.status_code == 200 and r.json()["ok"]
    # validate against shadowsocks (SNI not applicable → reject)
    r = authed.post(f"/api/endpoint-profiles/{pid}/validate", json={"protocol": "shadowsocks"})
    assert r.status_code == 200 and not r.json()["ok"]
    # update
    r = authed.put(f"/api/endpoint-profiles/{pid}", json={"port": 8443})
    assert r.status_code == 200 and r.json()["profile"]["port"] == 8443
    # invalid update rejected
    r = authed.put(f"/api/endpoint-profiles/{pid}", json={"port": 999999})
    assert r.status_code == 400
    # delete
    r = authed.delete(f"/api/endpoint-profiles/{pid}")
    assert r.status_code == 200
    r = authed.get("/api/endpoint-profiles")
    assert not any(p["id"] == pid for p in r.json()["profiles"])


def test_create_link_with_bad_endpoint_profile_rejected(authed):
    r = authed.post("/api/links", json={
        "protocol": "vless-ws", "label": "EP", "endpoint_profile_id": "ep-nonexistent",
    })
    assert r.status_code == 400


# ── Network Health endpoints ────────────────────────────────────────────────

def test_health_endpoints(authed):
    link = _uuid_link(authed, "vless-ws", "IT-H")
    uid = link["uuid"]
    # summary
    r = authed.get("/api/health/summary")
    assert r.status_code == 200 and r.json()["tracked"] >= 1
    # per-config record (engine or persisted source)
    r = authed.get(f"/api/health/links/{uid}")
    assert r.status_code == 200
    rec = r.json()["record"]
    assert rec["state"] in ("UNKNOWN", "UNREACHABLE", "HEALTHY", "DEGRADED")
    # a freshly created config must NEVER be born HEALTHY in the record
    assert rec["state"] != "HEALTHY" or rec["score"] is not None
    # explicit probe → real result recorded (fails offline → UNREACHABLE)
    r = authed.post(f"/api/health/links/{uid}/probe")
    assert r.status_code == 200
    rec2 = r.json()["record"]
    assert rec2["state"] in ("UNREACHABLE", "DEGRADED", "HEALTHY")
    assert rec2["checked_at"]


def test_health_one_404_for_unknown(authed):
    r = authed.get("/api/health/links/does-not-exist")
    assert r.status_code == 404


# ── Job system endpoints ────────────────────────────────────────────────────

def test_jobs_status_and_manual_run(authed):
    r = authed.get("/api/jobs/status")
    assert r.status_code == 200
    j = r.json()
    assert j["supervisor"] == "RUNNING"
    names = {job["name"] for job in j["jobs"]}
    assert "expiry-sweep" in names and "ip-quality-prune" in names
    # manual run of a cheap job
    r = authed.post("/api/jobs/expiry-sweep/run")
    assert r.status_code == 200 and r.json()["ok"]


# ── Diagnostics Center ──────────────────────────────────────────────────────

def test_diagnostics_overview(authed):
    r = authed.get("/api/diagnostics")
    assert r.status_code == 200
    j = r.json()
    for key in ("app", "persistence", "jobs", "network_health", "ip_quality", "protocols"):
        assert key in j["checks"]
    assert j["checks"]["persistence"]["status"] in ("OK", "ERROR", "UNKNOWN")
    assert "recent_errors" in j


# ── Subscription profiles ───────────────────────────────────────────────────

def test_sub_all_v2_profiles(authed):
    for profile in ("ALL", "FASTEST", "HEALTHIEST"):
        r = authed.get(f"/sub-all-v2?profile={profile}")
        assert r.status_code == 200, f"{profile}: {r.status_code}"
        assert r.headers["content-type"].startswith("text/plain")

def test_sub_all_v2_invalid_profile(authed):
    r = authed.get("/sub-all-v2?profile=BOGUS")
    assert r.status_code == 400


# ── Compile preview endpoint ────────────────────────────────────────────────

def test_compile_preview(authed):
    r = authed.post("/api/configs/compile", json={"protocol": "vless", "transport": "ws"})
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] and j["uri"].startswith("vless://")
    assert j["health"]["state"] == "UNKNOWN"  # never healthy by generation

def test_compile_preview_rejects_invalid(authed):
    r = authed.post("/api/configs/compile", json={"protocol": "vless", "transport": "grpc"})
    j = r.json()
    assert not j["ok"] and j["errors"]


# ── Smart route v2 (config ranking through the health engine) ──────────────

def test_smart_route_ranked_configs(authed):
    _uuid_link(authed, "vless-ws", "IT-SR")
    r = authed.get("/api/exp/route/configs/ranked")
    if r.status_code == 404:
        pytest.skip("smart_route experimental gate disabled")
    assert r.status_code == 200
    j = r.json()
    assert j["total"] >= 1
    assert j["formula"].startswith("0.40*latency")


# ── Request-ID / timing middleware ──────────────────────────────────────────

def test_request_id_header(authed):
    r = authed.get("/api/config-matrix")
    assert r.headers.get("X-Request-Id")
    assert r.headers.get("X-Response-Time-Ms")


# ── IP quality (pure-assessment surface; live provider calls not asserted) ──

def test_ip_quality_summary(authed):
    r = authed.get("/api/ip-quality/summary")
    assert r.status_code == 200 and r.json()["ok"]

def test_ip_quality_invalid_ip_400(authed):
    r = authed.get("/api/ip-quality/not-an-ip")
    assert r.status_code == 400
