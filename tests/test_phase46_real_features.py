"""Phase 46 — pytest suite for EMIX-PRO v13.2 (user-ordered real features).

Coverage:
  §A  emitter shapes: turbo (ed=2048 on path), SNI-spoof Mode B
      (sni=<spoof> + allowInsecure=1 + host=real), clean = base-identical,
      SS/MTProto unaffected (honesty).
  §B  PATCH: turbo single-slot (one config at a time — user order), spoof
      validation (reject garbage/IP, normalize), protocol gates.
  §C  REAL 0-RTT early-data E2E: a real WS client sends the protocol payload
      INSIDE the handshake (Sec-WebSocket-Protocol, base64url — exactly like
      xray ed=2048) against the real running server → real HTTP reply through
      the tunnel proves the server-side early-data path works.
  §D  REAL spoof client-path probe through a REAL TLS edge (any-SNI self-signed
      ingress in front of the app) — TLS(SNI=spoof) → WS(Host=real) → real
      VLESS bytes → real HTTP through the tunnel. Plus composition rules
      (spoof = primary verdict; clean-path evidence preserved; no false green).
  §E  turbo A/B endpoint: real measured normal vs 0-RTT runs.
  §F  login page: faint 123456 placeholder inside the password field, hint
      box + fillDefault gone (user order), theme/colors preserved.
  §G  fresh-UI: Cache-Control no-store on HTML responses.
  §H  version pin 13.3.0-emix-pro + feature list.

Run:  python -m pytest tests/ -q
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ─────────────────────────────────────────────────────────────────────────────
# fixtures — subprocess server (real boot path, isolated state)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def server(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("emix46_data")
    port = _free_port()
    env = dict(os.environ)
    env.update({
        "PORT": str(port),
        "DATA_DIR": str(data_dir),
        "ADMIN_PASSWORD": "123456",
        "PYTHONPATH": str(REPO),
    })
    env.pop("RAILWAY_PUBLIC_DOMAIN", None)
    proc = subprocess.Popen(
        [sys.executable, "main.py"], cwd=REPO, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 60
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("server died during boot")
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=2) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.4)
    else:
        proc.kill()
        raise RuntimeError("server did not come up")
    yield {"base": base, "port": port}
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()


@pytest.fixture(scope="session")
def session(server):
    import http.cookiejar
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(
        f"{server['base']}/api/login", data=json.dumps({"password": "123456"}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with op.open(req, timeout=10) as r:
        assert r.status == 200
    return op


def api(op, base, path, method="GET", body=None, timeout=120):
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"}, method=method)
    try:
        with op.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        # خطاهای 4xx/5xx هم (status, body) برگردند — نه exception
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


# ─────────────────────────────────────────────────────────────────────────────
# §A — emitter shapes (no server; direct function calls)
# ─────────────────────────────────────────────────────────────────────────────
UID = "01234567-89ab-cdef-0123-456789abcdef"


class TestEmitterShapes:
    def test_clean_link_identical_to_base(self):
        import main as m
        m.LINKS[UID] = {"label": "t", "alpn": "h2", "fingerprint": "chrome"}
        try:
            v = m.generate_share_link(UID, "panel.test", remark="r", protocol="vless-ws")
            assert f"vless://{UID}@panel.test:443?" in v
            assert "type=ws" in v and f"path=/ws/{UID}" in v
            assert "sni=panel.test" in v and "allowInsecure" not in v
            assert "ed=" not in v
        finally:
            m.LINKS.pop(UID, None)

    def test_turbo_link_shape(self):
        import main as m
        m.LINKS[UID] = {"label": "t", "turbo_enabled": True}
        try:
            v = m.generate_share_link(UID, "panel.test", remark="r", protocol="vless-ws")
            # ?ed=2048 appended to path (percent-encoded inside the query value)
            assert "path=/ws/" + UID + "%3Fed%3D2048" in v, v
            assert "sni=panel.test" in v and "allowInsecure" not in v
            t = m.generate_share_link(UID, "panel.test", remark="r", protocol="trojan-ws")
            assert "path=/trojan-ws%3Fed%3D2048" in t, t
            # xhttp عمداً ed نمی‌گیرد (فقط WS)
            x = m.generate_share_link(UID, "panel.test", remark="r", protocol="xhttp-packet-up")
            assert "ed=" not in x
        finally:
            m.LINKS.pop(UID, None)

    def test_turbo_off_no_ed(self):
        import main as m
        m.LINKS[UID] = {"label": "t", "turbo_enabled": False}
        try:
            v = m.generate_share_link(UID, "panel.test", remark="r", protocol="vless-ws")
            assert "ed=" not in v
        finally:
            m.LINKS.pop(UID, None)

    def test_spoof_link_mode_b(self):
        import main as m
        m.LINKS[UID] = {"label": "t", "spoof_sni": "www.bale.ir", "spoof_sni_enabled": True}
        try:
            for proto, scheme in (("vless-ws", "vless"), ("trojan-ws", "trojan"),
                                  ("xhttp-packet-up", "vless"),
                                  ("trojan-xhttp-stream-up", "trojan")):
                v = m.generate_share_link(UID, "panel.test", remark="r", protocol=proto)
                assert v.startswith(f"{scheme}://{UID}@panel.test:443?"), v[:60]
                assert "sni=www.bale.ir" in v
                assert "allowInsecure=1" in v
                assert "host=panel.test" in v, "Host = دامنه‌ی واقعی می‌ماند"
        finally:
            m.LINKS.pop(UID, None)

    def test_spoof_invalid_value_ignored(self):
        import main as m
        m.LINKS[UID] = {"label": "t", "spoof_sni": "104.17.1.999", "spoof_sni_enabled": True}
        try:
            v = m.generate_share_link(UID, "panel.test", remark="r", protocol="vless-ws")
            assert "sni=panel.test" in v and "allowInsecure" not in v
        finally:
            m.LINKS.pop(UID, None)

    def test_ss_and_mtproto_unaffected(self):
        """صداقت: SS/MTProto هیچ SNI/turbo اثری نمی‌گیرند (فرمت لینکشان ندارد)."""
        import main as m
        m.LINKS[UID] = {"label": "t", "turbo_enabled": True,
                        "spoof_sni": "www.bale.ir", "spoof_sni_enabled": True,
                        "ss_cipher": "aes-256-gcm", "ss_password": "pw1234567890"}
        try:
            ss = m.generate_share_link(UID, "panel.test", remark="r", protocol="shadowsocks")
            assert ss.startswith("ss://") and "sni=" not in ss and "ed=" not in ss
        finally:
            m.LINKS.pop(UID, None)


# ─────────────────────────────────────────────────────────────────────────────
# §B — PATCH semantics (subprocess server)
# ─────────────────────────────────────────────────────────────────────────────
class TestPatchSemantics:
    def test_turbo_single_slot(self, server, session):
        base = server["base"]
        st, l1 = api(session, base, "/api/links", "POST", {"label": "turbo-a", "protocol": "vless-ws"})
        st, l2 = api(session, base, "/api/links", "POST", {"label": "turbo-b", "protocol": "vless-ws"})
        u1, u2 = l1["uuid"], l2["uuid"]
        try:
            st, _ = api(session, base, f"/api/links/{u1}", "PATCH", {"turbo_enabled": True})
            assert st == 200
            st, links = api(session, base, "/api/links")
            by = {l["uuid"]: l for l in links["links"]}
            assert by[u1]["turbo_enabled"] is True
            assert "ed=" not in by[u2].get("vless_link", "")
            assert "%3Fed%3D2048" in by[u1]["vless_link"]
            # فعال کردن روی دومی → اولی خودکار خاموش (تک‌شانهای)
            st, _ = api(session, base, f"/api/links/{u2}", "PATCH", {"turbo_enabled": True})
            assert st == 200
            st, links = api(session, base, "/api/links")
            by = {l["uuid"]: l for l in links["links"]}
            assert by[u2]["turbo_enabled"] is True
            assert by[u1].get("turbo_enabled") is False
            assert "%3Fed%3D2048" in by[u2]["vless_link"]
            assert "%3Fed%3D2048" not in by[u1]["vless_link"]
        finally:
            api(session, base, f"/api/links/{u1}", "DELETE")
            api(session, base, f"/api/links/{u2}", "DELETE")

    def test_turbo_rejects_xhttp(self, server, session):
        base = server["base"]
        st, l = api(session, base, "/api/links", "POST", {"label": "turbo-x", "protocol": "xhttp-packet-up"})
        uid = l["uuid"]
        try:
            st, r = api(session, base, f"/api/links/{uid}", "PATCH", {"turbo_enabled": True})
            assert st == 400
            assert "VLESS-WS" in r["detail"] or "Trojan-WS" in r["detail"]
        finally:
            api(session, base, f"/api/links/{uid}", "DELETE")

    def test_spoof_validation_and_normalization(self, server, session):
        base = server["base"]
        st, l = api(session, base, "/api/links", "POST", {"label": "spoof-v", "protocol": "vless-ws"})
        uid = l["uuid"]
        try:
            # مقدار خراب → 400
            st, r = api(session, base, f"/api/links/{uid}", "PATCH", {"spoof_sni": "bad_host!!"})
            assert st == 400
            # IP → 400
            st, r = api(session, base, f"/api/links/{uid}", "PATCH", {"spoof_sni": "8.8.8.8"})
            assert st == 400
            # مقدار معتبر → نرمال‌سازی + فعال‌سازی
            st, r = api(session, base, f"/api/links/{uid}", "PATCH",
                        {"spoof_sni": "WWW.Bale.IR", "spoof_sni_enabled": True})
            assert st == 200
            st, links = api(session, base, "/api/links")
            by = {x["uuid"]: x for x in links["links"]}
            assert by[uid]["spoof_sni"] == "www.bale.ir"
            assert "sni=www.bale.ir" in by[uid]["vless_link"]
            assert "allowInsecure=1" in by[uid]["vless_link"]
            # خاموش کردن → لینک تمیز برمی‌گردد
            st, _ = api(session, base, f"/api/links/{uid}", "PATCH", {"spoof_sni_enabled": False})
            st, links = api(session, base, "/api/links")
            by = {x["uuid"]: x for x in links["links"]}
            assert "allowInsecure" not in by[uid]["vless_link"]
            assert "sni=" in by[uid]["vless_link"]
        finally:
            api(session, base, f"/api/links/{uid}", "DELETE")

    def test_spoof_needs_value_first(self, server, session):
        base = server["base"]
        st, l = api(session, base, "/api/links", "POST", {"label": "spoof-empty", "protocol": "vless-ws"})
        uid = l["uuid"]
        try:
            st, r = api(session, base, f"/api/links/{uid}", "PATCH", {"spoof_sni_enabled": True})
            assert st == 400
            assert "SNI" in r["detail"]
        finally:
            api(session, base, f"/api/links/{uid}", "DELETE")

    def test_spoof_rejects_ss(self, server, session):
        base = server["base"]
        st, l = api(session, base, "/api/links", "POST", {"label": "spoof-ss", "protocol": "shadowsocks"})
        uid = l["uuid"]
        try:
            st, r = api(session, base, f"/api/links/{uid}", "PATCH",
                        {"spoof_sni": "www.bale.ir", "spoof_sni_enabled": True})
            assert st == 400
        finally:
            api(session, base, f"/api/links/{uid}", "DELETE")


# ─────────────────────────────────────────────────────────────────────────────
# §C — REAL 0-RTT early-data E2E (subprocess server, real WS client)
# ─────────────────────────────────────────────────────────────────────────────
class TestRealEarlyData:
    def test_early_data_full_e2e(self, server, session):
        """کلاینت واقعی 0-RTT: payload داخل هندشیک (Sec-WebSocket-Protocol) →
        سرور بلافاصله پردازش می‌کند → پاسخ HTTP واقعی از داخل تونل."""
        import link_health
        base = server["base"]
        st, l = api(session, base, "/api/links", "POST", {"label": "ed-e2e", "protocol": "vless-ws"})
        uid = l["uuid"]
        try:
            ws_base = f"ws://127.0.0.1:{server['port']}"
            r = asyncio.run(link_health._probe_ws_tunnel(
                "vless", uid, {"protocol": "vless-ws"}, use_ed=True, ws_base=ws_base))
            assert r.get("ok") is True, f"early-data path failed: {r}"
            assert r.get("ws_ms") is not None and r["ws_ms"] > 0
            assert r.get("e2e_ms") is not None
            assert "HTTP" in (r.get("reply") or ""), r
        finally:
            api(session, base, f"/api/links/{uid}", "DELETE")

    def test_early_data_trojan_full_e2e(self, server, session):
        import link_health
        base = server["base"]
        st, l = api(session, base, "/api/links", "POST", {"label": "ed-tro", "protocol": "trojan-ws"})
        uid = l["uuid"]
        try:
            ws_base = f"ws://127.0.0.1:{server['port']}"
            r = asyncio.run(link_health._probe_ws_tunnel(
                "trojan", uid, {"protocol": "trojan-ws"}, use_ed=True, ws_base=ws_base))
            assert r.get("ok") is True, f"trojan early-data failed: {r}"
            assert "HTTP" in (r.get("reply") or "")
        finally:
            api(session, base, f"/api/links/{uid}", "DELETE")

    def test_backward_compat_no_early_data(self, server, session):
        """بدون ed → همان مسیر عادی (سازگاری کامل با کلاینت‌های فعلی)."""
        import link_health
        base = server["base"]
        st, l = api(session, base, "/api/links", "POST", {"label": "ed-none", "protocol": "vless-ws"})
        uid = l["uuid"]
        try:
            ws_base = f"ws://127.0.0.1:{server['port']}"
            r = asyncio.run(link_health._probe_ws_tunnel(
                "vless", uid, {"protocol": "vless-ws"}, use_ed=False, ws_base=ws_base))
            assert r.get("ok") is True, r
        finally:
            api(session, base, f"/api/links/{uid}", "DELETE")

    def test_turbo_ab_endpoint_real(self, server, session):
        base = server["base"]
        st, l = api(session, base, "/api/links", "POST", {"label": "ab-test", "protocol": "vless-ws"})
        uid = l["uuid"]
        try:
            st, d = api(session, base, f"/api/links/{uid}/turbo-ab", "POST", {}, timeout=180)
            assert st == 200
            assert d["ok"] is True, d
            assert d["normal"]["ok"] is True and d["turbo"]["ok"] is True
            assert d["normal"]["total_ms"] is not None and d["normal"]["total_ms"] > 0
            assert d["turbo"]["total_ms"] is not None and d["turbo"]["total_ms"] > 0
            assert "%3Fed%3D2048" in d["turbo_url"]
            assert "ed=" not in d["original_url"]
        finally:
            api(session, base, f"/api/links/{uid}", "DELETE")

    def test_turbo_ab_unknown_link_404(self, server, session):
        st, r = api(server and session, server["base"], "/api/links/none/turbo-ab", "POST", {})
        assert st == 404


# ─────────────────────────────────────────────────────────────────────────────
# §D — REAL spoof client-path probe through a REAL TLS edge
# ─────────────────────────────────────────────────────────────────────────────
def _make_self_signed_cert():
    import datetime
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
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
    """لبه‌ی TLS واقعی (مثل ingress Railway): هر SNI را می‌پذیرد (self-signed)."""

    def __init__(self, upstream_port: int):
        import ssl
        import tempfile
        self.upstream_port = upstream_port
        key_pem, cert_pem = _make_self_signed_cert()
        k = tempfile.NamedTemporaryFile(delete=False, suffix=".key")
        c = tempfile.NamedTemporaryFile(delete=False, suffix=".crt")
        k.write(key_pem)
        k.flush()
        c.write(cert_pem)
        c.flush()
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
        for f in self._files:
            try:
                os.unlink(f)
            except Exception:
                pass


@pytest.fixture(scope="module")
def tls_app_server(tmp_path_factory):
    """اپ درون‌پردازشی (TestClient) + uvicorn واقعی + لبه‌ی TLS واقعی."""
    import uvicorn
    from fastapi.testclient import TestClient
    import main

    with TestClient(main.app) as client:
        r = client.post("/api/login", json={"password": "123456"})
        assert r.status_code == 200
        _before = {l["uuid"] for l in client.get("/api/links").json()["links"]}

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

        yield {"client": client, "app_port": app_port,
               "tls_port": edge_holder["edge"].port, "before": _before}

        edge_holder["loop"].call_soon_threadsafe(edge_holder["loop"].stop)
        server.should_exit = True
        thread.join(timeout=10)
        asyncio.run(edge_holder["edge"].stop())
        for l in client.get("/api/links").json()["links"]:
            if l["uuid"] not in _before:
                client.delete(f"/api/links/{l['uuid']}")


class TestSpoofClientPath:
    def test_gating(self):
        import link_health
        assert link_health._link_spoof_sni(
            {"spoof_sni": "www.bale.ir", "spoof_sni_enabled": True}) == "www.bale.ir"
        assert link_health._link_spoof_sni({"spoof_sni": "x", "spoof_sni_enabled": True}) is None
        assert link_health._link_spoof_sni(
            {"spoof_sni": "www.bale.ir", "spoof_sni_enabled": False}) is None
        assert link_health._link_spoof_sni({}) is None

    def test_spoof_probe_full_e2e_through_tls_edge(self, tls_app_server):
        """TLS(SNI=جعلی، بدون verify) → WS(Host=واقعی) → بایت‌های واقعی VLESS →
        پاسخ HTTP واقعی از داخل تونل — دقیقاً مسیر کلاینتِ لینک جعلی."""
        import link_health
        import main
        client = tls_app_server["client"]
        r = client.post("/api/links", json={"label": "p46-spoof", "protocol": "vless-ws"})
        uid = r.json()["uuid"]
        try:
            client.patch(f"/api/links/{uid}",
                         json={"spoof_sni": "www.snap.ir", "spoof_sni_enabled": True})
            link = dict(main.LINKS[uid])
            result = asyncio.run(link_health._spoof_client_probe(
                "vless", uid, link, host="127.0.0.1", port=tls_app_server["tls_port"]))
            assert result.get("ok") is True, f"spoof client path failed: {result}"
            assert result.get("e2e_ms") is not None and result["e2e_ms"] > 0
            assert "HTTP" in str(result.get("reply", ""))
        finally:
            client.delete(f"/api/links/{uid}")

    def test_spoof_probe_honest_local_skip(self, tls_app_server, monkeypatch):
        import link_health
        import main
        client = tls_app_server["client"]
        r = client.post("/api/links", json={"label": "p46-skip", "protocol": "vless-ws"})
        uid = r.json()["uuid"]
        try:
            client.patch(f"/api/links/{uid}",
                         json={"spoof_sni": "www.bale.ir", "spoof_sni_enabled": True})
            monkeypatch.setattr(link_health, "get_host", lambda: "localhost")
            link = dict(main.LINKS[uid])
            result = asyncio.run(link_health._spoof_client_probe(
                "vless", uid, link, host=None))
            assert result.get("ok") is False
            assert "لوکال" in result.get("detail", "") or "عمومی" in result.get("detail", "")
        finally:
            client.delete(f"/api/links/{uid}")

    def test_composition_spoof_is_primary_no_false_green(self, tls_app_server, monkeypatch):
        import link_health
        import main
        client = tls_app_server["client"]
        r = client.post("/api/links", json={"label": "p46-comp", "protocol": "vless-ws"})
        uid = r.json()["uuid"]
        try:
            client.patch(f"/api/links/{uid}",
                         json={"spoof_sni": "www.bale.ir", "spoof_sni_enabled": True})

            async def fake_clean(*a, **k):
                return {"ok": True, "ws_ms": 5.0, "e2e_ms": 7.0, "reply": "HTTP/1.1 204"}

            async def fake_spoof(*a, **k):
                return {"ok": False, "detail": "TLS(SNI جعلی): timeout"}

            monkeypatch.setattr(link_health, "get_host", lambda: "panel.example.test")
            monkeypatch.setattr(link_health, "_probe_ws_tunnel", fake_clean)
            monkeypatch.setattr(link_health, "_spoof_client_probe", fake_spoof)
            link = dict(main.LINKS[uid])
            result = asyncio.run(link_health._run_link_ping(uid, link))
            assert result["client_path"] == "spoofed-sni"
            assert result["spoof_sni"] == "www.bale.ir"
            assert result["ok"] is False, "مسیر کلاینتِ مرده هرگز سبز نمی‌شود"
            assert result.get("clean_path", {}).get("ok") is True, "شواهد مسیر تمیز حفظ شود"

            async def fake_spoof_ok(*a, **k):
                return {"ok": True, "ws_ms": 9.0, "e2e_ms": 12.0, "reply": "HTTP/1.1 204"}
            monkeypatch.setattr(link_health, "_spoof_client_probe", fake_spoof_ok)
            result2 = asyncio.run(link_health._run_link_ping(uid, dict(main.LINKS[uid])))
            assert result2["ok"] is True
            assert result2["e2e_ms"] == 12.0, "متریک اصلی = مسیر کلاینت (SNI جعلی)"
        finally:
            client.delete(f"/api/links/{uid}")

    def test_non_spoof_link_legacy_shape(self, tls_app_server, monkeypatch):
        import link_health
        import main
        client = tls_app_server["client"]
        r = client.post("/api/links", json={"label": "p46-clean", "protocol": "vless-ws"})
        uid = r.json()["uuid"]
        try:
            async def fake_clean(*a, **k):
                return {"ok": True, "ws_ms": 5.0, "e2e_ms": 7.0, "reply": "HTTP/1.1 204"}
            monkeypatch.setattr(link_health, "get_host", lambda: "panel.example.test")
            monkeypatch.setattr(link_health, "_probe_ws_tunnel", fake_clean)
            result = asyncio.run(link_health._run_link_ping(uid, dict(main.LINKS[uid])))
            assert "client_path" not in result
            assert "clean_path" not in result
            assert result["ok"] is True
        finally:
            client.delete(f"/api/links/{uid}")


# ─────────────────────────────────────────────────────────────────────────────
# §F — login page: faint placeholder, no hint box (user order)
# ─────────────────────────────────────────────────────────────────────────────
class TestLoginPage:
    def test_placeholder_is_123456_faint(self):
        import pages
        assert 'id="pw" placeholder="123456"' in pages.LOGIN_HTML
        assert "#pw::placeholder" in pages.LOGIN_HTML  # استایل کمرنگ اختصاصی
        assert "رمز عبور را وارد کنید" not in pages.LOGIN_HTML

    def test_hint_box_and_filldefault_gone(self):
        import pages
        assert 'class="hint"' not in pages.LOGIN_HTML
        assert "fillDefault" not in pages.LOGIN_HTML
        assert "رمز پیش‌فرض سیستم" not in pages.LOGIN_HTML

    def test_style_and_colors_preserved(self):
        import pages
        # رنگ‌ها و استایل پایه دست‌نخورده
        for needle in ["--accent:#FF4D2E", "--accent2:#FF8A3D", "GATEWAY ONLINE",
                       "btngrad", "particles"]:
            assert needle in pages.LOGIN_HTML, needle


# ─────────────────────────────────────────────────────────────────────────────
# §G — fresh UI: HTML responses carry no-store
# ─────────────────────────────────────────────────────────────────────────────
class TestFreshUI:
    def test_login_no_store(self, server):
        with urllib.request.urlopen(f"{server['base']}/login", timeout=10) as r:
            assert r.status == 200
            assert "no-store" in (r.headers.get("Cache-Control") or "")

    def test_dashboard_no_store(self, server, session):
        req = urllib.request.Request(f"{server['base']}/dashboard")
        with session.open(req, timeout=10) as r:
            assert r.status == 200
            assert "no-store" in (r.headers.get("Cache-Control") or "")

    def test_dashboard_serves_new_ui_needles(self, server, session):
        req = urllib.request.Request(f"{server['base']}/dashboard")
        with session.open(req, timeout=10) as r:
            html = r.read().decode()
        for needle in ["toggleTurbo", "toggleSpoof", "turboBadge", "spoofBadge",
                       "el-turbo-toggle", "el-spoof-sni", "turbo-ab", "Real Delay"]:
            assert needle in html, needle


# ─────────────────────────────────────────────────────────────────────────────
# §H — version pin
# ─────────────────────────────────────────────────────────────────────────────
class TestVersionPin:
    def test_deployment_version(self, server):
        with urllib.request.urlopen(f"{server['base']}/api/deployment-version", timeout=10) as r:
            d = json.loads(r.read().decode())
        assert d["version"] == "13.3.0-emix-pro"
        assert "turbo-0rtt" in d["features"]
        assert "sni-spoof-per-link" in d["features"]
        assert "fresh-ui-no-store" in d["features"]
