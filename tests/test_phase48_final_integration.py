"""Phase 48 — FINAL PRODUCTION FIX & FEATURE INTEGRATION (v13.4.0).

Coverage (طبق سند کاربر — COMPLETE = CODED + CONNECTED + VISIBLE + TESTED):
  §A  CLIENT PING API: ثبت گزارش مرورگر (>=5 نمونه)، بازمحاسبه‌ی آمار از
      نمونه‌ها (ضد جعل — stat ناسازگار رد)، gateها (نمونه کم/خارج بازه/404/401)،
      last_client_ping در GET /api/links (ثبات داده).
  §B  endpoint_host: هاست واقعی emitted برای پینگ مرورگر (پنل برای vless،
      None صادقانه برای mtproto بدون public host).
  §C  IRAN ROUTING per-link (مستقل): create + PATCH (OFF/AUTO/DIRECT)،
      gateهای mtproto/invalid، iran-config JSON واقعی (قواعد routing، outbound
      از خود لینک، بدون ادعای egress)، sub/iran جدید + ساب پایه دست‌نخورده.
  §D  sr_route خلاصه‌ی صادق روی links list (null + reason وقتی مسیری نیست).
  §E  UI: Config Builder بخش Network با سه قابلیت جداجدا، Client Ping روی
      کارت، Ping Details، Route Details، JS سالم (node --check).
  §F  Regression: لینک بدون feature بایت‌به‌بایت پایه؛ نسخه 13.4.1-emix-pro.

Run:  python -m pytest tests/test_phase48_final_integration.py -q
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("emix48_data")
    port = _free_port()
    env = dict(os.environ)
    env.update({
        "PORT": str(port),
        "DATA_DIR": str(data_dir),
        "ADMIN_PASSWORD": "123456",
        "PYTHONPATH": str(REPO),
    })
    env.pop("RAILWAY_PUBLIC_DOMAIN", None)
    env["SMART_ROUTING_ENABLED"] = "false"  # v13.5: pre-default ON — tests stay hermetic
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
    yield {"base": base, "port": port}
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()


@pytest.fixture(scope="session")
def session(server):
    import http.cookiejar
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(
        f"{server['base']}/api/login", data=json.dumps({"password": "123456"}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with op.open(req, timeout=10) as r:
        assert r.status == 200
    return op


def api(op, base, path, method="GET", body=None, timeout=120):
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"}, method=method)
    try:
        with op.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.status, json.loads(e.read().decode())
        except Exception:
            return e.status, {}


def _mklink(op, base, **extra):
    body = {"label": "t48", "protocol": "vless-ws", "limit_value": 0,
            "expires_days": 0, **extra}
    st, d = api(op, base, "/api/links", "POST", body)
    assert st == 200, d
    return d["uuid"]


# ─────────────────────────────────────────────────────────────────────────────
# §A — CLIENT PING API (Real Client RTT — ثبت/اعتبارسنجی/ضد جعل)
# ─────────────────────────────────────────────────────────────────────────────
class TestClientPingAPI:
    def test_valid_client_ping_roundtrip(self, server, session):
        uid = _mklink(session, server["base"])
        samples = [120.5, 118.2, 125.0, 122.0, 119.0, 124.5]
        st, d = api(session, server["base"], f"/api/links/{uid}/client-ping", "POST", {
            "samples": samples, "measurement": "HTTPS", "first_ms": 480.0,
        })
        assert st == 200, d
        cp = d["client_ping"]
        assert cp["ok"] is True
        assert cp["measured_by"] == "client-browser"
        assert cp["measurement"] == "HTTPS"
        assert cp["total"] == 6 and cp["received"] == 6
        assert cp["min"] == 118.2 and cp["max"] == 125.0
        assert cp["median"] == 121.2          # sorted: 118.2,119,120.5,122,124.5,125 → (120.5+122)/2=121.25
        assert abs(cp["avg"] - 121.53) < 0.5
        assert cp["loss"] == 0
        assert cp["jitter"] is not None and cp["jitter"] > 0
        # ذخیره شده و در لیست برمی‌گردد (ثبات داده)
        st, d = api(session, server["base"], "/api/links")
        link = [l for l in d["links"] if l["uuid"] == uid][0]
        assert link["last_client_ping"]["median"] == 121.2

    def test_min_samples_enforced(self, server, session):
        uid = _mklink(session, server["base"])
        st, _ = api(session, server["base"], f"/api/links/{uid}/client-ping", "POST",
                    {"samples": [100, 105, 110]})
        assert st == 400          # سند: حداقل ۵ measurement

    def test_out_of_range_rejected(self, server, session):
        uid = _mklink(session, server["base"])
        for bad in ([0.2] * 6, [99999] * 6, [float("nan")] * 6):
            st, _ = api(session, server["base"], f"/api/links/{uid}/client-ping", "POST",
                        {"samples": bad})
            assert st == 400

    def test_fabricated_stats_rejected(self, server, session):
        """ضد جعل: median ارسالی که با نمونه‌ها نمی‌خواند رد می‌شود."""
        uid = _mklink(session, server["base"])
        st, _ = api(session, server["base"], f"/api/links/{uid}/client-ping", "POST", {
            "samples": [120, 121, 122, 123, 124, 125], "median": 42.0,
        })
        assert st == 400

    def test_loss_and_all_failed(self, server, session):
        uid = _mklink(session, server["base"])
        samples = [100.0, None, 102.0, None, 104.0, None]
        st, d = api(session, server["base"], f"/api/links/{uid}/client-ping", "POST",
                    {"samples": samples})
        assert st == 200
        assert d["client_ping"]["received"] == 3
        assert abs(d["client_ping"]["loss"] - 0.5) < 0.01
        # همه ناموفق → ok=false (Ping Failed — نه عدد ساختگی)
        st, d = api(session, server["base"], f"/api/links/{uid}/client-ping", "POST",
                    {"samples": [None] * 6})
        assert st == 200 and d["client_ping"]["ok"] is False
        assert d["client_ping"]["median"] is None

    def test_unknown_link_404(self, server, session):
        st, _ = api(session, server["base"], "/api/links/00000000-0000-0000-0000-000000000000/client-ping", "POST",
                    {"samples": [100] * 6})
        assert st == 404

    def test_unauthenticated_401(self, server):
        import http.cookiejar
        fresh = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        req = urllib.request.Request(
            f"{server['base']}/api/links/whatever/client-ping",
            data=json.dumps({"samples": [1] * 6}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            fresh.open(req, timeout=10)
            assert False, "باید 401 می‌داد"
        except urllib.error.HTTPError as e:
            assert e.status == 401

    def test_persistence_across_save(self, server, session):
        """client-ping در state ذخیره می‌شود (Volume)."""
        uid = _mklink(session, server["base"])
        api(session, server["base"], f"/api/links/{uid}/client-ping", "POST",
            {"samples": [111, 112, 113, 114, 115, 116]})
        st, d = api(session, server["base"], "/api/links")
        link = [l for l in d["links"] if l["uuid"] == uid][0]
        assert link["last_client_ping"]["median"] == 113.5  # (113+114)/2
        assert "measured_at" in link["last_client_ping"]


# ─────────────────────────────────────────────────────────────────────────────
# §B — endpoint_host (هدف واقعی پینگ مرورگر)
# ─────────────────────────────────────────────────────────────────────────────
class TestEndpointHost:
    def test_vless_endpoint_host_is_panel(self, server, session):
        _mklink(session, server["base"])
        st, d = api(session, server["base"], "/api/links")
        link = d["links"][0]
        assert link["endpoint_host"] is not None      # localhost در تست محلی معتبر است

    def test_mtproto_without_public_host_honest_null(self, server, session):
        body = {"label": "mt48", "protocol": "mtproto", "mtproto_port": 0}
        st, d = api(session, server["base"], "/api/links", "POST", body)
        assert st in (200, 409)   # 409 اگر پورت آزاد نباشد — تست host فقط روی 200
        if st == 200:
            st2, d2 = api(session, server["base"], "/api/links")
            mt = [l for l in d2["links"] if l["uuid"] == d["uuid"]][0]
            assert mt["endpoint_host"] is None   # صادقانه: قابل اندازه‌گیری نیست


# ─────────────────────────────────────────────────────────────────────────────
# §C — IRAN ROUTING per-link (مستقل از SNI و Smart Routing)
# ─────────────────────────────────────────────────────────────────────────────
class TestIranRouting:
    def test_create_with_iran_routing(self, server, session):
        st, d = api(session, server["base"], "/api/links", "POST",
                    {"label": "ir1", "protocol": "vless-ws", "iran_routing": "AUTO"})
        assert st == 200
        st2, d2 = api(session, server["base"], "/api/links")
        link = [l for l in d2["links"] if l["uuid"] == d["uuid"]][0]
        assert link["iran_routing"] == "AUTO"
        # مستقل بودن: spoof و SR ست نشده‌اند
        assert not link.get("spoof_sni_enabled") and link.get("smart_routing_mode", "OFF") == "OFF"

    def test_patch_iran_routing_modes(self, server, session):
        uid = _mklink(session, server["base"])
        for mode in ("AUTO", "DIRECT", "OFF"):
            st, _ = api(session, server["base"], f"/api/links/{uid}", "PATCH",
                        {"iran_routing": mode})
            assert st == 200
        st, d = api(session, server["base"], "/api/links")
        link = [l for l in d["links"] if l["uuid"] == uid][0]
        assert link["iran_routing"] == "OFF"

    def test_patch_invalid_mode_rejected(self, server, session):
        uid = _mklink(session, server["base"])
        st, _ = api(session, server["base"], f"/api/links/{uid}", "PATCH",
                    {"iran_routing": "ALWAYS"})
        assert st == 400

    def test_create_with_all_three_network_options(self, server, session):
        """سه قابلیت مستقل در یک ساخت: SNI spoof + SR + Iran Routing."""
        st, d = api(session, server["base"], "/api/links", "POST", {
            "label": "net3", "protocol": "vless-ws",
            "spoof_sni": "www.bale.ir", "spoof_sni_enabled": True,
            "smart_routing_mode": "AUTO", "iran_routing": "DIRECT",
        })
        assert st == 200, d
        st2, d2 = api(session, server["base"], "/api/links")
        link = [l for l in d2["links"] if l["uuid"] == d["uuid"]][0]
        assert link["spoof_sni_enabled"] is True and link["spoof_sni"] == "www.bale.ir"
        assert link["smart_routing_mode"] == "AUTO"
        assert link["iran_routing"] == "DIRECT"

    def test_iran_config_json_real_rules(self, server, session):
        uid = _mklink(session, server["base"], iran_routing="AUTO")
        st, cfg = api(session, server["base"], f"/api/links/{uid}/iran-config")
        assert st == 200, cfg
        rules = cfg["routing"]["rules"]
        tags = [r.get("outboundTag") for r in rules]
        # قواعد واقعی: private/ir → direct؛ آخرین قاعده → proxy
        assert "direct" in tags and "proxy" in tags
        ips = [ip for r in rules for ip in (r.get("ip") or [])]
        assert "geoip:ir" in ips and "geoip:private" in ips
        doms = [d for r in rules for d in (r.get("domain") or [])]
        assert any("bpi.ir" in d for d in doms)
        # outbound واقعی از خود لینک کاربر (vless با uuid)
        ob = [o for o in cfg["outbounds"] if o.get("tag") == "proxy"][0]
        assert ob["protocol"] == "vless"
        assert ob["settings"]["vnext"][0]["users"][0]["id"] == uid
        # صداقت: هیچ ادعای egress ایران در این feature نیست
        assert "IRAN_EGRESS" not in json.dumps(cfg)
        note = json.dumps(cfg["_emix"], ensure_ascii=False)
        assert "egress" in note and "verify" in note
        assert cfg["_emix"]["mode"] == "AUTO"

    def test_iran_config_direct_has_strict_rules(self, server, session):
        uid = _mklink(session, server["base"], iran_routing="DIRECT")
        st, cfg = api(session, server["base"], f"/api/links/{uid}/iran-config")
        assert st == 200
        doms = [d for r in cfg["routing"]["rules"] for d in (r.get("domain") or [])]
        assert "geosite:category-ir" in doms          # حالت DIRECT = قاعده‌ی اضافه

    def test_iran_config_off_rejected(self, server, session):
        uid = _mklink(session, server["base"])         # OFF
        st, _ = api(session, server["base"], f"/api/links/{uid}/iran-config")
        assert st == 400

    def test_trojan_link_parse(self, server, session):
        st, d = api(session, server["base"], "/api/links", "POST",
                    {"label": "trj", "protocol": "trojan-ws", "iran_routing": "AUTO"})
        assert st == 200
        st, cfg = api(session, server["base"], f"/api/links/{d['uuid']}/iran-config")
        assert st == 200
        ob = [o for o in cfg["outbounds"] if o.get("tag") == "proxy"][0]
        assert ob["protocol"] == "trojan"
        assert ob["settings"]["servers"][0]["address"]

    def test_sub_iran_endpoint_and_base_sub_untouched(self, server, session):
        uid = _mklink(session, server["base"], iran_routing="AUTO")
        # ساب پایه: همان base64 (رگرسیون — دست‌نخورده)
        with urllib.request.urlopen(f"{server['base']}/sub/{uid}", timeout=10) as r:
            import base64
            raw = base64.b64decode(r.read().decode()).decode()
        assert raw.startswith("vless://")
        # ساب ایران: JSON با قواعد
        with urllib.request.urlopen(f"{server['base']}/sub/{uid}/iran", timeout=10) as r:
            cfg = json.loads(r.read().decode())
        tags = [rr.get("outboundTag") for rr in cfg["routing"]["rules"]]
        assert "direct" in tags and "proxy" in tags

    def test_mtproto_iran_routing_rejected(self, server, session):
        body = {"label": "mtir", "protocol": "mtproto", "mtproto_port": 0,
                "iran_routing": "AUTO"}
        st, _ = api(session, server["base"], "/api/links", "POST", body)
        assert st == 400          # صادقانه: tg:// routing کلاینت ندارد


# ─────────────────────────────────────────────────────────────────────────────
# §D — sr_route روی links list (خلاصه‌ی صادق مسیر)
# ─────────────────────────────────────────────────────────────────────────────
class TestSrRouteSummary:
    def test_sr_link_without_active_route_honest_null(self, server, session):
        uid = _mklink(session, server["base"])
        api(session, server["base"], f"/api/links/{uid}", "PATCH",
            {"smart_routing_mode": "AUTO"})
        st, d = api(session, server["base"], "/api/links")
        link = [l for l in d["links"] if l["uuid"] == uid][0]
        # بدون مسیر ACTIVE (تستِ isolated) → null صادق + دلیل — نه مسیر جعلی
        assert link.get("sr_route") is None or link.get("sr_route", {}).get("endpoint")
        if link.get("sr_route") is None:
            assert link.get("sr_route_reason")

    def test_plain_link_no_sr_route_key(self, server, session):
        uid = _mklink(session, server["base"])
        st, d = api(session, server["base"], "/api/links")
        link = [l for l in d["links"] if l["uuid"] == uid][0]
        assert "sr_route" not in link or link.get("sr_route") is None


# ─────────────────────────────────────────────────────────────────────────────
# §E — UI: همه‌ی قابلیت‌ها واقعاً در pages.py متصل‌اند
# ─────────────────────────────────────────────────────────────────────────────
PAGES = (REPO / "pages.py").read_text(encoding="utf-8")


class TestUIIntegration:
    def test_config_builder_network_section(self):
        """بخش Network با سه قابلیت جداجدا در Config Builder (ساخت)."""
        assert 'id="netopt-section"' in PAGES
        assert 'بهینه‌سازی شبکه' in PAGES
        assert 'id="nl-spoof-toggle"' in PAGES and 'id="nl-spoof-sni"' in PAGES
        assert 'id="nl-sr-toggle"' in PAGES and 'id="nl-sr-mode"' in PAGES
        assert 'id="nl-iran-mode"' in PAGES
        for m in ("OFF", "AUTO", "DIRECT"):
            assert f'value="{m}"' in PAGES

    def test_edit_modal_iran_select(self):
        assert 'id="el-iran-mode"' in PAGES

    def test_client_ping_on_card(self):
        """دکمه‌ی پینگ کارت → اندازه‌گیری از مرورگر (نه سرور)."""
        assert "async function clientPing(uuid,btn)" in PAGES
        assert "onclick=\"clientPing('${l.uuid}',this)\"" in PAGES
        assert "function _cpProbe(host)" in PAGES
        assert "mode:'no-cors'" in PAGES
        assert "performance.now()" in PAGES
        # پینگ قدیمیِ سرور روی کارت حذف شده
        assert "pingLink('${l.uuid}'" not in PAGES

    def test_ping_stats_and_median_main(self):
        """min/median/avg/max/jitter/loss — پینگ اصلی = MEDIAN."""
        for fn in ("_cpStats(", "runClientPing(", "openPingDetails(", "pdRetest("):
            assert fn in PAGES
        assert "median" in PAGES and "jitter" in PAGES
        assert "CP_PROBES=6" in PAGES           # ۶ نمونه (≥۵ طبق سند)

    def test_ping_details_modal(self):
        assert 'id="modal-ping-details"' in PAGES
        assert 'id="pd-body"' in PAGES and 'id="pd-sub"' in PAGES
        assert "Measurement" in PAGES
        assert "HTTPS RTT" in PAGES             # برچسب صادق روش اندازه‌گیری
        assert "ICMP نیست" in PAGES             # صراحت: app-level معرفی نمی‌شود

    def test_ping_badge_client_first(self):
        """پینگ اصلی = Client RTT؛ نبودِ اندازه‌گیری = «—» (نه عدد سرور)."""
        assert "last_client_ping" in PAGES
        assert "Ping —" in PAGES
        assert "Ping Failed" in PAGES
        assert "Client RTT" in PAGES

    def test_ping_all_client_side(self):
        assert "runClientPing(cpHostOf(l))" in PAGES

    def test_route_details_modal(self):
        assert 'id="modal-route-details"' in PAGES
        assert "openRouteDetails(" in PAGES
        for k in ("Route Latency", "Client RTT", "Egress", "Score", "Jitter"):
            assert k in PAGES

    def test_iran_badge_and_download(self):
        assert "function iranBadge(l)" in PAGES
        assert "downloadIranConfig(" in PAGES
        assert "/iran-config" in PAGES

    def test_sr_badge_route_info(self):
        assert "l.sr_route" in PAGES
        assert "openRouteDetails" in PAGES

    def test_server_ping_stays_labeled_in_health(self):
        """Real Delay سمت سرور فقط در بخش سلامت با برچسب صادق مانده."""
        assert "healthTestAll" in PAGES
        assert "/api/links/ping-all" in PAGES

    def test_js_blocks_valid(self, tmp_path):
        import re
        scripts = re.findall(r"<script>(.*?)</script>", PAGES, re.S)
        assert len(scripts) >= 2
        js = tmp_path / "b1.js"
        js.write_text(scripts[1], encoding="utf-8")
        r = subprocess.run(["node", "--check", str(js)], capture_output=True)
        assert r.returncode == 0, r.stderr.decode()[:400]

    def test_mobile_responsive_modals(self):
        # مودال‌های جدید از همان کلاس‌های ریسپانسیو پایه استفاده می‌کنند
        assert '<div class="modal-v2" style="max-width:430px">' in PAGES
        assert '<div class="modal-v2" style="max-width:470px">' in PAGES


# ─────────────────────────────────────────────────────────────────────────────
# §F — Regression + version
# ─────────────────────────────────────────────────────────────────────────────
class TestRegression:
    def test_clean_link_untouched_with_iran_off(self):
        """لینک بدون feature (با iran_routing=OFF ست‌شده) بایت‌به‌بایت پایه است."""
        import main as m
        UID = "48484848-4848-4848-4848-484848484848"
        m.LINKS[UID] = {"label": "t", "alpn": "h2", "fingerprint": "chrome",
                        "iran_routing": "OFF", "smart_routing_mode": "OFF"}
        try:
            v = m.generate_share_link(UID, "panel.test", remark="r", protocol="vless-ws")
            assert v == f"vless://{UID}@panel.test:443?encryption=none&security=tls&type=ws&host=panel.test&path=/ws/{UID}&sni=panel.test&fp=chrome&alpn=h2#r"
        finally:
            m.LINKS.pop(UID, None)

    def test_version_13_4(self, server, session):
        st, d = api(session, server["base"], "/api/deployment-version")
        assert st == 200
        assert d["version"] == "13.7.0-emix-pro", d

    def test_existing_login_still_works(self, server, session):
        st, d = api(session, server["base"], "/api/links")
        assert st == 200 and "links" in d

    def test_health_endpoint(self, server):
        with urllib.request.urlopen(f"{server['base']}/api/ping", timeout=10) as r:
            assert json.loads(r.read().decode())["ok"] is True
