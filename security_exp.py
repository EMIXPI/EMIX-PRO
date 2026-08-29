# security_exp.py — enhancer های امنیتی toggle-based
# فعال‌سازی: experimental.is_enabled("rate_limit"), is_enabled("csrf_protection") و ...

import os
import time
import hmac
import secrets
import hashlib
import ipaddress
from typing import Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from experimental import is_enabled

logger = None


def _get_logger():
    global logger
    if logger is None:
        import logging
        logger = logging.getLogger("EMIX.sec")
    return logger


# ─── Rate Limiting ────────────────────────────────────────────────────────
# ساده: در-memory counter به ازای IP+endpoint.
# محدودیت‌ها:
#   /api/login:     5 تلاش در ۱۵ دقیقه
#   /api/*:         60 درخواست در دقیقه
#   other:          unlimited

_LOGIN_ATTEMPTS = {}  # ip → [(timestamp, ...)]
_API_HITS = {}  # (ip, minute) → count
_RATE_WINDOW_LOGIN = 900  # 15 دقیقه
_RATE_LIMIT_LOGIN = 5
_RATE_WINDOW_API = 60  # 1 دقیقه
_RATE_LIMIT_API = 60


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit_login(ip: str) -> bool:
    """بازگرداندن True اگر درخواست مجاز است."""
    now = time.time()
    attempts = _LOGIN_ATTEMPTS.get(ip, [])
    # پاک‌سازی قدیمی‌ها
    attempts = [t for t in attempts if now - t < _RATE_WINDOW_LOGIN]
    if len(attempts) >= _RATE_LIMIT_LOGIN:
        _LOGIN_ATTEMPTS[ip] = attempts
        return False
    attempts.append(now)
    _LOGIN_ATTEMPTS[ip] = attempts
    return True


def _check_rate_limit_api(ip: str) -> bool:
    """بازگرداندن True اگر درخواست مجاز است."""
    now = int(time.time())
    minute = now // 60
    key = (ip, minute)
    count = _API_HITS.get(key, 0)
    if count >= _RATE_LIMIT_API:
        _API_HITS[key] = count
        return False
    _API_HITS[key] = count + 1
    # پاک‌سازی قدیمی‌ها (هر ۵ دقیقه)
    if now % 300 == 0:
        cleanup = minute - 5
        for k in list(_API_HITS.keys()):
            if k[1] < cleanup:
                del _API_HITS[k]
    return True


# ─── IP Whitelist ─────────────────────────────────────────────────────────
def _is_ip_allowed(ip: str) -> bool:
    """اگر EMIX_ADMIN_IPS تنظیم شده، فقط آن‌ها اجازه دسترسی به admin دارند."""
    whitelist = os.environ.get("EMIX_ADMIN_IPS", "").strip()
    if not whitelist:
        return True  # محدودیت نیست
    allowed = [s.strip() for s in whitelist.split(",") if s.strip()]
    for entry in allowed:
        try:
            # پشتیبانی از CIDR
            if "/" in entry:
                net = ipaddress.ip_network(entry, strict=False)
                if ipaddress.ip_address(ip) in net:
                    return True
            elif entry == ip:
                return True
        except Exception:
            continue
    return False


# ─── CSRF ──────────────────────────────────────────────────────────────────
# مکانیزم: double-submit cookie
# 1. سرور توکن CSRF را در cookie ست می‌کند (پس از login)
# 2. کلاینت باید همان توکن را در هدر X-CSRF-Token بفرستد
# 3. سرور مقایسه می‌کند

CSRF_COOKIE = "emix_csrf"
CSRF_HEADER = "X-CSRF-Token"

_STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# exception‌ها: login (که هنوز توکن ندارد) و subscription endpoints (که token در URL می‌آید)
_CSRF_EXEMPT_PATHS = {
    "/api/login",
    "/api/logout",
    "/sub",
    "/sub/",
}


def _get_csrf_token(request: Request) -> Optional[str]:
    return request.cookies.get(CSRF_COOKIE)


def _verify_csrf(request: Request) -> bool:
    """بررسی توکن CSRF برای state-changing requests."""
    if not is_enabled("csrf_protection"):
        return True
    path = request.url.path
    # exempt paths
    for ex in _CSRF_EXEMPT_PATHS:
        if path.startswith(ex):
            return True
    # GET/HEAD/OPTIONS نیازی ندارند
    if request.method not in _STATE_CHANGING_METHODS:
        return True
    cookie_token = _get_csrf_token(request)
    header_token = request.headers.get(CSRF_HEADER)
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)


def gen_csrf_token() -> str:
    return secrets.token_urlsafe(32)


# ─── Security Headers Middleware ─────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """اضافه‌کردن CSP/HSTS/X-Frame-Options/etc."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        try:
            # فقط برای responses 200/300 (نه 500)
            if response.status_code < 500:
                if is_enabled("csp_headers"):
                    response.headers["Content-Security-Policy"] = (
                        "default-src 'self'; "
                        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                        "style-src 'self' 'unsafe-inline'; "
                        "img-src 'self' data: https:; "
                        "font-src 'self' data:; "
                        "connect-src 'self' https: wss:; "
                        "frame-ancestors 'none';"
                    )
                if is_enabled("hsts"):
                    response.headers["Strict-Transport-Security"] = (
                        "max-age=63072000; includeSubDomains; preload"
                    )
                response.headers["X-Frame-Options"] = "DENY"
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["Referrer-Policy"] = "no-referrer"
                response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        except Exception:
            pass
        return response


# ─── Rate Limit + CSRF + IP Whitelist Middleware ────────────────────────
class RateLimitMiddleware(BaseHTTPMiddleware):
    """اعمال rate limit + CSRF + IP whitelist."""

    async def dispatch(self, request, call_next):
        ip = _client_ip(request)

        # IP whitelist (فقط برای admin endpoints)
        if request.url.path.startswith("/api/admin") and not _is_ip_allowed(ip):
            return JSONResponse(
                {"detail": "IP not allowed"},
                status_code=403,
            )

        # rate limit login
        if request.url.path == "/api/login" and is_enabled("rate_limit"):
            if not _check_rate_limit_login(ip):
                return JSONResponse(
                    {"detail": "تعداد تلاش‌های ورود بیش از حد. ۱۵ دقیقه صبر کنید."},
                    status_code=429,
                    headers={"Retry-After": "900"},
                )

        # rate limit API (به‌جز subscription/static)
        elif (
            request.url.path.startswith("/api/")
            and not request.url.path.startswith("/sub")
            and is_enabled("rate_limit")
        ):
            if not _check_rate_limit_api(ip):
                return JSONResponse(
                    {"detail": "rate limit exceeded"},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )

        # CSRF verification
        if not _verify_csrf(request):
            return JSONResponse(
                {"detail": "CSRF token missing or invalid"},
                status_code=403,
            )

        response = await call_next(request)

        # ست‌کردن CSRF cookie روی login موفق
        # CRITICAL: اگر هر مرحله fail شود، باید response اصلی برگردد، نه empty.
        # در غیر این صورت، login به‌صورت empty body برمی‌گردد و کل پنل از کار می‌افتد.
        if request.url.path == "/api/login" and response.status_code == 200 and is_enabled("csrf_protection"):
            try:
                # خواندن body اصلی (به‌صورت bytes) — باید قبل از هر چیزی
                body = b""
                async for chunk in response.body_iterator:
                    if chunk:
                        body += chunk
                if not body:
                    # body خالی — هیچ کاری نکن (response اصلی دیگر قابل استفاده نیست
                    # چون body_iterator مصرف شده، یک JSONResponse خالی بساز)
                    return JSONResponse({"ok": True}, status_code=200)
                # parse body برای ساخت response جدید
                parsed = __import__("json").loads(body)
                new_response = JSONResponse(content=parsed, status_code=200)
                # ست‌کردن CSRF cookie روی response جدید
                token = gen_csrf_token()
                new_response.set_cookie(
                    CSRF_COOKIE,
                    token,
                    httponly=False,  # JavaScript باید بخواند
                    samesite="lax",
                    secure=True,
                    max_age=7 * 24 * 3600,
                )
                return new_response
            except Exception as e:
                _get_logger().warning(f"[security] CSRF cookie injection failed (returning fallback): {e}")
                # fallback: یک response ساده با body اصلی برگردان
                # (body_iterator مصرف شده، پس فقط status_code + headers را حفظ کن)
                try:
                    return JSONResponse({"ok": True}, status_code=200)
                except Exception:
                    return response

        return response


# ─── PBKDF2 Password (with sha256 backward-compat) ─────────────────────
# این از audit commit c892e3a الهام گرفته شده، ولی در یک module مجزا.
# فعال‌سازی: experimental.is_enabled("pbkdf2_password")

import hashlib
import os as _os
import secrets as _secrets

PBKDF2_ITERATIONS = 210_000


def hash_password_secure(pw: str) -> str:
    """هش PBKDF2 با salt تصادفی. خروجی: 'pbkdf2$<iters>$<salt_hex>$<hash_hex>'"""
    if not is_enabled("pbkdf2_password"):
        # legacy sha256 fallback
        from main import CONFIG
        return hashlib.sha256(f"{pw}{CONFIG['secret']}".encode()).hexdigest()
    if not pw:
        pw = ""
    salt = _secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password_secure(pw: str, stored: str) -> bool:
    """اعتبارسنجی با پشتیبانی از PBKDF2 و legacy sha256."""
    if not stored:
        return False
    # PBKDF2 format
    if stored.startswith("pbkdf2$"):
        try:
            _, iters_s, salt_hex, hash_hex = stored.split("$", 3)
            iters = int(iters_s)
            derived = hashlib.pbkdf2_hmac(
                "sha256",
                pw.encode("utf-8"),
                bytes.fromhex(salt_hex),
                iters,
            )
            return hmac.compare_digest(derived.hex(), hash_hex)
        except Exception:
            return False
    # legacy sha256(pw + secret)
    from main import CONFIG
    legacy = hashlib.sha256(f"{pw}{CONFIG['secret']}".encode()).hexdigest()
    return hmac.compare_digest(legacy, stored)


def needs_rehash(stored: str) -> bool:
    """آیا هش قدیمی است و باید به PBKDF2 ارتقا یابد؟"""
    return not stored.startswith("pbkdf2$")
