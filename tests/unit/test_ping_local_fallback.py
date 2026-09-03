# tests/unit/test_ping_local_fallback.py
# ══════════════════════════════════════════════════════════════════════════════
# v11.5.1-hotfix-identity — regression tests for honest probe vantage fallback.
#
# مشکل: برخی پلتفرم‌ها (Railway hairpin) connection سرویس به دامنه‌ی عمومی خودش
# را مسدود می‌کنند → health-sweep همه‌ی لینک‌ها را UNREACHABLE نشان می‌دهد، در
# حالی که کلاینت‌های واقعی از بیرون وصل می‌شوند («همه قطع شدند» در UI).
#
# FIX: اگر پروب مسیر عمومی شکست خورد، یک‌بار همان تونل از آدرس محلی پنل سنجیده
# می‌شود؛ نتیجه ok ولی با برچسب صادقانه fallback=local + fallback_note.
# هیچ‌وقت شواهد جعل نمی‌شود — فقط vantage دوم با برچسب.
# ══════════════════════════════════════════════════════════════════════════════
import pytest

# ترتیب حیاتی: main اول (ثبت کامل route ها)، بعد link_health —
# در غیر این صورت circular import رخ می‌دهد (link_health ← main ← link_health).
import main  # noqa: F401  (fully initializes the app + engines)
import link_health as lh


PUBLIC_BASE = "wss://panel.example.com"
LOCAL_BASE = "ws://127.0.0.1:8000"


@pytest.fixture
def vless_link():
    return {
        "uuid": "11111111-2222-3333-4444-555555555555",
        "protocol": "vless-ws",
        "active": True,
        "limit_bytes": 0,
        "used_bytes": 0,
        "expires_at": None,
    }


def _patch(monkeypatch, public_result, local_result):
    """پروب عمومی/محلی را با نتایج مصنوعی جایگزین می‌کند و get_host را عمومی
    می‌کند تا مسیر fallback فعال شود (بدون شبکه‌ی واقعی)."""
    async def fake_ws(kind, uid, link, use_ed=False, ws_base=None, no_verify=False,
                      path_prefix=""):
        if ws_base and ws_base.startswith("ws://127.0.0.1"):
            return dict(local_result)
        return dict(public_result)

    monkeypatch.setattr(lh, "_probe_ws_tunnel", fake_ws)
    monkeypatch.setattr(lh, "get_host", lambda: "panel.example.com")


@pytest.mark.asyncio
async def test_public_fail_local_ok_is_rescued_with_label(vless_link, monkeypatch):
    """پروب عمومی connect-refused، محلی OK → نتیجه ok=True با برچسب local."""
    _patch(monkeypatch,
           public_result={"ok": False, "detail": "Connect call failed"},
           local_result={"ok": True, "ws_ms": 5.1, "e2e_ms": 1.2,
                         "reply": "HTTP/1.1 200 OK"})
    out = await lh._run_link_ping(vless_link["uuid"], vless_link)
    assert out["ok"] is True
    assert out.get("fallback") == "local"
    assert "fallback_note" in out and out["fallback_note"]
    assert out.get("ws_ms") == 5.1
    # شاهد شکست عمومی در note حفظ شده (صادقانه)
    assert "Connect call failed" in out["fallback_note"]


@pytest.mark.asyncio
async def test_public_fail_local_fail_stays_dead(vless_link, monkeypatch):
    """هر دو vantage شکست خورده → ok=False (بدون نجات ساختگی)."""
    _patch(monkeypatch,
           public_result={"ok": False, "detail": "Connect call failed"},
           local_result={"ok": False, "detail": "ConnectionRefused local too"})
    out = await lh._run_link_ping(vless_link["uuid"], vless_link)
    assert out["ok"] is False
    assert out.get("fallback_attempted") == "local"
    assert "fallback" not in out


@pytest.mark.asyncio
async def test_no_fallback_when_host_is_local(vless_link, monkeypatch):
    """host= localhost → پروب اصلاً عمومی نیست → fallback نباید اجرا شود."""
    async def fake_ws(kind, uid, link, use_ed=False, ws_base=None, no_verify=False,
                      path_prefix=""):
        return {"ok": False, "detail": "boom"}
    monkeypatch.setattr(lh, "_probe_ws_tunnel", fake_ws)
    monkeypatch.setattr(lh, "get_host", lambda: "localhost")
    out = await lh._run_link_ping(vless_link["uuid"], vless_link)
    assert out["ok"] is False
    assert "fallback" not in out


@pytest.mark.asyncio
async def test_no_fallback_when_public_ok(vless_link, monkeypatch):
    """پروب عمومی موفق → هیچ fallback ای لازم نیست؛ نتیجه دست‌نخورده."""
    _patch(monkeypatch,
           public_result={"ok": True, "ws_ms": 12.0, "e2e_ms": 3.0,
                          "reply": "HTTP/1.1 200 OK"},
           local_result={"ok": True})
    out = await lh._run_link_ping(vless_link["uuid"], vless_link)
    assert out["ok"] is True
    assert "fallback" not in out
    assert out.get("ws_ms") == 12.0


@pytest.mark.asyncio
async def test_inactive_link_never_probed(vless_link, monkeypatch):
    """لینک غیرفعال → نتیجه فقط دلیل غیرفعالی؛ fallback هم نباید اجرا شود."""
    vless_link["active"] = False
    called = {"n": 0}

    async def fake_ws(*a, **k):
        called["n"] += 1
        return {"ok": True}

    monkeypatch.setattr(lh, "_probe_ws_tunnel", fake_ws)
    monkeypatch.setattr(lh, "get_host", lambda: "panel.example.com")
    out = await lh._run_link_ping(vless_link["uuid"], vless_link)
    assert out["ok"] is False
    assert "غیرفعال" in out["detail"]
    assert called["n"] == 0
