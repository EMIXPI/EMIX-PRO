# experimental.py — رجیستری مرکزی فیچرهای آزمایشی EMIX-PRO
# ▸ اصل auto-enable: بعد از هر redeploy در Railway، کل بخش آزمایشی و همه‌ی
#   فیچرها به طور پیش‌فرض فعال هستند. ادمین می‌تواند با `EMIX_EXPERIMENTAL=0`
#   یا `EMIX_ENABLE_<FEATURE>=0` به صراحت یک فیچر را غیرفعال کند.
# ▸ استثناها (که به setup نیاز دارند و نباید auto-enable شوند):
#     - ip_whitelist   → باید لیست IPها در `EMIX_ADMIN_IPS` تنظیم شود
#     - totp_2fa       → باید secret در `EMIX_TOTP_SECRET` تنظیم شود
#     - telegram_bot   → باید token در `EMIX_BOT_TOKEN` تنظیم شود
#   این سه فیچر همچنان opt-in باقی می‌مانند.
#
# رفتار env varها:
#   EMIX_EXPERIMENTAL=0            → کل بخش آزمایشی غیرفعال
#   EMIX_EXPERIMENTAL=1 (or unset) → کل بخش فعال
#   EMIX_ENABLE_<FEATURE>=0        → غیرفعال‌کردن یک فیچر خاص
#   EMIX_ENABLE_<FEATURE>=1        → فعال‌کردن صریح یک فیچر (حتی استثناها)

import os
import logging

logger = logging.getLogger("EMIX.exp")

# ─── رجیستری فیچرها ────────────────────────────────────────────────────────
# هر ورودی: (key, description, default, requires_experimental)
# default=True یعنی بعد از deploy خودکار فعال می‌شود.
# default=False یعنی به setup اضافی نیاز دارد و auto-enable نمی‌شود.
_FEATURES = {
    # ── Security (Phase 1) ──
    # NOTE: rate_limit, csrf_protection, csp_headers باید صریحاً فعال شوند.
    # این سه فیچر middleware فعال می‌کنند که اگر auto-enabled باشند،
    # می‌توانند به silently پنل را بشکنند (login empty body, POST blocked,
    # inline scripts blocked). ادمین باید صریحاً EMIX_ENABLE_*=1 را تنظیم کند.
    "pbkdf2_password":    ("هش رمز PBKDF2 با backward-compat sha256", True, True),
    "rate_limit":         ("محدودیت نرخ ورود و API (نیاز به middleware فعال)", False, True),
    "ip_whitelist":       ("whitelist IP برای endpoint‌های admin (نیاز به EMIX_ADMIN_IPS)", False, True),
    "csrf_protection":    ("محافظت CSRF (نیاز به middleware فعال — POST بدون توکن مسدود)", False, True),
    "csp_headers":        ("Content-Security-Policy headers (ممکن است inline scripts را بشکند)", False, True),
    "hsts":               ("Strict-Transport-Security", True, True),
    "totp_2fa":           ("احراز هویت دو مرحله‌ای TOTP (نیاز به EMIX_TOTP_SECRET)", False, True),

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
    "sub_encrypted":      ("subscription base64-encrypted (نیاز به EMIX_SUB_KEY)", False, True),
    "multi_host":         ("چند Host برای یک inbound (CDN fronting)", True, True),

    # ── Gaming Engine (Phase 4) ──
    "gaming_health":      ("Gaming Health Score + telemetry", True, True),
    "gaming_profiles":    ("۵ پروفایل FPS/MOBA/BR/MMO/General", True, True),
    "gaming_dashboard":   ("داشبورد زنده گیمینگ", True, True),
    "game_server_ping":   ("پینگ به سرورهای معروف بازی", True, True),

    # ── Network Engineering (Phase 5) ──
    "smart_route":        ("Smart Route Engine با scoring", True, True),
    "safe_failover":      ("Failover با hysteresis + cooldown", True, True),
    "traffic_accounting": ("شمارش واقعی bytes in/out", True, True),
    "retransmission":     ("مانیتور retransmission", True, True),
    "mtu_discovery":      ("MTU/PMTU discovery (Railway-aware)", True, True),
    "adaptive_transport": ("انتخاب خودکار بهترین پروتکل", True, True),
    "prometheus_metrics": ("endpoint /metrics", True, True),

    # ── Iran Optimization (Phase 6) ──
    "isp_detection":      ("تشخیص MCI/MtnIrancell/RighTel/Shatel", True, True),
    "per_isp_route":      ("مسیر اختصاصی به ازای هر ISP", True, True),
    "sni_rotation":       ("چرخش SNI لیست", True, True),

    # ── Stealth / Disguise (Phase 7) — بخش مجزا ──
    "stealth_section":    ("بخش مجزا برای استتار/جعل", True, True),
    "tls_fragmentation":  ("TLS hello fragmentation", True, True),
    "salamander_obfs":    ("Salamander obfuscation", True, True),
    "noise_padding":      ("Padding نویز تصادفی", True, True),
    "domain_fronting":    ("Domain fronting برای CDN", True, True),

    # ── Unified Configs (Phase 8) ──
    "unified_configs":    ("همه‌ی کانفیگ‌ها در بخش اصلی با type badge", True, True),
    "config_health_score":("badge امتیاز سلامت به هر کانفیگ", True, True),

    # ── Telegram Bot (Phase 9) ──
    "telegram_bot":       ("ربات تلگرام برای اعلان انقضا + login notify (نیاز به EMIX_BOT_TOKEN)", False, True),
}

# ─── API عمومی ────────────────────────────────────────────────────────────
def is_experimental_enabled() -> bool:
    """آیا کل بخش آزمایشی فعال است؟
    رفتار: پیش‌فرض فعال. فقط EMIX_EXPERIMENTAL=0 به صراحت آن را غیرفعال می‌کند.
    این یعنی بعد از هر redeploy در Railway، بخش آزمایشی خودکار live است.
    """
    return os.environ.get("EMIX_EXPERIMENTAL", "1") == "1"


def is_enabled(feature: str) -> bool:
    """آیا یک فیچر خاص فعال است؟
    منطق:
      1) اگر env var صریح EMIX_ENABLE_<FEATURE> تنظیم شده باشد، از آن استفاده کن.
         مقدار "1" → فعال، هر چیز دیگر → غیرفعال.
      2) در غیر این صورت، از default تعریف‌شده در _FEATURES استفاده کن.
      3) اگر فیچر requires_experimental=True باشد و کل بخش غیرفعال باشد، False برگردان.
    """
    if feature not in _FEATURES:
        logger.warning(f"Unknown experimental feature: {feature}")
        return False
    desc, default, requires_exp = _FEATURES[feature]

    # اگر فیچر نیاز به فعال‌سازی کل بخش دارد و بخش غیرفعال است
    if requires_exp and not is_experimental_enabled():
        return False

    # env var خاص فیچر — صریحاً override می‌کند
    env_val = os.environ.get(f"EMIX_ENABLE_{feature.upper()}", None)
    if env_val is not None:
        return env_val == "1"

    # در غیر این صورت، default (که برای اکثر فیچرها True است — auto-enable)
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
