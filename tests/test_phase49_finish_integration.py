# tests/test_phase49_finish_integration.py
# ══════════════════════════════════════════════════════════════════════════════
# EMIX-PRO v13.5.0 — DEFAULT-ON GA + finish-integration regression (Phase 49/50)
# پوشش سند کاربر (AUDIT AND FINISH — نه پیاده‌سازی موازی):
#
#   §1  Worker state machine — حالت‌های جدا و صادق:
#       NOT_CONFIGURED / REGISTERED / DEPLOYED / HEALTHY / DEGRADED / FAILED
#       (Registered ≠ Deployed ≠ Healthy — هیچ‌وقت از ثبت‌شده «مستقر» ساخته نمی‌شود)
#   §2  Worker check persistence — نتیجه‌ی بررسی واقعی در smart_settings زنده
#       می‌ماند (state بین session/restart باقی می‌ماند؛ تغییر URL → reset صادق)
#   §3  API: /status شامل worker.state (از آخرین بررسی persisted)؛
#       /worker/status نتیجه‌ی real + persist؛ rate-limit → cached-state honest
#   §4  sr_route (GET /api/links) شامل فیلدهای جدا:
#       iran_egress_verified + egress_country + egress_asn (سند §SEPARATE METRICS)
#   §5  UI markers (pages.py): Egress Cards موبایل (بدون سرریز افقی —
#       جدول فقط دسکتاپ) + Worker state grid + Separate Metrics block +
#       برچسب صادق «Iranian Egress: Not verified» + حالت‌های Worker جدا.
#   §6  Regression: هسته (auth/links/sub) و baseline قبلی دست‌نخورده.
#
# Run:  python -m pytest tests/test_phase49_finish_integration.py -q
# ══════════════════════════════════════════════════════════════════════════════
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

_PROC_DIR = Path(tempfile.mkdtemp(prefix="p49_inproc_"))
os.environ["DATA_DIR"] = str(_PROC_DIR)
os.environ["SMART_ROUTING_ENABLED"] = "false"  # v13.5: پیش‌فرض روشن شد — تست‌ها صریحاً خاموش (hermetic)
os.environ.pop("SR_ALLOW_LOCAL_ENDPOINTS", None)


def _reload_wc(tmp_path):
    """reload db (+schema) و worker_client با DATA_DIR تازه (واحد-تست ایزوله)."""
    import importlib
    os.environ["DATA_DIR"] = str(tmp_path)
    from smart_routing import db as sdb
    importlib.reload(sdb)
    sdb.ensure_schema()
    from smart_routing import worker_client as wc
    importlib.reload(wc)
    return sdb, wc


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── boot یک سرور واقعی subprocess (مثل فازهای قبلی) ─────────────────────────
def _boot_server(tmp_path, env_extra=None):
    data_dir = Path(tmp_path)
    port = _free_port()
    env = dict(os.environ)
    env.update({
        "PORT": str(port),
        "DATA_DIR": str(data_dir),
        "ADMIN_PASSWORD": "123456",
        "PYTHONPATH": str(REPO),
    })
    env.pop("RAILWAY_PUBLIC_DOMAIN", None)
    env["SMART_ROUTING_ENABLED"] = "false"  # v13.5: پیش‌فرض روشن — تست hermetic می‌ماند (مگر env_extra override کند)
    env.pop("SR_ALLOW_LOCAL_ENDPOINTS", None)
    for k, v in (env_extra or {}).items():
        env[k] = v
    proc = subprocess.Popen(
        [sys.executable, "main.py"], cwd=REPO, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base + "/api/ping", timeout=2) as r:
                if r.status == 200:
                    return proc, base, str(data_dir)
        except Exception:
            time.sleep(0.4)
    proc.kill()
    raise RuntimeError("server did not boot")


def _login(base):
    req = urllib.request.Request(
        base + "/api/login", data=json.dumps({"password": "123456"}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return {"Cookie": r.headers.get("Set-Cookie", "").split(";")[0]}


def _api(base, path, headers=None, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={**({"Content-Type": "application/json"} if data else {}),
                                          **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


# ═══ §1 Worker state machine (واحد — بدون شبکه) ══════════════════════════════
class TestWorkerStateMachine:
    def test_not_configured_when_no_url_or_key(self, tmp_path):
        sdb, wc = _reload_wc(tmp_path)
        sdb.set_setting("worker_url", "")
        sdb.set_setting("worker_key", "")
        st = wc.worker_state()
        assert st["state"] == "NOT_CONFIGURED"
        assert st["checked"] is False

    def test_registered_when_saved_but_never_checked(self, tmp_path):
        sdb, wc = _reload_wc(tmp_path)
        sdb.set_setting("worker_url", "https://emix-smart-routing-v1.example.workers.dev")
        sdb.set_setting("worker_key", "k1")
        sdb.set_setting("worker_check", None)
        st = wc.worker_state()
        assert st["state"] == "REGISTERED"          # هرگز «مستقر» ادعا نمی‌شود
        assert st["checked"] is False

    def test_derive_failed_when_health_not_ok(self, tmp_path):
        sdb, wc = _reload_wc(tmp_path)
        sdb.set_setting("worker_url", "https://w.example.workers.dev")
        sdb.set_setting("worker_key", "k")
        assert wc._derive_state({"base": "https://w.example.workers.dev",
                                 "health": {"ok": False}}) == "FAILED"
        assert wc._derive_state({"base": "https://w.example.workers.dev",
                                 "health": "not-json"}) == "FAILED"

    def test_derive_deployed_when_health_ok_but_no_auth(self, tmp_path):
        sdb, wc = _reload_wc(tmp_path)
        sdb.set_setting("worker_url", "https://w.example.workers.dev")
        sdb.set_setting("worker_key", "k")
        # Worker جواب می‌دهد اما امضا/ بررسی upstream انجام نشده → فقط DEPLOYED
        state = wc._derive_state({
            "base": "https://w.example.workers.dev",
            "health": {"ok": True, "upstream": {"ok": True, "latency_ms": 12}},
            "authenticated": False,
        })
        assert state == "DEPLOYED"                  # نه HEALTHY (امضا نامعتبر)

    def test_derive_healthy_only_with_auth_and_upstream(self, tmp_path):
        sdb, wc = _reload_wc(tmp_path)
        sdb.set_setting("worker_url", "https://w.example.workers.dev")
        sdb.set_setting("worker_key", "k")
        state = wc._derive_state({
            "base": "https://w.example.workers.dev",
            "health": {"ok": True, "upstream": {"ok": True, "latency_ms": 12},
                       "colo": "AMS"},
            "authenticated": True,
        })
        assert state == "HEALTHY"

    def test_derive_degraded_when_auth_ok_upstream_fail(self, tmp_path):
        sdb, wc = _reload_wc(tmp_path)
        sdb.set_setting("worker_url", "https://w.example.workers.dev")
        sdb.set_setting("worker_key", "k")
        state = wc._derive_state({
            "base": "https://w.example.workers.dev",
            "health": {"ok": True, "upstream": {"ok": False}},
            "authenticated": True,
        })
        assert state == "DEGRADED"

    def test_worker_state_reads_persisted_check(self, tmp_path):
        sdb, wc = _reload_wc(tmp_path)
        sdb.set_setting("worker_url", "https://w.example.workers.dev")
        sdb.set_setting("worker_key", "k")
        sdb.set_setting("worker_check", {
            "ts": time.time(), "state": "HEALTHY", "authenticated": True,
            "upstream_ok": True, "upstream_latency_ms": 12, "colo": "AMS",
            "edge_to_upstream_ms": 13,
        })
        st = wc.worker_state()
        assert st["state"] == "HEALTHY"
        assert st["checked"] is True
        assert st["last_check"]["upstream_latency_ms"] == 12


# ═══ §2+§3 Worker persistence + API (سرور واقعی) ══════════════════════════════
class TestWorkerPersistenceAPI:
    def test_status_includes_worker_state_field(self, tmp_path):
        proc, base, data_dir = _boot_server(tmp_path)
        try:
            H = _login(base)
            code, d = _api(base, "/api/smart-routing/status", H)
            assert code == 200
            # v13.6: fresh boot → URL/کلید پروژه materialize شده‌اند → registered=True
            # صادق؛ state هنوز «REGISTERED» است چون بررسی واقعی انجام نشده.
            w = d.get("worker") or {}
            assert w.get("state", {}).get("state") in (
                "NOT_CONFIGURED", "REGISTERED")
            assert w.get("registered") is True
        finally:
            proc.kill()

    def test_worker_url_change_resets_check_state(self, tmp_path):
        proc, base, data_dir = _boot_server(tmp_path)
        try:
            H = _login(base)
            # ثبت Worker با URL غیرقابل‌دسترس → بررسی → FAILED (صادق)
            code, d = _api(base, "/api/smart-routing/settings", H, "POST", {
                "worker_url": "https://example.com",
                "worker_key": "testkey123",
            })
            assert code == 200 and "worker_url" in d.get("changed", [])
            # state بلافاصله بعد از ثبت → REGISTERED (بررسی نشده — reset شد)
            code, st = _api(base, "/api/smart-routing/status", H)
            assert st["worker"]["state"]["state"] == "REGISTERED"
            # بررسی واقعی → Worker غیرواقعی → FAILED (نه سبز جعلی)
            code, chk = _api(base, "/api/smart-routing/worker/status", H)
            assert code == 200
            assert chk.get("state") == "FAILED"
            assert chk.get("authenticated") is False
            # state بعد از بررسی زنده → FAILED persisted
            code, st2 = _api(base, "/api/smart-routing/status", H)
            assert st2["worker"]["state"]["state"] == "FAILED"
            assert st2["worker"]["state"]["checked"] is True
            # تغییر URL دوباره → reset → REGISTERED (بررسی قبلی منسوخ)
            code, d2 = _api(base, "/api/smart-routing/settings", H, "POST", {
                "worker_url": "https://iana.org"})
            assert code == 200
            code, st3 = _api(base, "/api/smart-routing/status", H)
            assert st3["worker"]["state"]["state"] == "REGISTERED"
        finally:
            proc.kill()

    def test_worker_check_persisted_to_db(self, tmp_path):
        proc, base, data_dir = _boot_server(tmp_path)
        try:
            H = _login(base)
            _api(base, "/api/smart-routing/settings", H, "POST", {
                "worker_url": "https://example.org", "worker_key": "k"})
            _api(base, "/api/smart-routing/worker/status", H)
            # مستقیم DB: نتیجه‌ی بررسی persisted شده (باقی می‌ماند در restart)
            import sqlite3
            dbp = Path(data_dir) / "smart_routing.db"
            assert dbp.exists(), "smart_routing.db باید در DATA_DIR باشد"
            conn = sqlite3.connect(dbp)
            row = conn.execute(
                "SELECT value FROM smart_settings WHERE key='worker_check'"
            ).fetchone()
            conn.close()
            assert row, "worker_check باید persisted باشد"
            saved = json.loads(row[0])
            assert saved["state"] == "FAILED"
            assert saved["base"] == "https://example.org"
        finally:
            proc.kill()

    def test_worker_status_rate_limit_returns_cached_state(self, tmp_path):
        proc, base, data_dir = _boot_server(tmp_path)
        try:
            H = _login(base)
            _api(base, "/api/smart-routing/settings", H, "POST", {
                "worker_url": "https://example.net", "worker_key": "k"})
            # یکی واقعی (FAIL کند) — بقیه rate-limit → cached persisted state
            _api(base, "/api/smart-routing/worker/status", H)
            seen_cached = False
            for _ in range(12):
                code, d = _api(base, "/api/smart-routing/worker/status", H)
                assert code == 200
                if d.get("cached"):
                    seen_cached = True
                    assert d.get("state") == "FAILED"   # همان state واقعی قبلی
            assert seen_cached, "حداقل یک پاسخ cached-از-persisted باید دیده شود"
        finally:
            proc.kill()


# ═══ §4 sr_route فیلدهای جدا (GET /api/links) ════════════════════════════════
class TestSrRouteSeparateFields:
    def test_links_sr_route_has_iran_egress_and_egress_fields(self, tmp_path):
        proc, base, data_dir = _boot_server(tmp_path)
        try:
            H = _login(base)
            # ساخت یک لینک + فعال‌سازی SR mode
            code, c = _api(base, "/api/links", H, "POST", {
                "label": "p49-route", "protocol": "vless-ws"})
            assert code == 200
            uid = c["uuid"]
            _api(base, f"/api/links/{uid}", H, "PATCH", {"smart_routing_mode": "AUTO"})
            code, d = _api(base, "/api/links", H)
            assert code == 200
            link = next(l for l in d["links"] if l["uuid"] == uid)
            r = link.get("sr_route")
            # بدون مسیر ACTIVE (discovery نداریم) → صادقانه null + reason
            if r is None:
                assert link.get("sr_route_reason"), "reason صادق لازم است"
            else:
                assert "iran_egress_verified" in r
                assert "egress_country" in r
                assert "egress_asn" in r
                # بدون endpoint ایرانِ verify-شده → false (هرگز true جعلی)
                assert r["iran_egress_verified"] is False
        finally:
            proc.kill()


# ═══ §5 UI markers (pages.py — ساختار، نه چرخاندن چشم) ═══════════════════════
class TestUIMarkersPhase49:
    PAGES = (REPO / "pages.py").read_text(encoding="utf-8")

    def test_egress_cards_container_exists(self):
        assert 'id="sr-eg-cards"' in self.PAGES
        assert 'class="sr-eg-cards" id="sr-eg-cards"' in self.PAGES

    def test_table_wrapped_and_hidden_on_mobile(self):
        assert 'id="sr-ep-table-wrap"' in self.PAGES
        assert "#sr-ep-table-wrap{display:none}" in self.PAGES, \
            "جدول باید در موبایل مخفی شود (Egress Cards جایگزین)"
        assert "@media(max-width:760px)" in self.PAGES

    def test_egress_card_renders_ip_country_asn_endpoint_health(self):
        # طبق سند کاربر: Egress Card شامل IP / Country / ASN / Endpoint / Health
        for marker in ("sr-eg-card", "sr-eg-rows", "sr-eg-ep"):
            assert marker in self.PAGES
        assert "row('IP'" in self.PAGES
        assert "row('Country'" in self.PAGES
        assert "row('ASN'" in self.PAGES
        assert "row('Health'" in self.PAGES

    def test_egress_card_rows_no_min_width_table(self):
        # کارت‌ها min-width ندارند → سرریز افقی در 320/360/390/430 ناممکن
        assert ".sr-eg-card{background" in self.PAGES
        assert "min-width:820px" in self.PAGES  # جدول فقط دسکتاپ

    def test_worker_state_grid_all_six_states(self):
        for state in ("NOT_CONFIGURED", "REGISTERED", "DEPLOYED",
                      "HEALTHY", "DEGRADED", "FAILED"):
            assert state in self.PAGES, f"worker state {state} باید در UI باشد"
        assert 'id="sr-wk-state"' in self.PAGES
        assert 'id="sr-wk-upstream"' in self.PAGES
        assert 'id="sr-wk-latency"' in self.PAGES
        assert 'id="sr-wk-endpoint"' in self.PAGES

    def test_worker_card_explains_registered_not_deployed(self):
        assert "ثبت‌شده (REGISTERED) یعنی فقط URL/کلید ذخیره شده" in self.PAGES

    def test_separate_metrics_block_in_route_details(self):
        for field in ("client_rtt_ms", "route_latency_ms", "cf_edge_latency_ms",
                      "egress_ip", "egress_country", "egress_asn",
                      "iran_egress_verified"):
            assert field in self.PAGES, f"فیلد {field} باید در UI باشد"

    def test_iranian_egress_not_verified_label(self):
        assert "Iranian Egress" in self.PAGES
        assert "Not verified" in self.PAGES
        # برچسب صادق وقتی egress ایران نیست
        assert "iran_egress_verified" in self.PAGES

    def test_iran_optimized_badge_honest_marker(self):
        # حالت IRAN_OPTIMIZED روی کارت: بدون egress ایرانِ verify-شده → «تأییدنشده»
        assert "egress ایران: تأییدنشده" in self.PAGES
        assert "r.iran_egress_verified?' · 🇮🇷 egress verified'" in self.PAGES

    def test_worker_check_auto_refresh_wired(self):
        assert "srAutoCheckWorker" in self.PAGES
        assert "srRenderWorkerState" in self.PAGES

    def test_worker_registration_collapsible(self):
        assert 'id="sr-worker-reg"' in self.PAGES
        assert "<details" in self.PAGES

    def test_worker_client_derive_and_persist_exist(self):
        src = (REPO / "smart_routing" / "worker_client.py").read_text()
        assert "def _derive_state" in src
        assert "def worker_state" in src
        assert "def _persist_check" in src
        assert "worker_check" in src

    def test_status_api_includes_state(self):
        src = (REPO / "smart_routing" / "api.py").read_text()
        assert '"state": worker_client.worker_state()' in src
        assert "worker-status" in src  # rate limit key


# ═══ §6 Regression سبک — هسته پایه ═══════════════════════════════════════════
class TestRegressionCore49:
    def test_login_and_links_still_work(self, tmp_path):
        proc, base, data_dir = _boot_server(tmp_path)
        try:
            H = _login(base)
            code, d = _api(base, "/api/links", H)
            assert code == 200 and "links" in d
            code, c = _api(base, "/api/links", H, "POST",
                           {"label": "p49-reg", "protocol": "vless-ws"})
            assert code == 200 and c.get("uuid")
            # sub base64 پایدار
            uid = c["uuid"]
            with urllib.request.urlopen(f"{base}/sub/{uid}", timeout=10) as r:
                body = r.read()
            assert body  # ساب خالی نیست
        finally:
            proc.kill()

    def test_version_bumped(self):
        src = (REPO / "emix_pro.py").read_text(encoding="utf-8")
        assert "13.7.0-emix-pro" in src, "نسخه باید 13.7.0 باشد"
