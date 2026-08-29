# isp_detect.py — تشخیص ISP ایران و پیشنهاد مسیر/پروتکل
# هرگز fabrication نمی‌کند. اگر IP قابل تشخیص نیست، "unknown" برمی‌گرداند.

import os
import ipaddress
import httpx
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from experimental import is_enabled

router = APIRouter()

# ─── IP ranges شناخته‌شده‌ی ISP‌های ایران ───────────────────────────────────
# منبع: RIPE/NCC + ARIN + crl.apnic.net (داده‌های عمومی)
# توجه: این لیست ممکن است ناقص باشد؛ فقط برای تشخیص تقریبی استفاده می‌شود.
# برای دقت بالا، باید از API ipapi.co یا ipinfo.io استفاده شود.

_ISP_RANGES = {
    "mci": {
        "name": "MCI (Mobile Communication Company of Iran)",
        "ranges": [
            "5.112.0.0/13", "5.120.0.0/14", "5.124.0.0/14",
            "37.32.0.0/16", "37.130.0.0/16", "37.156.0.0/16",
            "46.209.0.0/16", "46.235.0.0/16",
            "91.98.0.0/15", "92.50.0.0/16", "92.51.0.0/16",
            "94.182.0.0/15", "95.80.0.0/16",
            "188.159.0.0/16",
            "217.218.0.0/15",
        ],
        "suggestion": "Trojan-WS با padding بالا + Reality با SNI تحریم‌نشده",
    },
    "mtnirancell": {
        "name": "MTN Irancell",
        "ranges": [
            "5.74.0.0/16", "5.114.0.0/16", "5.117.0.0/16", "5.118.0.0/16", "5.119.0.0/16",
            "37.63.0.0/16", "37.99.0.0/16",
            "46.21.0.0/16", "46.34.0.0/16", "46.35.0.0/16",
            "85.9.64.0/18", "85.133.128.0/17", "85.185.0.0/16",
            "91.99.0.0/16",
            "178.131.0.0/16",
        ],
        "suggestion": "VLESS-Reality با SNI ایرانی + uTLS chrome fingerprint",
    },
    "rightel": {
        "name": "RighTel",
        "ranges": [
            "5.108.0.0/16",
            "37.156.0.0/16",
            "91.103.0.0/16",
            "217.170.0.0/16",
        ],
        "suggestion": "Shadowsocks-2022 با 2022-blake3-aes-256-gcm + Reality",
    },
    "shatel": {
        "name": "Shatel",
        "ranges": [
            "5.134.0.0/16",
            "31.7.0.0/16",
            "37.137.0.0/16",
            "85.15.0.0/16",
            "91.92.0.0/14",
            "178.22.0.0/16",
        ],
        "suggestion": "VLESS-XHTTP-StreamUp با Reality + uTLS firefox",
    },
}


def _require_isp():
    if not is_enabled("isp_detection"):
        raise HTTPException(404, "isp_detection disabled")


def _check_ip_in_ranges(ip: str, ranges: list) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip)
        for cidr in ranges:
            try:
                net = ipaddress.ip_network(cidr, strict=False)
                if ip_obj in net:
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def detect_isp_from_ip(ip: str) -> dict:
    """تشخیص ISP از IP."""
    if not ip:
        return {"isp": "unknown", "reason": "no IP provided"}
    for key, info in _ISP_RANGES.items():
        if _check_ip_in_ranges(ip, info["ranges"]):
            return {
                "isp": key,
                "name": info["name"],
                "suggestion": info["suggestion"],
                "source": "internal-ranges",
            }
    return {"isp": "unknown", "reason": "no internal match"}


async def detect_isp_from_api(ip: str) -> dict:
    """تشخیص ISP از طریق API ipapi.co (برای دقت بیشتر)."""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"https://ipapi.co/{ip}/json/")
            if r.status_code != 200:
                return {"isp": "unknown", "reason": f"API {r.status_code}"}
            data = r.json()
            org = (data.get("org") or "").lower()
            asn = data.get("asn", "")
            country = data.get("country", "")
            # تشخیص ISP ایرانی
            isp = "unknown"
            if "mci" in org or "mobile communication company of iran" in org:
                isp = "mci"
            elif "irancell" in org or "mtn" in org:
                isp = "mtnirancell"
            elif "rightel" in org:
                isp = "rightel"
            elif "shatel" in org:
                isp = "shatel"
            elif country == "IR":
                isp = "iran-other"
            return {
                "isp": isp,
                "org": data.get("org"),
                "country": country,
                "city": data.get("city"),
                "asn": asn,
                "source": "ipapi.co",
            }
    except Exception as e:
        return {"isp": "unknown", "reason": str(e)}


@router.get("/api/exp/isp/detect")
async def detect_isp_endpoint(request: Request):
    """تشخیص ISP از IP درخواست‌کننده."""
    _require_isp()
    # تشخیص IP
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "")
    if not ip or ip == "127.0.0.1":
        return {"ok": True, "ip": ip, "isp": "local", "message": "local request"}

    # مرحله ۱: internal ranges (سریع)
    result = detect_isp_from_ip(ip)
    # مرحله ۲: اگر internal تشخیص نداد، API را امتحان کن
    if result.get("isp") == "unknown" and is_enabled("per_isp_route"):
        api_result = await detect_isp_from_api(ip)
        if api_result.get("isp") != "unknown":
            result = api_result

    # پیشنهاد پروتکل
    isp_key = result.get("isp", "unknown")
    if isp_key in _ISP_RANGES:
        result["protocol_suggestion"] = _ISP_RANGES[isp_key]["suggestion"]
        result["preferred_protocols"] = _ISP_RANGES[isp_key].get("preferred_protocols", [])

    return {"ok": True, "ip": ip, **result}


@router.post("/api/exp/isp/detect-by-ip")
async def detect_isp_by_ip(request: Request):
    """تشخیص ISP از یک IP خاص (برای admin)."""
    _require_isp()
    body = await request.json()
    ip = body.get("ip", "")
    if not ip:
        raise HTTPException(400, "ip required")
    # internal first
    result = detect_isp_from_ip(ip)
    if result.get("isp") == "unknown":
        result = await detect_isp_from_api(ip)
    isp_key = result.get("isp", "unknown")
    if isp_key in _ISP_RANGES:
        result["protocol_suggestion"] = _ISP_RANGES[isp_key]["suggestion"]
    return {"ok": True, "ip": ip, **result}


@router.get("/api/exp/isp/registry")
async def isp_registry():
    """لیست ISP های شناخته‌شده و پیشنهاد پروتکل."""
    _require_isp()
    return {
        "isps": [
            {
                "key": k,
                "name": v["name"],
                "suggestion": v["suggestion"],
                "ranges_count": len(v["ranges"]),
            }
            for k, v in _ISP_RANGES.items()
        ]
    }
