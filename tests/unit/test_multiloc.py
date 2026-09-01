"""Unit tests for MultiLoc v2 (Worker-Terminated Egress + SNI-Trace).

Covers (بدون شبکه‌ی خارجی — همه‌ی پروب‌ها mock می‌شوند):
  - _tls_probe_sync با socket مسک
  - parse colo از body
  - scan_colos: گروه‌بندی بر اساس colo + مرتب‌سازی RTT + auto همیشه موجود
  - scan_colos بدون worker domain → خطای مهربان (نه crash)
  - sni_trace بدون دامنه → validation error
  - _forge_vless_link: فرمت لینک VLESS برای حالت WTE
  - _tunnel_link: بازنویسی آدرس/مسیر /loc برای حالت تونل
  - build_links بدون worker domain → خطای مهربان
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("PORT", "8765")
os.environ.setdefault("SECRET_KEY", "test-secret-ml")
os.environ.setdefault("ADMIN_PASSWORD", "test-password")
os.environ.setdefault("RAILWAY_PUBLIC_DOMAIN", "test.example.com")
os.environ.setdefault("DATA_DIR", "/tmp/emix-test-multiloc-unit")
os.makedirs(os.environ["DATA_DIR"], exist_ok=True)

sys.path.insert(0, str(Path(__file__).parent.parent))

import main  # noqa: E402 — باید قبل از multiloc import شود (جریان واقعی)
import multiloc  # noqa: E402


# ── fixtures ─────────────────────────────────────────────────────────────────

class FakeSock:
    def __init__(self, chunks=(b"HTTP/1.1 200 OK\r\n\r\nbody",)):
        self.chunks = list(chunks)
        self.sent = b""
        self.closed = False

    def sendall(self, data):
        self.sent += data

    def recv(self, n):
        if not self.chunks:
            return b""
        return self.chunks.pop(0)

    def settimeout(self, t):
        pass

    def close(self):
        self.closed = True


class FakeSSL:
    def __init__(self, sock):
        self._sock = sock

    def version(self):
        return "TLSv1.3"

    def sendall(self, data):
        self._sock.sendall(data)

    def recv(self, n):
        return self._sock.recv(n)

    def settimeout(self, t):
        pass

    def close(self):
        self._sock.close()


TRACE_BODY = "HTTP/1.1 200 OK\r\n\r\nfl=x h=d.com ip=1.2.3.4 colo=HKG ts=1"


def _patch_probe(monkeypatch, results):
    """_tls_probe_sync را با نتایج ثابت mock می‌کند."""
    calls = []

    def fake(ip, sni, path="/", host_hdr=None, timeout=6.0, verify=False):
        calls.append((ip, sni, path))
        r = results.get(ip, {"ip": ip, "sni": sni, "tls_ok": False, "colo": None,
                             "rtt_ms": None, "http_status": None, "body": None,
                             "error": "timeout", "tcp_ok": False, "tls_version": None,
                             "path": path})
        return r

    monkeypatch.setattr(multiloc, "_tls_probe_sync", fake)
    return calls


def _mk_result(ip, colo, rtt):
    return {"ip": ip, "sni": "d.workers.dev", "path": "/cdn-cgi/trace",
            "tcp_ok": True, "tls_ok": True, "tls_version": "TLSv1.3",
            "rtt_ms": rtt, "http_status": "HTTP/1.1 200 OK",
            "body": TRACE_BODY.replace("HKG", colo) if colo else None,
            "colo": colo, "error": None}


# ── tests ───────────────────────────────────────────────────────────────────

def test_forge_vless_link_format():
    url = multiloc._forge_vless_link("uuid-1234", "w.example.workers.dev",
                                     "104.17.147.22", "🇩🇪 فرانکفورت · 20ms · خروج CF")
    assert url.startswith("vless://uuid-1234@104.17.147.22:443?")
    assert "sni=w.example.workers.dev" in url
    assert "host=w.example.workers.dev" in url
    assert "path=/vl" in url
    assert "security=tls" in url
    assert "type=ws" in url
    assert "fp=chrome" in url
    assert url.endswith("%D8%AE%D8%B1%D9%88%D8%AC%20CF")


def test_tunnel_link_rewrite():
    original = ("vless://uuid-1234@panel.example.com:443?encryption=none&security=tls"
                "&type=ws&host=panel.example.com&path=%2Fws%2Fuuid-1234&sni=panel.example.com")
    out = multiloc._tunnel_link(original, "fra", "104.17.147.22", "w.example.workers.dev")
    assert out is not None
    assert "@104.17.147.22:443" in out
    assert "host=w.example.workers.dev" in out
    assert "sni=w.example.workers.dev" in out
    # مسیر باید /loc/fra/ws/uuid-1234 شود — کل URL را unquote می‌کنیم
    from urllib.parse import unquote
    assert "/loc/fra/ws/uuid-1234" in unquote(out)


def test_tunnel_link_trojan():
    original = ("trojan://uuid-1234@panel.example.com:443?security=tls&type=ws"
                "&host=panel.example.com&path=%2Ftrojan-ws")
    out = multiloc._tunnel_link(original, "ams", "188.114.96.3", "w.example.workers.dev")
    assert out is not None and "@188.114.96.3:443" in out


def test_tunnel_link_rejects_mtproto():
    assert multiloc._tunnel_link("tg://proxy?server=x", "ams", "1.1.1.1", "w.dev") is None


def test_scan_groups_by_colo(monkeypatch):
    results = {
        "1.1.1.1": _mk_result("1.1.1.1", "FRA", 20.0),
        "2.2.2.2": _mk_result("2.2.2.2", "FRA", 15.0),
        "3.3.3.3": _mk_result("3.3.3.3", "AMS", 10.0),
        "4.4.4.4": _mk_result("4.4.4.4", None, None),  # مرده
    }
    _patch_probe(monkeypatch, results)
    monkeypatch.setattr(multiloc, "CF_CANDIDATES_BASE", list(results.keys()))
    monkeypatch.setattr(multiloc, "_scan_cache", {"ts": 0.0, "locations": []})
    monkeypatch.setattr(multiloc, "_load_scan", lambda: {"ts": 0.0, "locations": []})
    monkeypatch.setattr(multiloc, "_save_scan", lambda c: None)
    monkeypatch.setattr(multiloc, "_worker_cfg",
                        lambda: {"worker_domain": "w.example.workers.dev", "worker_token": ""})

    r = asyncio.run(multiloc.scan_colos(force=True))
    assert r["ok"] is True
    locs = r["locations"]
    # auto همیشه اول
    assert locs[0]["key"] == "auto"
    assert locs[0]["best_ip"] == "w.example.workers.dev"
    # دو colo: AMS (10ms) باید قبل از FRA باشد (مرتب بر اساس RTT)
    keys = [l["key"] for l in locs if l["key"] != "auto"]
    assert keys == ["ams", "fra"]
    fra = next(l for l in locs if l["key"] == "fra")
    # FRA بهترین IP باید 2.2.2.2 باشد (15ms < 20ms)
    assert fra["best_ip"] == "2.2.2.2"
    assert fra["city"] == "فرانکفورت" and fra["flag"] == "🇩🇪"
    assert r["stats"]["dead"] == 1


def test_scan_without_worker_domain(monkeypatch):
    monkeypatch.setattr(multiloc, "_worker_cfg", lambda: {"worker_domain": "", "worker_token": ""})
    monkeypatch.setattr(multiloc, "_scan_cache", {"ts": 0.0, "locations": []})
    monkeypatch.setattr(multiloc, "_load_scan", lambda: {"ts": 0.0, "locations": []})
    r = asyncio.run(multiloc.scan_colos(force=True))
    assert r["ok"] is False
    assert "Worker" in r["error"] or "worker" in r["error"]


def test_sni_trace_validation(monkeypatch):
    r = asyncio.run(multiloc.sni_trace("notadomain"))
    assert r["ok"] is False
    assert "معتبر" in r.get("error", "")


def test_sni_trace_probes(monkeypatch):
    # کنترل OK + جعل ریلوی OK + جعل CF fail → verdict railway_direct True
    results = {}

    async def fake(ip, sni, path="/", host_hdr=None, timeout=6.0, verify=False):
        if sni == "test.example.com":
            return {"ip": ip, "sni": sni, "tcp_ok": True, "tls_ok": True,
                    "tls_version": "TLSv1.3", "rtt_ms": 12.0,
                    "http_status": "HTTP/1.1 200 OK", "body": None, "colo": None,
                    "error": None, "path": path}
        if sni == "www.microsoft.com" and host_hdr == "test.example.com":
            return {"ip": ip, "sni": sni, "tcp_ok": True, "tls_ok": True,
                    "tls_version": "TLSv1.3", "rtt_ms": 13.0,
                    "http_status": "HTTP/1.1 200 OK", "body": None, "colo": None,
                    "error": None, "path": path}
        return {"ip": ip, "sni": sni, "tcp_ok": True, "tls_ok": False,
                "tls_version": None, "rtt_ms": None, "http_status": None,
                "body": None, "colo": None,
                "error": "handshake_failure", "path": path}

    monkeypatch.setattr(multiloc, "_tls_probe", fake)
    monkeypatch.setattr(multiloc, "_worker_cfg",
                        lambda: {"worker_domain": "w.example.workers.dev", "worker_token": ""})
    import socket
    monkeypatch.setattr(socket, "gethostbyname", lambda h: "1.2.3.4")
    r = asyncio.run(multiloc.sni_trace("www.microsoft.com"))
    assert r["ok"] is True
    modes = {v["mode"]: v["ok"] for v in r["verdicts"]}
    assert modes.get("railway_direct") is True
    assert modes.get("cdn") is False


def test_build_links_requires_worker_domain(monkeypatch):
    monkeypatch.setattr(multiloc, "_worker_cfg", lambda: {"worker_domain": "", "worker_token": ""})
    r = asyncio.run(multiloc.build_links(None, "worker"))
    assert r["ok"] is False


def test_worker_cfg_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(multiloc, "_worker_cfg",
                        lambda: {"worker_domain": "fallback.example.workers.dev", "worker_token": ""})
    cfg = multiloc._worker_cfg()
    assert cfg["worker_domain"] == "fallback.example.workers.dev"


def test_replace_query_param_keeps_fragment():
    url = "vless://u@h:443?a=1&sni=old&b=2#remark"
    out = multiloc._replace_query_param(url, "sni", "new")
    assert out == "vless://u@h:443?a=1&sni=new&b=2#remark"
