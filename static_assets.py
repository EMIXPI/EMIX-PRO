# static_assets.py
# ══════════════════════════════════════════════════════════════════════════════
# ماژول Assets سلف‌هاست + فشرده‌سازی GZip انتخابی
#
# 🎯 چرا؟
#   داشبورد و صفحه‌ی لاگین قبلاً فونت (Vazirmatn)، آیکون‌ها (Tabler) و
#   Chart.js را از CDNهای خارجی لود می‌کردند — در ایران این CDNها کند یا
#   فیلترند. حالا همه‌ی assets از خود پنل سرو می‌شوند → لود فوری.
#
# ⚡ GZip انتخابی (نه سراسری!):
#   GZipMiddleware استارلتیک پاسخ‌های استریمی را بافر می‌کند — حتی وقتی
#   درخواست gzip نخواسته باشد (IdentityResponder هدرها را تا اولین بادی
#   نگه می‌دارد). برای دانلینگ xhttp (یک تونل زنده‌ی طولانی) این یعنی
#   هیچ هدری به کلاینت نمی‌رسد تا داده‌ای جریان یابد → کانفیگ‌های xhttp
#   برای کلاینت‌های واقعی می‌خوابند!
#   راه‌حل: فشرده‌سازی فقط روی مسیرهای «bounded» (HTML داشبورد/لاگین،
#   APIهای JSON، assets). مسیرهای تونل (/xhttp-siz10/، /txhttp-siz10/)
#   هرگز وارد GZip نمی‌شوند — بایت‌به‌بایت پاس داده می‌شوند.
#
# 🔒 فلسفه جداسازی: اگر حذف شود، فقط /assets و فشرده‌سازی غیب می‌شود؛
#   پنل و تونل‌ها کار می‌کنند (HTML به CDN fallback می‌کند).
# ══════════════════════════════════════════════════════════════════════════════

from pathlib import Path

from fastapi.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles

ASSETS_DIR = Path(__file__).parent / "assets"

# مسیرهایی که پاسخشان «کامل و محدود» است و فشرده‌سازی برایشان امن است
COMPRESSIBLE_PREFIXES = ("/dashboard", "/login", "/assets/", "/api/")

# مسیرهای تونل/استریم — هرگز نباید فشرده یا بافر شوند (تضمینی؛ allowlist بالا کافی است
# اما این ردیف صریح، در برابر تغییرهای آینده هم محافظ می‌ماند)
NEVER_COMPRESS_PREFIXES = ("/xhttp-siz10/", "/txhttp-siz10/")


class _SelectiveGZip:
    """GZip فقط برای پاسخ‌های bounded؛ تونل‌های استریمی کاملاً دست‌نخورده."""

    def __init__(self, app, minimum_size: int = 1024, compresslevel: int = 6):
        self.app = app
        self._gzip = GZipMiddleware(app, minimum_size=minimum_size, compresslevel=compresslevel)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if any(path.startswith(p) for p in NEVER_COMPRESS_PREFIXES):
            # تونل زنده — عبور مستقیم بدون هیچ تغییری
            await self.app(scope, receive, send)
            return
        if any(path.startswith(p) for p in COMPRESSIBLE_PREFIXES):
            await self._gzip(scope, receive, send)
            return
        # بقیه (فایل‌های متفرقه، ریدایرکت‌ها و…) بدون فشرده‌سازی
        await self.app(scope, receive, send)


def register(app) -> None:
    """سرو فایل‌های استاتیک از /assets + GZip انتخابی (امن برای تونل‌ها)."""

    app.add_middleware(_SelectiveGZip)

    # ── سرو assets محلی ──
    if ASSETS_DIR.exists():
        app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
    else:
        # اگر پوشه assets موجود نبود (مثلاً حذف شده)، کرش نکن —
        # HTML به CDNهای اصلی fallback می‌کند.
        import logging
        logging.getLogger("EMIX").warning(
            "[static_assets] پوشه‌ی assets یافت نشد — از CDN استفاده می‌شود"
        )
