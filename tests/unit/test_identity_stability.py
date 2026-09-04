# tests/unit/test_identity_stability.py
# ══════════════════════════════════════════════════════════════════════════════
# v11.5.1-hotfix-identity — regression tests for the production outage
# «با تغییرات آخر همه‌ی کانفیگ‌ها قطع شدند».
#
# ROOT CAUSE that these tests pin down:
#   بدون Volume و بدون SECRET_KEY، هر ری‌دیپلوی (که هر git-push تریگر می‌کند)
#   یک secret تازه تولید می‌کرد → UUID کانفیگ‌های پیش‌فرض (مشتق از secret)
#   عوض می‌شد → همه‌ی کانفیگ‌های تحویل‌شده به کلاینت‌ها با 1008 رد می‌شدند.
#
# FIX: زنجیره‌ی هویت — SECRET_KEY env → فایل Volume → RAILWAY_SERVICE_ID /
# EMIX_IDENTITY_SEED (پایدار بین ری‌دیپلوی، بدون Volume) → رندوم (هشدار).
# ══════════════════════════════════════════════════════════════════════════════
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _boot_identity(env_extra: dict) -> dict:
    """Import main.py در یک subprocess تمیز با env دلخواه؛ خروجی:
    {secret, identity_source} — همان چیزی که دیپلوی واقعی تجربه می‌کند."""
    code = (
        "import json, main\n"
        "print(json.dumps({'secret': main.CONFIG['secret'],"
        " 'source': main.IDENTITY_SOURCE}))\n"
    )
    env = {k: v for k, v in os.environ.items()
           if k not in ("SECRET_KEY", "RAILWAY_SERVICE_ID", "EMIX_IDENTITY_SEED",
                        "DATA_DIR", "RAILWAY_PUBLIC_DOMAIN")}
    env.update(env_extra)
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
        cwd=str(REPO), env=env, timeout=120,
    )
    assert out.returncode == 0, f"boot failed: {out.stderr[-800:]}"
    return json.loads(out.stdout.strip().splitlines()[-1])


def _default_uuid_for(secret: str, prefix: str) -> str:
    """همان مشتق ensure_default_link — deterministic از secret."""
    base = hashlib.sha256(f"emix-default-{secret}".encode()).hexdigest()
    h = hashlib.sha256(f"{prefix}-{base}".encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


# ── 1. رگرسیون اصلی: ری‌دیپلوی بدون Volume نباید UUID ها را عوض کند ─────────

def test_redeploy_without_volume_keeps_uuids_with_railway_service_id():
    """دو دیپلوی «فRESH» (بدون Volume) با RAILWAY_SERVICE_ID ثابت →
    secret و UUID کانفیگ‌های پیش‌فرض باید یکسان بمانند.
    (قبل از فیکس: هر بوت UUID جدید → همه‌ی کانفیگ‌های قبلی قطع!)"""
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        r1 = _boot_identity({"RAILWAY_SERVICE_ID": "srv-fixed-123", "DATA_DIR": d1})
        r2 = _boot_identity({"RAILWAY_SERVICE_ID": "srv-fixed-123", "DATA_DIR": d2})
    assert r1["source"] == "railway_service_id"
    assert r2["source"] == "railway_service_id"
    assert r1["secret"] == r2["secret"], "identity must be stable across fresh deploys"
    for prefix in ("vless", "trojan", "ss"):
        assert _default_uuid_for(r1["secret"], prefix) == \
               _default_uuid_for(r2["secret"], prefix)


def test_different_service_ids_yield_different_uuids():
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        r1 = _boot_identity({"RAILWAY_SERVICE_ID": "srv-a", "DATA_DIR": d1})
        r2 = _boot_identity({"RAILWAY_SERVICE_ID": "srv-b", "DATA_DIR": d2})
    assert r1["secret"] != r2["secret"], "different services must not share identity"


# ── 2. اولویت‌ها (backward-compat حفظ شود) ───────────────────────────────────

def test_secret_key_env_wins_over_everything():
    with tempfile.TemporaryDirectory() as d:
        r = _boot_identity({"SECRET_KEY": "op-secret", "RAILWAY_SERVICE_ID": "srv-x",
                            "EMIX_IDENTITY_SEED": "seed-x", "DATA_DIR": d})
    assert r["secret"] == "op-secret"
    assert r["source"] == "secret_key_env"


def test_volume_secret_file_wins_over_env_seed():
    """دیپلوی موجود با Volume (فایل .rvg_secret) → رفتار قبلی بدون تغییر."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / ".rvg_secret").write_text("file-secret-stable", encoding="utf-8")
        r = _boot_identity({"RAILWAY_SERVICE_ID": "srv-x", "DATA_DIR": d})
    assert r["secret"] == "file-secret-stable"
    assert r["source"] == "secret_file"


def test_identity_seed_env_fallback():
    with tempfile.TemporaryDirectory() as d:
        r = _boot_identity({"EMIX_IDENTITY_SEED": "my-seed", "DATA_DIR": d})
    assert r["secret"] == "seed-v1:my-seed"
    assert r["source"] == "identity_seed_env"


def test_random_last_resort_is_labeled_unstable():
    with tempfile.TemporaryDirectory() as d:
        r = _boot_identity({"DATA_DIR": d})
    assert r["source"] == "random_no_seed"


# ── 2.b مسیر Permission-denied (باستندگی کل زنجیره) — حادثه‌ی production ────
# 🔴 ROOT CAUSE «پنل باز می‌شود ولی کانفیگ‌ها وصل نمی‌شوند»:
#   قبلاً DATA_DIR.mkdir داخل try بود؛ روی Railway بدون Volume (/data قابل
#   نوشتن نیست) خطای Permission کل زنجیره را می‌پراند و secret رندوم
#   برمی‌گشت — حتی اگر RAILWAY_SERVICE_ID موجود بود! نتیجه: هر ری‌دیپلوی
#   UUID همه‌ی کانفیگ‌های پیش‌فرض را عوض می‌کرد.
# این تست دقیقاً همان سناریو را بازسازی می‌کند: DATA_DIRِ غیرقابل‌نوشتن.

def _unwritable_dir(tmp_path) -> str:
    """مسیری که DATA_DIR.mkdir روی آن قطعی شکست می‌خورد (مستقل از پلتفرم):
    والد یک «فایل» است نه دایرکتوری → NotADirectoryError — همان رفتاری که
    «/data» غیرقابل‌نوشتن روی Railway بدون Volume تولید می‌کند."""
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("I am a file, not a directory", encoding="utf-8")
    return str(blocker / "data")


def test_unwritable_data_dir_still_uses_stable_railway_service_id(tmp_path):
    """(/data غیرقابل‌نوشتن) + RAILWAY_SERVICE_ID → secret باید پایدار و
    از نوع railway_service_id باشد — نه رندوم. (FIX v12.0.0-core)"""
    d = _unwritable_dir(tmp_path)
    r1 = _boot_identity({"RAILWAY_SERVICE_ID": "srv-fixed-123", "DATA_DIR": d})
    r2 = _boot_identity({"RAILWAY_SERVICE_ID": "srv-fixed-123", "DATA_DIR": d})
    assert r1["source"] == "railway_service_id", (
        f"identity must survive unwritable DATA_DIR — got {r1['source']}")
    assert r1["secret"] == r2["secret"], (
        "UUID rotation on redeploy without volume — the production outage bug is back")
    for prefix in ("vless", "trojan", "ss"):
        assert _default_uuid_for(r1["secret"], prefix) == \
               _default_uuid_for(r2["secret"], prefix)


def test_unwritable_data_dir_random_last_resort_is_labeled_unstable(tmp_path):
    """بدون هیچ seed و بدون دیسک → رندوم (ناگریز) ولی باید صادقانه
    «ناپایدار» برچسب بخورد — نه stable:true دروغین (FIX v12.0.0-core)."""
    d = _unwritable_dir(tmp_path)
    code = (
        "import json, main\n"
        "print(json.dumps({'source': main.IDENTITY_SOURCE,"
        " 'stable': main.IDENTITY_STABLE}))\n"
    )
    env = {k: v for k, v in os.environ.items()
           if k not in ("SECRET_KEY", "RAILWAY_SERVICE_ID", "EMIX_IDENTITY_SEED",
                        "DATA_DIR", "RAILWAY_PUBLIC_DOMAIN")}
    env["DATA_DIR"] = d
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
        cwd=str(REPO), env=env, timeout=120,
    )
    assert out.returncode == 0, f"boot failed: {out.stderr[-800:]}"
    info = json.loads(out.stdout.strip().splitlines()[-1])
    assert info["source"] == "random_no_seed"
    assert info["stable"] is False, "random identity must be labeled unstable"


# ── 3. public_host — ماندگاری دامنه‌ی خودآموخته بین ری‌استارت ────────────────

def test_public_host_saved_and_restored(tmp_path, monkeypatch):
    """بعد از ری‌دیپلوی، get_host() باید بلافاصله دامنه‌ی واقعی را برگرداند
    (نه localhost تا اولین بازدید از داشبورد)."""
    monkeypatch.delenv("RAILWAY_PUBLIC_DOMAIN", raising=False)
    os.environ["DATA_DIR"] = str(tmp_path)
    for var in ("SECRET_KEY", "RAILWAY_SERVICE_ID", "EMIX_IDENTITY_SEED"):
        os.environ.pop(var, None)
    import main as m
    m.DATA_DIR = m.Path(str(tmp_path))
    m.DATA_FILE = m.DATA_DIR / "rvg_state.json"

    m._LEARNED_PUBLIC_HOST = "emix-pro-production.up.railway.app"
    asyncio.run(m.save_state())
    saved = json.loads((tmp_path / "rvg_state.json").read_text(encoding="utf-8"))
    assert saved.get("public_host") == "emix-pro-production.up.railway.app"

    m._LEARNED_PUBLIC_HOST = None
    asyncio.run(m.load_state())
    assert m._LEARNED_PUBLIC_HOST == "emix-pro-production.up.railway.app"
    assert m.get_host() == "emix-pro-production.up.railway.app"


def test_public_host_restore_rejects_private_and_localhost(tmp_path):
    os.environ["DATA_DIR"] = str(tmp_path)
    for var in ("SECRET_KEY", "RAILWAY_SERVICE_ID", "EMIX_IDENTITY_SEED"):
        os.environ.pop(var, None)
    import main as m
    m.DATA_DIR = m.Path(str(tmp_path))
    m.DATA_FILE = m.DATA_DIR / "rvg_state.json"
    for bad in ("localhost", "127.0.0.1", "10.0.0.5", "192.168.1.4", "172.16.0.9"):
        (tmp_path / "rvg_state.json").write_text(
            json.dumps({"public_host": bad}), encoding="utf-8")
        m._LEARNED_PUBLIC_HOST = None
        asyncio.run(m.load_state())
        assert m._LEARNED_PUBLIC_HOST is None, f"{bad} must not be restored"


# ── 4. endpoint شفافیت هویت ──────────────────────────────────────────────────

def test_deployment_version_exposes_identity_block():
    from fastapi.testclient import TestClient
    import main as m
    with TestClient(m.app) as client:
        r = client.get("/api/deployment-version")
        assert r.status_code == 200
        ident = r.json().get("identity")
        assert ident and {"source", "stable_across_redeploy", "hint"} <= set(ident)
        assert isinstance(ident["stable_across_redeploy"], bool)
