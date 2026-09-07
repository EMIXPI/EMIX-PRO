# smart_routing/iran.py — IRAN_EGRESS (فقط با verify واقعی) + Iran-Direct rules
# ══════════════════════════════════════════════════════════════════════════════
# دو قابلیت مستقل (طبق سند):
#
# ۱) IRAN_EGRESS (capability):
#    فقط وقتی egress واقعاً از دو منبع مستقل ایران verify شود true می‌شود.
#    هرگز بر اساس SNI / DNS / Host / X-Forwarded-For / Geo header / کشورِ
#    تنظیمی، endpoint ایرانی اعلام نمی‌شود. اگر endpoint ایرانی واقعی پیدا
#    نشد → سیستم صریحاً «وجود ندارد» می‌گوید (ادعای خلاف واقع ممنوع).
#
# ۲) IRAN_DIRECT / DOMESTIC_ROUTE (قابل خاموش/روشن):
#    مقصدهای ایرانی از مسیر مستقیم کاربر، بقیه از VPN/Smart Route.
#    • IP کاربر جعل نمی‌شود؛ IP موبایل جایی به‌عنوان server IP نمی‌نشیند؛
#      SNI جایگزین routing نیست — قواعد routing واقعی (بر پایه‌ی GeoIP/CIDR/
#      domain classification) در قالب پیکربندی v2ray کلاینت صادر می‌شود.
#    • Routing: IRAN/DIRECT → direct · INTERNATIONAL → proxy
# ══════════════════════════════════════════════════════════════════════════════

import json

from . import db

def _main():
    import main
    return main

# ── IRAN_EGRESS ───────────────────────────────────────────────────────────────
def set_iran_capability(ep: dict, egress_result: dict) -> dict:
    """ثبت قابلیت IRAN_EGRESS فقط از نتیجه‌ی verify دو-منبعی (egress.verify)."""
    caps = ep.get("capabilities") or {}
    verified_ir = bool(
        egress_result.get("ok")
        and egress_result.get("status") == "VERIFIED"
        and egress_result.get("iran_egress")
    )
    if caps.get("IRAN_EGRESS") != verified_ir:
        # تغییر قابلیت → event شفاف (مخصوصاً وقتی false می‌شود)
        from . import db as _db
        _db.add_event(
            "verify",
            f"IRAN_EGRESS={verified_ir} برای {ep.get('address')} "
            f"(observed_country={egress_result.get('observed_country')})",
            endpoint_id=ep.get("id"),
        )
    caps["IRAN_EGRESS"] = verified_ir
    ep["capabilities"] = caps
    return ep


def iran_egress_report() -> dict:
    """گزارش صادق: فقط endpointهای IRAN_EGRESS واقعی — یا اعلام صریح «هیچ»."""
    have = []
    for ep in db.list_endpoints():
        caps = ep.get("capabilities") or {}
        ver = ep.get("verification") or {}
        eg = ver.get("egress") or {}
        if caps.get("IRAN_EGRESS") and eg.get("status") == "VERIFIED":
            have.append({
                "endpoint": ep.get("address"), "egress_ip": ep.get("observed_ip"),
                "observed_country": ep.get("observed_country"),
                "asn": ep.get("observed_asn"),
            })
    return {
        "count": len(have),
        "endpoints": have,
        "honest_note": (
            "هیچ endpoint با egress ایرانِ verify-شده وجود ندارد — سیستم ایران را"
            " جعل نمی‌کند (SNI/هدر/کشورِ تنظیمی ملاک نیست؛ فقط IP خروجی مشاهده‌شده"
            " از دو منبع مستقل)."
        ) if not have else "egress ایران از دو منبع مستقل verify شده است.",
    }


# ── IRAN_DIRECT / DOMESTIC_ROUTE ──────────────────────────────────────────────
# دامنه‌های شناخته‌شده‌ی ایرانی (خبرگی حسنه/به‌روزرسانی اپراتور) — قواعد routing
# واقعی کلاینت: هر دو خانواده‌ی geoip:ir و لیست دامنه صادر می‌شوند.
IR_DIRECT_DOMAINS = [
    # بانک‌ها و پرداخت
    "bpi.ir", "shaparak.ir", "digikala.com", "snapp.ir", "snappfood.ir",
    "tapsi.ir", "toscotech.com", "bale.ir", "eitaa.com", "rubika.ir",
    "soroushplus.ir", "telewebion.com", "aparat.com", "filimo.com", "namava.ir",
    "divar.ir", "khanoumi.com", "torob.com", "emalls.ir", "mysbir.ir",
    "irancell.ir", "mci.ir", "rightel.ir", "shatel.ir", "hiweb.ir",
    "parsonline.com", "mtnirancell.ir", "ir.zarinpal.com", "sadadpsp.ir",
    "asanpardakht.ir", "pec.ir", "sep.ir", "bmi.ir", "bank-melli.ir",
    "banksepah.ir", "tejaratbank.ir", "bsi.ir", "postbank.ir", "edbi.ir",
    # آموزش/دولت/خدمات
    "irimo.ir", "irna.ir", "isna.ir", "mehrnews.com", "tasnimnews.com",
    "khabaronline.ir", "hamshahrionline.ir", "varzesh3.com", "ico.ir",
    "moein.ir", "ir.gov.ir", "irica.gov.ir", "dps.ir", "ssaa.ir",
    "sharif.edu", "ut.ac.ir", "tmu.ac.ir", "iau.ir", "azad.ac.ir",
    "persianblog.ir", "blogfa.com", "niniweb.com", "alibaba.ir",
    "iranotel.com", "iranair.com", "mahanair.com", "qeshmair.com",
]
IR_DIRECT_DOMAINS = sorted(set(IR_DIRECT_DOMAINS))


def iran_direct_enabled() -> bool:
    return bool(db.get_setting("iran_direct_enabled", False))


def build_iran_direct_config(proxy_link: str, remark: str = "EMIX Smart") -> dict:
    """پیکربندی واقعی split-routing برای کلاینت v2ray/v2rayNG (v4.4+ JSON).

    قواعد واقعی: GeoIP private/ir + دامنه‌های ایرانی → outbound مستقیم؛
    بقیه → outbound پروکسی. این «routing واقعی» است — نه جعل IP/SNI."""
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
            {
                "tag": "proxy",
                "protocol": "vless",       # کلاینت، لینک EMIX را جایگزین می‌کند
                "settings": {"vnext": []},
                "_emix_link": proxy_link,
                "_hint": "این outbound را با لینک EMIX خود جایگزین کنید (کلاینت‌های"
                         " مدرن import لینک، outbound را خودشان می‌سازند)",
            },
            {"tag": "direct", "protocol": "freedom",
             "settings": {"domainStrategy": "UseIP"}},
            {"tag": "block", "protocol": "blackhole"},
        ],
        "routing": {
            "domainStrategy": "IPIfNonMatch",
            "rules": [
                {"type": "field", "ip": ["geoip:private"], "outboundTag": "direct"},
                {"type": "field", "ip": ["geoip:ir"], "outboundTag": "direct"},
                {"type": "field",
                 "domain": [f"domain:{d}" for d in IR_DIRECT_DOMAINS[:80]]
                          + ["regexp:.*\\.ir$"],
                 "outboundTag": "direct"},
                {"type": "field", "port": "53", "outboundTag": "direct"},
                {"type": "field", "network": "tcp,udp", "outboundTag": "proxy"},
            ],
        },
        "_emix": {
            "feature": "IRAN_DIRECT / DOMESTIC_ROUTE",
            "enabled": iran_direct_enabled(),
            "routing": "IRAN/DIRECT → direct · INTERNATIONAL → proxy",
            "note": "trffic داخلی از مسیر مستقیم کاربر عبور می‌کند؛ فقط ترافیک"
                    " بین‌المللی از تونل. IP کاربر جعل نمی‌شود.",
        },
    }


def iran_direct_summary() -> dict:
    return {
        "enabled": iran_direct_enabled(),
        "domains_count": len(IR_DIRECT_DOMAINS),
        "rules": ["geoip:private → direct", "geoip:ir → direct",
                  "domain:{ir} list → direct", "other → proxy"],
        "honest_note": "این قابلیت قواعد routing واقعی کلاینت صادر می‌کند (split"
                       " tunnel) — server پنل مسیر ترافیک محلی کاربر را تغییر"
                       " نمی‌دهد و IP کاربر جعل نمی‌شود.",
    }
