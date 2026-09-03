# ══════════════════════════════════════════════════════════════════════════════
# net_connect.py — اتصال خروجی TCP با اولویت IPv4 (فیکس Errno 101 روی Railway)
#
# 🔴 مشکل واقعی که این فایل حل می‌کند:
#   asyncio.open_connection() آدرس‌ها را به‌ترتیب سیستم (اغلب IPv6 اول) امتحان
#   می‌کند. Railway خروجی IPv6 ندارد → AAAA-only یا dual-stack target ها با
#   «[Errno 101] Network is unreachable» می‌میرند و کانفیگ‌ها به‌ظاهر «بدون پینگ»
#   می‌شوند (مثال زنده: ip-api.com از پنل تولیدی — ۲۰۹ خطا در لاگ).
#
# ✅ راه‌حل: resolve → مرتب‌سازی (IPv4 اول، IPv6 بعد) → اتصال به‌ترتیب؛
#   اولین موفق برمی‌گردد. اگر resolve چیزی نداد (IP عددی و…) رفتار اصلی
#   asyncio حفظ می‌شود. سازگار ۱۰۰٪ با امضای open_connection (reader, writer).
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# 🩺 WEAK-LINK TUNING — تیونینگ لینک‌های ضعیف/پرتاخیر (پورت‌شده از RVG v11.0.2)
#
# منبع: پروژه‌ی RVG (ریشه‌ی خانواده‌ی EMIX) — آخرین آپدیت خودکارش دقیقاً همین
# پروفایل را توزیع کرد («افزایش سرعت کانفیگ‌ها با اینترنت‌های ضعیف»):
#   1. RELAY_BUF = 256KB — چانک کوچک‌تر روی لینک پرتاخیر یعنی داده زودتر به
#      مقصد می‌رسد به‌جای صف‌کشیدن در بافر بزرگ (1MB قبلی).
#   2. SOCK_BUF = 512KB — بافر OS بزرگ (4MB قبلی) روی لینک ضعیف باعث
#      bufferbloat و تاخیر اضافه می‌شود، نه throughput بیشتر.
#   3. WRITE_HIGH_WATER = 128KB — drain زودتر، صف ارسال کوچک‌تر می‌ماند؛
#      تاخیر کمتر مخصوصاً وقتی پهنای‌باند سمت مقصد کم است.
#   4. TCP_USER_TIMEOUT = 20s — کانکشن‌های نیمه‌قطع (پرش وای‌فای↔موبایل‌دیتا)
#      بدون این دقیقه‌ها معلق می‌ماندند و throughput را قفل می‌کردند.
# همه‌ی پروتکل‌ها (VLESS/Trojan/SS/XHTTP) این مقادیر را از همین‌جا می‌خوانند —
# یک منبع حقیقت واحد برای پروفایل شبکه.
# ══════════════════════════════════════════════════════════════════════════════

RELAY_BUF = 256 * 1024           # 256KB — چانک رله روی لینک ضعیف
SOCK_BUF = 512 * 1024            # 512KB — بافر سوکت سطح OS (ضد bufferbloat)
WRITE_HIGH_WATER = 128 * 1024    # 128KB — آستانه‌ی drain زودهنگام
TCP_USER_TIMEOUT_MS = 20000      # 20s — قطع اتصال نیمه‌مرده

import asyncio
import socket


def apply_weak_link_tuning(sock) -> None:
    """اعمال پروفایل ضعیف-لینک روی یک سوکت متصل (best-effort، هرگز raise نمی‌کند).

    TCP_NODELAY/QUICKACK مثل قبل؛ بافرها طبق پروفایل RVG (512KB)؛
    TCP_USER_TIMEOUT برای درو کانکشن‌های نیمه‌قطع (پرش شبکه‌ی موبایل).
    """
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SOCK_BUF)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, SOCK_BUF)
        if hasattr(socket, "TCP_QUICKACK"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
        if hasattr(socket, "TCP_USER_TIMEOUT"):
            # روی لینک‌های ضعیف/موبایل، کانکشن‌های نیمه‌قطع بدون این می‌تونن
            # دقیقه‌ها معلق بمونن و throughput رو قفل کنن (RVG v11.0.2)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_USER_TIMEOUT,
                            TCP_USER_TIMEOUT_MS)
    except Exception:
        pass


async def open_connection_v4first(address: str, port: int, timeout: float = 10.0):
    """asyncio.open_connection با اولویت IPv4 (سازگار با خطای Errno 101 Railway).

    - اگر host هم A و هم AAAA داشته باشد: اول IPv4 امتحان می‌شود؛
      اگر IPv4 شکست خورد، IPv6 بعدی است (در محیط‌های دارای IPv6 همچنان کار می‌کند).
    - اگر DNS پاسخ نداد: همان open_connection اصلی (خطای اصلی حفظ می‌شود).
    - timeout کل هر تلاش، همان مقدار قبلی هر فراخوانی است.
    """
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(address, port, type=socket.SOCK_STREAM)
    except Exception:
        infos = []

    fams: list = []
    for info in infos:
        fam = info[0]
        if fam in (socket.AF_INET, socket.AF_INET6) and fam not in fams:
            fams.append(fam)
    # IPv4 اول، IPv6 بعد
    fams.sort(key=lambda f: 0 if f == socket.AF_INET else 1)

    last_exc = None
    for fam in fams:
        try:
            return await asyncio.wait_for(
                asyncio.open_connection(address, port, family=fam), timeout
            )
        except Exception as exc:
            last_exc = exc
            continue

    if last_exc is not None:
        raise last_exc

    # resolve چیزی نداد (IP عددی، خطای DNS و…) — رفتار اصلی
    return await asyncio.wait_for(asyncio.open_connection(address, port), timeout)
