# experimental.py — رجیستری مرکزی فیچرهای آزمایشی EMIX-PRO
# اصل: هیچ فیچر آزمایشی بدون toggle فعال نمی‌شود.
# هر فیچر با env var قابل کنترل است:
#   EMIX_EXPERIMENTAL=1           → فعال‌سازی کل بخش آزمایشی
#   EMIX_ENABLE_<FEATURE>=1       → فعال‌سازی یک فیچر خاص
#
# همه‌ی فیچرهای آزمایشی به‌صورت DEFAULT OFF هستند. ادمین باید صریحاً فعال کند.
# این تضمین می‌کند که پایداری اصلی پروژه هیچ‌گاه به خطر نیفتد.

import os
import logging

logger = logging.getLogger("EMIX.exp")

# ─── رجیستری فیچرها ────────────────────────────────────────────────────────
# هر ورودی: (key, description, default, requires_experimental)
_FEATURES = {
    # ── Security (Phase 1) ──
    "pbkdf2_password":    ("هش رمز PBKDF2 با backward-compat sha256", True, True),
    "rate_limit":         ("محدودیت نرخ ورود و API", True, True),
    "ip_whitelist":       ("whitelist IP برای endpoint‌های admin", False, True),
    "csrf_protection":    ("محافظت CSRF برای عملیات state-changing", True, True),
    "csp_headers":        ("Content-Security-Policy headers", True, True),
    "hsts":               ("Strict-Transport-Security", True, True),
    "totp_2fa":           ("احراز هویت دو مرحله‌ای TOTP", False, True),

    # ── New Protocols & Share Links (Phase 2) ──
    "reality_link_emit":  ("صدور لینک Reality برای VLESS/Trojan (بدون inbound)", True, True),
    "vmess_link_emit":    ("صدور لینک VMESS base64-JSON", True, True),
    "ss2022_link_emit":   ("صدور لینک SS-2022 (AEAD-2022 cipher)", True, True),
    "finalmask_link":     ("صدور لینک FinalMask (TLS fragmentation + obfs)", True, True),
    "utls_fingerprint":   ("امضای uTLS (chrome/firefox/safari) روی لینک‌ها", True, True),
    "pinned_cert":        ("Pinned cert SHA-256 روی لینک‌ها", True, True),
    "reality_spiderx":    ("spiderX path منحصر بفرد به ازای کلاینت", True, True),

    # ── Subscription Formats (Phase 3) ──
    "sub_raw":            ("subscription raw (default، همیشه فعال)", True, False),
    "sub_json":           ("subscription JSON (v2rayN/sing-box)", True, True),
    "sub_clash":          ("subscription Clash.Meta YAML", True, True),
    "sub_encrypted":      ("subscription base64-encrypted", False, True),
    "multi_host":         ("چند Host برای یک inbound (CDN fronting)", True, True),

    # ── Gaming Engine (Phase 4) ──
    "gaming_health":      ("Gaming Health Score + telemetry", False, True),
    "gaming_profiles":    ("۵ پروفایل FPS/MOBA/BR/MMO/General", False, True),
    "gaming_dashboard":   ("داشبورد زنده گیمینگ", False, True),
    "game_server_ping":   ("پینگ به سرورهای معروف بازی", False, True),

    # ── Network Engineering (Phase 5) ──
    "smart_route":        ("Smart Route Engine با scoring", False, True),
    "safe_failover":      ("Failover با hysteresis + cooldown", False, True),
    "traffic_accounting": ("شمارش واقعی bytes in/out", True, True),
    "retransmission":     ("مانیتور retransmission", False, True),
    "mtu_discovery":      ("MTU/PMTU discovery (Railway-aware)", False, True),
    "adaptive_transport": ("انتخاب خودکار بهترین پروتکل", False, True),
    "prometheus_metrics": ("endpoint /metrics", False, True),

    # ── Iran Optimization (Phase 6) ──
    "isp_detection":      ("تشخیص MCI/MtnIrancell/RighTel/Shatel", False, True),
    "per_isp_route":      ("مسیر اختصاصی به ازای هر ISP", False, True),
    "sni_rotation":       ("چرخش SNI لیست", False, True),

    # ── Stealth / Disguise (Phase 7) — بخش مجزا ──
    "stealth_section":    ("بخش مجزا برای استتار/جعل", True, True),
    "tls_fragmentation":  ("TLS hello fragmentation", False, True),
    "salamander_obfs":    ("Salamander obfuscation", False, True),
    "noise_padding":      ("Padding نویز تصادفی", False, True),
    "domain_fronting":    ("Domain fronting برای CDN", False, True),

    # ── Unified Configs (Phase 8) ──
    "unified_configs":    ("همه‌ی کانفیگ‌ها در بخش اصلی با type badge", True, True),
    "config_health_score":("badge امتیاز سلامت به هر کانفیگ", True, True),

    # ── Telegram Bot (Phase 9) ──
    "telegram_bot":       ("ربات تلگرام برای اعلان انقضا + login notify", False, True),
}

# ─── API عمومی ────────────────────────────────────────────────────────────
def is_experimental_enabled() -> bool:
    """آیا کل بخش آزمایشی فعال است؟"""
    return os.environ.get("EMIX_EXPERIMENTAL", "0") == "1"


def is_enabled(feature: str) -> bool:
    """آیا یک فیچر خاص فعال است؟"""
    if feature not in _FEATURES:
        logger.warning(f"Unknown experimental feature: {feature}")
        return False
    desc, default, requires_exp = _FEATURES[feature]

    # اگر فیچر نیاز به فعال‌سازی کل بخش دارد
    if requires_exp and not is_experimental_enabled():
        return False

    # env var خاص فیچر
    env_val = os.environ.get(f"EMIX_ENABLE_{feature.upper()}", None)
    if env_val is not None:
        return env_val == "1"

    # در غیر این صورت، default
    return default


def get_feature_status() -> dict:
    """برگرداندن وضعیت همه‌ی فیچرها (برای UI)."""
    return {
        "experimental_enabled": is_experimental_enabled(),
        "features": [
            {
                "key": k,
                "description": v[0],
                "enabled": is_enabled(k),
                "default": v[1],
                "requires_experimental": v[2],
                "env_var": f"EMIX_ENABLE_{k.upper()}",
            }
            for k, v in _FEATURES.items()
        ],
    }


def get_enabled_features_summary() -> str:
    """خلاصه‌ی متنی فیچرهای فعال (برای /api/deployment-version)."""
    enabled = [k for k in _FEATURES if is_enabled(k)]
    if not enabled:
        return "none (stable mode)"
    return ", ".join(enabled)


# ─── Helper برای UI ───────────────────────────────────────────────────────
def toggle_feature(feature: str, enabled: bool) -> bool:
    """تغییر وضعیت فیچر (runtime only — برای تست).
    توجه: این تغییر در env var ذخیره نمی‌شود؛ برای persist، ادمین باید
    env var را در Railway تنظیم کند."""
    if feature not in _FEATURES:
        return False
    # این فقط در runtime فعال می‌کند؛ در restart از بین می‌رود
    os.environ[f"EMIX_ENABLE_{feature.upper()}"] = "1" if enabled else "0"
    return True
