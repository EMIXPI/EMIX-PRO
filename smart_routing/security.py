# smart_routing/security.py — SSRF guard + امضای HMAC + replay + rate limit
# ══════════════════════════════════════════════════════════════════════════════
# امنیت طبق سند:
#   • SSRF: discovery/verify هرگز به localhost / RFC1918 / metadata / internal
#     دست نمی‌زند — پیش از هر اتصال، مقصد parse و resolve و بازبینی می‌شود.
#   • امضای درخواست (panel ↔ worker): HMAC-SHA256 روی (ts.nonce.method.path.body-hash)
#     + پنجره‌ی زمانی ±۹۰ ثانیه + nonce یک‌بارمصرف (replay protection).
#   • Rate limit: توکن‌باکت روی discovery/health/test — هر دو جهت.
#   • هیچ secretی hardcode نمی‌شود: env یا smart_settings (ثبت از UI).
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import hashlib
import hmac
import ipaddress
import os
import secrets
import socket
import time

# ── SSRF guard ────────────────────────────────────────────────────────────────
_BLOCKED_HOSTNAMES = {
    "localhost", "metadata.google.internal",
    "instance-data", "169.254.169.254",
}

# فقط برای تست/لوکال‌دو (pytest با سرور محلی) — در پروداکشن هرگز ست نمی‌شود.
# SSRF guard پروداکشن را هیچ‌کس نمی‌تواند خاموش کند بدون دسترسی به env ریلوی.
def _allow_local_endpoints() -> bool:
    return os.environ.get("SR_ALLOW_LOCAL_ENDPOINTS", "").strip().lower() in ("1", "true", "yes")


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    private_like = (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
        or ip.is_multicast or ip.is_unspecified
        or ip in ipaddress.ip_network("100.64.0.0/10")        # CGNAT
        or ip in ipaddress.ip_network("192.0.2.0/24")        # TEST-NET-1
        or ip in ipaddress.ip_network("198.51.100.0/24")     # TEST-NET-2
        or ip in ipaddress.ip_network("203.0.113.0/24")      # TEST-NET-3
        or ip in ipaddress.ip_network("192.176.0.0/16")      # block-doc
    )
    if private_like and _allow_local_endpoints():
        return False            # حالت تست/لوکال‌دو فقط — پروداکشن همیشه مسدود
    return private_like


def ssrf_check_host(address: str) -> tuple[bool, str]:
    """بررسی امن مقصد پیش از اتصال — (ok, reason).

    hostname باید به فقط IPهای عمومی resolve شود؛ IP literal باید عمومی باشد.
    """
    a = (address or "").strip().lower().rstrip(".")
    if not a:
        return False, "آدرس خالی است"
    if a in _BLOCKED_HOSTNAMES:
        return False, f"مقصد مسدودشده (SSRF): {a}"
    if a.endswith(".internal") or a.endswith(".local") or a.endswith(".railway.internal"):
        return False, f"دامنه‌ی داخلی ممنوع: {a}"
    try:
        ip = ipaddress.ip_address(a)
        if _is_blocked_ip(ip):
            return False, f"IP غیرعمومی ممنوع (SSRF): {a}"
        return True, "ip-public"
    except ValueError:
        pass  # hostname → resolve می‌کنیم
    try:
        infos = socket.getaddrinfo(a, None, proto=socket.IPPROTO_TCP)
    except Exception as e:
        return False, f"DNS resolve ناموفق: {str(e)[:80]}"
    if not infos:
        return False, "DNS خالی"
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except Exception:
            continue
        if _is_blocked_ip(ip):
            return False, f"resolve به IP غیرعمومی (SSRF): {ip}"
    return True, "dns-public"


def ssrf_safe_url(url: str) -> tuple[bool, str]:
    """بررسی URL کامل (فقط http/https، مقصد عمومی)."""
    from urllib.parse import urlparse
    try:
        u = urlparse((url or "").strip())
    except Exception:
        return False, "URL نامعتبر"
    if u.scheme not in ("http", "https"):
        return False, f"اسکیم مجاز نیست: {u.scheme}"
    if not u.hostname:
        return False, "hostname ندارد"
    ok, reason = ssrf_check_host(u.hostname)
    if not ok:
        return False, reason
    return True, "ok"


# ── HMAC signing (panel ↔ worker) ────────────────────────────────────────────
TS_WINDOW_S = 90          # ±۹۰ ثانیه (سند: timestamp + nonce + replay protection)
SIGN_HEADER_PREFIX = "x-sr-"


def canonical(ts: str, nonce: str, method: str, path: str, body: bytes | str) -> str:
    b = body.encode() if isinstance(body, str) else (body or b"")
    bh = hashlib.sha256(b).hexdigest()
    return f"{ts}.{nonce}.{method.upper()}.{path}.{bh}"


def sign(key: str, ts: str, nonce: str, method: str, path: str,
         body: bytes | str = b"") -> str:
    mac = hmac.new(key.encode(), canonical(ts, nonce, method, path, body).encode(),
                   hashlib.sha256)
    return mac.hexdigest()


def make_signed_headers(key: str, method: str, path: str,
                        body: bytes | str = b"") -> dict:
    ts = str(int(time.time()))
    nonce = secrets.token_urlsafe(16)
    sig = sign(key, ts, nonce, method, path, body)
    return {
        f"{SIGN_HEADER_PREFIX}timestamp": ts,
        f"{SIGN_HEADER_PREFIX}nonce": nonce,
        f"{SIGN_HEADER_PREFIX}signature": sig,
    }


async def verify_signed_request(key: str, ts: str, nonce: str, sig: str,
                                method: str, path: str, body: bytes = b"",
                                replay_check=None) -> tuple[bool, str]:
    """بررسی کامل: timestamp window + nonce replay + signature (constant-time).

    replay_check: callable(nonce)->bool (نمونه: db.nonce_seen — True یعنی تکراری).
    """
    if not key:
        return False, "کلید امضا تنظیم نشده"
    if not (ts and nonce and sig):
        return False, "هدرهای امضا ناقص"
    try:
        its = int(ts)
    except ValueError:
        return False, "timestamp نامعتبر"
    if abs(time.time() - its) > TS_WINDOW_S:
        return False, "timestamp خارج از پنجره (replay/کهنگی)"
    expect = sign(key, ts, nonce, method, path, body)
    if not hmac.compare_digest(expect, (sig or "").lower()):
        return False, "امضا نامعتبر"
    if replay_check is not None and replay_check(nonce):
        return False, "nonce تکراری (replay)"
    return True, "ok"


# ── rate limiting (توکن‌باکت در حافظه — برای جلوگیری از سوءاستفاده‌ی discovery) ─
_BUCKETS: dict[str, tuple[float, float]] = {}
_RATE_LOCK = asyncio.Lock()


async def rate_limit(bucket: str, max_per_window: int = 6, window_s: float = 60.0,
                     cost: float = 1.0) -> tuple[bool, float]:
    """False + بازگشتی ثانیه تا پر شدن؛ True یعنی مجاز."""
    async with _RATE_LOCK:
        now = time.time()
        tokens, refill_ts = _BUCKETS.get(bucket, (float(max_per_window), now))
        # refill
        elapsed = max(0.0, now - refill_ts)
        tokens = min(float(max_per_window), tokens + elapsed * (max_per_window / window_s))
        if tokens < cost:
            _BUCKETS[bucket] = (tokens, now)
            return False, (cost - tokens) / (max_per_window / window_s)
        _BUCKETS[bucket] = (tokens - cost, now)
        return True, 0.0
