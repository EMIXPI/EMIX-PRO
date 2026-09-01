# tests/unit/test_gaming_wte.py — WTE links + VPS auto-fallback
import asyncio
import json

import pytest

import gaming_boost as gb


def _mk_link(uid="d35ef54c-0000-0000-0000-000000000000", proto="vless-ws"):
    return f"vless://{uid}@emix-pro-production.up.railway.app:443?encryption=none&security=tls&type=ws&host=emix-pro-production.up.railway.app&path=%2Fws%2F{uid}&sni=emix-pro-production.up.railway.app&fp=chrome&alpn=h2%2Chttp%2F1.1#Test"


def test_gaming_link_wte_path():
    """WTE=True → path=/vl (worker-terminated) + host/sni=worker domain."""
    url = _mk_link()
    out = gb._gaming_link(url, "162.159.140.10", 443, "emix-gateway.personalemixone.workers.dev",
                          "auto", wte=True)
    assert out and out.startswith("vless://d35ef54c")
    assert "162.159.140.10:443" in out
    assert "path=%2Fvl" in out
    assert "host=emix-gateway.personalemixone.workers.dev" in out
    assert "sni=emix-gateway.personalemixone.workers.dev" in out
    # WS روی http/1.1
    assert "alpn=http%2F1.1" in out


def test_gaming_link_tunnel_path():
    """WTE=False → path=/loc/{loc}/ws/{uuid} (رفتار قبلی حفظ می‌شود)."""
    url = _mk_link()
    out = gb._gaming_link(url, "162.159.140.10", 443, "emix-gateway.personalemixone.workers.dev",
                          "tr")
    assert out and "path=%2Floc%2Ftr%2Fws%2F" in out


def test_gaming_link_rejects_other_protocols():
    assert gb._gaming_link("ss://xxx@host:443", "1.1.1.1", 443, "w.dev", "auto") is None


@pytest.mark.asyncio
async def test_vps_health_dead_bridge():
    """VPS black-hole → alive=False با دلیل (پروب واقعی TLS)."""
    cfg = {"vps_ip": "192.0.2.1", "vps_port": 443,
           "worker_domain": "emix-gateway.personalemixone.workers.dev"}
    res = await gb._vps_health(cfg, timeout=1.5)
    assert res.get("alive") is False
    assert res.get("error")


@pytest.mark.asyncio
async def test_vps_health_no_ip():
    res = await gb._vps_health({})
    assert res.get("alive") is False


@pytest.mark.asyncio
async def test_gaming_links_vps_autofallback(monkeypatch):
    """ورودی VPS ناسالم → لینک‌ها بدون خطا با ورودی کلادفلر ساخته می‌شوند."""
    # worker: v2.1 (wte) — پاسخ ساختگی
    async def fake_call_worker(cfg, path, method="GET", payload=None):
        if path == "/gateway-status":
            return {"ok": True, "version": "2.1.0-wte", "wte": True, "locations": []}
        if path == "/admin/vless-uuids":
            return {"ok": True, "synced": 1}
        return {"ok": True}
    monkeypatch.setattr(gb, "_call_worker", fake_call_worker)
    # VPS مرده (TEST-NET)
    async def fake_vps(cfg, timeout=6.0):
        return {"alive": False, "error": "TLS: black hole"}
    monkeypatch.setattr(gb, "_vps_health", fake_vps)
    # یک کانفیگ vless در LINKS
    from main import LINKS, LINKS_LOCK
    uid = "d35ef54c-0000-0000-0000-000000000000"
    async with LINKS_LOCK:
        LINKS[uid] = {"label": "Speed", "protocol": "vless-ws", "active": True,
                      "alpn": "h2,http/1.1", "fingerprint": "chrome"}
    try:
        res = await gb._gaming_links("vps", "auto")
        assert res.get("ok") is True
        assert res.get("vps_fallback") is True
        assert "سوئیچ" in res.get("entry", "")
        assert res.get("wte") is True
        assert res["links"], "links must not be empty"
        assert "path=%2Fvl" in res["links"][0]["gaming"]
        assert res["links"][0]["exit"].startswith("Cloudflare")
    finally:
        async with LINKS_LOCK:
            LINKS.pop(uid, None)


@pytest.mark.asyncio
async def test_sync_worker_uuids_pushes_vless_only():
    from main import LINKS, LINKS_LOCK
    async def fake_call_worker(cfg, path, method="GET", payload=None):
        assert path == "/admin/vless-uuids"
        assert payload["uuids"] == ["d35ef54c-0000-0000-0000-000000000000"]
        return {"ok": True, "synced": 1}
    orig = gb._call_worker
    gb._call_worker = fake_call_worker
    uid = "d35ef54c-0000-0000-0000-000000000000"
    async with LINKS_LOCK:
        LINKS[uid] = {"label": "V", "protocol": "vless-ws", "active": True}
        LINKS["trojan-1"] = {"label": "T", "protocol": "trojan-ws", "active": True}
    try:
        res = await gb._sync_worker_uuids({"worker_domain": "w.dev", "worker_token": "x"})
        assert res.get("ok") is True and res.get("pushed") == 1
    finally:
        gb._call_worker = orig
        async with LINKS_LOCK:
            LINKS.pop(uid, None); LINKS.pop("trojan-1", None)
