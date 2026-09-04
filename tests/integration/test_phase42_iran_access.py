# tests/integration/test_phase42_iran_access.py — Phase 42:
# IRAN ACCESSIBILITY & CONFIG-CONNECTIVITY — Test-D honest pinging + spoof reporting
#
# Coverage (user spec Phase 42):
#   §A  sni_spoof_active honesty: a Mode-B (direct Railway, no EMIX_CDN_DOMAIN)
#       spoof link must report ACTIVE — its URI/sub/sub-json really carry the
#       spoof (the old field required EMIX_CDN_DOMAIN and lied "inactive").
#   §B  _link_spoof_sni gating: enabled+valid → spoof; disabled/invalid → None;
#       CDN mode (EMIX_CDN_DOMAIN) → None (client path is the CDN, not this probe).
#   §C  REAL spoof-path client simulation through a REAL TLS edge: a local TLS
#       ingress (self-signed cert, accepts ANY SNI — like Railway's edge)
#       fronts the REAL app; _spoof_client_probe must complete
#       TLS(server_hostname=spoof) → WS upgrade (Host=panel host) → real VLESS
#       bytes → real HTTP reply through the tunnel. This is the exact path an
#       Xray client takes with a spoofed link.
#   §D  last_ping composition (Test-D): for spoof-enabled links the primary
#       verdict (ok/ws_ms/e2e_ms) comes from the CLIENT path (spoofed SNI),
#       the clean-path evidence is preserved under clean_path; a spoof-path
#       failure with a healthy clean path reports ok=False (no false green);
#       non-spoof links keep the legacy behavior untouched.
#   §E  honest guards: localhost panel host (no override) → honest skip note.
#   §F  UI acceptance: dashboard serves the spoof-path badge markers and the
#       emitter still produces Mode-B URIs (sni=<spoof> + allowInsecure=1).

import asyncio
import datetime
import ssl
import threading
import time

import pytest
import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

import main  # the real app — same boot path as Railway
import link_health


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_self_signed_cert():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "railway-edge.test")])
    now = datetime.datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    return key_pem, cert_pem


class _TLSEdge:
    """A REAL TLS ingress in front of the plain-HTTP app.

    Mimics the Railway edge for this test: terminates TLS, accepts ANY SNI
    (self-signed cert), and forwards the decrypted bytes to the app. The
    spoof probe must get through exactly like an Xray client with a spoofed
    link: TLS with server_hostname=<spoof> (cert ignored = allowInsecure=1)
    + HTTP Host header = the panel host.
    """

    def __init__(self, upstream_port: int):
        self.upstream_port = upstream_port
        import tempfile
        key_pem, cert_pem = _make_self_signed_cert()
        k = tempfile.NamedTemporaryFile(delete=False, suffix=".key")
        c = tempfile.NamedTemporaryFile(delete=False, suffix=".crt")
        k.write(key_pem); k.flush()
        c.write(cert_pem); c.flush()
        self._files = (k.name, c.name)
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.load_cert_chain(c.name, k.name)
        self.server = None
        self.port = None

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            upstream_reader, upstream_writer = await asyncio.open_connection(
                "127.0.0.1", self.upstream_port
            )
        except Exception:
            writer.close()
            return

        async def pump(src, dst):
            try:
                while True:
                    data = await src.read(65536)
                    if not data:
                        break
                    dst.write(data)
                    await dst.drain()
            except Exception:
                pass
            finally:
                try:
                    dst.close()
                except Exception:
                    pass

        await asyncio.gather(pump(reader, upstream_writer), pump(upstream_reader, writer))

    async def start(self):
        self.server = await asyncio.start_server(
            self._handle, "127.0.0.1", 0, ssl=self.ctx
        )
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        import os
        for f in self._files:
            try:
                os.unlink(f)
            except Exception:
                pass


@pytest.fixture(scope="module")
def client():
    """TestClient — boots the app lifespan exactly like the rest of the suite."""
    with TestClient(main.app) as c:
        r = c.post("/api/login", json={"password": "test-password"})
        assert r.status_code == 200, f"login failed: {r.status_code}"
        _before = {l["uuid"] for l in c.get("/api/links").json()["links"]}
        yield c
        for l in c.get("/api/links").json()["links"]:
            if l["uuid"] not in _before:
                c.delete(f"/api/links/{l['uuid']}")


@pytest.fixture(scope="module")
def real_server(client):
    """One REAL uvicorn server (lifespan already booted by the TestClient
    fixture — we do NOT run it twice) + one REAL TLS edge in front of it."""
    config = uvicorn.Config(main.app, host="127.0.0.1", port=0,
                            log_level="error", lifespan="off")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    app_port = None
    for _ in range(100):
        for s in getattr(server, "servers", []) or []:
            sockets = getattr(s, "sockets", None)
            if sockets:
                app_port = sockets[0].getsockname()[1]
                break
        if app_port:
            break
        time.sleep(0.1)
    assert app_port, "uvicorn did not start"

    edge_holder = {}

    def _run_edge():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        edge = _TLSEdge(app_port)
        loop.run_until_complete(edge.start())
        edge_holder["edge"] = edge
        edge_holder["loop"] = loop
        loop.run_forever()

    edge_thread = threading.Thread(target=_run_edge, daemon=True)
    edge_thread.start()
    for _ in range(50):
        if "edge" in edge_holder:
            break
        time.sleep(0.1)
    assert "edge" in edge_holder

    yield {"app_port": app_port, "tls_port": edge_holder["edge"].port}

    edge_holder["loop"].call_soon_threadsafe(edge_holder["loop"].stop)
    server.should_exit = True
    thread.join(timeout=10)
    asyncio.run(edge_holder["edge"].stop())


@pytest.fixture(scope="module")
def spoof_link(client):
    """A REAL vless-ws link with SNI spoof enabled (Mode B)."""
    r = client.post("/api/links", json={
        "label": "phase42-spoof-test",
        "protocol": "vless-ws",
        "spoof_sni": "www.snap.ir",
        "spoof_sni_enabled": True,
    })
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    uid = data.get("uuid") or data.get("id") or data.get("link", {}).get("uuid")
    assert uid, f"no uuid in response: {str(data)[:200]}"
    yield uid
    client.delete(f"/api/links/{uid}")


# ── §A sni_spoof_active honesty (the old lie: required EMIX_CDN_DOMAIN) ─────

def test_sA_spoof_active_without_cdn(client, spoof_link):
    links = {l["uuid"]: l for l in client.get("/api/links").json()["links"]}
    l = links[spoof_link]
    assert l["sni_spoof_active"] is True, (
        "Mode-B spoof (direct Railway + allowInsecure) is REAL — must report "
        f"active without EMIX_CDN_DOMAIN (got {l['sni_spoof_active']!r})")
    assert l["spoof_sni"] == "www.snap.ir"
    assert l["spoof_sni_enabled"] is True


def test_sA_clean_link_reports_inactive(client):
    r = client.post("/api/links", json={
        "label": "phase42-clean-test", "protocol": "vless-ws"})
    uid = r.json().get("uuid") or r.json().get("id")
    try:
        links = {l["uuid"]: l for l in client.get("/api/links").json()["links"]}
        assert links[uid]["sni_spoof_active"] is False
    finally:
        client.delete(f"/api/links/{uid}")


# ── §B _link_spoof_sni gating ───────────────────────────────────────────────

def test_sB_gating(monkeypatch):
    link = {"spoof_sni": "www.bale.ir", "spoof_sni_enabled": True}
    assert link_health._link_spoof_sni(link) == "www.bale.ir"
    assert link_health._link_spoof_sni({"spoof_sni": "x", "spoof_sni_enabled": True}) is None
    assert link_health._link_spoof_sni({"spoof_sni": "www.bale.ir",
                                        "spoof_sni_enabled": False}) is None
    assert link_health._link_spoof_sni({}) is None
    monkeypatch.setenv("EMIX_CDN_DOMAIN", "cdn.example.com")
    assert link_health._link_spoof_sni(link) is None, (
        "CDN mode: client path is the CDN domain — spoof probe must not run")


# ── §C REAL spoof-path client simulation through a REAL TLS edge ────────────

def test_sC_spoof_probe_full_e2e(real_server, spoof_link):
    """TLS(SNI=spoof, no verify) → WS(Host=real) → real VLESS bytes → real
    HTTP reply through the tunnel — the exact client path of a spoofed link."""
    link = main.LINKS[spoof_link]
    result = asyncio.run(link_health._spoof_client_probe(
        "vless", spoof_link, link,
        host="127.0.0.1", port=real_server["tls_port"]))
    assert result.get("ok") is True, (
        f"spoof client path must pass end-to-end through the TLS edge — got: {result}")
    assert result.get("e2e_ms") is not None and result["e2e_ms"] > 0
    assert "HTTP" in str(result.get("reply", ""))


def test_sC_spoof_probe_honest_local_skip(monkeypatch, spoof_link):
    """Localhost panel host (no override) → honest skip, never a fake ok."""
    monkeypatch.setattr(link_health, "get_host", lambda: "localhost")
    link = main.LINKS[spoof_link]
    result = asyncio.run(link_health._spoof_client_probe(
        "vless", spoof_link, link, host=None))
    assert result.get("ok") is False
    assert "لوکال" in result.get("detail", "") or "عمومی" in result.get("detail", "")


# ── §D last_ping composition (Test-D: verdict = the path the client uses) ───

def _stub(monkeypatch, clean_result, spoof_result):
    monkeypatch.setattr(link_health, "get_host", lambda: "panel.example.test")
    monkeypatch.setattr(
        link_health, "_probe_ws_tunnel",
        lambda *a, **k: asyncio.sleep(0, result=clean_result))
    monkeypatch.setattr(
        link_health, "_spoof_client_probe",
        lambda *a, **k: asyncio.sleep(0, result=spoof_result))


def test_sD_composition_spoof_is_primary(monkeypatch, spoof_link):
    _stub(monkeypatch,
          {"ok": True, "ws_ms": 5.0, "e2e_ms": 7.0, "reply": "HTTP/1.1 204"},
          {"ok": True, "ws_ms": 9.0, "e2e_ms": 12.0, "reply": "HTTP/1.1 204"})
    link = dict(main.LINKS[spoof_link])
    result = asyncio.run(link_health._run_link_ping(spoof_link, link))
    assert result["client_path"] == "spoofed-sni"
    assert result["spoof_sni"] == "www.snap.ir"
    assert result["allowInsecure"] == 1
    assert result["ok"] is True
    assert result["e2e_ms"] == 12.0, "primary metric = CLIENT path (spoofed SNI)"
    assert result["clean_path"]["e2e_ms"] == 7.0
    assert result["clean_path"]["ok"] is True


def test_sD_spoof_failure_is_not_false_green(monkeypatch, spoof_link):
    """Clean path healthy + spoof path dead → ok MUST be False (Test-D)."""
    _stub(monkeypatch,
          {"ok": True, "ws_ms": 5.0, "e2e_ms": 7.0, "reply": "HTTP/1.1 204"},
          {"ok": False, "ws_ms": None, "e2e_ms": None,
           "detail": "TLS(SNI جعلی): timeout"})
    link = dict(main.LINKS[spoof_link])
    result = asyncio.run(link_health._run_link_ping(spoof_link, link))
    assert result["ok"] is False, "a dead client path must never be a green ping"
    assert result["clean_path"]["ok"] is True, "clean-path evidence preserved"
    assert "SNI جعلی" in result["detail"]


def test_sD_non_spoof_link_unchanged(monkeypatch, client):
    """Legacy behavior for clean links: no client_path/clean_path keys."""
    _stub(monkeypatch,
          {"ok": True, "ws_ms": 5.0, "e2e_ms": 7.0, "reply": "HTTP/1.1 204"},
          {"ok": True, "ws_ms": 9.0, "e2e_ms": 12.0, "reply": "HTTP/1.1 204"})
    r = client.post("/api/links", json={"label": "p42-nospoof", "protocol": "vless-ws"})
    uid = r.json().get("uuid") or r.json().get("id")
    try:
        link = dict(main.LINKS[uid])
        result = asyncio.run(link_health._run_link_ping(uid, link))
        assert "client_path" not in result
        assert "clean_path" not in result
        assert result["ok"] is True
    finally:
        client.delete(f"/api/links/{uid}")


# ── §F UI acceptance + emitter regression ────────────────────────────────────

def test_sF_dashboard_serves_spoof_path_markers():
    html = main.DASHBOARD_HTML
    for needle in ("spoofed-sni", "SNI جعلی", "clean_path"):
        assert needle in html, f"dashboard must serve the {needle!r} marker"


def test_sF_emitter_still_carries_spoof(spoof_link):
    """The share link itself keeps Mode B: sni=<spoof> + allowInsecure=1."""
    uri = main.generate_share_link(spoof_link, main.get_host(),
                                   remark="test", protocol="vless-ws")
    assert uri.startswith("vless://")
    assert "sni=www.snap.ir" in uri
    assert "allowInsecure=1" in uri
