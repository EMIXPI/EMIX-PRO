# zeus_features.py
# ══════════════════════════════════════════════════════════════════════════════
# ماژول تنظیمات حرفه‌ای ZEUS — ISP + TLS Mask + Smart Mode + Security
#
# 🎯 هدف:
#   پیاده‌سازی ویژگی‌های پنل ZEUS رقیب (طبق عکس ارسالی کاربر) به‌صورت
#   یک ماژول کاملاً جدا از هسته‌ی EMIX. هیچ‌کدام از اندپوینت‌های اصلی
#   تغییر نمی‌کنند؛ این ماژول صرفاً state جدید + اندپوینت‌های جدید اضافه
#   می‌کند.
#
# ✅ بخش‌ها:
#   ۱) انتخاب ISP (همراه اول/ایرانسل/رایتل/مخابرات/شاد موبایل/هوشمند)
#      → توصیه‌گر پروتکل متناسب با هر ISP، بدون تغییر لینک‌ها
#   ۲) تنظیمات TLS Mask پیشرفته
#      → SNI سفارشی + Cipher Suites + JSON Fragment (تنظیمات Xray سمت کلاینت)
#      → تولید لینک با SNI override + خروجی JSON Fragment برای کلاینت
#   ۳) حالت هوشمند (Smart Mode)
#      → وقتی روشن باشد، به‌جای مرتب‌سازی ثابت، بهترین لینک لحظه‌ای پیشنهاد می‌شود
#   ۴) قفل‌سازی لاگین (Security Rate-Limit)
#      → میان‌افزار FastAPI که روی /api/login فقط اعمال می‌شود
#      → تعداد تلاش در فاصله‌ی زمانی محدود؛ تجاوز = بلاک موقت
#
# 🔒 فلسفه جداسازی (مثل bridge_boost.py و clean_ip_boost.py):
#   - state در zeus_config.json
#   - صفر تغییر در main.py (فقط یک خط register_routes اضافه می‌شود)
#   - اگر این فایل حذف شود، پنل و همه‌ی تونل‌ها بدون تغییر کار می‌کنند
#   - rate-limit فقط با فعال‌سازی صریح ادمین روشن می‌شود (پیش‌فرض: خاموش)
#
# ⚙️ اندپوینت‌ها:
#   GET  /api/zeus/config                 → تنظیمات کامل
#   POST /api/zeus/config                 → ذخیره‌ی تنظیمات کامل
#   GET  /api/zeus/isp                    → ISP فعلی + توصیه‌ها
#   POST /api/zeus/isp                    → تنظیم ISP
#   GET  /api/zeus/tls-mask               → تنظیمات TLS Mask
#   POST /api/zeus/tls-mask               → ذخیره‌ی TLS Mask
#   POST /api/zeus/tls-mask/links         → تولید لینک‌های Mask-شده برای همه‌ی کانفیگ‌ها
#   GET  /api/zeus/tls-mask/fragment-json  → JSON Fragment Xray برای کپی در کلاینت
#   GET  /api/zeus/smart                  → وضعیت حالت هوشمند
#   POST /api/zeus/smart                  → روشن/خاموش کردن Smart Mode
#   GET  /api/zeus/smart/recommend        → بهترین لینک لحظه‌ای (Smart)
#   GET  /api/zeus/security               → تنظیمات امنیت لاگین
#   POST /api/zeus/security               → ذخیره‌ی تنظیمات امنیت
#   POST /api/zeus/security/check         → بررسی دستی وضعیت لاگین (برای تست)
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import json
import re
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from main import (
    LINKS,
    LINKS_LOCK,
    DATA_DIR,
    get_host,
    require_auth,
    generate_share_link,
    is_link_allowed,
    logger,
)

ZEUS_FILE = DATA_DIR / "zeus_config.json"

# ──────────────────────────────────────────────────────────────────────────────
# لیست ISPهای ایرانی + توصیه‌ی پروتکل هر کدام
# منبع: تجربه‌ی عملی اپراتورهای ایرانی + تست‌های میدانی
# ──────────────────────────────────────────────────────────────────────────────
ISP_REGISTRY = {
    "mci": {
        "label": "همراه اول (MCI)",
        "icon": "ti-device-mobile",
        "color": "var(--accent2)",
        "expected_ping_ms": "50-100",
        "best_protocol": "vless-ws",
        "rationale": "MCI معمولاً WS+TLS روی CDN اروان را به‌خوبی پاس می‌دهد؛ HTTP/2 (alpn=h2) روی موبایل کار می‌کند",
        "tips": [
            "CDN اروان را فعال کنید تا ترافیک داخلی محاسبه شود",
            "اگر پینگ بالاست، آی‌پی تمیز را برای MCI امتحان کنید",
            "xhttp در MCI معمولاً کم‌فایده است، چون DPI آن ضعیف‌تر از MTN است",
        ],
    },
    "mtn": {
        "label": "ایرانسل (MTN)",
        "icon": "ti-antenna",
        "color": "var(--amber-t)",
        "expected_ping_ms": "100-200",
        "best_protocol": "trojan-xhttp-packet-up",
        "rationale": "MTN DPI قوی‌تری دارد؛ xhttp با packet-up و size=10 از سانسور عبور می‌کند",
        "tips": [
            "xhttp-packet-up برای دور زدن DPI ایرانسل بهتر است",
            "اگر xhttp کار نکرد، vless-ws با CDN امتحان کنید",
            "در ساعت اوج، xhttp-stream-up می‌تواند سرعت بهتری بدهد",
        ],
    },
    "rightel": {
        "label": "رایتل (Rightel)",
        "icon": "ti-broadcast",
        "color": "var(--accent2)",
        "expected_ping_ms": "50-200",
        "best_protocol": "trojan-ws",
        "rationale": "پوشش رایتل متغیر است؛ trojan با TLS ساده معمولاً پایدارتر از vless است",
        "tips": [
            "اگر پینگ متناوب است، چند بار تست پینگ بگیرید",
            "آی‌پی‌های تمیز متفاوتی برای رایتل می‌تواند بهتر باشد",
        ],
    },
    "mokhaberat": {
        "label": "مخابرات (ثابت)",
        "icon": "ti-phone",
        "color": "var(--accent2)",
        "expected_ping_ms": "20-70",
        "best_protocol": "vless-ws",
        "rationale": "خط ثابت معمولاً پینگ پایین و پایدار دارد؛ vless-ws سبک‌ترین گزینه است",
        "tips": [
            "در خط ثابت، نیازی به xhttp نیست — vless-ws سریع‌تر است",
            "CDN اروان روی مخابرات معمولاً خوب کار می‌کند",
        ],
    },
    "shad": {
        "label": "شاد موبایل",
        "icon": "ti-school",
        "color": "var(--green-t)",
        "expected_ping_ms": "10-30",
        "best_protocol": "shadowsocks",
        "rationale": "شاد موبایل شبکه‌ی محدود و فیلتر نشده‌ی آموزشی است؛ shadowsocks ساده‌ترین و سریع‌ترین انتخاب است",
        "tips": [
            "روی شبکه‌ی شاد، shadowsocks بدون TLS مستقیم کار می‌کند",
            "نیازی به CDN یا پل ندارید",
        ],
    },
    "smart": {
        "label": "حالت هوشمند",
        "icon": "ti-brain",
        "color": "var(--accent2)",
        "expected_ping_ms": "best-of-all",
        "best_protocol": "auto",
        "rationale": "تست همه‌ی پروتکل‌ها و انتخاب کمینه‌ی ws+e2e (مانند /api/links/best)",
        "tips": [
            "وقتی ISP مطمئن نیستید، حالت هوشمند را انتخاب کنید",
            "هر بار تست پینگ همه‌ی کانفیگ‌ها را می‌سنجد و بهترین را پیشنهاد می‌دهد",
        ],
    },
}

# ترتیب ارجح اسکن آی‌پی تمیز بر اساس ISP (الگوریتم ساده — فقط تقدم زمانی)
ISP_CLEAN_IP_PRIORITY = {
    "mci": "104.21.x",       # معیار تجربی — Cloudflare جلوی اروان
    "mtn": "172.67.x",
    "rightel": "104.18.x",
    "mokhaberat": "104.25.x",
    "shad": "any",
    "smart": "any",
}


# ──────────────────────────────────────────────────────────────────────────────
# ۱) ISP انتخاب
# ──────────────────────────────────────────────────────────────────────────────

def _default_cfg() -> dict:
    return {
        "isp": "smart",                 # mci/mtn/rightel/mokhaberat/shad/smart
        "tls_mask": {
            "enabled": False,
            "custom_sni": "www.speedtest.net",
            "cipher_suites": (
                "TLS_AES_256_GCM_SHA384:"
                "TLS_CHACHA20_POLY1305_SHA256:"
                "TLS_AES_128_GCM_SHA256"
            ),
            "fragment_length": "5-94",   # الگوی طول پکت fragment
            "fragment_delay": "0",        # تاخیر بین فرگمنت‌ها (ms)
            "fragment_packets": "tlshello",
            "fragment_maxsplit": 1,
        },
        "smart_mode": {
            "enabled": False,
            "interval_ms": 1000,         # فاصله‌ی بررسی مجدد
            "accuracy": 4,               # چند بار تست میانگین
        },
        "security": {
            "enabled": False,
            "min_password_length": 8,
            "attempt_interval_ms": 1000,
            "max_attempts": 5,
            "lockout_ms": 60000,          # مدت بلاک پس از تجاوز
        },
    }


def _load_cfg() -> dict:
    """تنظیمات را از ZEUS_FILE می‌خواند؛ اگر نباشد، پیش‌فرض برمی‌گرداند."""
    try:
        if ZEUS_FILE.exists():
            data = json.loads(ZEUS_FILE.read_text(encoding="utf-8"))
            # merge با پیش‌فرض برای مهاجرت امن (فیلدهای جدید به‌صورت خودکار اضافه می‌شوند)
            base = _default_cfg()
            for k, v in base.items():
                if k not in data:
                    data[k] = v
                elif isinstance(v, dict) and isinstance(data[k], dict):
                    for sk, sv in v.items():
                        if sk not in data[k]:
                            data[k][sk] = sv
            return data
    except Exception as exc:
        logger.warning(f"[zeus] خطا در خواندن تنظیمات: {exc}")
    return _default_cfg()


def _save_cfg(cfg: dict) -> None:
    try:
        ZEUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        ZEUS_FILE.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        logger.error(f"[zeus] خطا در ذخیره‌ی تنظیمات: {exc}")
        raise


# ──────────────────────────────────────────────────────────────────────────────
# ۲) TLS Mask — تولید لینک با SNI override
# ──────────────────────────────────────────────────────────────────────────────

def _apply_sni_override(link_url: str, custom_sni: str) -> str:
    """در یک لینک vless:// یا trojan://، پارامتر sni و host را با مقدار سفارشی
    جایگزین می‌کند. اگر پارامتری نباشد، اضافه نمی‌شود (ساختار اصلی حفظ می‌شود)."""
    if not link_url or not custom_sni:
        return link_url
    # الگوی: scheme://uuid@host:port?query#remark
    m = re.match(r"^([a-z0-9+]+://[^?#]+)\?([^#]*)#(.*)$", link_url)
    if not m:
        # بدون query string
        return link_url
    prefix, query, remark = m.group(1), m.group(2), m.group(3)
    # پارامترها را به dict تبدیل (ترتیب حفظ می‌شود)
    pairs = []
    seen = set()
    for kv in query.split("&"):
        if not kv:
            continue
        k, _, v = kv.partition("=")
        if k in ("sni", "host"):
            pairs.append(f"{k}={quote(custom_sni)}")
        else:
            pairs.append(kv)
        seen.add(k)
    # اگر sni یا host در لینک نبودند، اضافه‌شان می‌کنیم
    if "sni" not in seen:
        pairs.append(f"sni={quote(custom_sni)}")
    if "host" not in seen:
        pairs.append(f"host={quote(custom_sni)}")
    return f"{prefix}?{'&'.join(pairs)}#{remark}"


def _build_xray_fragment_json(cfg: dict) -> dict:
    """JSON Fragment برای تنظیمات Xray کلاینت می‌سازد.
    این در فایل config.json کلاینت Xray در بخش 'streamSettings' قرار می‌گیرد."""
    tm = cfg.get("tls_mask", {})
    return {
        "tcp": [
            {
                "type": "fragment",
                "settings": {
                    "packets": tm.get("fragment_packets", "tlshello"),
                    "lengths": [tm.get("fragment_length", "5-94")],
                    "delays": [str(tm.get("fragment_delay", "0"))],
                    "maxSplit": int(tm.get("fragment_maxsplit", 1)),
                },
            }
        ]
    }


def _build_xray_tls_settings_json(cfg: dict) -> dict:
    """بخش TLS Xray با cipher suites و SNI سفارشی (در streamSettings.tlsSettings)."""
    tm = cfg.get("tls_mask", {})
    return {
        "serverName": tm.get("custom_sni", ""),
        "cipherSuites": tm.get("cipher_suites", ""),
        "minVersion": "1.3",
        "maxVersion": "1.3",
    }


# ──────────────────────────────────────────────────────────────────────────────
# ۳) Security Rate-Limit — میان‌افزار روی /api/login
# ──────────────────────────────────────────────────────────────────────────────

# در حافظه نگه می‌دارد: IP → لیست timestamp تلاش‌های ناموفق
_login_attempts: dict[str, deque] = defaultdict(deque)
# IP‌های بلاک‌شده + زمان پایان بلاک
_login_blocked: dict[str, float] = {}
_LOCK = asyncio.Lock()


async def _check_login_allowed(ip: str, cfg: dict) -> tuple[bool, str]:
    """بررسی می‌کند آیا IP فعلاً مجاز به تلاش لاگین است.
    خروجی: (allowed, reason)"""
    sec = cfg.get("security", {})
    if not sec.get("enabled"):
        return True, "security-disabled"

    now = time.time()
    lockout_ms = int(sec.get("lockout_ms", 60000))
    max_attempts = int(sec.get("max_attempts", 5))
    interval_ms = int(sec.get("attempt_interval_ms", 1000))
    interval_s = max(interval_ms / 1000.0, 0.001)

    async with _LOCK:
        # چک بلاک
        if ip in _login_blocked:
            until = _login_blocked[ip]
            if now < until:
                remain = int((until - now))
                return False, f"locked-{remain}s"
            else:
                _login_blocked.pop(ip, None)

        # پاکسازی تلاش‌های قدیمی
        dq = _login_attempts[ip]
        while dq and (now - dq[0]) > interval_s * max_attempts:
            dq.popleft()

        if len(dq) >= max_attempts:
            _login_blocked[ip] = now + (lockout_ms / 1000.0)
            return False, f"max-attempts-exceeded-lockout-{lockout_ms}ms"

        return True, "ok"


async def _record_login_failure(ip: str) -> None:
    """بعد از یک تلاش ناموفق لاگین صدا زده می‌شود."""
    dq = _login_attempts[ip]
    dq.append(time.time())


async def _record_login_success(ip: str) -> None:
    """بعد از لاگین موفق، تاریخچه‌ی IP را پاک می‌کند."""
    async with _LOCK:
        _login_attempts.pop(ip, None)
        _login_blocked.pop(ip, None)


class ZeusSecurityMiddleware:
    """میان‌افزار ASGI که فقط روی POST /api/login اعمال می‌شود.
    اگر security.enabled=False باشد، مستقیم عبور می‌کند (صفر سربار)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        method = scope.get("method", "")
        if method != "POST" or path != "/api/login":
            return await self.app(scope, receive, send)

        # تنظیمات فعلی را بخوانیم
        cfg = _load_cfg()
        sec = cfg.get("security", {})
        if not sec.get("enabled"):
            return await self.app(scope, receive, send)

        # IP کلاینت را از scope استخراج کن
        ip = "unknown"
        for h in scope.get("headers", []):
            if h[0] == b"x-forwarded-for":
                ip = h[1].decode().split(",")[0].strip()
                break
            if h[0] == b"x-real-ip":
                ip = h[1].decode().strip()
        if ip == "unknown" and scope.get("client"):
            ip = scope["client"][0]

        allowed, reason = await _check_login_allowed(ip, cfg)
        if not allowed:
            # پاسخ 429 با ذکر دلیل
            body = json.dumps(
                {"detail": f"تلاش‌های بیش از حد. {reason}", "retry_after_ms": int(sec.get("lockout_ms", 60000))},
                ensure_ascii=False,
            ).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(body)).encode()),
                    (b"cache-control", b"no-store"),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        # ردپای موقت برای تعقیب نتیجه: یک wrapper روی send می‌سازیم تا status را ببینیم
        status_code = {"v": None}

        async def wrapped_receive():
            return await receive()

        async def wrapped_send(msg):
            if msg.get("type") == "http.response.start":
                status_code["v"] = msg.get("status", 200)
            await send(msg)

        await self.app(scope, wrapped_receive, wrapped_send)

        # بعد از پاسخ، تلاش را ثبت کن
        if status_code["v"] == 401:
            await _record_login_failure(ip)
        elif status_code["v"] == 200:
            await _record_login_success(ip)


# ──────────────────────────────────────────────────────────────────────────────
# ۴) Smart Mode — توصیه‌گر لحظه‌ای
# ──────────────────────────────────────────────────────────────────────────────

async def _smart_recommend() -> dict:
    """بهترین لینک لحظه‌ای را با تست همه‌ی کانفیگ‌ها می‌یابد.
    منطق: شبیه /api/links/best اما با مرتب‌سازی بر اساس total_ms."""
    import link_health
    async with LINKS_LOCK:
        targets = [(uid, dict(d)) for uid, d in LINKS.items() if is_link_allowed(d)]
    if not targets:
        return {"best": None, "checked": 0, "checked_at": datetime.now().isoformat()}

    sem = asyncio.Semaphore(4)

    async def _one(uid: str, link: dict):
        async with sem:
            try:
                r = await link_health._run_link_ping(uid, link)
                return {
                    "uuid": uid,
                    "label": link.get("label", uid[:8]),
                    "protocol": link.get("protocol", "vless-ws"),
                    "result": r,
                }
            except Exception as exc:
                return {
                    "uuid": uid,
                    "label": link.get("label", uid[:8]),
                    "protocol": link.get("protocol", "vless-ws"),
                    "result": {"ok": False, "detail": f"{type(exc).__name__}: {exc}"},
                }

    results = await asyncio.gather(*[_one(u, d) for u, d in targets])
    ranked = sorted(
        (r for r in results if r["result"].get("ok")),
        key=lambda r: (r["result"].get("ws_ms") or 0) + (r["result"].get("e2e_ms") or 0),
    )
    best = ranked[0] if ranked else None
    if best:
        best["total_ms"] = round((best["result"].get("ws_ms") or 0) + (best["result"].get("e2e_ms") or 0), 1)
    return {
        "best": best,
        "checked": len(results),
        "healthy": len(ranked),
        "checked_at": datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# ثبت اندپوینت‌ها روی app
# ──────────────────────────────────────────────────────────────────────────────

def register_routes(app) -> None:
    """همه‌ی اندپوینت‌های zeus را روی app ثبت می‌کند."""

    # ─── ۱) تنظیمات کامل ───────────────────────────────────────────────────
    @app.get("/api/zeus/config")
    async def zeus_get_config(_=Depends(require_auth)):
        cfg = _load_cfg()
        return {
            "isp": cfg.get("isp", "smart"),
            "isp_meta": ISP_REGISTRY.get(cfg.get("isp", "smart"), {}),
            "tls_mask": cfg.get("tls_mask", {}),
            "smart_mode": cfg.get("smart_mode", {}),
            "security": cfg.get("security", {}),
            "available_isps": [
                {"id": k, **v} for k, v in ISP_REGISTRY.items()
            ],
        }

    @app.post("/api/zeus/config")
    async def zeus_save_config(request: Request, _=Depends(require_auth)):
        body = await request.json()
        cfg = _load_cfg()
        if "isp" in body and body["isp"] in ISP_REGISTRY:
            cfg["isp"] = body["isp"]
        if "tls_mask" in body and isinstance(body["tls_mask"], dict):
            for k, v in body["tls_mask"].items():
                cfg["tls_mask"][k] = v
        if "smart_mode" in body and isinstance(body["smart_mode"], dict):
            for k, v in body["smart_mode"].items():
                cfg["smart_mode"][k] = v
        if "security" in body and isinstance(body["security"], dict):
            for k, v in body["security"].items():
                cfg["security"][k] = v
        _save_cfg(cfg)
        return {"ok": True, "config": cfg}

    # ─── ۲) ISP ────────────────────────────────────────────────────────────
    @app.get("/api/zeus/isp")
    async def zeus_get_isp(_=Depends(require_auth)):
        cfg = _load_cfg()
        isp_id = cfg.get("isp", "smart")
        return {
            "current": isp_id,
            "meta": ISP_REGISTRY.get(isp_id, {}),
            "available": [{"id": k, **v} for k, v in ISP_REGISTRY.items()],
        }

    @app.post("/api/zeus/isp")
    async def zeus_set_isp(request: Request, _=Depends(require_auth)):
        body = await request.json()
        new_isp = body.get("isp")
        if new_isp not in ISP_REGISTRY:
            raise HTTPException(status_code=400, detail=f"ISP نامعتبر: {new_isp}")
        cfg = _load_cfg()
        cfg["isp"] = new_isp
        _save_cfg(cfg)
        return {
            "ok": True,
            "current": new_isp,
            "meta": ISP_REGISTRY[new_isp],
        }

    # ─── ۳) TLS Mask ───────────────────────────────────────────────────────
    @app.get("/api/zeus/tls-mask")
    async def zeus_get_tls_mask(_=Depends(require_auth)):
        cfg = _load_cfg()
        return cfg.get("tls_mask", _default_cfg()["tls_mask"])

    @app.post("/api/zeus/tls-mask")
    async def zeus_save_tls_mask(request: Request, _=Depends(require_auth)):
        body = await request.json()
        cfg = _load_cfg()
        for k, v in body.items():
            cfg["tls_mask"][k] = v
        _save_cfg(cfg)
        return {"ok": True, "tls_mask": cfg["tls_mask"]}

    @app.get("/api/zeus/tls-mask/links")
    async def zeus_tls_masked_links(_=Depends(require_auth)):
        """برای هر کانفیگ فعال، لینک با SNI override بساز (فقط اگر tls_mask.enabled)."""
        cfg = _load_cfg()
        tm = cfg.get("tls_mask", {})
        if not tm.get("enabled"):
            return {"enabled": False, "links": []}
        sni = tm.get("custom_sni", "")
        host = get_host()
        async with LINKS_LOCK:
            snap = [(uid, dict(d)) for uid, d in LINKS.items()]
        out = []
        for uid, d in snap:
            proto = d.get("protocol", "vless-ws")
            if proto == "mtproto" or not is_link_allowed(d):
                continue
            original = generate_share_link(uid, host, remark=f"EMIX-{d.get('label', uid[:8])}", protocol=proto)
            masked = _apply_sni_override(original, sni)
            out.append({
                "uuid": uid,
                "label": d.get("label", uid[:8]),
                "protocol": proto,
                "original": original,
                "masked": masked,
            })
        return {"enabled": True, "sni": sni, "links": out}

    @app.get("/api/zeus/tls-mask/fragment-json")
    async def zeus_fragment_json(_=Depends(require_auth)):
        """JSON Fragment Xray برای کپی در کلاینت — به‌صورت PlainText."""
        cfg = _load_cfg()
        frag = _build_xray_fragment_json(cfg)
        tls = _build_xray_tls_settings_json(cfg)
        out = {
            "fragment": frag,
            "tlsSettings": tls,
            "_comment": "این JSON را در streamSettings مربوط به outbound پروکسی در Xray کلاینت کپی کنید",
        }
        return JSONResponse(out, headers={"Content-Type": "application/json; charset=utf-8"})

    # ─── ۴) Smart Mode ────────────────────────────────────────────────────
    @app.get("/api/zeus/smart")
    async def zeus_get_smart(_=Depends(require_auth)):
        cfg = _load_cfg()
        return cfg.get("smart_mode", _default_cfg()["smart_mode"])

    @app.post("/api/zeus/smart")
    async def zeus_save_smart(request: Request, _=Depends(require_auth)):
        body = await request.json()
        cfg = _load_cfg()
        for k, v in body.items():
            cfg["smart_mode"][k] = v
        _save_cfg(cfg)
        return {"ok": True, "smart_mode": cfg["smart_mode"]}

    @app.get("/api/zeus/smart/recommend")
    async def zeus_smart_recommend(_=Depends(require_auth)):
        """بهترین لینک لحظه‌ای — Smart Mode."""
        rec = await _smart_recommend()
        return rec

    # ─── ۵) Security ───────────────────────────────────────────────────────
    @app.get("/api/zeus/security")
    async def zeus_get_security(_=Depends(require_auth)):
        cfg = _load_cfg()
        sec = cfg.get("security", _default_cfg()["security"])
        # اطلاعات وضعیت زنده‌ی بلاک‌ها را هم اضافه می‌کنیم
        now = time.time()
        blocked = [
            {"ip": ip, "remaining_ms": int((until - now) * 1000)}
            for ip, until in _login_blocked.items()
            if now < until
        ]
        return {**sec, "currently_blocked": blocked}

    @app.post("/api/zeus/security")
    async def zeus_save_security(request: Request, _=Depends(require_auth)):
        body = await request.json()
        cfg = _load_cfg()
        for k, v in body.items():
            cfg["security"][k] = v
        _save_cfg(cfg)
        # اگر security خاموش شد، بافرها را پاک کن
        if not cfg["security"].get("enabled"):
            _login_attempts.clear()
            _login_blocked.clear()
        return {"ok": True, "security": cfg["security"]}

    @app.post("/api/zeus/security/check")
    async def zeus_security_check(_=Depends(require_auth)):
        """تست دستی — برای ادمین تا تأیید کند میان‌افزار فعال است."""
        cfg = _load_cfg()
        sec = cfg.get("security", {})
        return {
            "middleware_active": sec.get("enabled", False),
            "rules": {
                "min_password_length": sec.get("min_password_length", 8),
                "attempt_interval_ms": sec.get("attempt_interval_ms", 1000),
                "max_attempts": sec.get("max_attempts", 5),
                "lockout_ms": sec.get("lockout_ms", 60000),
            },
            "currently_blocked_count": sum(
                1 for _, until in _login_blocked.items() if time.time() < until
            ),
        }

    # ─── ۶) میان‌افزار Security ───────────────────────────────────────────
    # در انتهای register اضافه می‌شود تا روی همه‌ی /api/login‌ها (حتی آینده) اعمال شود
    app.add_middleware(ZeusSecurityMiddleware)
    logger.info("[zeus] Zeus features registered (isp/tls-mask/smart/security)")
