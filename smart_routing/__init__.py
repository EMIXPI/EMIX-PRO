# smart_routing — EMIX-PRO Smart Routing Network v1
# ══════════════════════════════════════════════════════════════════════════════
# ماژول مستقل و production-grade «شبکه‌ی مسیریابی هوشمند» برای EMIX-PRO.
#
# 🧭 فلسفه (طبق سند EMIX-PRO SMART ROUTING NETWORK v1):
#   1) هیچ IP/کشوری جعل نمی‌شود — هر endpoint فقط با تست واقعی معتبر است.
#   2) SNI Spoofing موجود کاملاً مستقل می‌ماند؛ این ماژول جایگزین آن نیست.
#   3) هسته‌ی EMIX-PRO دست نمی‌خورد — همه‌چیز additive و feature-flagged است.
#   4) موفقیت فقط یعنی: route established + traffic traversed + egress
#      observed + egress verified + health passed — در غیر این صورت UNVERIFIED.
#   5) Cloudflare Worker جدید (emix-smart-routing-v1) کاملاً مستقل از
#      workerهای قبلی EMIX است.
#
# 🔩 ساختار (هر زیرماژول یک مسئولیت):
#   db             → ذخیره‌گاه SQLite افزودنی (smart_* tables — migration امن)
#   security       → SSRF guard + امضای HMAC + replay protection + rate limit
#   discovery      → کشف endpoint از منابع عمومی مجاز (بدون اسکن کنترل‌نشده)
#   metrics        → اندازه‌گیری واقعی latency / jitter / packet loss (مسیر کلاینت)
#   egress         → verify واقعی خروجی IP + Geo/ASN از منابع مستقل
#   scoring        → امتیاز ترکیبی با وزن‌های قابل‌تنظیم
#   pool           → state machine پویا (ACTIVE/DEGRADED/UNHEALTHY/QUARANTINED/…)
#   selector       → انتخاب مسیر (حالت‌ها) + failover + جلوگیری از oscillation
#   health         → پایش دوره‌ای + تاریخچه‌ی ۲۰ چک آخر
#   worker_client  → ارتباط امضاشده با Cloudflare Worker جدید
#   iran           → قابلیت IRAN_EGRESS (فقط با verify واقعی) + Iran-Direct rules
#   engine         → ارکستراتور + حلقه‌های پس‌زمینه
#   api            → اندپوینت‌های /api/smart-routing/*
#
# 🚩 Feature Flag:
#   SMART_ROUTING_ENABLED (env) + settings.enabled (تگل ادمین).
#   v13.5.0: پیش‌فرض flag «روشن» است — قابلیت GA شد و روی fresh-deploy
#   بدون تنظیم دستی کار می‌کند (علت complaint کاربر: تگل ظاهراً «زود
#   خاموش می‌شد» چون env پیش‌فرض خاموش بود). opt-out صریح:
#   SMART_ROUTING_ENABLED=false (برای rollback کامل).
#   وقتی خاموش است: هیچ لینکی تغییر نمی‌کند، هیچ حلقه‌ای اجرا نمی‌شود،
#   کاربران موجود هیچ تفاوتی نمی‌بینند (rollback = false کردن flag).
# ══════════════════════════════════════════════════════════════════════════════

import os

__version__ = "1.1.0"
MODULE_NAME = "smart-routing"

# ── Feature flag (v13.5.0: پیش‌فرض روشن — GA؛ opt-out با false) ──────────────────
def env_flag() -> bool:
    """SMART_ROUTING_ENABLED از env — پیش‌فرض روشن (v13.5.0 GA).

    مقدارهای false/0/no/off → خاموش (rollback صریح)؛
    متغیر ست نشده → روشن (fresh-deploy بدون قدم دستی کار می‌کند)."""
    return os.environ.get("SMART_ROUTING_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")


# ── hookهای integration برای main.py (fail-safe — هرگز لینک‌سازی را نمی‌شکنند) ──
def route_front_for(host: str, link: dict, protocol: str):
    """فرانت مسیر هوشمند برای لینک — None یعنی «مسیر مستقیم، بدون تغییر».

    فقط وقتی مقدار برمی‌گرداند که:
      flag روشن باشد + لینک mode≠OFF داشته باشد + مسیر ACTIVE و verified موجود
      باشد. هر خطایی → None (رفتار پایه‌ی EMIX، بدون regression)."""
    try:
        if not env_flag():
            return None
        from . import selector, db
        if not db.get_setting("enabled", False):
            return None
        return selector.route_front_for(host, link, protocol)
    except Exception:
        return None


def apply_route_params(params: dict, link: dict, protocol: str) -> None:
    """اعمال پارامترهای مسیر هوشمند روی params لینک (in-place، fail-safe).

    وقتی route فعال است: sni=فرانت (cert معتبر workers.dev)، host=دامنه‌ی
    واقعی پنل (هدر WS)، allowInsecure حذف می‌شود. تداخل با SNI spoof:
    spoof پشت فرانت workers.dev مضر است (فاز ۴۴ اندازه‌گیری شد) → route
    فعال = spoof نادیده گرفته می‌شود (قاعده‌ی مستند در CHANGELOG)."""
    try:
        if not env_flag():
            return
        from . import selector
        selector.apply_route_params(params, link, protocol)
    except Exception:
        pass


def register_routes(app) -> None:
    """ثبت همه‌ی اندپوینت‌های /api/smart-routing/* + startup engine."""
    from .api import register_routes as _reg
    _reg(app)
