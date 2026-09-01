# exp_api.py — API endpoints برای فیچرهای آزمایشی
# همه‌ی endpoints فقط وقتی EMIX_EXPERIMENTAL=1 فعال می‌شوند.
# در غیر این صورت، 404 برمی‌گردانند تا پایداری اصلی حفظ شود.

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from typing import Optional
import os
import json
import time

from experimental import is_enabled, is_experimental_enabled, get_feature_status, toggle_feature
import link_emit

router = APIRouter()


def _require_experimental():
    """اگر بخش آزمایشی فعال نیست، 404 برگردان."""
    if not is_experimental_enabled():
        raise HTTPException(status_code=404, detail="experimental section disabled (set EMIX_EXPERIMENTAL=1)")


@router.get("/api/exp/status")
async def exp_status():
    """لیست همه‌ی فیچرهای آزمایشی با وضعیتشان."""
    return get_feature_status()


@router.post("/api/exp/toggle")
async def exp_toggle(request: Request):
    """تغییر وضعیت یک فیچر (runtime فقط — برای تست)."""
    _require_experimental()
    body = await request.json()
    feature = body.get("feature")
    enabled = bool(body.get("enabled", False))
    if not feature:
        raise HTTPException(400, "feature required")
    ok = toggle_feature(feature, enabled)
    if not ok:
        raise HTTPException(404, f"unknown feature: {feature}")
    return {"ok": True, "feature": feature, "enabled": enabled, "note": "runtime only — restart will reset; set EMIX_ENABLE_<FEATURE> env var for persistence"}


# ─── Link Emission Endpoints ─────────────────────────────────────────────

@router.post("/api/exp/link/vmess")
async def exp_emit_vmess(request: Request):
    """صدور لینک VMESS base64-JSON."""
    _require_experimental()
    if not is_enabled("vmess_link_emit"):
        raise HTTPException(403, "vmess_link_emit disabled")
    b = await request.json()
    link = link_emit.gen_vmess_link(
        address=b.get("address", ""),
        port=int(b.get("port", 443)),
        uuid=b.get("uuid", ""),
        name=b.get("name", ""),
        aid=int(b.get("aid", 0)),
        net=b.get("net", "ws"),
        host=b.get("host", ""),
        path=b.get("path", "/"),
        tls=b.get("tls", ""),
        sni=b.get("sni", ""),
        alpn=b.get("alpn", ""),
        fp=b.get("fp", "chrome"),
    )
    return {"ok": True, "link": link, "protocol": "vmess"}


@router.post("/api/exp/link/vless-reality")
async def exp_emit_vless_reality(request: Request):
    """صدور لینک VLESS-Reality."""
    _require_experimental()
    if not is_enabled("reality_link_emit"):
        raise HTTPException(403, "reality_link_emit disabled")
    b = await request.json()
    link = link_emit.gen_vless_reality_link(
        address=b.get("address", ""),
        port=int(b.get("port", 443)),
        uuid=b.get("uuid", ""),
        pbk=b.get("pbk", ""),
        sid=b.get("sid", ""),
        sni=b.get("sni", "www.cloudflare.com"),
        fp=b.get("fp", "chrome"),
        spx=b.get("spx", "/"),
        flow=b.get("flow", "xtls-rprx-vision"),
        name=b.get("name", ""),
    )
    return {"ok": True, "link": link, "protocol": "vless-reality"}


@router.post("/api/exp/link/trojan-reality")
async def exp_emit_trojan_reality(request: Request):
    """صدور لینک Trojan-Reality."""
    _require_experimental()
    if not is_enabled("reality_link_emit"):
        raise HTTPException(403, "reality_link_emit disabled")
    b = await request.json()
    link = link_emit.gen_trojan_reality_link(
        address=b.get("address", ""),
        port=int(b.get("port", 443)),
        password=b.get("password", ""),
        pbk=b.get("pbk", ""),
        sid=b.get("sid", ""),
        sni=b.get("sni", "www.cloudflare.com"),
        fp=b.get("fp", "chrome"),
        spx=b.get("spx", "/"),
        name=b.get("name", ""),
    )
    return {"ok": True, "link": link, "protocol": "trojan-reality"}


@router.post("/api/exp/link/ss2022")
async def exp_emit_ss2022(request: Request):
    """صدور لینک Shadowsocks-2022."""
    _require_experimental()
    if not is_enabled("ss2022_link_emit"):
        raise HTTPException(403, "ss2022_link_emit disabled")
    b = await request.json()
    link = link_emit.gen_ss2022_link(
        method=b.get("method", "2022-blake3-aes-256-gcm"),
        password=b.get("password", ""),
        address=b.get("address", ""),
        port=int(b.get("port", 443)),
        name=b.get("name", ""),
    )
    return {"ok": True, "link": link, "protocol": "ss-2022"}


@router.post("/api/exp/link/spiderx")
async def exp_emit_spiderx(request: Request):
    """تولید spiderX path منحصر بفرد به ازای کلاینت."""
    _require_experimental()
    if not is_enabled("reality_spiderx"):
        raise HTTPException(403, "reality_spiderx disabled")
    b = await request.json()
    path = link_emit.gen_spiderx_path(b.get("uuid", ""), b.get("sub_id", ""))
    return {"ok": True, "path": path}


@router.post("/api/exp/link/finalmask")
async def exp_emit_finalmask(request: Request):
    """اضافه‌کردن param های FinalMask به یک base link."""
    _require_experimental()
    if not is_enabled("finalmask_link"):
        raise HTTPException(403, "finalmask_link disabled")
    b = await request.json()
    link = link_emit.gen_finalmask_link(b.get("base_link", ""), b.get("fm_config"))
    return {"ok": True, "link": link}


@router.post("/api/exp/link/uTLS")
async def exp_emit_utls(request: Request):
    """اضافه‌کردن uTLS fingerprint به یک link."""
    _require_experimental()
    if not is_enabled("utls_fingerprint"):
        raise HTTPException(403, "utls_fingerprint disabled")
    b = await request.json()
    link = link_emit.add_utls_fingerprint(b.get("link", ""), b.get("fp", "chrome"))
    return {"ok": True, "link": link}


# Audit fix: مسیرهای FastAPI case-sensitive هستند؛ فرانت‌اند (expEmitLink)
# «utls» می‌فرستاد و روت اصلی «uTLS» بود → همیشه 404. alias کوچک اضافه شد.
@router.post("/api/exp/link/utls", include_in_schema=False)
async def exp_emit_utls_alias(request: Request):
    return await exp_emit_utls(request)


# ─── Subscription Format Endpoints ──────────────────────────────────────

@router.post("/api/exp/subscription")
async def exp_subscription_multi_format(request: Request):
    """تولید subscription در چند فرمت: raw, json, clash, encrypted."""
    _require_experimental()
    b = await request.json()
    links = b.get("links", [])
    remarks = b.get("remarks", [])
    fmt = b.get("format", "raw")
    if fmt == "raw":
        return {"ok": True, "format": "raw", "content": link_emit.gen_subscription_raw(links)}
    elif fmt == "json":
        if not is_enabled("sub_json"):
            raise HTTPException(403, "sub_json disabled")
        return {"ok": True, "format": "json", "content": link_emit.gen_subscription_json(links, remarks)}
    elif fmt == "clash":
        if not is_enabled("sub_clash"):
            raise HTTPException(403, "sub_clash disabled")
        return {"ok": True, "format": "clash", "content": link_emit.gen_subscription_clash(links, remarks)}
    elif fmt == "encrypted":
        if not is_enabled("sub_encrypted"):
            raise HTTPException(403, "sub_encrypted disabled")
        key = b.get("key", os.environ.get("EMIX_SUB_KEY", "default"))
        return {"ok": True, "format": "encrypted", "content": link_emit.gen_subscription_encrypted(links, key)}
    else:
        raise HTTPException(400, f"unknown format: {fmt}")


# ─── Stealth / Disguise Section ──────────────────────────────────────────

@router.get("/api/exp/stealth/registry")
async def exp_stealth_registry():
    """رجیستری متدهای استتار/جعل قابل دسترس."""
    _require_experimental()
    return {
        "stealth_methods": [
            {
                "key": "tls_fragmentation",
                "name": "TLS Hello Fragmentation",
                "description": "شکستن TLS ClientHello به چند fragment برای عبور از DPI",
                "enabled": is_enabled("tls_fragmentation"),
                "platform": "client-side (xray-core 26+)",
                "config_key": "fm_tls_fragment",
            },
            {
                "key": "salamander_obfs",
                "name": "Salamander Obfuscation",
                "description": "obfuscation بر اساس salsa20 برای مقابله با تشخیص پروتکل",
                "enabled": is_enabled("salamander_obfs"),
                "platform": "client-side",
                "config_key": "fm_salamander",
            },
            {
                "key": "noise_padding",
                "name": "Noise Padding",
                "description": "اضافه‌کردن padding تصادفی به payload",
                "enabled": is_enabled("noise_padding"),
                "platform": "client-side",
                "config_key": "fm_noise",
            },
            {
                "key": "domain_fronting",
                "name": "Domain Fronting (CDN)",
                "description": "استفاده از SNI متفاوت با Host header برای عبور از DPI",
                "enabled": is_enabled("domain_fronting"),
                "platform": "panel + worker",
                "config_key": "fm_domain_fronting",
            },
            {
                "key": "reality_spiderx",
                "name": "Per-client Reality spiderX",
                "description": "مسیر منحصر بفرد spiderX به ازای کلاینت — جلوگیری از correlation",
                "enabled": is_enabled("reality_spiderx"),
                "platform": "panel",
                "config_key": "reality_spiderx",
            },
            {
                "key": "utls_fingerprint",
                "name": "uTLS Fingerprint Emission",
                "description": "امضای TLS (chrome/firefox/safari) روی همه‌ی لینک‌ها",
                "enabled": is_enabled("utls_fingerprint"),
                "platform": "panel",
                "config_key": "utls_fingerprint",
            },
            {
                "key": "pinned_cert",
                "name": "Pinned Certificate SHA-256",
                "description": "تأیید cert با hash SHA-256 — جلوگیری از SNI spoofing",
                "enabled": is_enabled("pinned_cert"),
                "platform": "panel",
                "config_key": "pinned_cert",
            },
        ]
    }


# ─── Unified Configs View (Phase 8) ──────────────────────────────────────

@router.get("/api/exp/unified-configs")
async def exp_unified_configs():
    """نمایش همه‌ی کانفیگ‌ها (از همه‌ی بخش‌ها) در یک view مرکزی."""
    _require_experimental()
    if not is_enabled("unified_configs"):
        raise HTTPException(403, "unified_configs disabled")

    # استخراج کانفیگ‌ها از state پنل
    from main import LINKS, LINKS_LOCK, SUBS, NODES, AUTH
    configs = []

    # links (main configs)
    async with LINKS_LOCK:
        for uuid, link in LINKS.items():
            proto = link.get("protocol") or link.get("type") or "unknown"
            # Generate the actual share-link on-the-fly (includes SNI spoofing + allowInsecure)
            from main import generate_share_link, get_host
            host = get_host()
            share_url = ""
            try:
                share_url = generate_share_link(uuid, host, remark=f"EMIX-{link.get('label', link.get('name', ''))}", protocol=proto)
            except Exception:
                pass
            configs.append({
                "uuid": uuid,
                "name": link.get("name", "") or link.get("label", ""),
                "type": proto,
                "section": "links",
                "type_label": _type_label(proto),
                "enabled": link.get("enabled", link.get("active", True)),
                "expiry": link.get("expiry") or link.get("expires_at"),
                "usage_bytes": link.get("usage_bytes", link.get("used_bytes", 0)),
                "limit_bytes": link.get("limit_bytes"),
                "url": share_url,
                "sub_url": f"/sub/{uuid}",
                "health": link.get("health") or link.get("last_ping", {}),
            })

    # subs (subscription groups)
    for sub_id, sub in SUBS.items():
        configs.append({
            "uuid": sub_id,
            "name": sub.get("name", ""),
            "type": "subscription-group",
            "section": "subscriptions",
            "type_label": "Subscription Group",
            "enabled": True,
            "url": f"/sub/{sub_id}",
        })

    # nodes
    for nid, node in NODES.items():
        configs.append({
            "uuid": nid,
            "name": node.get("name", ""),
            "type": "node",
            "section": "nodes",
            "type_label": f"Node ({node.get('type', 'unknown')})",
            "enabled": node.get("enabled", True),
            "address": node.get("address", ""),
        })

    # wg/ovpn (if exists)
    # these are stored separately — read from where they live
    from main import CONFIG
    if CONFIG.get("wg_endpoint"):
        configs.append({
            "uuid": "wg-main",
            "name": "WireGuard Main",
            "type": "wireguard",
            "section": "vpn-pro",
            "type_label": "WireGuard",
            "enabled": True,
            "endpoint": CONFIG.get("wg_endpoint"),
        })
    if CONFIG.get("ovpn_endpoint"):
        configs.append({
            "uuid": "ovpn-main",
            "name": "OpenVPN Main",
            "type": "openvpn",
            "section": "vpn-pro",
            "type_label": "OpenVPN",
            "enabled": True,
            "endpoint": CONFIG.get("ovpn_endpoint"),
        })

    # experimental emissions (reality, vmess, ss-2022, etc.)
    if is_enabled("reality_link_emit"):
        configs.append({
            "uuid": "exp-reality",
            "name": "Reality Link Emitter",
            "type": "reality-emitter",
            "section": "experimental",
            "type_label": "Reality Link (VLESS+Trojan)",
            "enabled": is_enabled("reality_link_emit"),
        })
    if is_enabled("vmess_link_emit"):
        configs.append({
            "uuid": "exp-vmess",
            "name": "VMESS Emitter",
            "type": "vmess-emitter",
            "section": "experimental",
            "type_label": "VMESS base64-JSON",
            "enabled": is_enabled("vmess_link_emit"),
        })
    if is_enabled("ss2022_link_emit"):
        configs.append({
            "uuid": "exp-ss2022",
            "name": "SS-2022 Emitter",
            "type": "ss2022-emitter",
            "section": "experimental",
            "type_label": "Shadowsocks 2022",
            "enabled": is_enabled("ss2022_link_emit"),
        })

    return {
        "ok": True,
        "total": len(configs),
        "configs": configs,
        "sections": ["links", "subscriptions", "nodes", "vpn-pro", "experimental"],
    }


def _type_label(t: str) -> str:
    """تبدیل type فنی به label قابل فهم."""
    mapping = {
        "vless-ws": "VLESS WebSocket",
        "vless-xhttp": "VLESS XHTTP",
        "vless-xhttp-stream-up": "VLESS XHTTP Stream-Up",
        "vless-xhttp-packet-up": "VLESS XHTTP Packet-Up",
        "vless-reality": "VLESS Reality",
        "trojan-ws": "Trojan WebSocket",
        "trojan-xhttp": "Trojan XHTTP",
        "trojan-reality": "Trojan Reality",
        "shadowsocks": "Shadowsocks",
        "shadowsocks-2022": "Shadowsocks 2022",
        "mtproto": "MTProto",
        "vmess": "VMESS",
        "http-proxy": "HTTP Proxy",
        "wireguard": "WireGuard",
        "openvpn": "OpenVPN",
        "reality-emitter": "Reality Link Emitter",
        "vmess-emitter": "VMESS Emitter",
        "ss2022-emitter": "SS-2022 Emitter",
    }
    return mapping.get(t, t.title() if t else "Unknown")


# ─── Anti-DPI Config Recheck (Phase 9) ───────────────────────────────────

@router.post("/api/exp/recheck-anti-dpi")
async def exp_recheck_anti_dpi():
    """بررسی مجدد سلامت و پینگ همه‌ی کانفیگ‌های ضد-DPI."""
    _require_experimental()
    from main import LINKS, LINKS_LOCK
    results = []
    async with LINKS_LOCK:
        for uuid, link in LINKS.items():
            ltype = link.get("protocol") or link.get("type") or ""
            is_anti_dpi = (
                "xhttp" in ltype or
                "reality" in ltype or
                ltype == "trojan-ws" or
                ltype == "vless-ws"
            )
            if not is_anti_dpi:
                continue
            lp = link.get("last_ping", {}) or {}
            results.append({
                "uuid": uuid,
                "name": link.get("label", "") or link.get("name", ""),
                "type": ltype,
                "type_label": _type_label(ltype),
                "enabled": link.get("active", link.get("enabled", True)),
                "anti_dpi": True,
                "needs_recheck": True,
                "current_ping": lp.get("ok"),
                "current_ws_ms": lp.get("ws_ms"),
                "current_reply": lp.get("reply", ""),
            })
    return {"ok": True, "anti_dpi_configs": results, "total": len(results)}
