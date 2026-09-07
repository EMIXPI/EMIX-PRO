# tests/test_phase51_boot_values.py
# ══════════════════════════════════════════════════════════════════════════════
# EMIX-PRO v13.6.0 — BOOT VALUES + VOLUME AUTO-ATTACH — پوشش درخواست مالک:
#   «مقادیر با هر دیپلوی/ری‌دیپلوی خودکار ست شوند» → کلید/URL پروژه baked +
#   materialize_defaults در هر boot + self-heal کلید Worker.
#   «Volume بعد از دیپلوی اتومات attach نمی‌شود» → تشخیص mount + پیوست
#   خودکار از طریق GraphQL ریلوی + ضد-حلقه + بنر/UI صادق.
#
# §1  worker_key — زنجیره‌ی اولویت DB → env → کلید پروژه
# §2  DEFAULT_SETTINGS — کلید پروژه به‌عنوان پیش‌فرض + mask در all_settings
# §3  materialize_defaults — در هر boot فقط کلیدهای غایب (idempotent/ایمن)
# §4  self-heal کلید Worker — کلید قدیمی ناسازگار → کلید پروژه + ذخیره DB
# §5  volume_bootstrap — تشخیص mount (mountinfo) + status صادق
# §6  ensure_volume — no-op ها + create موفق (mock GraphQL) + ضد-حلقه
# §7  منبع توکن — env RAILWAY_TOKEN مقدم بر فایل (volume_bootstrap._token)
# §8  سرور واقعی fresh-boot — مقادیر ست شده + /api/persistence/status + health-all
# §9  UI markers — بنر پایداری + سطر Volume + نوت کلید پروژه
# ══════════════════════════════════════════════════════════════════════════════

import importlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

_PROC_DIR = Path(tempfile.mkdtemp(prefix="p51_inproc_"))
os.environ["DATA_DIR"] = str(_PROC_DIR)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _reload_modules(tmp_path):
    """reload db (+schema) و worker_client با DATA_DIR تازه — ایزوله از بقیه‌ی سوئیت."""
    os.environ["DATA_DIR"] = str(tmp_path)
    from smart_routing import db as sdb
    importlib.reload(sdb)
    sdb.ensure_schema()
    from smart_routing import worker_client as wc
    importlib.reload(wc)
    return sdb, wc


def _reload_vb(tmp_path):
    """reload volume_bootstrap با DATA_DIR تازه (مسیر ماژول top-level)."""
    os.environ["DATA_DIR"] = str(tmp_path)
    import volume_bootstrap as vb
    importlib.reload(vb)
    return vb


def _login(base):
    req = urllib.request.Request(
        base + "/api/login", data=json.dumps({"password": "123456"}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.headers.get("Set-Cookie", "").split(";")[0]


def _api(base, cookie, method, path, body=None, timeout=90):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base + path, data=data, method=method,
        headers={"Cookie": cookie, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


def _boot_server(tmp_path, extra_env=None):
    port = _free_port()
    env = dict(os.environ)
    env.update({"PORT": str(port), "DATA_DIR": str(tmp_path),
                "ADMIN_PASSWORD": "123456", "PYTHONPATH": str(REPO)})
    env.pop("RAILWAY_PUBLIC_DOMAIN", None)
    env.pop("SMART_ROUTING_ENABLED", None)
    env.pop("SR_SIGNING_KEY", None)
    env.pop("RAILWAY_SERVICE_ID", None)
    env.pop("RAILWAY_TOKEN", None)
    env.update(extra_env or {})
    proc = subprocess.Popen([sys.executable, "main.py"], cwd=REPO, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base + "/api/ping", timeout=2) as r:
                if r.status == 200:
                    return proc, base
        except Exception:
            time.sleep(0.4)
    proc.kill()
    raise RuntimeError("server did not boot")


# ═══ §1 worker_key — زنجیره‌ی اولویت ═════════════════════════════════════════
class TestWorkerKeyChain:
    def test_fresh_db_falls_back_to_project_key(self, tmp_path):
        sdb, wc = _reload_modules(tmp_path)
        assert wc.worker_key() == wc.PROJECT_SIGNING_KEY, \
            "fresh-deploy بدون DB/env → کلید پروژه (با هر دیپلوی ست می‌شود)"

    def test_env_beats_project_key(self, tmp_path, monkeypatch):
        sdb, wc = _reload_modules(tmp_path)
        monkeypatch.setenv("SR_SIGNING_KEY", "env-key-51")
        importlib.reload(wc)
        assert wc.worker_key() == "env-key-51"
        monkeypatch.delenv("SR_SIGNING_KEY")

    def test_db_beats_env_and_project(self, tmp_path, monkeypatch):
        sdb, wc = _reload_modules(tmp_path)
        sdb.set_setting("worker_key", "db-key-51")
        monkeypatch.setenv("SR_SIGNING_KEY", "env-key-51")
        importlib.reload(wc)
        assert wc.worker_key() == "db-key-51"
        monkeypatch.delenv("SR_SIGNING_KEY")

    def test_key_source_honest(self, tmp_path, monkeypatch):
        sdb, wc = _reload_modules(tmp_path)
        assert wc.worker_key_source() == "project-default"
        monkeypatch.setenv("SR_SIGNING_KEY", "env-key-51")
        importlib.reload(wc)
        assert wc.worker_key_source() == "env"
        monkeypatch.delenv("SR_SIGNING_KEY")
        sdb.set_setting("worker_key", "db-key-51")
        importlib.reload(wc)
        assert wc.worker_key_source() == "db"

    def test_candidate_keys_unique_and_ordered(self, tmp_path, monkeypatch):
        sdb, wc = _reload_modules(tmp_path)
        sdb.set_setting("worker_key", "db-key-51")
        monkeypatch.setenv("SR_SIGNING_KEY", "env-key-51")
        importlib.reload(wc)
        cands = wc._candidate_keys()
        assert cands[0] == "db-key-51"
        assert cands[1] == "env-key-51"
        assert cands[2] == wc.PROJECT_SIGNING_KEY
        assert len(set(cands)) == len(cands), "بدون تکرار"
        monkeypatch.delenv("SR_SIGNING_KEY")


# ═══ §2 DEFAULT_SETTINGS — کلید پروژه baked ══════════════════════════════════
class TestDefaultSettingsKey:
    def test_default_worker_key_is_project_key(self, tmp_path):
        sdb, _ = _reload_modules(tmp_path)
        assert sdb.DEFAULT_SETTINGS["worker_key"] == sdb._PROJECT_KEY

    def test_all_settings_masks_project_key(self, tmp_path):
        sdb, _ = _reload_modules(tmp_path)
        s = sdb.all_settings()
        assert "worker_key" not in s, "کلید خام هرگز برنمی‌گردد"
        assert "…" in (s.get("worker_key_masked") or ""), "mask نمایش داده می‌شود"

    def test_project_key_single_source(self):
        """کلید در __init__.py تعریف شده و db/worker_client از همانجا می‌خوانند."""
        init = (REPO / "smart_routing" / "__init__.py").read_text(encoding="utf-8")
        m = re.search(r'PROJECT_SIGNING_KEY = "([^"]+)"', init)
        assert m and len(m.group(1)) >= 30
        dbsrc = (REPO / "smart_routing" / "db.py").read_text(encoding="utf-8")
        assert "from . import PROJECT_SIGNING_KEY" in dbsrc
        wcsrc = (REPO / "smart_routing" / "worker_client.py").read_text(encoding="utf-8")
        assert "from . import PROJECT_SIGNING_KEY" in wcsrc


# ═══ §3 materialize_defaults — هر boot فقط کلیدهای غایب ══════════════════════
class TestMaterializeDefaults:
    def test_fresh_db_writes_all_keys(self, tmp_path):
        sdb, _ = _reload_modules(tmp_path)
        written = sdb.materialize_defaults()
        assert set(written) == {"enabled", "worker_url", "worker_key"}
        assert sdb.get_setting("enabled") is True
        assert sdb.get_setting("worker_url") == sdb.DEFAULT_SETTINGS["worker_url"]
        assert sdb.get_setting("worker_key") == sdb._PROJECT_KEY
        # حالا rowهای واقعی در DB هستند (has_setting → True)
        for k in ("enabled", "worker_url", "worker_key"):
            assert sdb.has_setting(k)

    def test_admin_values_never_overwritten(self, tmp_path):
        sdb, _ = _reload_modules(tmp_path)
        sdb.set_setting("enabled", False)                      # ادمین خاموش کرده
        sdb.set_setting("worker_key", "custom-admin-key")
        written = sdb.materialize_defaults()
        assert "enabled" not in written and "worker_key" not in written
        assert "worker_url" in written                          # فقط غایب
        assert sdb.get_setting("enabled") is False, "مقدار ادمین دست‌نخورده"
        assert sdb.get_setting("worker_key") == "custom-admin-key"

    def test_idempotent_second_call(self, tmp_path):
        sdb, _ = _reload_modules(tmp_path)
        sdb.materialize_defaults()
        assert sdb.materialize_defaults() == [], "دوبار اجرا → هیچ نوشتنی"

    def test_explicit_clear_url_respected(self, tmp_path):
        """پاک‌کردن صریح URL از UI → باز materialize نمی‌شود (NOT_CONFIGURED حفظ)."""
        sdb, _ = _reload_modules(tmp_path)
        sdb.set_setting("worker_url", "")
        written = sdb.materialize_defaults()
        assert "worker_url" not in written
        assert sdb.has_setting("worker_url")


# ═══ §4 self-heal کلید Worker ════════════════════════════════════════════════
class TestKeySelfHeal:
    def test_old_db_key_migrates_to_project_key(self, tmp_path, monkeypatch):
        """کلید قدیمی DB با Worker (کلید پروژه) امتبا دارد → self-heal + ذخیره."""
        sdb, wc = _reload_modules(tmp_path)
        sdb.set_setting("worker_key", "old-stale-key")     # قدیمی/ناسازگار
        sdb.set_setting("worker_url", "https://heal.example.workers.dev")
        importlib.reload(wc)

        calls = []

        async def fake_signed(method, path, body=None, timeout=20.0, key=None):
            calls.append((path, key))
            # فقط کلید پروژه معتبر است؛ بقیه 401
            if key == wc.PROJECT_SIGNING_KEY:
                return {"ok": True, "colo": "AMS", "country": "NL"}
            return {"ok": False, "error": "HTTP 401 — امضای نامعتبر"}

        async def fake_health():
            return {"ok": True, "upstream": {"ok": True, "latency_ms": 9}, "colo": "AMS"}

        monkeypatch.setattr(wc, "_signed_call", fake_signed)
        monkeypatch.setattr(wc, "worker_health", fake_health)

        out = None
        import asyncio
        out = asyncio.run(wc.worker_full_check())

        assert out["state"] == "HEALTHY", "بعد از self-heal با کلید پروژه → HEALTHY"
        assert out["authenticated"] is True
        # کلید معتبر در DB ذخیره شد → بررسی بعدی مستقیم
        assert sdb.get_setting("worker_key") == wc.PROJECT_SIGNING_KEY
        # امتحان‌ها: اول کلید DB (قدیمی)، بعد کاندید پروژه
        assert calls[0] == ("/sr/edge-info", "old-stale-key")
        assert "/sr/edge-info" in calls[1][0] and calls[1][1] == wc.PROJECT_SIGNING_KEY
        # probe-upstream با کلید شفاء‌یافته امضا شد
        probe_calls = [c for c in calls if c[0] == "/sr/probe-upstream"]
        assert probe_calls and probe_calls[0][1] == wc.PROJECT_SIGNING_KEY

    def test_all_keys_invalid_no_state_lie(self, tmp_path, monkeypatch):
        """هیچ کلیدی معتبر نیست → authenticated=False صادق (نه سبز جعلی)."""
        sdb, wc = _reload_modules(tmp_path)
        sdb.set_setting("worker_key", "bad-1")

        async def fake_signed(method, path, body=None, timeout=20.0, key=None):
            return {"ok": False, "error": "HTTP 401 — امضای نامعتبر"}

        async def fake_health():
            return {"ok": True, "upstream": {"ok": True, "latency_ms": 9}}

        monkeypatch.setattr(wc, "_signed_call", fake_signed)
        monkeypatch.setattr(wc, "worker_health", fake_health)
        import asyncio
        out = asyncio.run(wc.worker_full_check())
        assert out["authenticated"] is False
        assert out["state"] == "DEPLOYED", "پاسخ می‌دهد ولی امضا نامعتبر → فقط DEPLOYED"
        assert sdb.get_setting("worker_key") == "bad-1", "کلید DB دست‌نخورده"


# ═══ §5 volume_bootstrap — تشخیص mount + status ══════════════════════════════
class TestMountDetection:
    def test_is_mount_false_for_tmp_dir(self, tmp_path):
        vb = _reload_vb(tmp_path)
        assert vb.is_mount(tmp_path) is False, "دایرکتوری tmp روی overlay — mount نیست"

    def test_mount_entries_parse(self):
        import volume_bootstrap as vb
        entries = vb._mount_entries()
        assert isinstance(entries, list) and len(entries) > 0, "/proc/self/mountinfo خوانده می‌شود"

    def test_root_not_counted_as_data_mount(self, tmp_path):
        vb = _reload_vb(tmp_path)
        # root «/» خودش mount (overlay) است ولی عمداً حساب نمی‌شود:
        assert vb.is_mount(Path("/")) is False or vb.mount_entry(Path("/")) is None \
            or vb.mount_entry(Path("/"))["fstype"] in ("overlay", "tmpfs")

    def test_status_local_not_at_risk(self, tmp_path, monkeypatch):
        vb = _reload_vb(tmp_path)
        monkeypatch.delenv("RAILWAY_SERVICE_ID", raising=False)
        st = vb.status()
        assert st["on_railway"] is False
        assert st["at_risk"] is False, "خارج از Railway → بدون بنر/هشدار"

    def test_status_at_risk_on_railway_without_mount(self, tmp_path, monkeypatch):
        vb = _reload_vb(tmp_path)
        monkeypatch.setenv("RAILWAY_SERVICE_ID", "srv-51")
        monkeypatch.setenv("RAILWAY_PROJECT_ID", "prj-51")
        monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "env-51")
        st = vb.status()
        assert st["on_railway"] is True
        assert st["persistent"] is False
        assert st["at_risk"] is True, "روی Railway بدون Volume → در معرض خطر (صادق)"
        monkeypatch.delenv("RAILWAY_SERVICE_ID")
        monkeypatch.delenv("RAILWAY_PROJECT_ID")
        monkeypatch.delenv("RAILWAY_ENVIRONMENT_ID")

    def test_unescape_mount_octal(self):
        import volume_bootstrap as vb
        assert vb._unescape_mount("/tmp/my\\040dir") == "/tmp/my dir"
        assert vb._unescape_mount("/data") == "/data"


# ═══ §6 ensure_volume — no-op ها + create + ضد-حلقه ══════════════════════════
class TestEnsureVolume:
    def test_noop_when_not_on_railway(self, tmp_path, monkeypatch):
        vb = _reload_vb(tmp_path)
        monkeypatch.delenv("RAILWAY_SERVICE_ID", raising=False)
        import asyncio
        out = asyncio.run(vb.ensure_volume())
        assert out["action"] == "not-railway"

    def test_noop_when_already_mounted(self, tmp_path, monkeypatch):
        vb = _reload_vb(tmp_path)
        monkeypatch.setenv("RAILWAY_SERVICE_ID", "srv-51")
        monkeypatch.setattr(vb, "mount_entry", lambda p: {"fstype": "ext4", "source": "/dev/sdb"})
        import asyncio
        out = asyncio.run(vb.ensure_volume())
        assert out["action"] == "already-mounted"
        monkeypatch.delenv("RAILWAY_SERVICE_ID")

    def test_noop_when_disabled_by_env(self, tmp_path, monkeypatch):
        vb = _reload_vb(tmp_path)
        monkeypatch.setenv("RAILWAY_SERVICE_ID", "srv-51")
        monkeypatch.setenv("AUTO_VOLUME_ATTACH", "false")
        import asyncio
        out = asyncio.run(vb.ensure_volume())
        assert out["action"] == "disabled-by-env"
        monkeypatch.delenv("RAILWAY_SERVICE_ID")
        monkeypatch.delenv("AUTO_VOLUME_ATTACH")

    def test_missing_token_returns_manual_guide(self, tmp_path, monkeypatch):
        vb = _reload_vb(tmp_path)
        monkeypatch.setenv("RAILWAY_SERVICE_ID", "srv-51")
        monkeypatch.setenv("RAILWAY_PROJECT_ID", "prj-51")
        monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "env-51")
        monkeypatch.delenv("RAILWAY_TOKEN", raising=False)
        monkeypatch.setattr(vb, "_token", lambda: "")
        import asyncio
        out = asyncio.run(vb.ensure_volume())
        assert out["ok"] is False and out["action"] == "missing-token-or-ids"
        for k in ("RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT_ID"):
            monkeypatch.delenv(k)

    def test_create_and_nudge_when_no_volumes(self, tmp_path, monkeypatch):
        """fresh project (بدون Volume) → volumeCreate + nudge redeploy فقط بعد از موفقیت."""
        vb = _reload_vb(tmp_path)
        monkeypatch.setenv("RAILWAY_SERVICE_ID", "srv-51")
        monkeypatch.setenv("RAILWAY_PROJECT_ID", "prj-51")
        monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "env-51")
        monkeypatch.setattr(vb, "_token", lambda: "tok-51")

        gql_calls = []

        async def fake_gql(token, query, variables):
            gql_calls.append((query.split("(")[0], variables))
            if query.strip().startswith("query"):
                return True, {"project": {"volumes": {"edges": []}}}, ""
            if "volumeCreate" in query:
                return True, {"volumeCreate": {"id": "vol-51", "name": "data"}}, ""
            if "VariableUpsert" in query:
                return True, True, ""
            return False, None, "unknown"

        monkeypatch.setattr(vb, "_gql", fake_gql)
        import asyncio
        out = asyncio.run(vb.ensure_volume())
        assert out["ok"] is True and out["action"] == "created"
        assert out["redeploy_nudged"] is True

        def kind_of(q):
            s = q.strip()
            if s.startswith("query"):
                return "query"
            if "volumeCreate" in s:
                return "volumeCreate"
            if "VariableUpsert" in s:
                return "VariableUpsert"
            return "other"

        kinds = [kind_of(c[0]) for c in gql_calls]
        assert kinds == ["query", "volumeCreate", "VariableUpsert"], \
            "ترتیب: بررسی → ساخت → nudge (فقط بعد از موفقیت)"
        # mutation ساخت با mountPath درست
        create_vars = gql_calls[1][1]
        assert create_vars["input"]["mountPath"] == str(tmp_path)
        assert create_vars["input"]["serviceId"] == "srv-51"
        assert create_vars["input"]["environmentId"] == "env-51"
        for k in ("RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT_ID"):
            monkeypatch.delenv(k)

    def test_no_create_when_project_has_volumes(self, tmp_path, monkeypatch):
        """ضد-حلقه: Volume موجود → create/redeploy ممنوع (فقط راهنمای صادق)."""
        vb = _reload_vb(tmp_path)
        monkeypatch.setenv("RAILWAY_SERVICE_ID", "srv-51")
        monkeypatch.setenv("RAILWAY_PROJECT_ID", "prj-51")
        monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "env-51")
        monkeypatch.setattr(vb, "_token", lambda: "tok-51")

        async def fake_gql(token, query, variables):
            return True, {"project": {"volumes": {"edges": [{"node": {"id": "v", "name": "x"}}]}}}, ""

        monkeypatch.setattr(vb, "_gql", fake_gql)
        import asyncio
        out = asyncio.run(vb.ensure_volume())
        assert out["ok"] is False
        assert out["action"] == "volume-exists-not-mounted"
        assert out["volumes"] == 1
        for k in ("RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT_ID"):
            monkeypatch.delenv(k)

    def test_no_redeploy_when_create_fails(self, tmp_path, monkeypatch):
        """create ناموفق → هرگز nudge نمی‌شود (ضد حلقه‌ی redeploy بی‌نهایت)."""
        vb = _reload_vb(tmp_path)
        monkeypatch.setenv("RAILWAY_SERVICE_ID", "srv-51")
        monkeypatch.setenv("RAILWAY_PROJECT_ID", "prj-51")
        monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "env-51")
        monkeypatch.setattr(vb, "_token", lambda: "tok-51")

        gql_calls = []

        async def fake_gql(token, query, variables):
            gql_calls.append(query)
            if query.strip().startswith("query"):
                return True, {"project": {"volumes": {"edges": []}}}, ""
            return False, None, "GraphQL: permissions denied"

        monkeypatch.setattr(vb, "_gql", fake_gql)
        import asyncio
        out = asyncio.run(vb.ensure_volume())
        assert out["ok"] is False and out["action"] == "create-failed"
        assert len(gql_calls) == 2, "query + create فقط — nudge هرگز صدا نشد"
        for k in ("RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT_ID"):
            monkeypatch.delenv(k)


# ═══ §7 منبع توکن — env RAILWAY_TOKEN مقدم بر فایل (volume_bootstrap) ════════
# توجه: هسته‌ی bottokentcpproxy.py بایت‌به‌بایت با ریفرنس پایه یکسان می‌ماند
# (قرارداد فاز ۴۵) — اولویت env فقط در لایه‌ی جدید volume_bootstrap._token است.
class TestTokenEnvFallback:
    def test_env_token_beats_file(self, tmp_path, monkeypatch):
        vb = _reload_vb(tmp_path)
        monkeypatch.setenv("RAILWAY_TOKEN", "env-railway-token-51")
        assert vb._token() == "env-railway-token-51"
        monkeypatch.delenv("RAILWAY_TOKEN")

    def test_file_token_when_no_env(self, tmp_path, monkeypatch):
        vb = _reload_vb(tmp_path)
        monkeypatch.delenv("RAILWAY_TOKEN", raising=False)
        # توکن فایل در DATA_DIR تازه ذخیره می‌شود (همان قرارداد پنل)
        import bottokentcpproxy as btp
        os.environ["DATA_DIR"] = str(tmp_path)
        importlib.reload(btp)
        importlib.reload(vb)
        btp.save_token("file-token-51")
        assert vb._token() == "file-token-51"

    def test_no_token_anywhere(self, tmp_path, monkeypatch):
        vb = _reload_vb(tmp_path)
        monkeypatch.delenv("RAILWAY_TOKEN", raising=False)
        # bottokentcpproxy هم با DATA_DIR تازه reload شود (نباید توکن قبلی را ببیند)
        import bottokentcpproxy as btp
        os.environ["DATA_DIR"] = str(tmp_path)
        importlib.reload(btp)
        importlib.reload(vb)
        btp.clear_token()
        assert vb._token() == ""

    def test_base_bottokentcpproxy_untouched(self):
        """قرارداد فاز ۴۵: هسته دست‌نخورده — env فقط در لایه‌ی جدید است."""
        ref = Path("/home/z/my-project/emix-healthy")
        if not ref.exists():
            pytest.skip("EMIX reference repo not present")
        assert (REPO / "bottokentcpproxy.py").read_bytes() == \
            (ref / "bottokentcpproxy.py").read_bytes()


# ═══ §8 سرور واقعی fresh-boot — مقادیر ست شده + اندپوینت‌ها ═══════════════════
class TestFreshBootValues:
    def test_persistence_status_and_materialized_defaults(self, tmp_path):
        proc, base = _boot_server(tmp_path)
        try:
            H = _login(base)
            # 1) version
            with urllib.request.urlopen(base + "/api/deployment-version", timeout=10) as r:
                d = json.loads(r.read())
            assert d["version"] == "13.6.0-emix-pro"
            assert "boot-defaults" in d["features"] and "volume-autoboot" in d["features"]

            # 2) مقادیر در DB materialize شده‌اند (از API تنظیمات قابل‌مشاهده)
            code, s = _api(base, H, "GET", "/api/smart-routing/settings")
            assert code == 200
            assert s["settings"]["enabled"] is True
            assert s["settings"]["worker_url"] == \
                "https://emix-smart-routing-v1.personalemixone.workers.dev"
            assert "worker_key_masked" in s["settings"], \
                "کلید پروژه ست شده → mask دیده می‌شود"

            # 3) /api/persistence/status (احراز هویت لازم)
            code, p = _api(base, H, "GET", "/api/persistence/status")
            assert code == 200 and p["ok"] is True
            assert p["persistent"] is False, "لوکال: mount نیست (صادق)"
            assert p["on_railway"] is False
            assert p["at_risk"] is False

            # 4) health-all — بخش volume با فیلدهای جدید
            code, h = _api(base, H, "GET", "/api/system/health-all")
            assert code == 200
            vol = h["sections"]["volume"]
            assert "persistent" in vol and "on_railway" in vol and "at_risk" in vol
            assert vol["ok"] is True, "لوکال بدون mount = قرمز نیست"

            # 5) بدون احراز هویت → 401
            try:
                urllib.request.urlopen(base + "/api/persistence/status", timeout=5)
                assert False, "باید 401 می‌داد"
            except urllib.error.HTTPError as e:
                assert e.code == 401
        finally:
            proc.kill()

    def test_smart_status_worker_registered_from_project(self, tmp_path):
        """fresh boot: Worker با URL/کلید پروژه registered + key_source صادق."""
        proc, base = _boot_server(tmp_path)
        try:
            H = _login(base)
            code, d = _api(base, H, "GET", "/api/smart-routing/status")
            assert code == 200
            w = d["worker"]
            assert w["registered"] is True, "URL + کلید پروژه → ثبت‌شده از boot"
            assert w["state"]["key_missing"] is False
            # v13.6: در boot مقدار پروژه در DB materialize شده → منبع «db»
            # (با مقدار پروژه) صادق است؛ بدون materialize → project-default.
            assert w["state"]["key_source"] in ("db", "project-default")
        finally:
            proc.kill()


# ═══ §9 UI markers — بنر پایداری + سطر Volume + نوت کلید ═════════════════════
class TestUIMarkersPhase51:
    PAGES = (REPO / "pages.py").read_text(encoding="utf-8")

    def test_persistence_banner_function(self):
        assert "checkPersistenceBanner" in self.PAGES, "بنر پایداری در پنل"
        assert "/api/persistence/status" in self.PAGES

    def test_banner_only_at_risk(self):
        assert "d.at_risk" in self.PAGES, "بنر فقط با at_risk نمایش داده می‌شود"

    def test_volume_row_honest_labels(self):
        assert "موقت — Volume متصل نیست" in self.PAGES
        assert "پایدار ✓ (" in self.PAGES

    def test_worker_note_mentions_project_key(self):
        assert "کلید قدیمی ناسازگار، خودکار به کلید فعال پروژه به‌روزرسانی می‌شود" in self.PAGES

    def test_volume_bootstrap_module_exists(self):
        assert (REPO / "volume_bootstrap.py").exists()
        src = (REPO / "volume_bootstrap.py").read_text(encoding="utf-8")
        assert "volumeCreate" in src and "mountinfo" in src

    def test_main_hooks_volume_bootstrap(self):
        src = (REPO / "main.py").read_text(encoding="utf-8")
        assert "volume_bootstrap.ensure_volume" in src, "startup hook"
        assert "volume_bootstrap.register_routes(app)" in src

    def test_api_startup_materializes(self):
        src = (REPO / "smart_routing" / "api.py").read_text(encoding="utf-8")
        assert "materialize_defaults" in src, "هر boot مقادیر را ست می‌کند"
