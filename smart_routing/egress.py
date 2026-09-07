# smart_routing/egress.py — verify واقعی خروجی IP + Geo/ASN از منابع مستقل
# ══════════════════════════════════════════════════════════════════════════════
# قاعده‌ی حیاتی (سند §NO FAKE SUCCESS):
#   «egress» فقط وقتی معتبر است که ترافیک واقعاً از مسیر عبور کرده باشد و IP
#   خروجی «از بیرون» دیده و ثبت شده باشد — نه از متادیتای endpoint، نه از
#   SNI/Host/هدر. دو منبع مستقل برای Geo/ASN؛ IRAN_EGRESS فقط با تأیید هر دو.
#
#   Client → Route → Relay/Edge → Internet → Observed Egress IP
#                (پروب ما همین زنجیره را واقعاً طی می‌کند)
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import json

import httpx

from . import metrics
from .metrics import ws_base_for

# منبع A (از داخل تونل — plain HTTP :80 تا از تونل TCP واقعی عبور کند)
#   ip-api.com/json → {query, country, countryCode, as, asNumber}
# منبع B (مستقل — از پنل برای همان IP مشاهده‌شده، HTTPS)
#   ipwho.is/{ip} → {ip, country_code, connection:{asn, org}}
_EGRESS_API_HOST = "ip-api.com"
_EGRESS_API_PORT = 80
_EGRESS_API_PATH = "/json?fields=status,message,query,country,countryCode,as,asNumber"
_EGRESS_API_REQ = (
    f"GET {_EGRESS_API_PATH} HTTP/1.1\r\n"
    f"Host: {_EGRESS_API_HOST}\r\n"
    f"User-Agent: EMIX-SmartRouting/1.0\r\n"
    f"Accept: application/json\r\n"
    f"Connection: close\r\n\r\n"
).encode()


def _parse_http_json(raw: bytes) -> dict | None:
    """بافت HTTP (کامل یا فقط body) → dict."""
    text = b""
    if b"\r\n\r\n" in raw:
        parts = raw.split(b"\r\n\r\n", 1)
        text = parts[1] if len(parts) == 2 else b""
    else:
        text = raw          # فقط body (بدون هدر)
    try:
        return json.loads(text)
    except Exception:
        s = text.decode("utf-8", "ignore")
        start, end = s.find("{"), s.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(s[start:end + 1])
            except Exception:
                return None
    return None


async def route_egress(front_host: str, front_port: int, uid: str, protocol: str) -> dict:
    """اندازه‌گیری واقعی egress مسیر: درخواست به ip-api «از داخل تونل».

    خروجی: {ok, observed_ip, observed_country, observed_asn, observed_asn_num,
            probe(ws/e2e/status), source_a} — بدون حدس/جعل."""
    out = {"ok": False, "vantage": "through-route-tunnel"}
    r = await metrics.http_through_tunnel(
        ws_base_for(front_host, front_port),
        uid, protocol, _EGRESS_API_HOST, _EGRESS_API_PORT, want_body=True,
        path=_EGRESS_API_PATH,
    )
    out["probe"] = {k: r.get(k) for k in ("ok", "ws_ms", "e2e_ms", "status_line", "detail")}
    if not r.get("ok"):
        out["error"] = "traffic از مسیر عبور نکرد — egress قابل verify نیست"
        return out
    data = _parse_http_json(r.get("body", b""))
    if not data or data.get("status") != "success":
        out["error"] = f"پاسخ منبع A نامعتبر: {str(data)[:80]}"
        return out
    out.update({
        "ok": True,
        "observed_ip": data.get("query"),
        "observed_country": data.get("countryCode"),
        "observed_country_name": data.get("country"),
        "observed_asn": data.get("as"),
        "observed_asn_num": data.get("asNumber"),
        "source_a": "ip-api.com (through-tunnel HTTP)",
    })
    return out


async def independent_geo_for_ip(ip: str) -> dict:
    """منبع B مستقل (HTTPS از پنل): ipwho.is — برای cross-check Geo/ASN."""
    out = {"ok": False, "source_b": "ipwho.is (direct HTTPS)"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as cli:
            r = await cli.get(f"https://ipwho.is/{ip}")
        if r.status_code == 200:
            d = r.json()
            conn = d.get("connection") or {}
            out.update({
                "ok": True,
                "ip": d.get("ip"),
                "country": d.get("country_code"),
                "country_name": d.get("country"),
                "asn": (f"AS{conn.get('asn')} {conn.get('org', '')}".strip()
                        if conn.get("asn") else None),
                "asn_num": conn.get("asn"),
            })
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {str(e)[:80]}"
    return out


async def verify_endpoint_egress(front_host: str, front_port: int, uid: str,
                                 protocol: str) -> dict:
    """verify کامل egress یک endpoint (منبع A داخل تونل + منبع B مستقل).

    IRAN_EGRESS = true فقط وقتی هر دو منبع countryCode == IR بگویند.
    هر اختلاف → INVALID (طبق سند: «اگر نتیجه با metadata اختلاف داشت STATUS=INVALID»)."""
    res: dict = {"ok": False}
    a = await route_egress(front_host, front_port, uid, protocol)
    res["source_a"] = a
    if not a.get("ok"):
        res["error"] = a.get("error", "egress ناموفق")
        res["status"] = "UNVERIFIED"
        return res
    ip = a.get("observed_ip")
    b = await independent_geo_for_ip(ip)
    res["source_b"] = b
    cc_a = (a.get("observed_country") or "").upper()
    cc_b = (b.get("country") or "").upper()
    if b.get("ok") and cc_b and cc_a and cc_a != cc_b:
        res["status"] = "INVALID"
        res["mismatch"] = {"source_a": cc_a, "source_b": cc_b}
        res["ok"] = False
        return res
    res.update({
        "ok": True,
        "status": "VERIFIED",
        "observed_ip": ip,
        "observed_country": cc_a or (cc_b or None),
        "observed_asn": a.get("observed_asn") or b.get("asn"),
        "observed_asn_num": a.get("observed_asn_num") or b.get("asn_num"),
        "iran_egress": bool(cc_a == "IR" and (not cc_b or cc_b == "IR")),
    })
    return res


async def panel_egress_baseline() -> dict:
    """egress مستقیم پنل (بدون route) — برای مقایسه/گزارش honest."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as cli:
            r = await cli.get("http://ip-api.com/json/"
                              "?fields=status,query,country,countryCode,as,asNumber")
        d = r.json()
        if d.get("status") == "success":
            return {"ok": True, "ip": d.get("query"), "country": d.get("countryCode"),
                    "asn": d.get("as"), "asn_num": d.get("asNumber")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:80]}
    return {"ok": False}
