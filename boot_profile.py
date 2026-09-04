# ══════════════════════════════════════════════════════════════════════════════
# boot_profile.py — پروفایل بوت EMIX-PRO (احیای v12.0.0-core)
#
# 🔴 دردِ اصلی که این ماژول حل می‌کند:
#   EMIX-PRO بعد از ماه‌ها افزودن موتور، به ۴۶هزار خط و ۶۰+ ماژول رسیده بود که
#   «همه‌شان» در بوت import و register می‌شدند. نتیجه: هر موتوری می‌توانست بوت
#   را سنگین/شکننده کند و سلامتِ «پروتکل پایه‌ی EMIX» (پینگ + رله + ساب) را
#   گروگان بگیرد — همان‌که نسخه‌ی اصلی EMIX با ۱۴هزار خط سالم نگهش داشته بود.
#
# ✅ راه‌حل — قرارداد «هسته‌ی همیشه‌زنده»:
#   - CORE (همیشه، بدون شرط): پینگ/سلامت، رله‌ی VLESS/Trojan/Shadowsocks/MTProto،
#     لینک‌ها/سابسکریپشن، داشبورد، لاگین، بکاپ، کامپایلر کانفیگ، jobهای حیاتی.
#     هیچ چیزی خارج از این لیست اجازه ندارد بوت را شرطی کند.
#   - ENGINES (اختیاری): ۲۰+ موتور PRO — در پروفایل «core» به‌صورت پیش‌فرض
#     خاموش‌اند و فقط با env روشن می‌شوند. خاموشی‌شان هیچ‌وقت کرش نیست؛ فقط
#     اندپوینت‌هایشان ثبت نمی‌شود و بخش مرتبطِ داشبورد خالی می‌ماند.
#
#   EMIX_PROFILE=core   ← پیش‌فرض؛ بوت سبکِ هم‌ترازِ EMIX (فقط هسته)
#   EMIX_PROFILE=full   ← رفتار قبلی؛ همه‌ی موتورها مثل v11
#   EMIX_ENABLE=multiloc,gaming_boost    ← روشن‌کردن موتور دلخواه در core
#   EMIX_DISABLE=ip_quality,gaming_boost ← خاموش‌کردن موتور دلخواه در full
# ══════════════════════════════════════════════════════════════════════════════

import os
import time

PROFILE_CORE = "core"
PROFILE_FULL = "full"

# ── رجیستری موتورهای اختیاری ────────────────────────────────────────────────
# name → (گروه، توضیح کوتاه). اسم‌ها همان gate هایی هستند که main.py چک می‌کند.
ENGINES: dict[str, tuple[str, str]] = {
    # شتاب‌دهنده‌ها و پل‌ها
    "bridge_boost":     ("boost", "پل ایران CDN/VPS"),
    "turbo_boost":      ("boost", "لینک‌های 0-RTT توربو + A/B"),
    "clean_ip_boost":   ("boost", "اسکنر IP تمیز اروان"),
    "zeus_features":    ("boost", "تنظیمات ZEUS (ISP/TLS-Mask/Smart/Security)"),
    "gaming_boost":     ("boost", "مرکز گیمینگ + اسکنر CF"),
    "multiloc":         ("boost", "پل چندلوکیشن v2 + WTE"),
    # موتورهای v11.2+ (راستی‌آزمایی شبکه)
    "egress_engine":    ("truth", "راستی‌آزمایی خروجی/مسیر"),
    "route_engine":     ("truth", "مسیرهای first-class"),
    "failover_engine":  ("truth", "فیل‌اور بدون کورکورانه"),
    "account_manager":  ("truth", "حساب‌ها/دستگاه‌ها/سابسکریپشن"),
    "domestic_route_engine": ("truth", "تقسیم‌ترافیک ایران (split tunneling)"),
    "iran_gateway":     ("truth", "گیت‌وی ایرانی IRAN_PROXY"),
    "iran_direct":      ("truth", "دارایی‌های اندپوینت IRAN_DIRECT"),
    "capability_engine":("truth", "ماتریس توانمندی/اعتبارسنجی"),
    "config_builder":   ("truth", "سازنده‌ی کانفیگ یکپارچه"),
    "structured_events":("truth", "رویدادهای ساخت‌یافته"),
    "railway_infra":    ("truth", "زیرساخت Railway + Volume"),
    # آزمایشی و امنیت
    "experimental":     ("labs",  "بخش آزمایشی + exp_api"),
    "security_exp":     ("labs",  "میدل‌ویر امنیتی آزمایشی"),
    "link_emit":        ("labs",  "صدور لینک پروتکل‌های جدید"),
    # کیفیت و هوش شبکه
    "ip_quality":       ("intel", "موتور کیفیت IP"),
    "smart_route":      ("intel", "روتینگ هوشمند v3"),
    "isp_detect":       ("intel", "تشخیص ISP"),
    "gaming_health":    ("intel", "سلامت گیمینگ"),
    # مدیریت SNI/VPN
    "sni_management":   ("mgmt", "پروفایل‌های SNI"),
    "security_signatures": ("mgmt", "امضاهای امنیتی"),
    "vpn_pro":          ("mgmt", "نودهای VPN (WG/OpenVPN)"),
}

# ── موتورهای «همیشه‌روشن» — هسته‌ی دوم (اولویت اپراتور، v12.1) ───────────────
# Iran Direct ستون‌فقرات پنل است؛ موتور دیتاست/پالیسی آن در هر دو پروفایل
# روشن می‌ماند (خروجی کلاینت‌محورش /sub-json خودش مستقلاً هسته است).
#
# ── Phase 40 §32 — «دیوار پروفایل» برداشته شد ────────────────────────────────
# تجربه‌ی اصلی محصول = ساخت/مدیریت/تست کانفیگ از یک ورک‌اسپیس. اگر آن زنجیره
# فقط در EMIX_PROFILE=full کار می‌کرد، کاربرِ پروفایل core (پیش‌فرضِ دیپلوی
# واقعی) به دیوار «پروفایل دیگری را فعال کنید» می‌خورد — که نقض UX نهایی است.
# زنجیره‌ی ساخت کانفیگ سبک و pure-python است (بدون وابستگی شبکه در import)؛
# پس بخشی از «هسته‌ی همیشه‌زنده» می‌شود:
#   config_builder + capability_engine + iran_direct + iran_gateway
#   + structured_events + turbo_boost (تست A/B واقعی) + account_manager
# آنها همچنان fail-safe اند (ثبتشان try/except است — خرابی‌شان هرگز بوت را
# نمی‌شکند؛ فقط همان موتور صادقانه غایب می‌ماند).
ALWAYS_ON: set[str] = {
    "domestic_route_engine",
    "config_builder",
    "capability_engine",
    "iran_direct",
    "iran_gateway",
    "structured_events",
    "turbo_boost",
    "account_manager",
    # ── Phase 43 — «بخش سلامت پنل» نباید دیوار پروفایل داشته باشد ──────────────
    # گزارش عملی (کاربر واقعی روی core): دکمه‌ی «بررسی سلامت همه‌چیز» و کارت
    # «کیفیت IP» در صفحه‌ی سلامت/تشخیص مرده بودند (404) چون UI بدون قید رندر
    # می‌شود ولی موتور زیرش در core خاموش است — دقیقاً همان نقض UX §40-32.
    # هر دو ماژول fail-safe اند (ثبتشان try/except است) و pure-python بدون
    # شبکه در import. railway_infra = سلامت خودِ پنل + بنر volume (حفاظت از
    # دست‌بردگی دیتا)؛ ip_quality = کارت تشخیص IP. هر دو هسته‌ی اپراتورند.
    "railway_infra",
    "ip_quality",
}

# هسته‌ی همیشه‌زنده — فقط برای گزارش و self-check بوت (هرگز gate نمی‌شوند)
CORE_SURFACE = [
    ("/api/ping",        "healthcheck سبک Railway"),
    ("/health",          "سلامت + شمارنده‌ی کانکشن‌ها"),
    ("/ws/{uuid}",       "رله‌ی VLESS over WebSocket"),
    ("/trojan-ws",       "رله‌ی Trojan over WebSocket"),
    ("/ss-ws",           "رله‌ی Shadowsocks over WS"),
    ("/sub/{uuid}",      "سابسکریپشن/اشتراک لینک"),
    ("/sub-json/{uuid}", "ساب JSON با قواعد IR-Direct (داخلی‌کردن مصرف)"),
    ("/dashboard",       "داشبورد مدیریت"),
    ("/login",           "احراز هویت پنل"),
    ("/api/network/test/quick", "پروب مرحله‌ای واقعی DNS/TCP/TLS — ورک‌اسپیس کانفیگ"),
    # ── Phase 40: زنجیره‌ی ساخت کانفیگ = هسته (دیوار پروفایل برداشته شد §32) ──
    ("/api/config-builder/capabilities", "قابلیت‌های واقعی ساخت کانفیگ (پروتکل/نود/مسیریابی)"),
    ("/api/config-builder/preview",      "پیش‌نمایش از همان کامپایلر کانونی"),
    ("/api/config-builder/generate",     "ساخت نهایی + ذخیره‌ی لینک زنده + تاریخچه"),
    ("/api/config-builder/history",      "تاریخچه‌ی کانفیگ‌های ساخته‌شده"),
]

_report: dict = {
    "profile": None,
    "engines": {},       # name → {"enabled": bool, "loaded": bool|None, "ms": float}
    "started_at": time.time(),
}
_resolved: dict | None = None


def _resolve_profile() -> dict:
    """پروفایل + override های granular را یک‌بار محاسبه می‌کند."""
    global _resolved
    if _resolved is not None:
        return _resolved

    raw = (os.environ.get("EMIX_PROFILE") or PROFILE_CORE).strip().lower()
    profile = PROFILE_FULL if raw in ("full", "all", "1", "true") else PROFILE_CORE

    def _csv(name: str) -> set[str]:
        return {x.strip() for x in (os.environ.get(name) or "").split(",") if x.strip()}

    force_on = _csv("EMIX_ENABLE")
    force_off = _csv("EMIX_DISABLE")

    enabled_map: dict[str, bool] = {}
    for name in ENGINES:
        if name in force_off:
            enabled_map[name] = False
        elif name in force_on:
            enabled_map[name] = True
        else:
            enabled_map[name] = (profile == PROFILE_FULL)

    _resolved = {"profile": profile, "enabled": enabled_map}
    _report["profile"] = profile
    return _resolved


def current_profile() -> str:
    return _resolve_profile()["profile"]


def enabled(name: str) -> bool:
    """آیا موتور اختیاری «name» باید در این بوت لود شود؟ (هسته همیشه True است
    ولی برای هسته این تابع صدا زده نمی‌شود — هسته gate ندارد.)"""
    if name in ALWAYS_ON:
        return True
    return _resolve_profile()["enabled"].get(name, False)


def all_enabled(*names: str) -> bool:
    """True فقط اگر همه‌ی موتورهای خواسته‌شده فعال باشند — برای wiring
    های چندموتوره (مثل phase38) که نصفه‌کار نباید وصل شوند."""
    return all(enabled(n) for n in names)


def note(name: str, loaded: bool, ms: float = 0.0) -> None:
    """main.py بعد از تلاش برای لود هر موتور، نتیجه را ثبت می‌کند."""
    _report["engines"][name] = {
        "enabled": _resolve_profile()["enabled"].get(name, False),
        "loaded": loaded,
        "ms": round(ms, 1),
    }


def report() -> dict:
    """گزارش کامل بوت — برای /api/boot-profile و self-check استارت‌آپ."""
    out = dict(_report)
    out["profile"] = current_profile()
    out["core_surface"] = [
        {"path": p, "desc": d, "registered": bool(core_registry.get(p))}
        for p, d in CORE_SURFACE
    ]
    # موتورهای ALWAYS_ON جزو «اختیاری‌ها» شمرده نمی‌شوند — آنها هسته‌اند
    engines_view = {n: e for n, e in _report["engines"].items()
                    if n not in ALWAYS_ON}
    enabled_map = {n: v for n, v in _resolve_profile()["enabled"].items()
                   if n not in ALWAYS_ON}
    loaded = sum(1 for e in engines_view.values() if e.get("loaded"))
    out["always_on"] = {
        n: {"loaded": _report["engines"].get(n, {}).get("loaded")}
        for n in sorted(ALWAYS_ON)
    }
    out["engines"] = engines_view
    out["summary"] = {
        "engines_total": len(ENGINES) - len(ALWAYS_ON & set(ENGINES)),
        "engines_enabled": sum(1 for v in enabled_map.values() if v),
        "engines_loaded": loaded,
        "engines_failed": sum(
            1 for e in engines_view.values()
            if e.get("enabled") and e.get("loaded") is False),
    }
    return out


class EngineDisabled(Exception):
    """پرتاب‌شده توسط بلوک‌های بزرگِ gate-شده در main.py — یعنی موتور «کرش
    نکرده»، طبق پروفایل بوت خاموش است (لاگ info نه error)."""
    def __init__(self, tag: str, msg: str = ""):
        self.tag = tag
        super().__init__(msg or f"{tag} disabled by boot profile")


# مسیرهای هسته که self-check استارت‌آپ ثبت‌شدنشان را بررسی می‌کند
# (boot_profile.core_registry توسط main.py بعد از ثبت روت‌ها پر می‌شود).
core_registry: dict[str, bool] = {}


def reset_for_tests() -> None:
    """فقط برای تست‌ها — وضعیت resolve را پاک می‌کند."""
    global _resolved
    _resolved = None
    _report["engines"] = {}
    _report["profile"] = None
