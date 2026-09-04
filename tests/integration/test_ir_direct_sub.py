# tests/integration/test_ir_direct_sub.py — v12.1.0 /sub-json (IR-Direct)
# ══════════════════════════════════════════════════════════════════════════════
# e2e روی اپ واقعی: هسته (seed دیتاست + /sub-json) باید بدون هیچ موتور
# اختیاری کار کند — این همان «داخلی کردن مصرف حتی با کانفیگ» است.
#   §1 sing-box: 200 + قواعد واقعی از دیتاست seed (2500+ پیشوند)
#   §2 xray: 200 + routing.rules
#   §3 صداقت: ss → 422 SPLIT_TUNNEL_NOT_SUPPORTED · uuid نامعلوم → 404
#   §4 SNI spoof لینک → منعکس در کانفیگ کلاینت
#   §5 /api/links فیلد sub_json_urls را می‌دهد
# ══════════════════════════════════════════════════════════════════════════════
import os

import pytest
from fastapi.testclient import TestClient

import main as m  # noqa: E402


_REVIVAL_UID = "b0a1c2d3-e4f5-6789-abcd-ef0123456789"


@pytest.fixture(scope="module", autouse=True)
def _isolate_shared_state():
    _links = dict(m.LINKS)
    _subs = dict(m.SUBS)
    state_file = m.DATA_FILE
    saved_bytes = state_file.read_bytes() if state_file.exists() else None
    yield
    m.LINKS.clear(); m.LINKS.update(_links)
    m.SUBS.clear(); m.SUBS.update(_subs)
    try:
        if saved_bytes is not None:
            state_file.write_bytes(saved_bytes)
    except Exception:
        pass


def _make_link(uid: str, protocol: str = "vless-ws", **extra) -> None:
    m.LINKS[uid] = {
        "label": "ir-direct-e2e", "limit_bytes": 0, "used_bytes": 0,
        "created_at": "2026-09-04T00:00:00", "active": True,
        "expires_at": None, "note": "", "is_default": False, "sub_id": None,
        "protocol": protocol, "alpn": "h2,http/1.1", "fingerprint": "chrome",
        **extra,
    }


def test_singbox_sub_json_with_real_dataset():
    _make_link(_REVIVAL_UID)
    with TestClient(m.app) as client:
        r = client.get(f"/sub-json/{_REVIVAL_UID}?client=singbox")
    assert r.status_code == 200
    cfg = r.json()
    # قواعد باید از دیتاست واقعی seed پر شده باشند (startup core سeed را لود می‌کند)
    ip_rule = next(r2 for r2 in cfg["route"]["rules"] if "ip_cidr" in r2)
    assert len(ip_rule["ip_cidr"]) >= 2000, (
        f"IR dataset not loaded — only {len(ip_rule['ip_cidr'])} prefixes")
    assert r.headers.get("x-emix-ir-rules", "").startswith(
        f"prefixes={len(ip_rule['ip_cidr'])}")
    proxy = next(o for o in cfg["outbounds"] if o["tag"] == "proxy")
    assert proxy["server"] == os.environ["RAILWAY_PUBLIC_DOMAIN"]
    assert proxy["transport"]["path"] == f"/ws/{_REVIVAL_UID}"


def test_xray_sub_json_with_routing_rules():
    _make_link(_REVIVAL_UID)
    with TestClient(m.app) as client:
        r = client.get(f"/sub-json/{_REVIVAL_UID}?client=xray")
    assert r.status_code == 200
    cfg = r.json()
    ip_rule = next(r2 for r2 in cfg["routing"]["rules"] if "ip" in r2)
    assert len(ip_rule["ip"]) >= 2000 and ip_rule["outboundTag"] == "direct"
    assert cfg["outbounds"][0]["settings"]["vnext"][0]["address"] == \
        os.environ["RAILWAY_PUBLIC_DOMAIN"]


def test_honest_rejections():
    ss_uid = "c0a1c2d3-e4f5-6789-abcd-ef0123456789"
    _make_link(ss_uid, protocol="shadowsocks")
    with TestClient(m.app) as client:
        r_ss = client.get(f"/sub-json/{ss_uid}?client=singbox")
        r_unknown = client.get("/sub-json/00000000-0000-0000-0000-000000000000")
        r_bad = client.get(f"/sub-json/{_REVIVAL_UID}?client=clash")
    assert r_ss.status_code == 422
    assert r_ss.json()["error"] == "SPLIT_TUNNEL_NOT_SUPPORTED"
    assert r_unknown.status_code == 404
    assert r_bad.status_code == 422


def test_spoofed_link_reflected_in_sub_json():
    spoof_uid = "d0a1c2d3-e4f5-6789-abcd-ef0123456789"
    _make_link(spoof_uid, spoof_sni_enabled=True, spoof_sni="dl.example.ir")
    with TestClient(m.app) as client:
        r = client.get(f"/sub-json/{spoof_uid}?client=singbox")
    assert r.status_code == 200
    proxy = next(o for o in r.json()["outbounds"] if o["tag"] == "proxy")
    assert proxy["tls"]["server_name"] == "dl.example.ir"
    assert proxy["tls"]["insecure"] is True  # حالت B — بدون CDN


def test_api_links_exposes_sub_json_urls():
    _make_link(_REVIVAL_UID)
    ss_uid = "c0a1c2d3-e4f5-6789-abcd-ef0123456789"
    os.environ.setdefault("ADMIN_PASSWORD", "test-password")
    with TestClient(m.app) as client:
        client.post("/api/login", json={"password": os.environ.get("ADMIN_PASSWORD")})
        r = client.get("/api/links")
    assert r.status_code == 200
    raw = r.json().get("links", r.json())
    by_uid = {l["uuid"]: l for l in (raw if isinstance(raw, list) else raw.values())}
    assert by_uid[_REVIVAL_UID]["sub_json_urls"]["singbox"].endswith("client=singbox")
    assert by_uid[_REVIVAL_UID]["sub_json_urls"]["xray"].endswith("client=xray")
    assert by_uid[ss_uid]["sub_json_urls"] is None  # ss → صداقت
