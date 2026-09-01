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

import asyncio
import socket


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
