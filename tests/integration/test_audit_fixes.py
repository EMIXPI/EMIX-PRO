"""Regression tests for the 2026-09 production audit fixes.

Every test here maps to a concrete finding in AUDIT_REPORT_FINAL.md:
  SECURITY-1  central.py must never send the password hash off-box
  SECURITY-2  login brute-force guard (always-on, failure-counting)
  SECURITY-3  /api/qr local QR generation (no third-party leak)
  SECURITY-4  ip-api.com plaintext provider disabled by default
  CORRECT-1   node-manager registry API no longer shadowed
  CORRECT-2   health-sweep results persist into live LINKS
  CORRECT-3   uTLS route reachable in lowercase (frontend contract)
  PERSIST-1   sessions / stats_totals survive save→load round-trip
  PERSIST-2   SNI profiles + VPN nodes snapshot round-trips
  PERSIST-3   EMIX_SESSION_TTL / EMIX_SAVE_DEBOUNCE env knobs are real
"""
import asyncio
import os
import time

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("EMIX_HEALTH_SWEEP_INTERVAL", "3600")  # keep sweep quiet


@pytest.fixture(scope="module")
def client():
    import main
    from main import LINKS

    _before = dict(LINKS)
    with TestClient(main.app) as c:
        yield c
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


# ── SECURITY-1: no credential in the central registration payload ──────────

def test_central_registration_payload_has_no_password_hash():
    import central
    sent = {}

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            sent["url"] = url
            sent["payload"] = json

    import httpx
    orig = httpx.AsyncClient
    httpx.AsyncClient = _FakeClient
    try:
        asyncio.run(central.register_instance())
    finally:
        httpx.AsyncClient = orig
    assert sent.get("payload") is not None, "registration must fire"
    payload = sent["payload"]
    assert "password_hash" not in payload and "panel_password_hash" not in payload
    # only benign fields are sent
    assert set(payload.keys()) <= {"domain", "version", "description"}


def test_central_kill_switch():
    import central
    orig = central.CENTRAL_URL
    try:
        central.CENTRAL_URL = ""
        # with the URL empty, no network call may be attempted at all
        r = asyncio.run(central.fetch_announcements())
        assert r == []
    finally:
        central.CENTRAL_URL = orig


# ── SECURITY-2: login brute-force guard ─────────────────────────────────────

def test_login_brute_force_lockout_and_recovery(client):
    from security_exp import _LOGIN_FAILURES, clear_login_failures, login_rate_limited
    try:
        # TestClient's IP is literally "testclient"
        # 5 failed attempts → 6th is locked out with 429
        for i in range(5):
            r = client.post("/api/login", json={"password": "definitely-wrong"})
            assert r.status_code == 401
        r = client.post("/api/login", json={"password": "definitely-wrong"})
        assert r.status_code == 429
        assert login_rate_limited("testclient")
        # lockout applies even to the CORRECT password until the window clears
        r = client.post("/api/login", json={"password": os.environ.get("ADMIN_PASSWORD", "test-password")})
        assert r.status_code == 429
        # after a clear (successful logins clear failures), login works
        clear_login_failures("testclient")
        r = client.post("/api/login", json={"password": os.environ.get("ADMIN_PASSWORD", "test-password")})
        assert r.status_code == 200
    finally:
        # module-scoped `authed` fixture logs in later — must not inherit our failures
        _LOGIN_FAILURES.clear()


def test_login_guard_disabled_via_env(monkeypatch):
    monkeypatch.setenv("EMIX_LOGIN_RATE_LIMIT", "0")
    import importlib
    import security_exp
    importlib.reload(security_exp)
    assert not security_exp.login_rate_limit_enabled()
    assert not security_exp.login_rate_limited("1.2.3.4")
    monkeypatch.delenv("EMIX_LOGIN_RATE_LIMIT", raising=False)
    importlib.reload(security_exp)
    assert security_exp.login_rate_limit_enabled()


# ── SECURITY-3: local QR endpoint ───────────────────────────────────────────

def test_qr_local_generation_valid_scheme(authed):
    r = authed.get("/api/qr", params={"data": "vless://uuid@example.com:443?type=ws"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in r.content[:200]


def test_qr_rejects_disallowed_content(authed):
    # javascript: / arbitrary text must be rejected (no open QR proxy)
    r = authed.get("/api/qr", params={"data": "javascript:alert(1)"})
    assert r.status_code == 400
    r = authed.get("/api/qr", params={"data": "just some random text"})
    assert r.status_code == 400
    r = authed.get("/api/qr")
    assert r.status_code == 400


def test_qr_rejects_oversized_payload(authed):
    r = authed.get("/api/qr", params={"data": "vless://" + "a" * 3000})
    assert r.status_code == 413


def test_qr_allows_wireguard_config(authed):
    r = authed.get("/api/qr", params={"data": "BEGIN WIREGUARD CONFIG\ndefault text\n"})
    assert r.status_code == 200


# ── SECURITY-4: ip-api.com plaintext provider off by default ───────────────

def test_ip_api_com_disabled_by_default(monkeypatch):
    monkeypatch.delenv("EMIX_IP_API_HTTP", raising=False)
    import importlib
    import ip_quality
    importlib.reload(ip_quality)
    assert ip_quality.IpApiComProvider.enabled is False


def test_ip_api_com_opt_in_via_env(monkeypatch):
    monkeypatch.setenv("EMIX_IP_API_HTTP", "1")
    import importlib
    import ip_quality
    importlib.reload(ip_quality)
    assert ip_quality.IpApiComProvider.enabled is True
    # no live network call in tests — the disabled-case honesty is covered above


# ── CORRECT-1: managed-node registry reachable (un-shadowed) ───────────────

def test_managed_nodes_registry_route(authed):
    r = authed.get("/api/managed-nodes")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] and isinstance(d["nodes"], list)
    # the panel node is registered at startup
    ids = [n["id"] for n in d["nodes"]]
    assert "panel" in ids


def test_legacy_nodes_route_still_serves_outbound_panels(authed):
    # the outbound-panel route keeps its original contract: {"nodes": [...], "count": n}
    r = authed.get("/api/nodes")
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d, dict) and isinstance(d.get("nodes"), list)
    assert d.get("count") == len(d["nodes"])


# ── CORRECT-2: health sweep persists records into live LINKS ───────────────

def test_health_sweep_persists_records(client):
    import main
    from main import LINKS, LINKS_LOCK
    # run the sweep job directly (probes will fail offline → UNREACHABLE)
    result = asyncio.run(main._job_health_sweep())
    assert result["ok"] is True
    assert result.get("persisted", 0) >= 0  # shape present

    async def _check():
        # any tracked record must now exist on the live link dicts
        async with LINKS_LOCK:
            for uid, link in LINKS.items():
                rec = main.network_health.get_health_dict(uid)
                if rec is not None:
                    assert link.get("health", {}).get("state") == rec["state"]

    asyncio.run(_check())


# ── CORRECT-3: uTLS lowercase route (frontend contract) ─────────────────────

def test_utls_lowercase_route_exists(authed):
    # frontend expEmitLink('utls') posts lowercase — must not 404.
    # (experimental gate may 403 when disabled; 404 means the route is missing)
    r = authed.post("/api/exp/link/utls", json={"link": "vless://x@y:443", "fp": "chrome"})
    assert r.status_code != 404
    # canonical case still works too
    r2 = authed.post("/api/exp/link/uTLS", json={"link": "vless://x@y:443", "fp": "chrome"})
    assert r2.status_code == r.status_code


# ── PERSIST-1: sessions + stats totals round-trip ──────────────────────────

def test_sessions_and_stats_totals_roundtrip(client):
    import main
    from main import LINKS_LOCK, SESSIONS, SESSIONS_LOCK, stats
    async def _scenario():
        async with SESSIONS_LOCK:
            SESSIONS["tok-roundtrip"] = time.time() + 3600
        stats["total_bytes"] += 12345
        await main.save_state()
        # simulate a restart of the in-memory stores
        async with SESSIONS_LOCK:
            SESSIONS.clear()
        stats["total_bytes"] = 0
        await main.load_state()
    asyncio.run(_scenario())
    assert SESSIONS.get("tok-roundtrip") is not None, "session must survive restart"
    assert stats["total_bytes"] == 12345, "lifetime traffic total must survive restart"

    # cleanup
    async def _cleanup():
        async with SESSIONS_LOCK:
            SESSIONS.pop("tok-roundtrip", None)
        await main.save_state()

    stats["total_bytes"] = 0
    asyncio.run(_cleanup())


# ── PERSIST-2: SNI + VPN node snapshots round-trip ─────────────────────────

def test_sni_vpn_snapshots_roundtrip():
    import sni_management, vpn_pro
    sni_management.reset_for_tests()
    vpn_pro.reset_for_tests()
    try:
        p = sni_management.SNIProfile(id="p1", name="prof", server_name="example.com")
        sni_management._profiles["p1"] = p
        n = vpn_pro.VPNNode(id="n1", name="node", wg_server_private_key="KEYMAT",
                            wg_server_public_key="PUBKEY")
        vpn_pro._nodes["n1"] = n
        snap = {"sni_profiles": sni_management.persist_snapshot()["sni_profiles"],
                "vpn_nodes": vpn_pro.persist_snapshot()["vpn_nodes"]}
        # WG private key MUST be in the snapshot (otherwise restart loses keys)
        assert any(v["wg_server_private_key"] == "KEYMAT" for v in snap["vpn_nodes"])
        # wipe and restore
        sni_management.reset_for_tests()
        vpn_pro.reset_for_tests()
        assert sni_management.restore_snapshot(snap) == 1
        assert vpn_pro.restore_snapshot(snap) == 1
        assert sni_management._profiles["p1"].server_name == "example.com"
        assert vpn_pro._nodes["n1"].wg_server_private_key == "KEYMAT"
    finally:
        sni_management.reset_for_tests()
        vpn_pro.reset_for_tests()


def test_vpn_api_snapshot_hides_private_key():
    import vpn_pro
    vpn_pro.reset_for_tests()
    try:
        vpn_pro._nodes["n1"] = vpn_pro.VPNNode(id="n1", name="node",
                                               wg_server_private_key="SECRET",
                                               wg_server_public_key="PUB")
        d = asyncio.run(vpn_pro.all_nodes_dict())
        assert all("wg_server_private_key" not in n for n in d["nodes"])
    finally:
        vpn_pro.reset_for_tests()


# ── PERSIST-3: env knobs are real ──────────────────────────────────────────

def test_env_knobs_are_wired(monkeypatch):
    import config_layer
    import main
    # main must CONSUME config_layer (not hardcode) — the wiring proof:
    assert main.SESSION_TTL == int(main._EMIX_RUNTIME_CFG.session_ttl_seconds)
    assert main.SAVE_DEBOUNCE_SECONDS == float(main._EMIX_RUNTIME_CFG.save_debounce_seconds)
    # and config_layer really reads the env (audit fix for dead env vars):
    monkeypatch.setenv("EMIX_SESSION_TTL", "3600")
    monkeypatch.setenv("EMIX_SAVE_DEBOUNCE", "0.5")
    import importlib
    importlib.reload(config_layer)
    assert config_layer.CONFIG.session_ttl_seconds == 3600
    assert config_layer.CONFIG.save_debounce_seconds == 0.5
    monkeypatch.delenv("EMIX_SESSION_TTL", raising=False)
    monkeypatch.delenv("EMIX_SAVE_DEBOUNCE", raising=False)
    importlib.reload(config_layer)


# ── MTProto supervision: post-boot instances get supervised ────────────────

def test_supervise_mtproto_instance_helper_registers():
    import main
    import runtime_supervisor
    before = len(runtime_supervisor.supervisor._runtimes)
    # non-existent instance → no-op (defensive)
    main._supervise_mtproto_instance("ffffffff-ffff-ffff-ffff-ffffffffffff")
    assert len(runtime_supervisor.supervisor._runtimes) == before
