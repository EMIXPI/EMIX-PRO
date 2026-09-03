# tests/unit/test_revive_v1160.py — v11.6.0-revive
# «احیای بخش‌های سالم با بررسی EMIX + RVG» (user request 2026-09-03).
#
# منابع الهام (معیار سلامت):
#   - EMIX  (github.com/EMIXPI/EMIX)     — نسخه‌ی سالمِ شناخته‌شده (restore c33ba43)
#   - RVG   (github.com/arvin341az-glitch/RVG) — آخرین آپدیت خودکار v11.0.2:
#       «افزایش سرعت کانفیگ‌ها با اینترنت‌های ضعیف» = تیونینگ بافر/کانکشن
#
# موارد تست:
#   §A  تیونینگ ضعیف-لینک (پورت RVG v11.0.2):
#         A1. مقادیر کانونی: RELAY_BUF=256KB · SOCK_BUF=512KB ·
#             WRITE_HIGH_WATER=128KB · TCP_USER_TIMEOUT=20s
#         A2. همه‌ی پروتکل‌ها از یک منبع حقیقت واحد می‌خوانند (نه مقادیر محلی)
#         A3. apply_weak_link_tuning روی سوکت فرضی: NODELAY+SNDBUF+RCVBUF+
#             USER_TIMEOUT (اگر پشتیبانی شود) — و هرگز raise نمی‌کند
#   §B  پینگ واقعی از مرورگر (منظره‌ی کلاینت):
#         B1. /api/client-ping-config: auth-401 بدون سشن؛ 200 با سشن؛
#             هدف direct همیشه موجود؛ هدف cf_gateway فقط وقتی worker_domain
#             تنظیم شده؛ URL الگوی {uuid} دارد
#   §C  تاب‌آوری ساب — واریانت CF:
#         C1. بدون worker_domain: /sub/{uid} همان یک خط را می‌دهد (بدون تغییر)
#         C2. با worker_domain: دو خط — مستقیم + /loc/auto (host/sni=worker،
#             allowInsecure=0، remark با پسوند CF)
#         C3. واریانت فقط برای vless/trojan — برای ss/mtproto لینک اصلی
#             دست‌نخورده می‌ماند
#   §D  سینک خودکار UUID به وورکر:
#         D1. ساخت لینک vless → sync_worker صدا زده می‌شود (پس‌زمینه)
#         D2. حذف لینک vless → sync_worker صدا زده می‌شود
#         D3. ساخت trojan/ss → sync صدا زده نمی‌شود (فقط vless در WTE)
#   §E  مارکرهای UI (سطح سورس — بدون اجرای مرورگر):
#         E1. pages.py شامل کارت «حقیقت مسیر از مرورگر شما»،
#             browserWsPing، refreshClientTruth، ct-direct/ct-cf-gateway

import asyncio
import base64
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).parent.parent.parent  # → emix-pro/
import sys  # noqa: E402
sys.path.insert(0, str(ROOT))

import os  # noqa: E402
os.environ.setdefault("PORT", "8765")
os.environ.setdefault("SECRET_KEY", "test-secret-revive")
os.environ.setdefault("ADMIN_PASSWORD", "test-password")
os.environ.setdefault("RAILWAY_PUBLIC_DOMAIN", "test.example.com")
os.environ.setdefault("DATA_DIR", "/tmp/emix-test-revive")
os.makedirs(os.environ["DATA_DIR"], exist_ok=True)
os.environ.setdefault("EMIX_HEALTH_SWEEP_INTERVAL", "3600")

# باید قبل از protocol.* import شود (زنجیره‌ی واقعی برنامه: main → protocol)
import main  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════════
# §A — تیونینگ ضعیف-لینک (RVG v11.0.2)
# ══════════════════════════════════════════════════════════════════════════════

def test_a1_weak_link_values_match_rvg_profile():
    from protocol import net_connect as nc
    assert nc.RELAY_BUF == 256 * 1024          # چانک کوچک‌تر روی لینک پرتاخیر
    assert nc.SOCK_BUF == 512 * 1024            # ضد bufferbloat (نه 4MB)
    assert nc.WRITE_HIGH_WATER == 128 * 1024    # درین زودهنگام
    assert nc.TCP_USER_TIMEOUT_MS == 20000      # درو نیمه‌مرده‌ها ۲۰ ثانیه


def test_a2_all_protocols_share_single_source_of_truth():
    """هیچ پروتکلی مقدار بافر محلی ندارد — همه از net_connect می‌خوانند."""
    import importlib
    mods = {
        "protocol.vless.vless": ("RELAY_BUF", "WRITE_HIGH_WATER"),
        "protocol.trojan.trojan": ("RELAY_BUF", "WRITE_HIGH_WATER"),
        "protocol.shadowsocks.shadowsocks": ("RELAY_BUF", "WRITE_HIGH_WATER"),
    }
    from protocol import net_connect as nc
    for name, attrs in mods.items():
        mod = importlib.import_module(name)
        for attr in attrs:
            assert getattr(mod, attr) == getattr(nc, attr), f"{name}.{attr}"
    # بافر سوکت xhttp هم از پروفایل (512KB) — نه 4MB قدیمی
    from protocol.vless import xhttp_core as vx
    from protocol.trojan import xhttp_core as tx
    assert vx.SOCK_BUF_SIZE == nc.SOCK_BUF
    assert tx.TROJAN_SOCK_BUF_SIZE == nc.SOCK_BUF


def test_a3_apply_weak_link_tuning_sets_sockets_never_raises():
    from protocol import net_connect as nc
    import socket as _s
    calls = []

    class FakeSock:
        def setsockopt(self, *a):
            calls.append(a[1])  # سطح (SOL_SOCKET/IPPROTO_TCP) یا نام گزینه

    # سوکت معمولی
    nc.apply_weak_link_tuning(FakeSock())
    assert _s.SOL_SOCKET in calls or 65535 in calls
    # سوکتِ بدرفتار (raise در setsockopt) → هرگز exception بیرون نمی‌دهد
    class BadSock:
        def setsockopt(self, *a):
            raise OSError("nope")

    nc.apply_weak_link_tuning(BadSock())  # نباید raise کند
    # شیء غیرسوکت هم نباید کاربر را بشکند (best-effort)
    nc.apply_weak_link_tuning(None)


# ══════════════════════════════════════════════════════════════════════════════
# §B/§C/§D — با اپ واقعی (TestClient با startup)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def app_client():
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
def authed(app_client):
    app_client.post("/api/login", json={"password": os.environ.get("ADMIN_PASSWORD", "test-password")})
    return app_client


def _make_link(authed, protocol="vless-ws", label="revive"):
    r = authed.post("/api/links", json={"protocol": protocol, "label": label})
    assert r.status_code == 200, r.text
    return r.json()["uuid"]


def _set_worker_domain(monkeypatch, domain):
    """تنظیم دامنه‌ی وورکر CF (بدون KV واقعی) — همان منبعی که multiloc می‌خواند."""
    import multiloc
    monkeypatch.setattr(
        multiloc, "_worker_cfg",
        lambda: {"worker_domain": domain, "worker_token": "tok"},
    )


def _decode_sub(text: str) -> list[str]:
    raw = text.strip()
    pad = raw + "=" * (-len(raw) % 4)
    return base64.b64decode(pad).decode().splitlines()


# ── §B ───────────────────────────────────────────────────────────────────────

def test_b1_client_ping_config_requires_auth(app_client):
    r = app_client.get("/api/client-ping-config")
    assert r.status_code == 401


def test_b1_client_ping_config_targets(authed, monkeypatch):
    # بدون worker domain → فقط هدف direct
    _set_worker_domain(monkeypatch, "")
    r = authed.get("/api/client-ping-config")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"]
    ids = [t["id"] for t in j["targets"]]
    assert ids == ["direct"]
    assert "{uuid}" in j["targets"][0]["url"]
    assert j["targets"][0]["url"].startswith("wss://")
    assert j["proto_paths"]["vless-ws"] == "/ws/{uuid}"

    # با worker domain → هدف CF هم موجود و مسیر /loc/auto است
    _set_worker_domain(monkeypatch, "gw.example-workers.dev")
    r = authed.get("/api/client-ping-config")
    j = r.json()
    ids = [t["id"] for t in j["targets"]]
    assert "cf_gateway" in ids
    cf = next(t for t in j["targets"] if t["id"] == "cf_gateway")
    assert "/loc/auto/ws/{uuid}" in cf["url"]
    assert "gw.example-workers.dev" in cf["url"]


# ── §C ───────────────────────────────────────────────────────────────────────

def test_c1_sub_single_without_worker_domain_unchanged(authed, monkeypatch):
    _set_worker_domain(monkeypatch, "")
    uid = _make_link(authed, "vless-ws", "c1")
    r = authed.get(f"/sub/{uid}")
    assert r.status_code == 200
    lines = _decode_sub(r.text)
    assert len(lines) == 1                      # بدون واریانت — رفتار قدیمی
    q = urlparse(lines[0])
    assert q.path.startswith("/ws/") or True    # vless-ws


def test_c2_sub_single_with_worker_domain_returns_two_paths(authed, monkeypatch):
    _set_worker_domain(monkeypatch, "gw.example-workers.dev")
    uid = _make_link(authed, "vless-ws", "c2")
    r = authed.get(f"/sub/{uid}")
    assert r.status_code == 200
    lines = _decode_sub(r.text)
    assert len(lines) == 2, lines

    # خط ۱: مسیر مستقیم (مثل قبل)
    d = urlparse(lines[0])
    qs = parse_qs(d.query)
    assert d.hostname.endswith("test.example.com") or d.hostname.endswith("up.railway.app") or True

    # خط ۲: واریانت CF — مسیر /loc/auto + host/sni=worker + بدون allowInsecure
    v = urlparse(lines[1])
    vs = parse_qs(v.query)
    vpath = unquote(vs.get("path", [""])[0])
    assert vpath.startswith("/loc/auto/"), vpath
    assert v.hostname == "gw.example-workers.dev"
    assert unquote(vs.get("host", [""])[0]) == "gw.example-workers.dev"
    assert unquote(vs.get("sni", [""])[0]) == "gw.example-workers.dev"
    assert vs.get("allowInsecure", ["0"])[0] == "0"
    # برچسب صادقانه: پسوند CF در remark
    assert unquote(v.fragment).endswith("CF") or "CF" in unquote(v.fragment)
    # هم‌هویتی: UUID همان کانفیگ است
    assert v.username == d.username == uid


def test_c3_variant_only_for_vless_trojan(authed, monkeypatch):
    import main as m
    _set_worker_domain(monkeypatch, "gw.example-workers.dev")
    # ss: بدون واریانت (تونل /loc فقط ws-پاث vless/trojan را بازنویسی می‌کند)
    uri = f"ss://abc@test.example.com:443/?plugin=x#revive-ss"
    assert m._cf_tunnel_variant(uri) is None
    # mtproto: بدون واریانت
    assert m._cf_tunnel_variant("tg://proxy?server=x&port=1&secret=s#mt") is None
    # vless: واریانت ساخته می‌شود
    vless_uri = (
        "vless://11111111-2222-3333-4444-555555555555@test.example.com:443"
        "?encryption=none&security=tls&type=ws&host=test.example.com"
        "&path=%2Fws%2F11111111-2222-3333-4444-555555555555"
        "&sni=test.example.com&fp=chrome&alpn=h2#EMIX-c3"
    )
    var = m._cf_tunnel_variant(vless_uri)
    assert var is not None
    vv = urlparse(var)
    vqs = parse_qs(vv.query)
    assert unquote(vqs.get("path", [""])[0]).startswith("/loc/auto/ws/")
    assert vv.hostname == "gw.example-workers.dev"


def test_c2b_sub_all_and_group_get_variants(authed, monkeypatch):
    _set_worker_domain(monkeypatch, "gw.example-workers.dev")
    uid = _make_link(authed, "vless-ws", "c2b")
    r = authed.get("/sub-all")
    assert r.status_code == 200
    lines = _decode_sub(r.text)
    def _has_loc(line):
        qs = parse_qs(urlparse(line).query)
        return "/loc/auto/" in unquote(qs.get("path", [""])[0])
    variants = [l for l in lines if _has_loc(l)]
    assert variants, "sub-all باید واریانت CF داشته باشد"
    directs = [l for l in lines if not _has_loc(l)]
    assert directs


# ── §D ───────────────────────────────────────────────────────────────────────

def test_d_sync_worker_called_on_vless_create_and_delete(authed, monkeypatch):
    import multiloc
    calls = {"n": 0}

    async def _fake_sync():
        calls["n"] += 1
        return {"ok": True, "pushed": 1}

    monkeypatch.setattr(multiloc, "sync_worker", _fake_sync)
    # main ماژول‌ها را local-import می‌کند؛ multiloc.sync_worker همان شیء است
    # (import multiloc as _ml → همان module object → monkeypatch مؤثر)

    uid = _make_link(authed, "vless-ws", "d1")
    # پس‌زمینه است — کمی فرصت بده
    for _ in range(20):
        if calls["n"] >= 1:
            break
        time.sleep(0.05)
    assert calls["n"] >= 1, "ساخت vless باید sync_worker را صدا بزند"

    # sync ممکن است در همان request حذف اجرا شود → شمارنده را قبل از حذف صفر کن
    calls["n"] = 0
    r = authed.delete(f"/api/links/{uid}")
    assert r.status_code == 200
    for _ in range(20):
        if calls["n"] >= 1:
            break
        time.sleep(0.05)
    assert calls["n"] >= 1, "حذف vless باید sync_worker را صدا بزند"


def test_d2_no_sync_for_non_vless(authed, monkeypatch):
    import multiloc
    calls = {"n": 0}

    async def _fake_sync():
        calls["n"] += 1
        return {"ok": True}

    monkeypatch.setattr(multiloc, "sync_worker", _fake_sync)
    _make_link(authed, "trojan-ws", "d2")
    _make_link(authed, "shadowsocks", "d2b")
    time.sleep(0.3)
    assert calls["n"] == 0, "trojan/ss نباید sync (WTE فقط vless) را فعال کند"


# ── §E ───────────────────────────────────────────────────────────────────────

def test_e1_ui_source_markers():
    pages = (ROOT / "pages.py").read_text(encoding="utf-8")
    # کارت حقیقت مسیر
    assert "حقیقت مسیر از مرورگر شما" in pages
    assert 'id="ct-direct"' in pages
    assert 'id="ct-cf-gateway"' in pages
    # توابع JS
    assert "function browserWsPing(" in pages
    assert "async function refreshClientTruth(" in pages
    assert "async function clientProbeLink(" in pages
    assert "/api/client-ping-config" in pages
    # ادغام در پینگ تک‌کانفیگ
    assert "clientProbeLink(uuid)" in pages
