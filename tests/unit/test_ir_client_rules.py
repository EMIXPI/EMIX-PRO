# tests/unit/test_ir_client_rules.py — v12.1.0 IR-Direct client rules
# ══════════════════════════════════════════════════════════════════════════════
# «داخلی کردن مصرف حتی با کانفیگ» — کانفیگ کامل کلاینت (sing-box / xray) با
# قواعد split-tunneling. قراردادها:
#   §1  خروجی sing-box: outbounds (proxy/direct/block) + route.rules شامل
#       domain_suffix [.ir] و ip_cidr [پیشوندهای دیتاست] → direct، final=proxy
#   §2  خروجی xray: routing.rules با ip/domain → direct + outbounds freedom
#   §3  single-source-of-truth: پروکسی‌ساید از URI منتشرشده پارس می‌شود —
#       SNI spoof (allowInsecure بدون CDN) دقیقاً منعکس می‌شود
#   §4  صداقت: ss/mtproto و xhttp-on-singbox → SPLIT_TUNNEL_NOT_SUPPORTED
#   §5  پشتیبانی پروتکل‌ها (client_rules_supported) هم‌عرض با بیلدر
# ══════════════════════════════════════════════════════════════════════════════
import asyncio

import pytest

import ir_client_rules as icr


VLESS_URI = ("vless://aaa1b2c3-d4e5-f6a7-b8c9-d0e1f2a3b4c5@test.example.com:443"
             "?encryption=none&security=tls&type=ws&host=test.example.com"
             "&path=%2Fws%2Faaa1b2c3&sni=test.example.com&fp=chrome"
             "&alpn=h2%2Chttp%2F1.1")
SPOOFED_URI = ("vless://aaa1b2c3-d4e5-f6a7-b8c9-d0e1f2a3b4c5@test.example.com:443"
               "?encryption=none&security=tls&type=ws&host=test.example.com"
               "&path=%2Fws%2Faaa1b2c3&sni=dl.example.ir&fp=chrome"
               "&alpn=h2%2Chttp%2F1.1&allowInsecure=1")
TROJAN_URI = ("trojan://aaa1b2c3-d4e5-f6a7-b8c9-d0e1f2a3b4c5@test.example.com:443"
              "?security=tls&type=ws&host=test.example.com&path=%2Ftrojan-ws"
              "&sni=test.example.com&fp=chrome&alpn=h2%2Chttp%2F1.1")
SS_URI = ("ss://YWVzLTI1Ni1nY206cGFzcw==@test.example.com:443"
          "?security=tls&type=ws&host=test.example.com&path=%2Fss-ws#EMIX")
XHTTP_URI = ("vless://aaa1b2c3-d4e5-f6a7-b8c9-d0e1f2a3b4c5@test.example.com:443"
             "?encryption=none&security=tls&type=xhttp&mode=packet-up"
             "&host=test.example.com&path=%2Fxhttp-siz10%2Fpacket-up%2Faaa1b2c3"
             "&sni=test.example.com&fp=chrome&alpn=h2%2Chttp%2F1.1")

PREFIXES = ["5.144.128.0/17", "188.121.96.0/19", "2a06:2b00::/29"]


GW_SOCKS = {"gateway_id": "gw-t", "name": "Tehran", "endpoint": "5.144.1.2",
            "port": 1080, "protocol": "socks5", "username": "u1",
            "password": "p1", "egress_ip": "5.144.1.2"}
GW_HTTP = {"gateway_id": "gw-h", "name": "Tabriz", "endpoint": "gw.example.ir",
           "port": 8080, "protocol": "http", "username": "",
           "password": "", "egress_ip": "2.1.2.3"}


def _setup(uri: str, gateway: dict | None = None):
    link = {"label": "t", "protocol": "vless-ws", "active": True,
            "used_bytes": 0, "limit_bytes": 0, "expires_at": None}
    icr.set_deps(
        get_link_fn=lambda uid: _async(link),
        is_allowed_fn=lambda l: True,
        share_link_fn=lambda uid, host, remark="", protocol="vless-ws": uri,
        host_fn=lambda: "test.example.com",
        headers_fn=lambda *a, **k: {"profile-title": "t"},
        prefixes_fn=lambda: list(PREFIXES),
        default_protocol="vless-ws",
        gateway_fn=lambda: gateway,
    )
    return link


async def _async(v):
    return v


def _build(client: str, uri: str = VLESS_URI, geosite: bool = False,
           exit_mode: str = "auto", gateway: dict | None = None):
    _setup(uri, gateway=gateway)
    return asyncio.run(icr.build_client_rules_config_async(
        "aaa1b2c3-d4e5-f6a7-b8c9-d0e1f2a3b4c5", client, geosite=geosite,
        exit_mode=exit_mode))


# ── §1 sing-box ──────────────────────────────────────────────────────────────

def test_singbox_structure_and_ir_rules():
    config, meta = _build("singbox")
    types = [o["type"] for o in config["outbounds"]]
    assert "proxy" in [o["tag"] for o in config["outbounds"]]
    assert {"direct", "block"} <= set(types)
    proxy = next(o for o in config["outbounds"] if o["tag"] == "proxy")
    assert proxy["type"] == "vless" and proxy["uuid"] == "aaa1b2c3-d4e5-f6a7-b8c9-d0e1f2a3b4c5"
    assert proxy["transport"]["type"] == "ws"
    assert proxy["tls"]["server_name"] == "test.example.com"
    rules = config["route"]["rules"]
    domain_rules = [r for r in rules if "domain_suffix" in r]
    ip_rules = [r for r in rules if "ip_cidr" in r]
    assert domain_rules and ".ir" in domain_rules[0]["domain_suffix"]
    assert domain_rules[0]["outbound"] == "direct"
    assert ip_rules and set(ip_rules[0]["ip_cidr"]) == set(PREFIXES)
    assert config["route"]["final"] == "proxy"
    assert meta["prefix_count"] == len(PREFIXES)


def test_singbox_dns_ir_domains_go_direct_dns():
    config, _ = _build("singbox")
    dns_rules = [r for r in config["dns"]["rules"] if r]
    assert any(".ir" in (r.get("domain_suffix") or []) for r in dns_rules)


# ── §2 xray ──────────────────────────────────────────────────────────────────

def test_xray_structure_and_ir_rules():
    config, meta = _build("xray")
    protocols = {o["tag"]: o["protocol"] for o in config["outbounds"]}
    assert protocols["proxy"] == "vless"
    assert protocols["direct"] == "freedom"
    rules = config["routing"]["rules"]
    ip_rule = next(r for r in rules if "ip" in r)
    assert set(ip_rule["ip"]) == set(PREFIXES) and ip_rule["outboundTag"] == "direct"
    dom_rule = next(r for r in rules if "domain" in r)
    assert ".ir" in dom_rule["domain"] and dom_rule["outboundTag"] == "direct"


def test_xray_xhttp_transport_and_singbox_rejects():
    cfg, _ = _build("xray", uri=XHTTP_URI)
    ss = cfg["outbounds"][0]["streamSettings"]
    assert ss["network"] == "xhttp" and ss["xhttpSettings"]["mode"] == "packet-up"
    with pytest.raises(icr.IrRulesError) as ei:
        _build("singbox", uri=XHTTP_URI)
    assert ei.value.code == "SPLIT_TUNNEL_NOT_SUPPORTED"
    assert "xray" in ei.value.detail


# ── §3 SNI spoofing بازتاب داده می‌شود ───────────────────────────────────────

def test_sni_spoof_reflected_in_client_configs():
    s_cfg, s_meta = _build("singbox", uri=SPOOFED_URI)
    proxy = next(o for o in s_cfg["outbounds"] if o["tag"] == "proxy")
    assert proxy["tls"]["server_name"] == "dl.example.ir"
    assert proxy["tls"]["insecure"] is True
    assert s_meta["sni"] == "dl.example.ir"
    x_cfg, _ = _build("xray", uri=SPOOFED_URI)
    tls = x_cfg["outbounds"][0]["streamSettings"]["tlsSettings"]
    assert tls["serverName"] == "dl.example.ir" and tls["allowInsecure"] is True


def test_trojan_supported_on_both_clients():
    s_cfg, _ = _build("singbox", uri=TROJAN_URI)
    assert next(o for o in s_cfg["outbounds"] if o["tag"] == "proxy")["type"] == "trojan"
    x_cfg, _ = _build("xray", uri=TROJAN_URI)
    assert x_cfg["outbounds"][0]["protocol"] == "trojan"


# ── §4 صداقت ─────────────────────────────────────────────────────────────────

def test_shadowsocks_honestly_rejected():
    for client in ("singbox", "xray"):
        with pytest.raises(icr.IrRulesError) as ei:
            _build(client, uri=SS_URI)
        assert ei.value.code == "SPLIT_TUNNEL_NOT_SUPPORTED"


def test_unknown_client_rejected():
    with pytest.raises(icr.IrRulesError):
        _build("clash")


# ── §5 ماتریس پشتیبانی ───────────────────────────────────────────────────────

def test_client_rules_supported_matrix():
    assert icr.client_rules_supported("vless-ws")
    assert icr.client_rules_supported("trojan-ws")
    assert icr.client_rules_supported("vless-xhttp-packet-up")
    assert not icr.client_rules_supported("shadowsocks")
    assert not icr.client_rules_supported("mtproto")
    assert not icr.client_rules_supported("")


# ── §6 Iran-Exit (v12.2) — «IP من با کانفیگ همچنان ایران» ────────────────────

def test_singbox_ir_exit_chains_through_gateway():
    cfg, meta = _build("singbox", exit_mode="ir", gateway=GW_SOCKS)
    gw_ob = next(o for o in cfg["outbounds"] if o["tag"] == "ir-gateway")
    assert gw_ob["type"] == "socks"
    assert gw_ob["server"] == "5.144.1.2" and gw_ob["server_port"] == 1080
    assert gw_ob["detour"] == "proxy"          # زنجیره: کلاینت→EMIX→گیت‌وی
    assert gw_ob["username"] == "u1" and gw_ob["password"] == "p1"
    assert cfg["route"]["final"] == "ir-gateway"  # همه‌ی ترافیک نامتعارض از ایران
    # قواعد IR-Direct سر جایشان: داخلی از ISP کاربر (باز IP ایران)
    dom = next(r for r in cfg["route"]["rules"] if "domain_suffix" in r)
    assert dom["outbound"] == "direct"
    assert meta["exit"] == "ir" and meta["gateway"] == "5.144.1.2"


def test_singbox_ir_exit_http_gateway_no_auth():
    cfg, _ = _build("singbox", exit_mode="ir", gateway=GW_HTTP)
    gw_ob = next(o for o in cfg["outbounds"] if o["tag"] == "ir-gateway")
    assert gw_ob["type"] == "http" and "username" not in gw_ob
    assert gw_ob["detour"] == "proxy"


def test_xray_ir_exit_dialer_proxy_first_outbound():
    cfg, meta = _build("xray", exit_mode="ir", gateway=GW_SOCKS)
    first = cfg["outbounds"][0]
    assert first["tag"] == "ir-gateway" and first["protocol"] == "socks"
    assert first["streamSettings"]["sockopt"]["dialerProxy"] == "proxy"
    assert first["settings"]["servers"][0]["users"][0]["user"] == "u1"
    # در xray ترافیک بدون-قاعده به اولین outbound می‌رود → ایران
    dom = next(r for r in cfg["routing"]["rules"] if "domain" in r)
    assert dom["outboundTag"] == "direct"
    assert meta["exit"] == "ir"


def test_ir_exit_without_verified_gateway_is_honest():
    for client in ("singbox", "xray"):
        with pytest.raises(icr.IrRulesError) as ei:
            _build(client, exit_mode="ir", gateway=None)
        assert ei.value.code == "NO_VERIFIED_IRAN_GATEWAY"
        assert "VERIFIED" in ei.value.detail


def test_invalid_exit_mode_rejected():
    with pytest.raises(icr.IrRulesError) as ei:
        _build("singbox", exit_mode="banana")
    assert ei.value.code == "INVALID_EXIT_MODE"


def test_auto_mode_ignores_gateway():
    cfg, meta = _build("singbox", exit_mode="auto", gateway=GW_SOCKS)
    assert "ir-gateway" not in [o["tag"] for o in cfg["outbounds"]]
    assert cfg["route"]["final"] == "proxy"
    assert meta["exit"] == "auto"
