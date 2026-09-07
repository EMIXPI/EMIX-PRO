# tests/test_phase50_default_on.py
# ══════════════════════════════════════════════════════════════════════════════
# EMIX-PRO v13.5.0 — SMART ROUTING DEFAULT-ON (GA) — پوشش شکایات کاربر:
#   «تگل زود خاموش می‌شد» → ریشه: env flag پیش‌فرض خاموش؛ v13.5: پیش‌فرض روشن.
#   «Worker کلادفلیر به‌طور پیش‌فرض ست نشده» → v13.5: worker_url پیش‌فرض + env key.
#   «یک بخش تو خالی شده» → discovery از فرانت پیش‌فرض Worker — بخش خالی نمی‌ماند.
#   پاپ‌آپ حمایت از سازنده → لینک پروژه‌ی فعلی EMIX-PRO.
#
# §1  env_flag — پیش‌فرض روشن / opt-out صریح
# §2  DEFAULT_SETTINGS — enabled + worker_url پیش‌فرض
# §3  worker_client — fallback URL/key + key_missing صادق
# §4  discovery — فرانت Worker پیش‌فرض بدون ثبت دستی کشف می‌شود
# §5  سرور واقعی fresh-deploy — موتور بدون قدم دستی روشن می‌ماند
# §6  ایمنی — لینک بدون حالت SR حتی با flag روشن → شکل پایه (بدون hijack)
# §7  UI markers — لینک EMIX-PRO + auto enable-env-flag + رفرش زنده
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

_PROC_DIR = Path(tempfile.mkdtemp(prefix="p50_inproc_"))
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


def _reload_selector(tmp_path):
    """db + selector با DB تازه — برای تست‌های ایمنی emission (بدون endpointهای ACTIVE)."""
    sdb, _ = _reload_modules(tmp_path)
    from smart_routing import selector as sel
    importlib.reload(sel)          # selector دوباره به db تازه bind می‌شود
    return sdb, sel


def _login(base):
    req = urllib.request.Request(
        base + "/api/login", data=json.dumps({"password": "123456"}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.headers.get("Set-Cookie", "").split(";")[0]


def _api(base, cookie, method, path, body=None, timeout=60):
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


# ═══ §1 env_flag — پیش‌فرض روشن (ریشه‌ی «زود خاموش می‌شد») ═══════════════════
class TestEnvFlagDefaultOn:
    def test_unset_means_true(self, monkeypatch):
        monkeypatch.delenv("SMART_ROUTING_ENABLED", raising=False)
        from smart_routing import env_flag
        importlib.reload(importlib.import_module("smart_routing"))
        from smart_routing import env_flag as ef2
        assert ef2() is True, "v13.5: متغیر ست نشده → روشن (fresh-deploy کار می‌کند)"

    @pytest.mark.parametrize("val", ["false", "0", "no", "off", "FALSE", " Off "])
    def test_explicit_false_opts_out(self, monkeypatch, val):
        monkeypatch.setenv("SMART_ROUTING_ENABLED", val)
        from smart_routing import env_flag
        importlib.reload(importlib.import_module("smart_routing"))
        from smart_routing import env_flag as ef2
        assert ef2() is False, f"{val!r} → خاموش (rollback صریح)"

    @pytest.mark.parametrize("val", ["true", "1", "yes", "on", "TRUE"])
    def test_explicit_true(self, monkeypatch, val):
        monkeypatch.setenv("SMART_ROUTING_ENABLED", val)
        from smart_routing import env_flag
        importlib.reload(importlib.import_module("smart_routing"))
        from smart_routing import env_flag as ef2
        assert ef2() is True


# ═══ §2 DEFAULT_SETTINGS — پیش‌فرض‌های نسخه ═══════════════════════════════════
class TestDefaultSettings:
    def test_enabled_default_true(self, tmp_path):
        sdb, _ = _reload_modules(tmp_path)
        assert sdb.get_setting("enabled") is True, "fresh-deploy: موتور بدون تگل روشن"

    def test_worker_url_default_preset(self, tmp_path):
        sdb, _ = _reload_modules(tmp_path)
        wu = sdb.get_setting("worker_url")
        assert wu == "https://emix-smart-routing-v1.personalemixone.workers.dev", \
            "Worker کلادفلیر پیش‌فرضِ این نسخه ست شده باشد"

    def test_admin_override_wins(self, tmp_path):
        sdb, _ = _reload_modules(tmp_path)
        sdb.set_setting("enabled", False)
        sdb.set_setting("worker_url", "https://custom.example.workers.dev")
        assert sdb.get_setting("enabled") is False
        assert sdb.get_setting("worker_url") == "https://custom.example.workers.dev"


# ═══ §3 worker_client — fallback + صداقت key_missing ══════════════════════════
class TestWorkerClientDefaults:
    def test_worker_base_falls_back_to_default(self, tmp_path):
        sdb, wc = _reload_modules(tmp_path)
        assert wc.worker_base() == wc.DEFAULT_WORKER_URL

    def test_explicit_clear_disables_default(self, tmp_path):
        """پاک‌کردن صریح URL از UI → row خالی → NOT_CONFIGURED (نه پیش‌فرض)."""
        sdb, wc = _reload_modules(tmp_path)
        sdb.set_setting("worker_url", "")        # ثبت خالیِ صریح
        importlib.reload(wc)
        assert wc.worker_base() == ""
        st = wc.worker_state()
        assert st["state"] == "NOT_CONFIGURED"

    def test_worker_key_from_env_when_db_empty(self, tmp_path, monkeypatch):
        sdb, wc = _reload_modules(tmp_path)
        monkeypatch.setenv("SR_SIGNING_KEY", "env-secret-key")
        importlib.reload(wc)
        assert wc.worker_key() == "env-secret-key"
        monkeypatch.delenv("SR_SIGNING_KEY")

    def test_worker_key_db_wins_over_env(self, tmp_path, monkeypatch):
        sdb, wc = _reload_modules(tmp_path)
        sdb.set_setting("worker_key", "db-key")
        monkeypatch.setenv("SR_SIGNING_KEY", "env-key")
        importlib.reload(wc)
        assert wc.worker_key() == "db-key"
        monkeypatch.delenv("SR_SIGNING_KEY")

    def test_worker_state_registered_key_missing_honest(self, tmp_path):
        sdb, wc = _reload_modules(tmp_path)
        st = wc.worker_state()          # fresh DB → URL پیش‌فرض پروژه + کلید پروژه (v13.6)
        assert st["state"] == "REGISTERED"   # NOT_CONFIGURED نیست — URL هست
        assert st["key_missing"] is False    # v13.6: کلید پیش‌فرض پروژه موجود است
        assert st["key_source"] == "project-default"  # منبع صادق
        assert st["base"] == wc.DEFAULT_WORKER_URL

    def test_worker_state_no_key_missing_when_key_present(self, tmp_path):
        sdb, wc = _reload_modules(tmp_path)
        sdb.set_setting("worker_key", "k")
        importlib.reload(wc)
        st = wc.worker_state()
        assert st["key_missing"] is False

    def test_derive_state_not_configured_only_without_base(self, tmp_path):
        sdb, wc = _reload_modules(tmp_path)
        assert wc._derive_state({"base": None, "health": {"ok": True}}) == "NOT_CONFIGURED"
        # با URL (حتی بدون کلید) Worker بررسی‌پذیر است → DEPLOYED صادق
        assert wc._derive_state({"base": wc.DEFAULT_WORKER_URL,
                                 "health": {"ok": True, "upstream": {"ok": True}},
                                 "authenticated": False}) == "DEPLOYED"


# ═══ §4 discovery — فرانت Worker پیش‌فرض کشف می‌شود (بخش خالی نمی‌ماند) ══════
class TestDiscoveryDefaultWorker:
    def test_discover_from_worker_without_registration(self, tmp_path):
        sdb, wc = _reload_modules(tmp_path)
        import asyncio
        from smart_routing import discovery
        importlib.reload(discovery)
        eps = asyncio.run(discovery.discover_from_worker())
        assert len(eps) == 1
        assert eps[0]["address"] == "emix-smart-routing-v1.personalemixone.workers.dev"
        assert eps[0]["source"] == "cf-worker"
        assert (eps[0]["capabilities"] or {}).get("CF_EDGE") is True

    def test_discovery_respects_admin_override(self, tmp_path):
        sdb, wc = _reload_modules(tmp_path)
        # هاست عمومی قابل‌resolve (SSRF-guard DNS را رد می‌کند اگر resolve نشود)
        sdb.set_setting("worker_url", "https://www.cloudflare.com")
        import asyncio
        from smart_routing import discovery
        importlib.reload(discovery)
        eps = asyncio.run(discovery.discover_from_worker())
        assert eps[0]["address"] == "www.cloudflare.com"


# ═══ §5 fresh-deploy real server — موتور بدون قدم دستی روشن ═════════════════
class TestFreshDeployEngineOn:
    def test_engine_active_by_default_on_fresh_boot(self, tmp_path):
        """boot بدون SMART_ROUTING_ENABLED و بدون تنظیم دستی → موتور روشن می‌ماند."""
        port = _free_port()
        env = dict(os.environ)
        env.update({"PORT": str(port), "DATA_DIR": str(tmp_path),
                    "ADMIN_PASSWORD": "123456", "PYTHONPATH": str(REPO)})
        env.pop("RAILWAY_PUBLIC_DOMAIN", None)
        env.pop("SMART_ROUTING_ENABLED", None)          # ← پیش‌فرض جدید: باید روشن بماند
        env.pop("SR_SIGNING_KEY", None)
        proc = subprocess.Popen([sys.executable, "main.py"], cwd=REPO, env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        base = f"http://127.0.0.1:{port}"
        try:
            deadline = time.time() + 60
            while time.time() < deadline:
                try:
                    with urllib.request.urlopen(base + "/api/ping", timeout=2) as r:
                        if r.status == 200:
                            break
                except Exception:
                    time.sleep(0.4)
            else:
                raise RuntimeError("server did not boot")
            H = _login(base)
            code, d = _api(base, H, "GET", "/api/smart-routing/status")
            assert code == 200
            eng = d["engine"]
            assert eng["env_flag"] is True, "پیش‌فرض v13.5: flag روشن"
            assert eng["settings_enabled"] is True, "پیش‌فرض v13.5: settings روشن"
            assert eng["active"] is True, "تگل دیگر «زود خاموش» نمی‌شود"
            assert eng["running_loops"] is True, "حلقه‌های discovery/health از boot"
            # Worker پیش‌فرض: state صادق (URL و کلید پروژه از v13.6 موجودند)
            w = d["worker"]
            assert w["url"] == "https://emix-smart-routing-v1.personalemixone.workers.dev"
            assert w["state"]["state"] in ("REGISTERED", "DEPLOYED", "HEALTHY")
            assert w["state"].get("key_missing") is False, \
                "v13.6: کلید پروژه → بررسی HMAC از boot ممکن است"
            assert w["state"].get("key_source") in ("db", "project-default"), \
                "v13.6: مقدار پروژه در boot materialize شده → db (با مقدار پروژه) صادق است"
            # تنظیمات API هم پیش‌فرض‌ها را نشان می‌دهد
            code, s = _api(base, H, "GET", "/api/smart-routing/settings")
            assert code == 200 and s["settings"]["enabled"] is True
            assert s["settings"]["worker_url"] == w["url"]
        finally:
            proc.kill()


# ═══ §6 ایمنی — لینک بدون حالت SR hijack نمی‌شود (حتی flag روشن) ═════════════
class TestNoHijackSafety:
    def test_link_without_mode_stays_base_form(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SMART_ROUTING_ENABLED", raising=False)   # → روشن (پیش‌فرض)
        _reload_selector(tmp_path)    # DB تازه — بدون endpoint ACTIVE
        import main
        uid = "05bdffc0-a663-05fa-3797-a0b0335909ff"
        main.LINKS[uid] = {"label": "p50-safe", "protocol": "vless-ws", "active": True}
        link = main.generate_share_link(uid, "emixpanel.example.com")
        assert "@emixpanel.example.com:443" in link
        assert "sni=emixpanel.example.com" in link

    def test_link_with_mode_but_no_active_routes_stays_base(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SMART_ROUTING_ENABLED", raising=False)
        _reload_selector(tmp_path)    # DB تازه — هیچ مسیر ACTIVE/verified
        import main
        uid = "05bdffc0-a663-05fa-3797-a0b0335909fe"
        main.LINKS[uid] = {"label": "p50-safe2", "protocol": "vless-ws", "active": True,
                           "smart_routing_mode": "AUTO"}
        link = main.generate_share_link(uid, "emixpanel.example.com")
        assert "@emixpanel.example.com:443" in link, \
            "هیچ مسیر verified فعالی نیست → لینک مستقیم می‌ماند (صداقت)"


# ═══ §7 UI markers — پاپ‌آپ EMIX-PRO + auto-flag + رفرش زنده ══════════════════
class TestUIMarkers:
    PAGES = (REPO / "pages.py").read_text(encoding="utf-8")

    def test_support_popup_links_to_current_project(self):
        assert 'href="https://github.com/EMIXPI/EMIX-PRO"' in self.PAGES, \
            "پاپ‌آپ حمایت از سازنده → پروژه‌ی فعلی EMIX-PRO"

    def test_support_popup_no_old_base_repo_link(self):
        assert 'href="https://github.com/EMIXPI/EMIX"' not in self.PAGES, \
            "لینک پروژه‌ی پایه‌ی قدیمی نباید باشد"

    def test_toggle_auto_enables_env_flag(self):
        assert "enable-env-flag" in self.PAGES, "تگل → فعال‌سازی خودکار flag روی Railway"
        assert "SMART_ROUTING_ENABLED روی Railway فعال شد" in self.PAGES

    def test_live_refresh_timer(self):
        assert "__srLiveTimer" in self.PAGES, "به‌روزرسانی زنده‌ی صفحه‌ی smart"

    def test_worker_default_note(self):
        assert "به‌طور پیش‌فرض در پروژه ست شده‌اند" in self.PAGES
        assert "SR_SIGNING_KEY" in self.PAGES

    def test_key_missing_hint_in_worker_state(self):
        assert "st.key_missing" in self.PAGES

    def test_worker_client_default_url_constant(self):
        src = (REPO / "smart_routing" / "worker_client.py").read_text(encoding="utf-8")
        assert "DEFAULT_WORKER_URL = PROJECT_WORKER_URL" in src
        init = (REPO / "smart_routing" / "__init__.py").read_text(encoding="utf-8")
        assert 'PROJECT_WORKER_URL = "https://emix-smart-routing-v1.personalemixone.workers.dev"' in init

    def test_project_signing_key_baked(self):
        """v13.6: کلید پروژه در repo — با هر دیپلوی مقادیر ست می‌شوند."""
        init = (REPO / "smart_routing" / "__init__.py").read_text(encoding="utf-8")
        m = re.search(r'PROJECT_SIGNING_KEY = "([^"]+)"', init)
        assert m and len(m.group(1)) >= 30, "کلید امضای پیش‌فرض پروژه باید baked باشد"

    def test_env_flag_default_true_in_code(self):
        src = (REPO / "smart_routing" / "__init__.py").read_text(encoding="utf-8")
        assert '"SMART_ROUTING_ENABLED", "true"' in src

    def test_version_1350(self):
        src = (REPO / "emix_pro.py").read_text(encoding="utf-8")
        assert 'EMIX_PRO_VERSION = "13.6.0-emix-pro"' in src
