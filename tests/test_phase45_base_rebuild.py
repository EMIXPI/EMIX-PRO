"""Phase 45 — pytest suite for EMIX-PRO v13.1 (rebuilt on the EMIX base).

fresh, focused suite for the new architecture:
- base core integrity (byte-level, golden behaviors, originality guard)
- REAL E2E ping engine (subprocess uvicorn + real protocol handlers)
- health-all report + version pin

Run:  python -m pytest tests/ -q
"""
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
from collections import Counter
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


# ─────────────────────────────────────────────────────────────────────────────
# §A — base core integrity (static; no server needed)
# ─────────────────────────────────────────────────────────────────────────────
class TestBaseIntegrity:
    def test_protocols_tuple_untouched(self):
        import main as m
        assert m.PROTOCOLS == (
            "vless-ws", "xhttp-packet-up", "xhttp-stream-up",
            "trojan-ws", "trojan-xhttp-packet-up", "trojan-xhttp-stream-up",
            "mtproto", "shadowsocks",
        )
        assert m.DEFAULT_PROTOCOL == "vless-ws"

    def test_share_link_golden_formats(self):
        import main as m
        uid = "01234567-89ab-cdef-0123-456789abcdef"
        m.LINKS[uid] = {"label": "t", "alpn": "h2", "fingerprint": "chrome"}
        try:
            host = "panel.test"
            v = m.generate_share_link(uid, host, remark="r", protocol="vless-ws")
            assert v.startswith(f"vless://{uid}@{host}:443?")
            assert "type=ws" in v and f"path=/ws/{uid}" in v and f"sni={host}" in v

            t = m.generate_share_link(uid, host, remark="r", protocol="trojan-ws")
            assert t.startswith(f"trojan://{uid}@{host}:443?")
            assert "type=ws" in t and "path=/trojan-ws" in t

            x = m.generate_share_link(uid, host, remark="r", protocol="xhttp-packet-up")
            assert x.startswith(f"vless://{uid}@{host}:443?")
            assert "type=xhttp" in x and "mode=packet-up" in x
            assert f"path=/xhttp-siz10/packet-up/{uid}" in x

            tx = m.generate_share_link(uid, host, remark="r", protocol="trojan-xhttp-stream-up")
            assert tx.startswith(f"trojan://{uid}@{host}:443?")
            assert "mode=stream-up" in tx and f"/txhttp-siz10/stream-up/{uid}" in tx

            ss = m.generate_share_link(uid, host, remark="r", protocol="shadowsocks")
            assert ss.startswith("ss://") and f"@{host}:443" in ss
        finally:
            m.LINKS.pop(uid, None)

    def test_base_core_files_identical_to_emix_reference(self):
        """هسته‌ی EMIX باید بایت‌به‌بایت با ریپوی مرجع یکی باشد (اگر مرجع حاضر باشد).

        مستثنای مستند و تنها: protocol/trojan/trojan.py — رفع باگ پنهان HashCache
        (حذف+ساخت لینک → auth لینک جدید Trojan می‌شکست؛ Phase 45 با ۳ خط،
        با شواهد تست کامل در §B)."""
        ref = Path("/home/z/my-project/emix-healthy")
        if not ref.exists():
            pytest.skip("EMIX reference repo not present in this environment")
        files = ["central.py", "updater.py", "botgeneratedomin.py",
                 "bottokentcpproxy.py", "zeussocks5.py", "requirements.txt"]
        for f in files:
            assert (REPO / f).read_bytes() == (ref / f).read_bytes(), f"base file changed: {f}"
        for pf in sorted((ref / "protocol").rglob("*.py")):
            rel = pf.relative_to(ref)
            if str(rel) == "protocol/trojan/trojan.py":
                continue  # تنها مستثنای مستند (رفع باگ HashCache — بالا)
            assert (REPO / rel).read_bytes() == pf.read_bytes(), f"protocol file changed: {rel}"

    def test_main_pages_only_additive_diff(self):
        """main.py / pages.py فقط درجِ افزودنی دارند — هیچ خطِ موجودِ پایه حذف نشده."""
        ref = Path("/home/z/my-project/emix-healthy")
        if not (ref / "main.py").exists():
            pytest.skip("EMIX reference repo not present")
        for fname in ["main.py", "pages.py"]:
            base_lines = (ref / fname).read_text(encoding="utf-8").splitlines()
            new_lines = (REPO / fname).read_text(encoding="utf-8").splitlines()
            base_cnt = Counter(l for l in base_lines if l.strip())
            new_cnt = Counter(l for l in new_lines if l.strip())
            lost = {l: c for l, c in base_cnt.items() if new_cnt[l] < c}
            assert not lost, f"{fname}: base lines removed: {list(lost)[:5]}"

    def test_no_worker_cf_machinery_in_source(self):
        """ماشین‌های worker/CF اضافه‌شده‌ی خود ما از سورس حذف شده‌اند."""
        guard = {
            "main.py": ["personalemixone", "emix-gateway", "EMIX_PUBLIC_HOST", "cf_gateway",
                        "cloudflare_edge", "smart_route", "sni_spoof", "iran_gateway", "multiloc"],
            "pages.py": ["personalemixone", "emix-gateway", "EMIX_PUBLIC_HOST", "cf_gateway",
                         "cloudflare_edge", "sni_spoof"],
            "link_health.py": ["spoof", "workers.dev", "personalemixone"],
            "emix_pro.py": ["workers.dev", "personalemixone"],
        }
        for fname, bads in guard.items():
            src = (REPO / fname).read_text(encoding="utf-8")
            for b in bads:
                assert b not in src, f"{fname} still references {b!r}"

    def test_version_module(self):
        import emix_pro
        assert emix_pro.EMIX_PRO_VERSION == "13.1.0-emix-pro"
        assert "real-e2e-ping" in emix_pro.EMIX_PRO_FEATURES


# ─────────────────────────────────────────────────────────────────────────────
# live server fixture (REAL uvicorn subprocess, real handlers)
# ─────────────────────────────────────────────────────────────────────────────
def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("emix45_data")
    port = _free_port()
    env = dict(os.environ)
    env.update({
        "PORT": str(port),
        "DATA_DIR": str(data_dir),
        "ADMIN_PASSWORD": "123456",
        "PYTHONPATH": str(REPO),
    })
    env.pop("RAILWAY_PUBLIC_DOMAIN", None)
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
    yield base
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
        f"{server}/api/login", data=json.dumps({"password": "123456"}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with op.open(req, timeout=10) as r:
        assert r.status == 200
    return op


# plain opener for no-auth endpoints (module has no .open)
_plain_opener = urllib.request.build_opener()


def api(op, base, path, method="GET", body=None, timeout=90):
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"}, method=method)
    with op.open(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


# ─────────────────────────────────────────────────────────────────────────────
# §B — REAL E2E ping per protocol (real client path through real handlers)
# ─────────────────────────────────────────────────────────────────────────────
PROBE_PROTOCOLS = [
    "vless-ws", "trojan-ws", "shadowsocks",
    "xhttp-packet-up", "xhttp-stream-up",
    "trojan-xhttp-packet-up", "trojan-xhttp-stream-up",
]


class TestRealPingEngine:
    @pytest.mark.parametrize("proto", PROBE_PROTOCOLS)
    def test_real_e2e_ping(self, server, session, proto):
        st, link = api(session, server, "/api/links", "POST",
                       {"label": f"t-{proto}", "protocol": proto, "limit_value": 0})
        assert st == 200
        try:
            st, p = api(session, server, f"/api/links/{link['uuid']}/ping", "POST", {})
            assert p.get("ok") is True, p
            assert p.get("ws_ms") is not None and p["ws_ms"] > 0
            assert p.get("e2e_ms") is not None and p["e2e_ms"] > 0
            assert "HTTP" in (p.get("reply") or "")
        finally:
            api(session, server, f"/api/links/{link['uuid']}", "DELETE")

    def test_ping_all_shape_and_persistence(self, server, session):
        st, link = api(session, server, "/api/links", "POST",
                       {"label": "t-all", "protocol": "vless-ws"})
        try:
            st, d = api(session, server, "/api/links/ping-all", "POST", {}, timeout=180)
            assert st == 200
            assert d["total"] >= 1
            assert d["ok"] >= 1
            assert d["failed"] == d["total"] - d["ok"]
            assert d["stages"] == ["connect", "ws-handshake", "protocol", "tunnel-reply"]
            st, links = api(session, server, "/api/links")
            mine = [l for l in links["links"] if l["uuid"] == link["uuid"]][0]
            assert mine.get("last_ping", {}).get("ok") is True
        finally:
            api(session, server, f"/api/links/{link['uuid']}", "DELETE")

    def test_trojan_hashcache_delete_create_regression(self, server, session):
        """Regression (باگ پنهان پایه، رفع Phase 45): حذف یک لینک و ساخت لینک جدید
        (طول dict یکسان می‌ماند) → cache هش Trojan کهنه می‌شد و auth لینک جدید با
        «trojan auth failed» می‌شکست — کانفیگ ظاهراً سالم ولی قطع. بعد از fix،
        هر چرخه‌ی حذف+ساخت باید بلافاصله سالم ping بدهد."""
        leftover = []
        try:
            for proto in ["trojan-ws", "trojan-ws", "trojan-xhttp-packet-up",
                          "trojan-xhttp-stream-up", "trojan-ws"]:
                st, link = api(session, server, "/api/links", "POST",
                               {"label": f"reg-{proto}", "protocol": proto})
                leftover.append(link["uuid"])
                st, p = api(session, server, f"/api/links/{link['uuid']}/ping", "POST", {})
                assert p.get("ok") is True, f"hash-cache regression: {proto} → {p.get('detail')}"
                api(session, server, f"/api/links/{link['uuid']}", "DELETE")
                leftover.pop()
        finally:
            for u in leftover:
                try:
                    api(session, server, f"/api/links/{u}", "DELETE")
                except Exception:
                    pass

    def test_ping_unknown_link_404(self, server, session):
        with pytest.raises(urllib.error.HTTPError) as e:
            api(session, server, "/api/links/nonexistent/ping", "POST", {})
        assert e.value.code == 404

    def test_ping_requires_auth(self, server):
        with pytest.raises(urllib.error.HTTPError) as e:
            req = urllib.request.Request(f"{server}/api/links/ping-all", method="POST")
            urllib.request.urlopen(req, timeout=10)
        assert e.value.code == 401

    def test_best_links_ranking(self, server, session):
        st, link = api(session, server, "/api/links", "POST",
                       {"label": "t-best", "protocol": "trojan-ws"})
        try:
            st, d = api(session, server, "/api/links/best", "POST", {}, timeout=180)
            assert st == 200
            assert d["healthy"] >= 1 and len(d["ranking"]) >= 1
            assert d["ranking"][0]["total_ms"] > 0
        finally:
            api(session, server, f"/api/links/{link['uuid']}", "DELETE")


# ─────────────────────────────────────────────────────────────────────────────
# §C — health-all + version + heartbeat
# ─────────────────────────────────────────────────────────────────────────────
class TestHealthAndVersion:
    def test_deployment_version_pin(self, server):
        st, v = api(_plain_opener, server, "/api/deployment-version")
        assert v["version"] == "13.1.0-emix-pro"
        assert "EMIX 9.2" in v["base_panel"]
        assert "real-e2e-ping" in v["features"]

    def test_health_all_sections(self, server, session):
        st, h = api(session, server, "/api/system/health-all", timeout=30)
        assert st == 200
        secs = h["sections"]
        for k in ["panel", "links", "protocols", "egress", "volume", "runtime"]:
            assert k in secs
        assert secs["links"]["total"] >= 0
        assert secs["volume"]["writable"] is True
        assert set(secs["protocols"]["supported"]) == set(PROBE_PROTOCOLS + ["mtproto"])

    def test_health_all_requires_auth(self, server):
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"{server}/api/system/health-all", timeout=10)
        assert e.value.code == 401

    def test_api_ping_heartbeat(self, server):
        st, p = api(_plain_opener, server, "/api/ping")
        assert p["ok"] is True


# ─────────────────────────────────────────────────────────────────────────────
# §D — dashboard UI wiring + originality
# ─────────────────────────────────────────────────────────────────────────────
class TestDashboardUI:
    def get_html(self, server, session):
        with session.open(urllib.request.Request(f"{server}/dashboard"), timeout=10) as r:
            return r.read().decode()

    def test_ui_needles(self, server, session):
        html = self.get_html(server, session)
        for needle in ["سلامت سیستم", "تست همه‌ی کانفیگ‌ها", "modal-health",
                       "pingLink", "pingBadge", "openHealth", "healthTestAll",
                       "/api/system/health-all", "/api/links/ping-all"]:
            assert needle in html, f"missing UI needle: {needle}"

    def test_no_added_cf_worker_machinery_in_html(self, server, session):
        html = self.get_html(server, session)
        for bad in ["personalemixone", "emix-gateway", "EMIX_PUBLIC_HOST",
                    "cf_gateway", "sni_spoof"]:
            assert bad not in html, f"worker/CF leftover in UI: {bad}"

    def test_js_blocks_parse(self, server, session):
        html = self.get_html(server, session)
        scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
        assert scripts
        for i, s in enumerate(scripts):
            tmp = Path(f"/tmp/phase45_test_js_{i}.js")
            tmp.write_text(s, encoding="utf-8")
            r = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True)
            assert r.returncode == 0, f"JS block {i} broken: {r.stderr[:200]}"
