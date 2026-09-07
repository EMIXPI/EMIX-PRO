# net_features.py
# ══════════════════════════════════════════════════════════════════════════════
# EMIX-PRO v13.4 — «FINAL PRODUCTION FIX & FEATURE INTEGRATION»
# ماژول افزودنیِ مستقل برای سه قابلیت جدید (طبق سند کاربر):
#
#   ۱) CLIENT PING (Real Client RTT):
#      پینگ اصلی UI از مرورگرِ کاربر اندازه‌گیری می‌شود (USER DEVICE → CONFIG
#      ENDPOINT → RESPONSE → USER DEVICE) — نه از Railway و نه از Cloudflare.
#      مرورگر ICMP ندارد → روش اندازه‌گیری = HTTPS RTT (fetch no-cors) و
#      همان صادقانه در UI برچسب می‌خورد: «Measurement: HTTPS (Browser)».
#      این ماژول فقط «اعتبارسنجی + ثبت» داده‌ی گزارش‌شده‌ی مرورگر را انجام
#      می‌دهد؛ هیچ عددی اینجا ساخته نمی‌شود (NO FAKE PING — سخت‌گیرانه).
#      حداقل ۵ نمونه الزامی است؛ آمار (min/median/avg/max/jitter/loss) روی
#      همان نمونه‌های دریافتی محاسبه/صحت‌سنجی می‌شود.
#
#   ۲) IRAN ROUTING (per-link, مستقل از SNI Spoofing):
#      حالت‌ها: OFF / AUTO / DIRECT
#      • OFF    = بدون قواعد ایران (همه‌ی ترافیک از تونل)
#      • AUTO   = قواعد routing واقعی کلاینت: دامنه‌ها/GeoIP ایران → DIRECT،
#                 بین‌المللی → تونل (split-routing — IP کاربر جعل نمی‌شود)
#      • DIRECT = مثل AUTO + اتصال مستقیم لینک (بدون فرانت Smart Routing) و
#                 اولویت‌دهی مجوز خروجی داخلی برای ترافیک غیر-بین‌المللی
#      SNI ≠ Iran Egress و SNI ≠ Domestic Routing — این قابلیت هیچ ربطی به
#      جعل SNI ندارد و هیچ ادعای «egress ایران» نمی‌کند (فقط smart_routing
#      با verify دو-منبعی چنین ادعایی دارد — ماژول جدا).
#
#   ۳) SR ROUTE INFO (نمایش مسیر انتخاب‌شده روی لینک):
#      خلاصه‌ی صادق مسیر فعال (endpoint/country/ASN/egress/latency/jitter/
#      loss/health/score) برای GET /api/links — بدون مسیر فعال = null + reason.
#
# 🔌 فلسفه: این فایل کاملاً مستقل است؛ اگر حذف شود پنل و تونل‌ها کار می‌کنند.
# ══════════════════════════════════════════════════════════════════════════════

import math
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote

from fastapi import HTTPException

IRAN_ROUTING_MODES = ("OFF", "AUTO", "DIRECT")

# ── CLIENT PING (اعتبارسنجی گزارش مرورگر — نه تولید عدد) ────────────────────
def validate_client_ping(body: dict) -> dict:
    """داده‌ی پینگ مرورگر را اعتبارسنجی و نرمال می‌کند.

    مرورگر نمونه‌ها را خودش اندازه گرفته (HTTPS RTT)؛ سرور فقط صحت
    ساختار/بازه‌ها را چک می‌کند و آمار را از «همان نمونه‌ها» بازمی‌سازد —
    اگر مرورگر دروغ/stat جعلی فرستاده باشد، مقادیر بازمحاسبه‌شده با
    ارسالی mismatch می‌شود و ۴۰۰ می‌گیرد (ضد جعل)."""
    if not isinstance(body, dict):
        raise HTTPException(400, "بدنه نامعتبر است")
    samples = body.get("samples")
    if not isinstance(samples, list) or len(samples) < 5:
        raise HTTPException(
            400,
            "حداقل ۵ نمونه‌ی اندازه‌گیری لازم است (سند: MULTIPLE SAMPLES)",
        )
    if len(samples) > 30:
        raise HTTPException(400, "بیش از ۳۰ نمونه پذیرفته نمی‌شود")
    clean = []
    for s in samples:
        if s is None:
            clean.append(None)          # probe ناموفق = packet loss
            continue
        try:
            v = float(s)
        except (TypeError, ValueError):
            raise HTTPException(400, "نمونه باید عدد (میلی‌ثانیه) یا null باشد")
        if not math.isfinite(v) or v < 1.0 or v > 15000.0:
            raise HTTPException(
                400,
                "مقدار نمونه خارج از بازه‌ی واقعی است (۱ تا ۱۵۰۰۰ ms) — "
                "پینگ ساختگی پذیرفته نمی‌شود",
            )
        clean.append(round(v, 1))

    # ── آمار از نمونه‌های دریافتی (بازمحاسبه — مقاوم در برابر جعل) ──
    ok_vals = [v for v in clean if v is not None]
    if not ok_vals:
        stats = {
            "ok": False, "total": len(clean), "received": 0,
            "min": None, "median": None, "avg": None, "max": None,
            "jitter": None, "loss": 1.0,
        }
    else:
        sv = sorted(ok_vals)
        n = len(sv)
        median = sv[n // 2] if n % 2 else round((sv[n // 2 - 1] + sv[n // 2]) / 2, 1)
        avg = round(sum(sv) / n, 1)
        jitter = None
        if n >= 2:
            diffs = [abs(sv[i] - sv[i - 1]) for i in range(1, n)]
            jitter = round(sum(diffs) / len(diffs), 1)
        stats = {
            "ok": True, "total": len(clean), "received": n,
            "min": sv[0], "median": median, "avg": avg, "max": sv[-1],
            "jitter": jitter, "loss": round(1.0 - n / len(clean), 3),
        }
    # مقایسه‌ی صادقانه: اگر مرورگر stat فرستاده و با بازمحاسبه نمی‌خوانَد → رد
    for k in ("median", "min", "max", "avg", "jitter"):
        sent = body.get(k)
        if sent is not None and stats.get(k) is not None:
            try:
                if abs(float(sent) - float(stats[k])) > 2.0:
                    raise HTTPException(
                        400,
                        f"«{k}» ارسالی با نمونه‌ها نمی‌خواند — داده‌ی ناسازگار رد شد",
                    )
            except (TypeError, ValueError):
                raise HTTPException(400, f"«{k}» باید عدد باشد")
    measurement = str(body.get("measurement") or "HTTPS").strip().upper()
    if measurement not in ("HTTPS", "WEBSOCKET"):
        measurement = "HTTPS"
    stats["measurement"] = measurement      # برچسب صادق روش اندازه‌گیری
    stats["measured_by"] = "client-browser" # صریح: مرورگرِ کاربر
    stats["measured_at"] = datetime.now().isoformat()
    return stats


# ── ENDPOINT HOST (هاست واقعی emitted — برای پینگ سمت مرورگر) ────────────────
def endpoint_host_for(link: dict, host: str, protocol: str) -> str | None:
    """هاستی که لینکِ تولیدشده واقعاً به آن اشاره می‌کند (فرانت SR یا پنل).

    مرورگر دقیقاً به همین هاست HTTPS RTT می‌زند — همان مسیر واقعی کاربر.
    برای mtproto بدون public host → None (صادقانه: قابل اندازه‌گیری نیست)."""
    if not link:
        return host
    if protocol == "mtproto":
        ph = link.get("mtproto_public_host")
        return str(ph).strip() if ph else None
    if (link.get("smart_routing_mode") or "OFF").upper() not in ("OFF",):
        try:
            from smart_routing import route_front_for
            front = route_front_for(host, link, protocol)
            if front:
                return front
        except Exception:
            pass
    return host


# ── IRAN ROUTING — پیکربندی واقعی split-routing (v2ray JSON) ─────────────────
def _parse_vless_outbound(link_url: str) -> dict:
    """لینک vless:// شما → outbound کامل xray (tls/ws یا xhttp)."""
    u = urlparse(link_url)
    if u.scheme != "vless":
        raise ValueError("not vless")
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    uid = unquote(u.username or "")
    host = u.hostname or ""
    port = u.port or 443
    net = q.get("type", "ws")
    stream = {"network": net}
    sec = q.get("security", "tls")
    if sec == "tls":
        tls = {
            "serverName": q.get("sni") or host,
            "allowInsecure": str(q.get("allowInsecure", "0")) in ("1", "true"),
        }
        if q.get("fp"):
            tls["fingerprint"] = q["fp"]
        if q.get("alpn"):
            tls["alpn"] = [a for a in q["alpn"].split(",") if a]
        stream["security"] = "tls"
        stream["tlsSettings"] = tls
    if net == "ws":
        ws = {"path": q.get("path", "/")}
        if q.get("host"):
            ws["headers"] = {"Host": q["host"]}
        stream["wsSettings"] = ws
    elif net == "xhttp":
        xs = {"path": q.get("path", "/"), "mode": q.get("mode", "auto")}
        if q.get("host"):
            xs["host"] = q["host"]
        stream["xhttpSettings"] = xs
    return {
        "tag": "proxy",
        "protocol": "vless",
        "settings": {"vnext": [{
            "address": host, "port": port,
            "users": [{"id": uid, "encryption": "none", "level": 0}],
        }]},
        "streamSettings": stream,
    }


def _parse_trojan_outbound(link_url: str) -> dict:
    u = urlparse(link_url)
    if u.scheme != "trojan":
        raise ValueError("not trojan")
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    pwd = unquote(u.username or "")
    host = u.hostname or ""
    port = u.port or 443
    net = q.get("type", "ws")
    stream = {"network": net}
    tls = {
        "serverName": q.get("sni") or host,
        "allowInsecure": str(q.get("allowInsecure", "0")) in ("1", "true"),
    }
    if q.get("fp"):
        tls["fingerprint"] = q["fp"]
    if q.get("alpn"):
        tls["alpn"] = [a for a in q["alpn"].split(",") if a]
    stream["security"] = "tls"
    stream["tlsSettings"] = tls
    if net == "ws":
        ws = {"path": q.get("path", "/")}
        if q.get("host"):
            ws["headers"] = {"Host": q["host"]}
        stream["wsSettings"] = ws
    elif net == "xhttp":
        xs = {"path": q.get("path", "/"), "mode": q.get("mode", "auto")}
        if q.get("host"):
            xs["host"] = q["host"]
        stream["xhttpSettings"] = xs
    return {
        "tag": "proxy",
        "protocol": "trojan",
        "settings": {"servers": [{
            "address": host, "port": port, "password": pwd, "level": 0,
        }]},
        "streamSettings": stream,
    }


def build_iran_route_config(link_url: str, remark: str, mode: str) -> dict:
    """پیکربندی کامل v2ray/xray با routing واقعی ایران (بر پایه‌ی لینک خود کاربر).

    قواعد واقعی (نه جعل IP/SNI):
      geoip:private + geoip:ir + دامنه‌های .ir و لیست ایرانی → outbound direct
      بقیه‌ی ترافیک → outbound proxy (همان لینک EMIX کاربر)
    DIRECT اضافه دارد: ترافیکِ داخلیِ تشخیص‌نیافته هم اول مستقیم ارزیابی می‌شود
    (domainStrategy IPIfNonMatch + اولویت قواعد direct) و DNS داخلی مستقیم."""
    parsed = None
    proto = None
    for fn, name in ((_parse_vless_outbound, "vless"), (_parse_trojan_outbound, "trojan")):
        try:
            parsed = fn(link_url)
            proto = name
            break
        except Exception:
            continue
    if parsed is None:
        raise HTTPException(
            400,
            "این پروتکل در قالب JSON routing قابل تبدیل نیست (فقط لینک‌های "
            "VLESS/Trojan پشتیبانی می‌شوند) — برای Shadowsocks/MTProto قواعد "
            "routing را در کلاینت خودتان تنظیم کنید",
        )
    from smart_routing import iran as _iran
    strict = (mode or "AUTO").upper() == "DIRECT"
    rules = [
        {"type": "field", "ip": ["geoip:private"], "outboundTag": "direct"},
        {"type": "field", "ip": ["geoip:ir"], "outboundTag": "direct"},
        {
            "type": "field",
            "domain": [f"domain:{d}" for d in _iran.IR_DIRECT_DOMAINS[:80]]
                      + ["regexp:.*\\.ir$"],
            "outboundTag": "direct",
        },
        {"type": "field", "port": "53", "outboundTag": "direct"},
    ]
    if strict:
        # DIRECT: ترافیک داخلیِ شناخته‌شده هم قبل از match نهایی مستقیم
        rules.append({"type": "field", "domain": ["geosite:category-ir"],
                      "outboundTag": "direct"})
    rules.append({"type": "field", "network": "tcp,udp", "outboundTag": "proxy"})
    return {
        "log": {"loglevel": "warning"},
        "dns": {
            "servers": [
                {"address": "1.1.1.1", "domains": ["geosite:category-ir", "domain:ir"]},
                "8.8.8.8",
                "localhost",
            ],
            "queryStrategy": "UseIPv4",
        },
        "outbounds": [
            parsed,
            {"tag": "direct", "protocol": "freedom",
             "settings": {"domainStrategy": "UseIP"}},
            {"tag": "block", "protocol": "blackhole"},
        ],
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules": rules,
        },
        "_emix": {
            "feature": "IRAN_ROUTING",
            "mode": (mode or "AUTO").upper(),
            "protocol": proto,
            "remark": remark,
            "link": link_url,
            "routing": "IRAN/DOMESTIC → direct · INTERNATIONAL → proxy",
            "honest_note": (
                "قواعد routing واقعی کلاینت (GeoIP/دامنه) — IP کاربر جعل "
                "نمی‌شود و این قابلیت هیچ ادعایی درباره‌ی egress ایران ندارد؛ "
                "egress فقط در «مسیریابی هوشمند» و فقط با verify دو-منبعی "
                "اعلام می‌شود. SNI Spoofing مستقل است و در این JSON نیست."
            ),
        },
    }
