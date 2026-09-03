# ══════════════════════════════════════════════════════════════════════════════
# ir_client_rules.py — ساب JSON با قواعد IR-Direct (هسته‌ی همیشه‌زنده v12.1)
#
# 🔴 دردی که حل می‌کند (خواسته‌ی صریح اپراتور):
#   «داخلی کردن مصرف حتی با کانفیگ» — مصرف داخلی از مسیر ISP خود کاربر برود،
#   حتی وقتی از کانفیگ استفاده می‌کند؛ سریع‌تر، بدون بلاک داخلی، و بدون
#   هدررفت پهنای‌باند Railway برای ترافیک ایران.
#
# چطور؟ کانفیگ‌های URI-محور (vless://…) قابلیت حمل قواعد روتینگ ندارند —
# قبلاً همین‌جا دو راه داشتیم: یا «فقط ظاهرِ پشتیبانی» یا صداقت
# (SPLIT_TUNNEL_NOT_SUPPORTED). راه سوم درست است: خروجی **کانفیگ کامل
# کلاینت** (sing-box / xray) که هم پروکسی EMIX را دارد هم route rules:
#
#     ┌─ مقصد ایرانی (IP در پیشوندهای RIPEstat-IR یا دامنه‌ی .ir) → direct
#     └─ بقیه‌ی دنیا → پروکسی EMIX (همان کانفیگ، همان UUID، همان SNI/اسپویف)
#
# ✅ یک منبع حقیقت: پروکسی‌ساید کانفیگ از **همان generate_share_link پارس**
#    می‌شود — یعنی SNI Spoofing (هر دو حالت CDN و allowInsecure) و واریانت
#    CF و هر تغییر آینده‌ی emission خودکار اینجا هم اعمال می‌شود.
# ✅ پیشوندها از همان دیتاست موتور domestic می‌آیند (dataset_prefixes).
# ✅ صداقت: پروتکل/کلاینتی که رول‌پذیر نیست → SPLIT_TUNNEL_NOT_SUPPORTED —
#    هرگز کانفیگی که فقط «شبیه» split-tunnel است تحویل داده نمی‌شود.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

# نکته: Request/HTTPException باید در سطح ماژول باشند — با postponed
# annotations، FastAPI انوتیشن‌ها را در __globals__ تابع رزولور می‌کند.
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

import ipaddress
from typing import Callable, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

IR_CLIENT_RULES_VERSION = "1.0.0"

SUPPORTED_CLIENTS = ("singbox", "xray")

# پروتکل‌هایی که کانفیگ کامل کلاینت‌شان قابل ساخت است (تورنت/MTProto خیر).
# xhttp فقط برای xray — برای singbox در زمان build صادقانه رد می‌شود.
SUPPORTED_PROTOCOLS = (
    "vless-ws", "trojan-ws",
    "vless-xhttp-packet-up", "vless-xhttp-stream-up",
    "trojan-xhttp-packet-up", "trojan-xhttp-stream-up",
)


def client_rules_supported(protocol: str) -> bool:
    """برای فیلد sub_json_urls در /api/links — قضاوت نهایی هنگام build است."""
    return (protocol or "") in SUPPORTED_PROTOCOLS


# قواعد دامنه‌ای مبتنی بر TLD — بدون نیاز به فایل geosite سمت کلاینت
IR_DOMAIN_SUFFIXES = [".ir", ".ایران"]

# قواعد سراسری سمت کلاینت (اختیاری، ?geosite=1): فایل‌های rule-set رسمی
_SINGBOX_GEOSITE_IR = ("https://raw.githubusercontent.com/SagerNet/sing-geosite/"
                       "rule-set/geosite-ir.srs")
_XRAY_GEOSITE_IR = "geosite:ir"


class IrRulesError(Exception):
    """خطای صادقانه‌ی تولید قواعد — code یکی از:
    SPLIT_TUNNEL_NOT_SUPPORTED | NO_DATASET (با rule دامنه‌ای ادامه داده می‌شود)"""
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(detail or code)


# ── DI container (بدون import چرخشی از main) ────────────────────────────────
_deps: Dict[str, Callable] = {}


def set_deps(get_link_fn, is_allowed_fn, share_link_fn, host_fn,
             headers_fn, prefixes_fn, default_protocol) -> None:
    _deps.clear()
    _deps.update({
        "get_link": get_link_fn,           # async (uid) -> link | None
        "is_allowed": is_allowed_fn,       # (link) -> bool
        "share_link": share_link_fn,       # (uuid, host, remark, protocol) -> uri
        "host": host_fn,                   # () -> public host
        "headers": headers_fn,             # build_sub_headers(label, used, limit, expires)
        "prefixes": prefixes_fn,           # () -> list[str] normalized IR prefixes
        "default_protocol": default_protocol,
    })


# ── پارس URI منتشرشده — single source of truth برای پروکسی‌ساید ─────────────

def _parse_share_uri(uri: str) -> dict:
    u = urlparse(uri)
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    return {
        "scheme": u.scheme,                       # vless | trojan | ss
        "uuid": unquote(u.username or ""),
        "password": unquote(u.password or ""),
        "host": u.hostname or "",
        "port": u.port or 443,
        "net": q.get("type", "ws"),
        "mode": q.get("mode", ""),
        "security": q.get("security", "tls"),
        "ws_host": q.get("host", ""),
        "path": unquote(q.get("path", "/")),
        "sni": q.get("sni", ""),
        "fp": q.get("fp", "chrome"),
        "alpn": [a for a in unquote(q.get("alpn", "")).split(",") if a],
        "insecure": q.get("allowInsecure") == "1",
    }


def _tls_block_singbox(p: dict) -> dict:
    tls = {
        "enabled": p["security"] == "tls",
        "server_name": p["sni"] or p["host"],
        "utls": {"enabled": True, "fingerprint": p["fp"] or "chrome"},
    }
    if p["alpn"]:
        tls["alpn"] = p["alpn"]
    if p["insecure"]:
        tls["insecure"] = True
    return tls


def _transport_singbox(p: dict) -> Optional[dict]:
    if p["net"] == "ws":
        t = {"type": "ws", "path": p["path"]}
        if p["ws_host"]:
            t["headers"] = {"Host": p["ws_host"]}
        return t
    if p["net"] == "httpupgrade":
        t = {"type": "httpupgrade", "path": p["path"], "host": p["ws_host"]}
        return t
    return None  # xhttp در sing-box پشتیبانی نمی‌شود → صادقانه رد می‌شود


def _proxy_outbound_singbox(p: dict) -> dict:
    if p["scheme"] == "vless":
        ob: dict = {
            "type": "vless", "tag": "proxy",
            "server": p["host"], "server_port": p["port"],
            "uuid": p["uuid"], "flow": "",
            "tls": _tls_block_singbox(p), "packet_encoding": "xudp",
        }
    elif p["scheme"] == "trojan":
        ob = {
            "type": "trojan", "tag": "proxy",
            "server": p["host"], "server_port": p["port"],
            "password": p["uuid"] or p["password"],
            "tls": _tls_block_singbox(p),
        }
    else:
        raise IrRulesError(
            "SPLIT_TUNNEL_NOT_SUPPORTED",
            f"protocol {p['scheme']!r} over client-rules format is not supported — "
            "از vless-ws یا trojan-ws استفاده کنید")
    t = _transport_singbox(p)
    if t is None:
        raise IrRulesError(
            "SPLIT_TUNNEL_NOT_SUPPORTED",
            f"transport {p['net']!r} در sing-box پشتیبانی نمی‌شود — "
            "برای xhttp از ?client=xray استفاده کنید")
    ob["transport"] = t
    return ob


def _stream_settings_xray(p: dict) -> dict:
    ss: dict = {"network": p["net"], "security": p["security"]}
    if p["security"] == "tls":
        tls = {
            "serverName": p["sni"] or p["host"],
            "allowInsecure": bool(p["insecure"]),
            "fingerprint": p["fp"] or "chrome",
        }
        if p["alpn"]:
            tls["alpn"] = p["alpn"]
        ss["tlsSettings"] = tls
    if p["net"] == "ws":
        ws: dict = {"path": p["path"]}
        if p["ws_host"]:
            ws["headers"] = {"Host": p["ws_host"]}
        ss["wsSettings"] = ws
    elif p["net"] == "xhttp":
        x: dict = {"path": p["path"]}
        if p["mode"]:
            x["mode"] = p["mode"]
        if p["ws_host"]:
            x["host"] = [p["ws_host"]]
        ss["xhttpSettings"] = x
    return ss


def _proxy_outbound_xray(p: dict) -> dict:
    if p["scheme"] == "vless":
        ob = {
            "tag": "proxy", "protocol": "vless",
            "settings": {"vnext": [{
                "address": p["host"], "port": p["port"],
                "users": [{"id": p["uuid"], "encryption": "none",
                           "flow": "", "level": 0}],
            }]},
            "streamSettings": _stream_settings_xray(p),
        }
    elif p["scheme"] == "trojan":
        ob = {
            "tag": "proxy", "protocol": "trojan",
            "settings": {"servers": [{
                "address": p["host"], "port": p["port"],
                "password": p["uuid"] or p["password"], "level": 0,
            }]},
            "streamSettings": _stream_settings_xray(p),
        }
    else:
        raise IrRulesError(
            "SPLIT_TUNNEL_NOT_SUPPORTED",
            f"protocol {p['scheme']!r} over client-rules format is not supported — "
            "از vless-ws / trojan-ws / vless-xhttp استفاده کنید")
    return ob


# ── سازنده‌های کانفیگ کامل ───────────────────────────────────────────────────

def _normalize_prefixes(prefixes: List[str]) -> List[str]:
    out, seen = [], set()
    for p in prefixes:
        try:
            norm = str(ipaddress.ip_network(str(p).strip(), strict=False))
        except ValueError:
            continue
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


async def build_client_rules_config_async(uid: str, client: str, *,
                                          geosite: bool = False,
                                          label: str = "EMIX") -> tuple[dict, dict]:
    """(config_dict, meta) — meta برای هدرها و لاگ."""
    client = (client or "singbox").strip().lower()
    if client not in SUPPORTED_CLIENTS:
        raise IrRulesError("SPLIT_TUNNEL_NOT_SUPPORTED",
                           f"client {client!r} نامعتبر است — singbox | xray")

    link = await _deps["get_link"](uid)
    if not link or not _deps["is_allowed"](link):
        raise KeyError(uid)

    host = _deps["host"]()
    protocol = link.get("protocol", _deps["default_protocol"])
    uri = _deps["share_link"](uid, host, remark=f"EMIX-{label}", protocol=protocol)
    p = _parse_share_uri(uri)

    prefixes = _normalize_prefixes(_deps["prefixes"]())
    meta = {"client": client, "protocol": protocol, "host": host,
            "prefix_count": len(prefixes), "geosite": bool(geosite),
            "sni": p["sni"] or p["host"], "insecure": p["insecure"]}

    domain_rule: dict = {"outbound": "direct", "domain_suffix": list(IR_DOMAIN_SUFFIXES)}
    ip_rule: dict = {"outbound": "direct", "ip_cidr": prefixes}

    if client == "singbox":
        proxy_ob = _proxy_outbound_singbox(p)
        rules: List[dict] = [domain_rule]
        route_sets: List[dict] = []
        if geosite:
            route_sets.append({"type": "remote", "tag": "geosite-ir",
                               "format": "binary", "url": _SINGBOX_GEOSITE_IR,
                               "download_detour": "proxy"})
            rules.append({"rule_set": ["geosite-ir"], "outbound": "direct"})
        if prefixes:
            rules.append(ip_rule)
        config = {
            "log": {"level": "warn"},
            "dns": {
                "servers": [
                    {"tag": "ir-dns", "address": "178.22.122.100", "detour": "direct"},
                    {"tag": "global-dns", "address": "1.1.1.1", "detour": "proxy"},
                ],
                "rules": [
                    {"domain_suffix": list(IR_DOMAIN_SUFFIXES), "server": "ir-dns"},
                    {"rule_set": ["geosite-ir"], "server": "ir-dns"} if geosite else None,
                ],
                "final": "global-dns",
                "strategy": "prefer_ipv4",
            },
            "inbounds": [{
                "type": "mixed", "tag": "mixed-in",
                "listen": "127.0.0.1", "listen_port": 2080,
            }],
            "outbounds": [
                proxy_ob,
                {"type": "direct", "tag": "direct"},
                {"type": "block", "tag": "block"},
                {"type": "dns", "tag": "dns-out"},
            ],
            "route": {
                "rules": [r for r in rules if r],
                "rule_set": route_sets,
                "final": "proxy",
                "auto_detect_interface": True,
            },
        }
        # dns rule_set به dns.servers نیاز ندارد ولی به route.rule_set وابسته است؛
        # اگر geosite خاموش است، rule dns را هم حذف کردیم (None filter بالا).
        return config, meta

    # ── xray ────────────────────────────────────────────────────────────────
    proxy_ob = _proxy_outbound_xray(p)
    xrules: List[dict] = [
        {"type": "field", "domain": list(IR_DOMAIN_SUFFIXES), "outboundTag": "direct"},
    ]
    if geosite:
        xrules.insert(1, {"type": "field", "domain": [_XRAY_GEOSITE_IR],
                          "outboundTag": "direct"})
    if prefixes:
        xrules.append({"type": "field", "ip": prefixes, "outboundTag": "direct"})
    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {"tag": "socks-in", "listen": "127.0.0.1", "port": 10808,
             "protocol": "socks", "settings": {"udp": True, "auth": "noauth"}},
            {"tag": "http-in", "listen": "127.0.0.1", "port": 10809,
             "protocol": "http", "settings": {"auth": "noauth"}},
        ],
        "outbounds": [
            proxy_ob,
            {"tag": "direct", "protocol": "freedom", "settings": {}},
            {"tag": "block", "protocol": "blackhole", "settings": {}},
        ],
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules": xrules,
        },
    }
    return config, meta


# ── ثبت اندپوینت‌ها (DI — بدون وابستگی به import main) ──────────────────────

def register_routes(app, *, get_link_fn, is_allowed_fn, share_link_fn, host_fn,
                    headers_fn, prefixes_fn, default_protocol) -> None:
    """`GET /sub-json/{uuid}?client=singbox|xray&geosite=0|1` — عمومی مثل /sub
    (کلید راز همان UUID لینک است). خروجی: کانفیگ کامل با قواعد IR-Direct."""
    set_deps(get_link_fn, is_allowed_fn, share_link_fn, host_fn,
             headers_fn, prefixes_fn, default_protocol)

    @app.get("/sub-json/{uuid}")
    async def sub_json(uuid: str, request: Request,
                       client: str = "singbox", geosite: int = 0):
        link = await get_link_fn(uuid)
        if not link or not is_allowed_fn(link):
            raise HTTPException(status_code=404, detail="not found or inactive")
        try:
            config, meta = await build_client_rules_config_async(
                uuid, client, geosite=bool(geosite),
                label=str(link.get("label") or "EMIX"))
        except IrRulesError as exc:
            return JSONResponse(status_code=422, content={
                "ok": False, "error": exc.code, "detail": exc.detail,
                "supported_clients": list(SUPPORTED_CLIENTS),
            })
        headers = headers_fn(link.get("label", "EMIX"),
                             link.get("used_bytes", 0),
                             link.get("limit_bytes", 0),
                             link.get("expires_at"))
        headers.update({
            "content-disposition":
                f'attachment; filename="emix-ir-direct-{client}.json"',
            "x-emix-ir-rules": f"prefixes={meta['prefix_count']};v={IR_CLIENT_RULES_VERSION}",
            "profile-web-page-url": str(request.url),
        })
        return JSONResponse(content=config, headers=headers)
