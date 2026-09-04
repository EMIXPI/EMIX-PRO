# tests/unit/test_network_test.py — Phase 39: Real Network Test Service
#
# Unit tests for network_test.py — the staged DNS→TCP→TLS→SNI probe engine.
# REAL sockets only: a local TCP listener is started on a thread for the
# TCP/DNS stages; honest-error classification is verified against a
# nonexistent domain (real DNS resolution attempt). No mocked latencies.

import asyncio
import socket
import threading
import time

import pytest

import network_test


# ── fixtures: real local TCP listener ────────────────────────────────────────

@pytest.fixture(scope="module")
def local_tcp():
    """A REAL TCP listener on 127.0.0.1:0 — accept connections, echo nothing."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    port = srv.getsockname()[1]

    def _serve():
        while True:
            try:
                conn, _ = srv.accept()
                conn.close()
            except OSError:
                return

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    yield ("127.0.0.1", port)
    srv.close()


# ── staged probe: real DNS + TCP against the local listener ─────────────────

@pytest.mark.asyncio
async def test_staged_probe_tcp_real(local_tcp):
    host, port = local_tcp
    res = await network_test.staged_probe(host, port, use_tls=False, timeout=4.0)
    # 127.0.0.1 is an IP — DNS stage short-circuits via getaddrinfo (still real)
    assert res["ok"] is True
    assert res["error_code"] is None
    assert res["stages_ms"]["dns"] is not None
    assert res["stages_ms"]["tcp"] is not None
    assert res["stages_ms"]["tcp"] >= 0.0
    assert res["total_ms"] is not None and res["total_ms"] >= 0.0
    # TLS not requested → not claimed
    assert res["stages_ms"]["tls"] is None
    assert res["cert"] == {}


@pytest.mark.asyncio
async def test_staged_probe_closed_port_honest():
    # port 9 (discard) on 127.0.0.1 — refused or timeout, never fake success
    res = await network_test.staged_probe("127.0.0.1", 9, use_tls=False, timeout=2.0)
    assert res["ok"] is False
    assert res["error_code"] in ("TCP_REFUSED", "TIMEOUT")
    assert res["error_detail"]


@pytest.mark.asyncio
async def test_staged_probe_dns_error_honest():
    # a domain that cannot resolve — real getaddrinfo failure
    res = await network_test.staged_probe(
        "this-domain-does-not-exist-zzz.invalid", 443, use_tls=False, timeout=4.0)
    assert res["ok"] is False
    assert res["error_code"] == "DNS_ERROR"
    assert "gaierror" in res["error_detail"] or "Name or service" in res["error_detail"]


@pytest.mark.asyncio
async def test_staged_probe_never_blocks_loop_long():
    """§29 — probe runs in executor with hard cap; even a slow target returns."""
    t0 = time.perf_counter()
    res = await network_test.staged_probe(
        "10.255.255.1", 443, use_tls=False, timeout=2.0)  # unroutable → timeout
    dt = time.perf_counter() - t0
    assert dt < 10.0, "probe exceeded executor cap — event loop blocked"
    assert res["ok"] is False
    assert res["error_code"] in ("TIMEOUT", "TCP_REFUSED")


# ── result shape invariants (honesty rules) ─────────────────────────────────

@pytest.mark.asyncio
async def test_result_shape_on_failure_has_no_fake_ms(local_tcp):
    host, port = local_tcp
    res = await network_test.staged_probe("nonexistent-zzz.invalid", port,
                                          use_tls=False, timeout=4.0)
    # failed probe must NEVER carry a fake total latency
    assert res["ok"] is False
    assert res["total_ms"] is None


def test_error_codes_contract():
    for code in ("DNS_ERROR", "TCP_REFUSED", "TIMEOUT", "TLS_ERROR", "SNI_ERROR"):
        assert code in network_test.ERROR_CODES


def test_validate_target_rejects_blocked_hosts():
    from fastapi import HTTPException
    from pydantic import BaseModel

    class _TR(BaseModel):
        address: str = ""
        port: int = 443
        sni: str = ""
        tls: bool = True
        insecure: bool = False
        timeout: float = 8.0
        link_uid: str = ""

    # localhost is blocked (SSRF posture)
    with pytest.raises(HTTPException):
        network_test._validate_target(_TR(address="localhost"))
    with pytest.raises(HTTPException):
        network_test._validate_target(_TR(address="127.0.0.1"))
    # invalid port
    with pytest.raises(HTTPException):
        network_test._validate_target(_TR(address="example.com", port=0))
    # SNI must be a hostname, not an IP
    with pytest.raises(HTTPException):
        network_test._validate_target(_TR(address="example.com", sni="1.2.3.4"))
    # valid target passes and is normalized
    addr, port, sni = network_test._validate_target(
        _TR(address="Example.COM.", port=443, sni="Foo.Example.com"))
    assert addr == "example.com"
    assert port == 443
    assert sni == "foo.example.com"


def test_parse_cert_der_with_cryptography():
    """_parse_cert must extract CN/SAN from DER via cryptography when given."""
    # self-signed cert generated on the fly — REAL x509 structure
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    import datetime

    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ncc-test.example")])
    cert = (x509.CertificateBuilder()
            .subject_name(subject).issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=30))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName("ncc-test.example")]),
                critical=False)
            .sign(key, hashes.SHA256()))
    from cryptography.hazmat.primitives.serialization import Encoding
    der = cert.public_bytes(Encoding.DER)
    out = network_test._parse_cert(der, None)
    assert out["subject_cn"] == "ncc-test.example"
    assert "ncc-test.example" in out["sans"]
    assert out["days_left"] is not None and 28 <= out["days_left"] <= 32


def test_parse_cert_empty_is_honest():
    out = network_test._parse_cert(b"", None)
    assert out == {"subject_cn": "", "issuer": "", "not_after": "",
                   "days_left": None, "sans": [], "verify_mode": ""}


# ── routes registered on a real FastAPI app ─────────────────────────────────

@pytest.mark.asyncio
async def test_routes_register():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    def _ra():  # fake require_auth
        return None

    network_test.register_routes(app, _ra)
    paths = {r.path for r in app.routes}
    assert "/api/network/test/quick" in paths
    assert "/api/network/test/tls" in paths
    assert "/api/network/test/sni" in paths
    assert "/api/network/test/diagnostic" in paths
    assert "/api/network/test/targets" in paths

    client = TestClient(app)
    r = client.post("/api/network/test/quick", json={"address": "127.0.0.1"})
    assert r.status_code == 400  # blocked host — honest refusal
    r = client.post("/api/network/test/quick", json={"address": "", "port": 443})
    assert r.status_code == 400
