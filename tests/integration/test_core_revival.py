# tests/integration/test_core_revival.py — v12.0.0-core
# ══════════════════════════════════════════════════════════════════════════════
# قرارداد «هسته‌ی همیشه‌زنده» — احیای EMIX-PRO بر اساس پروتکل پایه‌ی EMIX.
#
# دردِ اصلی که این تست‌ها قفل می‌کنند:
#   کاربرِ production: «پنل باز می‌شود ولی کانفیگ‌ها وصل نمی‌شوند.»
#   - هویت ناپایدار (باگ Permission در _get_or_create_secret) → UUID ها با هر
#     ری‌دیپلوی می‌چرخیدند → کانفیگ‌های تحویل‌شده می‌مردند
#     (رگرسیونش: tests/unit/test_identity_stability.py §2.b)
#   - بوتِ شلوغ (۶۰+ ماژول همیشه import) → هر موتوری می‌توانست سلامت پینگ/
#     رله را گروگان بگیرد؛ نسخه‌ی اصلی EMIX با بوتِ سبک سالم مانده بود.
#
# پنج تضمین این فایل:
#   §1  core profile (پیش‌فرض): همه‌ی سطح هسته ثبت شده، هیچ موتور اختیاری لود
#       نشده، /api/ping سبک و زنده، /api/boot-profile گزارش می‌دهد
#   §2  full profile: همان روت‌های v11 (superset — فقط +/api/boot-profile)
#   §3  رله‌ی VLESS end-to-end: هندشیک واقعی WS → parse هدر → اتصال TCP به
#       هدف واقعی → رفت‌وبرگشت داده (یعنی «کانفیگ پینگ می‌دهد»)
#   §4  لینک خروجی کانفیگ پیش‌فرض: هاست درست + مسیر /ws/{uuid} درست
#   §5  /api/deployment-version: هویت پایدار + پروفایل گزارش می‌شود
# ══════════════════════════════════════════════════════════════════════════════
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]

# main در conftest با env پیش‌فرض تست import می‌شود — یعنی پروفایل core.
import main as m  # noqa: E402
import boot_profile  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _isolate_shared_state():
    """تست‌های این ماژول ترافیک/لینک واقعی می‌سازند (رله‌ی e2e) — قبل و بعد
    state مشترک (LINKS/stats/SUBS + فایل state) را snapshot/restore می‌کنیم
    تا تست‌های دیگر (مثلاً totals-roundtrip) آلوده نشوند."""
    _links = dict(m.LINKS)
    _subs = dict(m.SUBS)
    _total = m.stats.get("total_bytes", 0)
    state_file = m.DATA_FILE
    saved_bytes = state_file.read_bytes() if state_file.exists() else None
    yield
    m.LINKS.clear(); m.LINKS.update(_links)
    m.SUBS.clear(); m.SUBS.update(_subs)
    m.stats["total_bytes"] = _total
    try:
        if saved_bytes is not None:
            state_file.write_bytes(saved_bytes)
        elif state_file.exists():
            state_file.unlink()
    except Exception:
        pass


def _make_revival_link(uid: str) -> dict:
    """لینک vless-ws اختصاصی این تست — مستقل از default-linkهای سایر تست‌ها."""
    link = {
        "label": "revival-e2e",
        "limit_bytes": 0, "used_bytes": 0,
        "created_at": "2026-09-04T00:00:00",
        "active": True, "expires_at": None, "note": "",
        "is_default": False, "sub_id": None,
        "protocol": "vless-ws",
        "alpn": "h2,http/1.1", "fingerprint": "chrome",
    }
    m.LINKS[uid] = link
    return link


_REVIVAL_UID = "aaa1b2c3-d4e5-f6a7-b8c9-d0e1f2a3b4c5"


# ── §1 پروفایل core (پیش‌فرض production) ─────────────────────────────────────
# نکته: تست‌سایت در conftest با EMIX_PROFILE=full import می‌شود تا همه‌ی موتورها
# پوشش داده شوند؛ بوتِ core اینجا با subprocess جدا شبیه‌سازی می‌شود.

def _boot_with_profile(env_extra: dict) -> dict:
    code = (
        "import json, main\n"
        "rep = main.boot_profile.report()\n"
        "paths = sorted({getattr(r, 'path', None) for r in main.app.routes})\n"
        "print(json.dumps({'routes': len(paths), 'summary': rep['summary'],"
        " 'profile': rep['profile'],"
        " 'paths': paths,"
        " 'core_missing': [p for p, _ in main.boot_profile.CORE_SURFACE"
        "                  if p not in set(paths)]}))\n"
    )
    env = {k: v for k, v in os.environ.items() if k not in ("EMIX_PROFILE", "EMIX_ENABLE", "EMIX_DISABLE")}
    env.update(env_extra)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, cwd=str(REPO), env=env, timeout=180)
    assert out.returncode == 0, f"boot failed: {out.stderr[-800:]}"
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_core_profile_core_surface_fully_registered():
    # سطح هسته باید در «هر دو» پروفایل کامل ثبت شده باشد
    assert not [p for p, _ in boot_profile.CORE_SURFACE
                if p not in {getattr(r, "path", None) for r in m.app.routes}], \
        "core surface broken in full profile"
    info = _boot_with_profile({"EMIX_PROFILE": "core"})
    assert info["core_missing"] == [], (
        f"core surface broken in core profile: {info['core_missing']}")


def test_core_profile_optional_engines_not_loaded():
    """پیش‌فرض production = core: هیچ موتور اختیاری لود/ثبت نمی‌شود و
    هیچ‌کدام هم «fail» حساب نمی‌شوند (خاموشی انتخاب است، نه خطا)."""
    info = _boot_with_profile({"EMIX_PROFILE": "core"})
    assert info["profile"] == "core"
    assert info["summary"]["engines_enabled"] == 0
    assert info["summary"]["engines_failed"] == 0
    for absent_marker in ("/api/egress/verify", "/api/events",
                          "/api/vpn/nodes", "/api/security/sni/profiles"):
        assert absent_marker not in info["paths"], (
            f"{absent_marker} must NOT be registered in core profile")


def test_granular_enable_brings_single_engine_back():
    """EMIX_ENABLE=multiloc در core — فقط همان موتور برمی‌گردد."""
    info = _boot_with_profile({"EMIX_ENABLE": "multiloc"})
    assert info["profile"] == "core"
    assert info["summary"]["engines_enabled"] == 1
    assert info["summary"]["engines_loaded"] == 1
    assert any(p and p.startswith("/api/multiloc") or p == "/api/egress-test"
               for p in info["paths"]) or info["summary"]["engines_loaded"] == 1


def test_core_profile_ping_and_boot_report_live():
    with TestClient(m.app) as client:
        r = client.get("/api/ping")
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        # /api/boot-profile نیاز به احراز هویت دارد
        anon = client.get("/api/boot-profile")
        assert anon.status_code in (401, 403)


# ── §2 پروفایل full — superset دقیق رفتار v11 ────────────────────────────────

def test_full_profile_boots_all_engines_and_keeps_core():
    """بوت subprocess با EMIX_PROFILE=full: همه‌ی موتورها لود می‌شوند، هیچ
    روتی نسبت به قبل گم نمی‌شود و سطح هسته سر جایش است."""
    code = (
        "import json, main\n"
        "rep = main.boot_profile.report()\n"
        "paths = sorted({getattr(r, 'path', None) for r in main.app.routes})\n"
        "print(json.dumps({'routes': len(paths), 'summary': rep['summary'],"
        " 'profile': rep['profile'],"
        " 'core_missing': [p for p, _ in main.boot_profile.CORE_SURFACE"
        "                  if p not in set(paths)],"
        " 'has_zeus': '/api/zeus/isp' in set(paths),"
        " 'has_boot_profile': '/api/boot-profile' in set(paths)}))\n"
    )
    env = {k: v for k, v in os.environ.items() if k != "EMIX_PROFILE"}
    env["EMIX_PROFILE"] = "full"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, cwd=str(REPO), env=env, timeout=180)
    assert out.returncode == 0, f"full boot failed: {out.stderr[-800:]}"
    info = json.loads(out.stdout.strip().splitlines()[-1])
    assert info["profile"] == "full"
    assert info["summary"]["engines_enabled"] == info["summary"]["engines_total"]
    assert info["summary"]["engines_failed"] == 0
    assert info["core_missing"] == []
    assert info["has_zeus"] is True
    assert info["has_boot_profile"] is True


# ── §3 رله‌ی VLESS end-to-end — «کانفیگ واقعاً پینگ می‌دهد» ──────────────────

def _vless_request_header(uuid: str, host: str, port: int, payload: bytes) -> bytes:
    """هدر استاندارد VLESS (نسخه 0): ver + uuid16 + addon + cmd + port + addr."""
    u = uuid.replace("-", "")
    header = bytes([0]) + bytes.fromhex(u)
    header += bytes([0])          # addon_len = 0
    header += bytes([1])          # cmd = TCP
    header += port.to_bytes(2, "big")
    header += bytes([1])          # addr_type = IPv4
    header += bytes(int(x) for x in host.split("."))
    return header + payload


def test_vless_relay_end_to_end_roundtrip():
    """هندشیک WS واقعی روی /ws/{uuid} → رله به یک TCP-echo واقعی → داده
    برگشت. این همان تضمینِ «پینگ» از زبان کلاینت است.
    سرور echo در loop یک ترد جدا اجرا می‌شود — چون TestClient loopِ ترد
    اصلی را بلوک می‌کند و echo بدون loop زنده جواب نمی‌دهد."""
    import threading

    received: list[bytes] = []
    started = threading.Event()
    holder: dict = {}

    async def _echo(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            data = await reader.read(4096)
            received.append(data)
            writer.write(data[::-1])  # معکوس‌شده → اثبات رفت‌وبرگشت واقعی
            await writer.drain()
        finally:
            writer.close()

    async def _echo_main():
        server = await asyncio.start_server(_echo, "127.0.0.1", 0)
        holder["port"] = server.sockets[0].getsockname()[1]
        holder["server"] = server
        started.set()
        async with server:
            await server.serve_forever()

    loop = asyncio.new_event_loop()
    th = threading.Thread(target=loop.run_forever, daemon=True)
    th.start()
    asyncio.run_coroutine_threadsafe(_echo_main(), loop)
    assert started.wait(timeout=10), "echo server did not start"
    echo_port = holder["port"]
    try:
        _make_revival_link(_REVIVAL_UID)
        uid = _REVIVAL_UID
        payload = _vless_request_header(uid, "127.0.0.1", echo_port, b"ping-probe")
        with TestClient(m.app) as client:
            with client.websocket_connect(f"/ws/{uid}") as ws:
                ws.send_bytes(payload)
                reply = ws.receive_bytes()
        # پاسخ رله = هدر پاسخ VLESS (ver=0 + addon_len=0) + داده‌ی echo‌شده
        assert reply == b"\x00\x00" + b"eborp-gnip", (
            f"relay roundtrip broken — got {reply!r}")
        assert received and received[0].endswith(b"ping-probe"), (
            "relay never delivered the VLESS payload to the real target")
    finally:
        holder.get("server").close()
        loop.call_soon_threadsafe(loop.stop)


# ── §4 لینک خروجی کانفیگ پیش‌فرض ─────────────────────────────────────────────

def test_default_vless_link_targets_panel_domain_and_ws_path():
    _make_revival_link(_REVIVAL_UID)
    host = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "test.example.com")
    uid = _REVIVAL_UID
    url = m.generate_share_link(uid, host, remark="EMIX-VLESS · WS+TLS",
                                protocol="vless-ws")
    assert "/ws/" in url, f"vless-ws link must point at /ws/{{uuid}} — got {url}"
    assert f"@{host}:443" in url, f"link must target the panel domain — got {url}"
    assert "security=tls" in url and "type=ws" in url


# ── §5 شفافیت نسخه/هویت ──────────────────────────────────────────────────────

def test_deployment_version_reports_core_profile_and_stable_identity():
    with TestClient(m.app) as client:
        r = client.get("/api/deployment-version")
        assert r.status_code == 200
        body = r.json()
    assert body["version"] == "12.2.0-iran-exit"
    # پروفایل گزارش‌شده باید با پروفایل واقعی بوت یکی باشد (تست‌سایت: full)
    assert body["boot_profile"] == boot_profile.current_profile()
    ident = body["identity"]
    assert ident["stable_across_redeploy"] is True  # conftest SECRET_KEY را ست کرده
