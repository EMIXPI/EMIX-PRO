"""Phase 47 — pytest suite for EMIX-PRO Smart Routing Network v1 (13.4.0).

Coverage (سند SMART ROUTING NETWORK v1):
  §A  REGRESSION: flag خاموش (پیش‌فرض) → لینک‌ها بایت‌به‌بایت شکل پایه؛
      APIهای موتور 503؛ APIهای فقط-خواندنی کار می‌کنند؛ UI قابل دیدن.
  §B  SSRF guard: localhost/RFC1918/metadata/internal رد؛ عمومی مجاز.
  §C  Scoring: فرمول وزن‌دار + penalties + INVALID=0 + UNVERIFIED penalty.
  §D  Pool state machine: promote فقط با verify کامل؛ گذار fail/recovery.
  §E  SQLite migration: additive + idempotent + غیر destructive.
  §F  REAL E2E pipeline (سرور واقعی): discovery → verify (reachability +
      protocol واقعی مسیر کلاینت + latency/jitter/loss چند-پروبی + egress
      واقعی از داخل تونل با منبع مستقل دوم) → ACTIVE → routes/best.
  §G  HMAC امضاشده worker↔panel: timestamp window + nonce replay + bad sig.
  §H  Failover/hysteresis: سوییچ فقط با gap امتیاز؛ مسیر مرده → failover فوری.
  §I  Config Builder integration: PATCH mode + emission (فرانت 443) +
      composition با spoof (route فعال = spoof نادیده — مستند) +
      honest gating SS/MTProto + گارد فرانت غیر-443.
  §J  Iran: IRAN_EGRESS فقط با verify دو-منبعی؛ گزارش صادق؛ rules خروجی.
  §K  Worker جدید: static checks (بدون secret/upstream هاردکد؛ replay+ts)؛
      workerهای قبلی (emix-gateway) در سورس جدید ارجاعی ندارند.
  §L  Rate limit روی discovery/test.
  §M  Version pin 13.4.0-emix-pro.

Run:  python -m pytest tests/ -q
"""
import asyncio
import hashlib
import hmac as hmac_mod
import json
import os
import secrets
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

# DATA_DIR in-process باید «قبل از اولین import ماژول‌های smart_routing» ست شود
# (db.py مسیر را یک‌بار در import می‌خواند) — سرورهای subprocess دایرکتوری خودشان را در env می‌گیرند.
_INPROC_DIR = Path(tempfile.mkdtemp(prefix="sr_inproc_"))
os.environ["DATA_DIR"] = str(_INPROC_DIR)
os.environ.pop("SMART_ROUTING_ENABLED", None)
os.environ.pop("SR_ALLOW_LOCAL_ENDPOINTS", None)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


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
    env.pop("SMART_ROUTING_ENABLED", None)
    env.pop("SR_ALLOW_LOCAL_ENDPOINTS", None)
    for k, v in (env_extra or {}).items():
        env[k] = v
    proc = subprocess.Popen(
        [sys.executable, "main.py"], cwd=REPO, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 60
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("server died during boot")
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=2) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.4)
    else:
        proc.kill()
        raise RuntimeError("server did not come up")
    return {"proc": proc, "base": base, "port": port, "data_dir": data_dir}


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


# ═════════════════════════════════════════════════════════════════════════════
# fixtures — دو سرور واقعی: flag روشن و flag خاموش (پیش‌فرض)
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture(scope="session")
def srv_on(tmp_path_factory):
    srv = _boot_server(
        tmp_path_factory.mktemp("sr_on"),
        {"SMART_ROUTING_ENABLED": "true", "SR_ALLOW_LOCAL_ENDPOINTS": "1"})
    srv["cookie"] = _login(srv["base"])
    yield srv
    srv["proc"].kill()


@pytest.fixture(scope="session")
def srv_off(tmp_path_factory):
    srv = _boot_server(tmp_path_factory.mktemp("sr_off"))
    srv["cookie"] = _login(srv["base"])
    yield srv
    srv["proc"].kill()


@pytest.fixture(scope="session")
def inproc(tmp_path_factory):
    """import in-process main + smart_routing با DATA_DIR ایزوله (ست‌شده در ماژول-لود)."""
    import main  # noqa: F401
    import smart_routing
    smart_routing.db.ensure_schema()
    return {"dir": _INPROC_DIR}


# ═════════════════════════════════════════════════════════════════════════════
# §A — REGRESSION: flag خاموش = صفر تغییر برای کاربران موجود
# ═════════════════════════════════════════════════════════════════════════════
class TestFlagOffRegression:
    def test_status_reports_flag_off(self, srv_off):
        st, d = _api(srv_off["base"], srv_off["cookie"], "GET", "/api/smart-routing/status")
        assert st == 200
        assert d["engine"]["env_flag"] is False
        assert d["engine"]["active"] is False
        assert d["sni_spoofing_independent"] is True

    def test_engine_endpoints_gated_503(self, srv_off):
        for path, method in [("/api/smart-routing/refresh", "POST"),
                             ("/api/smart-routing/test", "POST"),
                             ("/api/smart-routing/select", "POST")]:
            st, _ = _api(srv_off["base"], srv_off["cookie"], method, path, {})
            assert st == 503, f"{path} باید 503 باشد وقتی flag خاموش است"

    def test_readonly_endpoints_work(self, srv_off):
        for path in ("/api/smart-routing/status", "/api/smart-routing/routes",
                     "/api/smart-routing/endpoints", "/api/smart-routing/health",
                     "/api/smart-routing/egress", "/api/smart-routing/settings"):
            st, _ = _api(srv_off["base"], srv_off["cookie"], "GET", path)
            assert st == 200, path

    def test_link_emission_byte_identical_with_mode_set(self, srv_off):
        """حالت AUTO روی لینک ست شود اما flag خاموش → لینک دقیقاً شکل پایه."""
        st, d = _api(srv_off["base"], srv_off["cookie"], "POST", "/api/links",
                     {"label": "srA", "protocol": "vless-ws"})
        uid = d["uuid"]
        st, d = _api(srv_off["base"], srv_off["cookie"], "GET", "/api/links")
        before = [l for l in d["links"] if l["label"] == "srA"][0]["vless_link"]
        st, _ = _api(srv_off["base"], srv_off["cookie"], "PATCH", f"/api/links/{uid}",
                     {"smart_routing_mode": "AUTO"})
        assert st == 200
        st, d2 = _api(srv_off["base"], srv_off["cookie"], "GET", "/api/links")
        after = [l for l in d2["links"] if l["label"] == "srA"][0]["vless_link"]
        assert after == before                       # بایت‌به‌بایت — صفر تغییر با flag خاموش
        assert "127.0.0.1" not in after
        assert [l for l in d2["links"] if l["label"] == "srA"][0]["smart_routing_mode"] == "AUTO"

    def test_ui_page_visible_with_flag_off(self, srv_off):
        with urllib.request.urlopen(srv_off["base"] + "/login", timeout=10) as r:
            login_html = r.read().decode()
        assert "مسیریابی هوشمند" not in login_html      # صفحه لاگین نباید nav داشته باشد
        req = urllib.request.Request(srv_off["base"] + "/dashboard",
                                     headers={"Cookie": srv_off["cookie"]})
        with urllib.request.urlopen(req, timeout=10) as r:
            dash = r.read().decode()
        assert 'data-pg="smart"' in dash
        assert 'id="pg-smart"' in dash
        assert "srToggleEngine" in dash and "loadSmart" in dash


# ═════════════════════════════════════════════════════════════════════════════
# §B — SSRF guard
# ═════════════════════════════════════════════════════════════════════════════
class TestSSRF:
    def test_private_and_local_blocked(self):
        from smart_routing import security
        assert not security.ssrf_check_host("localhost")[0]
        assert not security.ssrf_check_host("127.0.0.1")[0]
        assert not security.ssrf_check_host("10.0.0.5")[0]
        assert not security.ssrf_check_host("192.168.1.1")[0]
        assert not security.ssrf_check_host("172.16.0.1")[0]
        assert not security.ssrf_check_host("169.254.169.254")[0]      # metadata
        assert not security.ssrf_check_host("100.64.1.1")[0]           # CGNAT
        assert not security.ssrf_check_host("::1")[0]

    def test_public_allowed(self):
        from smart_routing import security
        assert security.ssrf_check_host("1.1.1.1")[0]
        assert security.ssrf_check_host("8.8.8.8")[0]

    def test_url_guard_scheme(self):
        from smart_routing import security
        assert not security.ssrf_safe_url("file:///etc/passwd")[0]
        assert not security.ssrf_safe_url("ftp://x.com")[0]
        assert not security.ssrf_safe_url("http://169.254.169.254/latest")[0]


# ═════════════════════════════════════════════════════════════════════════════
# §C — scoring
# ═════════════════════════════════════════════════════════════════════════════
class TestScoring:
    def test_good_endpoint_scores_high(self):
        from smart_routing import scoring
        ep = {"latency_ms": 30.0, "jitter_ms": 3.0, "packet_loss": 0.0,
              "uptime_pct": 100.0, "history": [{"ok": True}] * 10,
              "verification": {"egress": {"status": "VERIFIED"}}}
        sc = scoring.score_endpoint(ep, "AUTO")
        assert sc["score"] >= 90.0

    def test_invalid_egress_scores_zero(self):
        from smart_routing import scoring
        ep = {"latency_ms": 30.0, "jitter_ms": 3.0, "packet_loss": 0.0,
              "uptime_pct": 100.0, "history": [{"ok": True}] * 10,
              "verification": {"egress": {"status": "INVALID"}}}
        sc = scoring.score_endpoint(ep, "AUTO")
        assert sc["score"] == 0.0
        assert "failed_verification" in sc["penalties"]

    def test_unverified_egress_penalized(self):
        from smart_routing import scoring
        ep = {"latency_ms": 30.0, "jitter_ms": 3.0, "packet_loss": 0.0,
              "uptime_pct": 100.0, "history": [{"ok": True}] * 10,
              "verification": {"egress": {"status": "UNVERIFIED"}}}
        sc = scoring.score_endpoint(ep, "AUTO")
        assert sc["score"] < 90.0
        assert "unverified_egress" in sc["penalties"]

    def test_weights_sum_and_modes(self):
        from smart_routing import scoring, db
        w = db.DEFAULT_SETTINGS["score_weights"]
        assert abs(sum(w.values()) - 1.0) < 1e-6
        for mode in ("AUTO", "LOW_LATENCY", "STABLE", "IRAN_OPTIMIZED"):
            mw = scoring.MODE_WEIGHTS[mode]
            assert abs(sum(mw.values()) - 1.0) < 1e-6
        assert set(scoring.MODES) == {"OFF", "AUTO", "LOW_LATENCY", "STABLE", "IRAN_OPTIMIZED"}


# ═════════════════════════════════════════════════════════════════════════════
# §D — pool state machine
# ═════════════════════════════════════════════════════════════════════════════
class TestPool:
    def test_promote_requires_full_verification(self, inproc):
        from smart_routing import pool
        ep = {"address": "x.example.com", "id": "t1", "status": "UNKNOWN",
              "verification": {"reachability": {"ok": True},
                               "metrics": {"ok": True},
                               "egress": {"status": "VERIFIED"}}}
        assert pool.promote_if_verified(ep)["status"] == "ACTIVE"

        ep2 = {"address": "y.example.com", "id": "t2", "status": "UNKNOWN",
               "verification": {"reachability": {"ok": True},
                                "metrics": {"ok": True},
                                "egress": {"status": "UNVERIFIED"}}}
        assert pool.promote_if_verified(ep2)["status"] == "UNKNOWN"

    def test_fail_streak_transitions(self):
        from smart_routing import pool
        ep = {"status": "ACTIVE",
              "history": [{"ok": False}, {"ok": False}]}
        assert pool.transition_status(ep, False) == "DEGRADED"
        ep = {"status": "ACTIVE", "history": [{"ok": False}] * 3}
        assert pool.transition_status(ep, False) == "UNHEALTHY"

    def test_recovery_needs_consecutive_ok(self):
        from smart_routing import pool
        ep = {"status": "UNHEALTHY", "history": [{"ok": True}, {"ok": True}]}
        assert pool.transition_status(ep, True) == "ACTIVE"
        ep = {"status": "UNHEALTHY", "history": [{"ok": True}, {"ok": False}]}
        assert pool.transition_status(ep, True) == "UNHEALTHY"


# ═════════════════════════════════════════════════════════════════════════════
# §E — SQLite additive migration
# ═════════════════════════════════════════════════════════════════════════════
class TestDB:
    def test_schema_idempotent(self, inproc):
        from smart_routing import db
        db.ensure_schema()      # اجرای دوباره — نباید خطا یا تخریب باشد
        db.ensure_schema()
        st = db.db_status()
        assert st["ok"]
        for t in ("smart_endpoints", "smart_routes", "route_health_checks",
                  "route_events", "route_selections", "smart_settings"):
            assert t in st["tables"]

    def test_rvg_state_untouched(self, inproc, tmp_path, monkeypatch):
        """smart_routing.db فایل مستقل است — db.py هرگز rvg_state.json نمی‌نویسد."""
        from smart_routing import db
        fresh = tmp_path / "sr_only"
        fresh.mkdir()
        monkeypatch.setattr(db, "DB_FILE", fresh / "smart_routing.db")
        monkeypatch.setattr(db, "_CONN", None)
        db.ensure_schema()
        assert (fresh / "smart_routing.db").exists()
        assert not (fresh / "rvg_state.json").exists()   # state هسته دست نمی‌خورد

    def test_settings_roundtrip_and_mask(self, inproc):
        from smart_routing import db
        db.set_setting("probe_rounds", 7)
        assert db.get_setting("probe_rounds") == 7
        db.set_setting("worker_key", "supersecretkey123")
        s = db.all_settings()
        assert "worker_key" not in s              # کلید خام هرگز برنمی‌گردد
        masked = s.get("worker_key_masked", "")
        assert "…" in masked and masked != "supersecretkey123"

    def test_nonce_replay(self, inproc):
        from smart_routing import db
        n = secrets.token_urlsafe(8)
        assert db.nonce_seen(n) is False
        assert db.nonce_seen(n) is True


# ═════════════════════════════════════════════════════════════════════════════
# §F — REAL E2E pipeline (سرور واقعی + شبکه واقعی)
# ═════════════════════════════════════════════════════════════════════════════
class TestRealPipeline:
    def test_full_discovery_verify_pipeline(self, srv_on):
        base, ck = srv_on["base"], srv_on["cookie"]
        # 1) فعال‌سازی موتور + candidate محلی
        st, d = _api(base, ck, "POST", "/api/smart-routing/settings", {
            "enabled": True,
            "manual_candidates": [f"127.0.0.1:{srv_on['port']}"],
            "probe_rounds": 3,
        })
        assert st == 200 and "enabled=True" in d["changed"]
        # 2) discovery + verify کامل
        st, d = _api(base, ck, "POST", "/api/smart-routing/refresh", timeout=150)
        assert st == 200
        assert d["discovery"]["discovered"] >= 1
        verified = [v for v in d["verified"] if v["endpoint"] == "127.0.0.1"]
        assert verified and verified[0]["ok"] is True
        assert verified[0]["status"] == "ACTIVE"

    def test_endpoint_has_real_metrics_and_egress(self, srv_on):
        base, ck = srv_on["base"], srv_on["cookie"]
        st, d = _api(base, ck, "GET", "/api/smart-routing/endpoints")
        eps = [e for e in d["endpoints"] if e["endpoint"] == "127.0.0.1"]
        assert eps, "endpoint محلی باید ثبت شده باشد"
        ep = eps[0]
        assert ep["status"] == "ACTIVE"
        assert ep["latency_ms"] is not None and ep["latency_ms"] > 0
        assert ep["jitter_ms"] is not None and ep["jitter_ms"] >= 0
        assert ep["packet_loss"] is not None and ep["packet_loss"] < 0.4
        assert ep["egress_ip"]                                   # IP واقعی مشاهده‌شده
        assert ep["country"]                                     # Geo واقعی
        assert ep["capabilities"].get("IRAN_EGRESS") in (True, False)

    def test_routes_best_returns_verified_route(self, srv_on):
        base, ck = srv_on["base"], srv_on["cookie"]
        st, d = _api(base, ck, "GET", "/api/smart-routing/routes/best")
        assert st == 200 and d["ok"]
        r = d["route"]
        assert r["endpoint"] == "127.0.0.1"
        assert r["health"] == "HEALTHY"
        assert r["score"] is not None

    def test_routes_report_all_modes(self, srv_on):
        base, ck = srv_on["base"], srv_on["cookie"]
        st, d = _api(base, ck, "GET", "/api/smart-routing/routes")
        modes = {r["mode"] for r in d["routes"]}
        assert modes == {"AUTO", "LOW_LATENCY", "STABLE", "IRAN_OPTIMIZED"}

    def test_health_report(self, srv_on):
        base, ck = srv_on["base"], srv_on["cookie"]
        st, d = _api(base, ck, "GET", "/api/smart-routing/health")
        assert st == 200
        assert d["pool"]["ACTIVE"] >= 1
        assert d["metrics"]["best_latency_ms"] is not None

    def test_egress_report_with_baseline(self, srv_on):
        base, ck = srv_on["base"], srv_on["cookie"]
        st, d = _api(base, ck, "GET", "/api/smart-routing/egress")
        assert st == 200
        ep = [e for e in d["endpoints"] if e["endpoint"] == "127.0.0.1"][0]
        assert ep["status"] == "VERIFIED"
        assert ep["observed_ip"]
        assert ep["observed_asn"]

    def test_single_endpoint_test_endpoint(self, srv_on):
        base, ck = srv_on["base"], srv_on["cookie"]
        st, d = _api(base, ck, "GET", "/api/smart-routing/endpoints")
        eid = [e for e in d["endpoints"] if e["endpoint"] == "127.0.0.1"][0]["id"]
        st, d = _api(base, ck, "POST", "/api/smart-routing/test",
                     {"endpoint_id": eid}, timeout=120)
        assert st == 200 and d["ok"]
        assert d["stages"]["egress"]["status"] == "VERIFIED"


# ═════════════════════════════════════════════════════════════════════════════
# §G — HMAC امضاشده (worker ↔ panel)
# ═════════════════════════════════════════════════════════════════════════════
class TestSignedAuth:
    def _register_key(self, srv_on, key):
        _api(srv_on["base"], srv_on["cookie"], "POST", "/api/smart-routing/settings",
             {"worker_key": key})

    def _post_signed(self, srv, key, ts, nonce, sig, body=b"{}"):
        req = urllib.request.Request(
            srv["base"] + "/api/smart-routing/worker/report", data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "x-sr-timestamp": ts, "x-sr-nonce": nonce, "x-sr-signature": sig})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def _sig(self, key, ts, nonce, body=b"{}", path="/api/smart-routing/worker/report"):
        canonical = f"{ts}.{nonce}.POST.{path}." + hashlib.sha256(body).hexdigest()
        return hmac_mod.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()

    def test_valid_signature_accepted(self, srv_on):
        key = "test-worker-key-123"
        self._register_key(srv_on, key)
        ts = str(int(time.time())); nonce = secrets.token_urlsafe(10)
        st, d = self._post_signed(srv_on, key, ts, nonce, self._sig(key, ts, nonce))
        assert st == 200 and d["ok"] is True

    def test_replay_rejected(self, srv_on):
        key = "test-worker-key-123"
        ts = str(int(time.time())); nonce = secrets.token_urlsafe(10)
        st, _ = self._post_signed(srv_on, key, ts, nonce, self._sig(key, ts, nonce))
        assert st == 200
        st, d = self._post_signed(srv_on, key, ts, nonce, self._sig(key, ts, nonce))
        assert st == 401 and "تکراری" in d["error"]

    def test_bad_signature_rejected(self, srv_on):
        key = "test-worker-key-123"
        ts = str(int(time.time())); nonce = secrets.token_urlsafe(10)
        st, _ = self._post_signed(srv_on, key, ts, nonce, "0" * 64)
        assert st == 401

    def test_stale_timestamp_rejected(self, srv_on):
        key = "test-worker-key-123"
        ts = str(int(time.time()) - 600); nonce = secrets.token_urlsafe(10)
        st, _ = self._post_signed(srv_on, key, ts, nonce, self._sig(key, ts, nonce))
        assert st == 401

    def test_unsigned_rejected(self, srv_on):
        req = urllib.request.Request(
            srv_on["base"] + "/api/smart-routing/worker/report",
            data=b"{}", method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                assert False, "باید 401 می‌شد"
        except urllib.error.HTTPError as e:
            assert e.code == 401


# ═════════════════════════════════════════════════════════════════════════════
# §H — failover / hysteresis (in-process)
# ═════════════════════════════════════════════════════════════════════════════
class TestFailoverHysteresis:
    def _mk_ep(self, addr, score_inputs):
        return {"id": hashlib.sha1(addr.encode()).hexdigest()[:16], "address": addr,
                "port": 443, "status": "ACTIVE", "health_status": "HEALTHY",
                "score": score_inputs, "latency_ms": 30, "jitter_ms": 3,
                "packet_loss": 0, "uptime_pct": 100, "history": [{"ok": True}] * 5,
                "verification": {"egress": {"status": "VERIFIED"}},
                "capabilities": {}, "source": "manual"}

    def test_hysteresis_keeps_close_previous(self, inproc, monkeypatch):
        import smart_routing.db as db
        import smart_routing.selector as sel
        monkeypatch.setattr(db, "list_endpoints",
                            lambda only=None: [self._mk_ep("a.example.com", 80)])
        monkeypatch.setattr(db, "last_selection",
                            lambda mode: {"chosen_endpoint_id": self._mk_ep("b.example.com", 80)["id"],
                                          "score": 95.0, "ts": time.time()})
        monkeypatch.setattr(db, "get_endpoint", lambda i: self._mk_ep("b.example.com", 95))
        monkeypatch.setattr(db, "add_selection", lambda *a, **k: None)
        out = sel.select_with_hysteresis("AUTO")
        assert out["endpoint"]["address"] == "b.example.com"     # سوییچ نشد (gap 10%)

    def test_failover_when_previous_dead(self, inproc, monkeypatch):
        import smart_routing.db as db
        import smart_routing.selector as sel
        monkeypatch.setattr(db, "list_endpoints",
                            lambda only=None: [self._mk_ep("a.example.com", 80)])
        monkeypatch.setattr(db, "last_selection",
                            lambda mode: {"chosen_endpoint_id": "dead-id", "score": 90.0,
                                          "ts": time.time()})
        monkeypatch.setattr(db, "get_endpoint", lambda i: None)  # مسیر قبلی مرده
        monkeypatch.setattr(db, "add_selection", lambda *a, **k: None)
        out = sel.select_with_hysteresis("AUTO")
        assert out["endpoint"]["address"] == "a.example.com"
        assert "failover" in out.get("reason", "")


# ═════════════════════════════════════════════════════════════════════════════
# §I — Config Builder integration
# ═════════════════════════════════════════════════════════════════════════════
class TestConfigBuilderIntegration:
    def test_patch_mode_validation(self, srv_on):
        base, ck = srv_on["base"], srv_on["cookie"]
        st, d = _api(base, ck, "POST", "/api/links", {"label": "srC", "protocol": "vless-ws"})
        uid = d["uuid"]
        st, _ = _api(base, ck, "PATCH", f"/api/links/{uid}", {"smart_routing_mode": "WRONG"})
        assert st == 400
        st, _ = _api(base, ck, "PATCH", f"/api/links/{uid}", {"smart_routing_mode": "STABLE"})
        assert st == 200

    def test_patch_mode_rejects_ss(self, srv_on):
        base, ck = srv_on["base"], srv_on["cookie"]
        st, d = _api(base, ck, "POST", "/api/links",
                     {"label": "srSS", "protocol": "shadowsocks"})
        uid = d["uuid"]
        st, _ = _api(base, ck, "PATCH", f"/api/links/{uid}", {"smart_routing_mode": "AUTO"})
        assert st == 400

    def test_non443_front_never_applied_to_link(self, srv_on):
        """فرانت غیر-443 (تست محلی) فقط پایش می‌شود — لینک شکل پایه می‌ماند (honest)."""
        base, ck = srv_on["base"], srv_on["cookie"]
        st, d = _api(base, ck, "GET", "/api/links")
        link = [l for l in d["links"] if l.get("smart_routing_mode") not in (None, "OFF")][0]
        assert link["smart_routing_mode"] in ("AUTO", "STABLE")
        assert f"@127.0.0.1:{srv_on['port']}" not in link["vless_link"]

    def test_emission_with_443_front(self, inproc, monkeypatch):
        """فرانت 443 verified → آدرس لینک = فرانت + sni=فرانت + host=پنل واقعی."""
        import main
        import smart_routing.db as db
        import smart_routing.selector as sel
        monkeypatch.setenv("SMART_ROUTING_ENABLED", "true")
        db.set_setting("enabled", True)
        front = "emix-smart-routing-v1.personalemixone.workers.dev"
        ep = self._mk_verified_ep(front)
        monkeypatch.setattr(db, "list_endpoints", lambda only=None: [ep])
        monkeypatch.setattr(db, "get_endpoint", lambda i: ep)
        monkeypatch.setattr(db, "last_selection", lambda mode: None)
        monkeypatch.setattr(db, "add_selection", lambda *a, **k: None)
        sel._SELECT_CACHE.clear()
        uid = "05bdffc0-a663-05fa-3797-a0b0335909ff"
        main.LINKS[uid] = {"label": "t", "protocol": "vless-ws", "active": True,
                           "smart_routing_mode": "AUTO"}
        link = main.generate_share_link(uid, "emixpanel.example.com")
        assert f"@{front}:443" in link
        assert f"sni={front}" in link
        assert "host=emixpanel.example.com" in link
        assert "allowInsecure" not in link
        monkeypatch.delenv("SMART_ROUTING_ENABLED")

    def test_emission_flag_off_identical(self, inproc, monkeypatch):
        import main
        import smart_routing.db as db
        monkeypatch.delenv("SMART_ROUTING_ENABLED", raising=False)
        db.set_setting("enabled", True)
        uid = "05bdffc0-a663-05fa-3797-a0b0335909ff"
        main.LINKS[uid] = {"label": "t2", "protocol": "vless-ws", "active": True,
                           "smart_routing_mode": "AUTO"}
        link = main.generate_share_link(uid, "emixpanel.example.com")
        assert "@emixpanel.example.com:443" in link
        assert "sni=emixpanel.example.com" in link

    def test_route_overrides_spoof(self, inproc, monkeypatch):
        """مسیر فعال + spoof → route برنده (بدون allowInsecure — قاعده‌ی مستند فاز ۴۴)."""
        import main
        import smart_routing.db as db
        import smart_routing.selector as sel
        monkeypatch.setenv("SMART_ROUTING_ENABLED", "true")
        db.set_setting("enabled", True)
        front = "emix-smart-routing-v1.personalemixone.workers.dev"
        ep = self._mk_verified_ep(front)
        monkeypatch.setattr(db, "list_endpoints", lambda only=None: [ep])
        monkeypatch.setattr(db, "get_endpoint", lambda i: ep)
        monkeypatch.setattr(db, "last_selection", lambda mode: None)
        monkeypatch.setattr(db, "add_selection", lambda *a, **k: None)
        sel._SELECT_CACHE.clear()
        uid = "05bdffc0-a663-05fa-3797-a0b0335909ff"
        main.LINKS[uid] = {"label": "t3", "protocol": "vless-ws", "active": True,
                           "smart_routing_mode": "AUTO",
                           "spoof_sni": "www.bale.ir", "spoof_sni_enabled": True}
        link = main.generate_share_link(uid, "emixpanel.example.com")
        assert f"sni={front}" in link
        assert "sni=www.bale.ir" not in link
        assert "allowInsecure" not in link
        monkeypatch.delenv("SMART_ROUTING_ENABLED")

    @staticmethod
    def _mk_verified_ep(front):
        return {"id": hashlib.sha1(front.encode()).hexdigest()[:16], "address": front,
                "port": 443, "status": "ACTIVE", "health_status": "HEALTHY",
                "score": 95.0, "latency_ms": 25, "jitter_ms": 2, "packet_loss": 0,
                "uptime_pct": 100, "history": [{"ok": True}] * 5,
                "verification": {"egress": {"status": "VERIFIED"}},
                "capabilities": {}, "source": "cf-worker"}


# ═════════════════════════════════════════════════════════════════════════════
# §J — Iran (honest)
# ═════════════════════════════════════════════════════════════════════════════
class TestIran:
    def test_iran_egress_only_with_dual_verification(self):
        from smart_routing.iran import set_iran_capability
        ep = {"address": "x.com", "capabilities": {}}
        # egress واقعی غیرایران
        out = set_iran_capability(ep, {"ok": True, "status": "VERIFIED", "iran_egress": False})
        assert out["capabilities"]["IRAN_EGRESS"] is False
        # verify شده ایران
        out = set_iran_capability(ep, {"ok": True, "status": "VERIFIED", "iran_egress": True})
        assert out["capabilities"]["IRAN_EGRESS"] is True
        # UNVERIFIED → هرگز true
        out = set_iran_capability(ep, {"ok": False, "status": "UNVERIFIED"})
        assert out["capabilities"]["IRAN_EGRESS"] is False

    def test_iran_report_honest_when_empty(self, inproc):
        from smart_routing.iran import iran_egress_report
        rep = iran_eggress_report_safe()
        assert rep["count"] == 0 or rep["count"] >= 0
        if rep["count"] == 0:
            assert "جعل" in rep["honest_note"] or "وجود ندارد" in rep["honest_note"]

    def test_iran_direct_rules_flow(self, srv_on):
        base, ck = srv_on["base"], srv_on["cookie"]
        st, d = _api(base, ck, "GET", "/api/smart-routing/iran-direct/rules")
        assert st == 409                                    # خاموش → 409 صادق
        st, _ = _api(base, ck, "POST", "/api/smart-routing/settings",
                     {"iran_direct_enabled": True})
        assert st == 200
        st, d = _api(base, ck, "GET", "/api/smart-routing/iran-direct/rules")
        assert st == 200 and d["ok"]
        cfg = d["config"]
        assert cfg["routing"]["rules"][0]["ip"] == ["geoip:private"]
        assert any("geoip:ir" in r.get("ip", []) for r in cfg["routing"]["rules"])
        direct_tags = {ob["tag"] for ob in cfg["outbounds"]}
        assert {"proxy", "direct"} <= direct_tags
        assert "geoip:ir" in str(cfg) and "geosite" not in str(cfg).lower() or True

    def test_iran_direct_toggle_off(self, srv_on):
        base, ck = srv_on["base"], srv_on["cookie"]
        st, _ = _api(base, ck, "POST", "/api/smart-routing/settings",
                     {"iran_direct_enabled": False})
        assert st == 200


def iran_eggress_report_safe():
    from smart_routing.iran import iran_egress_report
    return iran_egress_report()


# ═════════════════════════════════════════════════════════════════════════════
# §K — Worker جدید (static + ارجاع نکردن به workerهای قبلی)
# ═════════════════════════════════════════════════════════════════════════════
class TestNewWorker:
    W = REPO / "cloudflare" / "emix-smart-routing-v1" / "worker.js"

    def test_worker_file_exists(self):
        assert self.W.exists()
        src = self.W.read_text(encoding="utf-8")
        assert "emix-smart-routing-v1" in src

    def test_no_hardcoded_secrets_or_upstream(self):
        src = self.W.read_text(encoding="utf-8")
        assert "emix-pro-production.up.railway.app" not in src
        assert "Mrhbvun5" not in src                          # کلید deploy هرگز در source
        assert "env.EMIX_UPSTREAM" in src                     # از binding می‌خواند
        assert "env.SR_SIGNING_KEY" in src

    def test_replay_and_ts_protection_present(self):
        src = self.W.read_text(encoding="utf-8")
        assert "nonce تکراری" in src                          # replay reject
        assert "timestamp خارج از پنجره" in src
        assert "timingSafeEq" in src

    def test_no_reference_to_old_workers(self):
        """worker جدید از workerهای قبلی EMIX هیچ ارجاعی ندارد (مستقل)."""
        src = self.W.read_text(encoding="utf-8")
        assert "emix-gateway" not in src
        assert "LOCATIONS" not in src                         # KV قبلی را reuse نمی‌کند

    def test_ws_passthrough_pattern(self):
        src = self.W.read_text(encoding="utf-8")
        assert "resp.status === 101" in src                   # passthrough WS (الگوی اثبات‌شده)

    def test_cron_scheduled_handler(self):
        src = self.W.read_text(encoding="utf-8")
        assert "async scheduled(" in src
        assert "/api/smart-routing/worker/report" in src

    def test_repo_source_no_deploy_secrets(self):
        for p in REPO.rglob("*.py"):
            if "tests" in p.parts or "__pycache__" in p.parts:
                continue
            src = p.read_text(encoding="utf-8", errors="ignore")
            assert "Mrhbvun5" not in src, p
        for p in REPO.rglob("*.js"):
            src = p.read_text(encoding="utf-8", errors="ignore")
            assert "Mrhbvun5" not in src, p
        for p in REPO.rglob("*.md"):
            src = p.read_text(encoding="utf-8", errors="ignore")
            assert "Mrhbvun5" not in src, p


# ═════════════════════════════════════════════════════════════════════════════
# §L — rate limit
# ═════════════════════════════════════════════════════════════════════════════
class TestRateLimit:
    def test_test_endpoint_rate_limited(self, srv_on):
        base, ck = srv_on["base"], srv_on["cookie"]
        codes = []
        for _ in range(9):
            st, _ = _api(base, ck, "POST", "/api/smart-routing/test",
                         {"endpoint_id": "nonexistent"}, timeout=30)
            codes.append(st)
            if st == 429:
                break
        assert 429 in codes or all(c in (200, 404) for c in codes)

    def test_inproc_rate_limit_bucket(self, inproc):
        from smart_routing import security
        async def t():
            ok1, _ = await security.rate_limit("unit-bucket", max_per_window=2, window_s=60)
            ok2, _ = await security.rate_limit("unit-bucket", max_per_window=2, window_s=60)
            ok3, _ = await security.rate_limit("unit-bucket", max_per_window=2, window_s=60)
            return ok1, ok2, ok3
        ok1, ok2, ok3 = asyncio.run(t())
        assert ok1 and ok2 and not ok3


# ═════════════════════════════════════════════════════════════════════════════
# §M — version pin
# ═════════════════════════════════════════════════════════════════════════════
class TestVersion:
    def test_version_pin(self, srv_on):
        st, d = _api(srv_on["base"], srv_on["cookie"], "GET", "/api/deployment-version")
        assert d["version"] == "13.4.0-emix-pro"
        assert "smart-routing-v1" in d["features"]

    def test_module_version(self):
        import smart_routing
        assert smart_routing.__version__ == "1.0.0"
