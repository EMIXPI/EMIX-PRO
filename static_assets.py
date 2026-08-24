# static_assets.py
# ══════════════════════════════════════════════════════════════════════════════
# ماژول Assets سلف‌هاست + فشرده‌سازی GZip
#
# 🎯 چرا؟
#   داشبورد و صفحه‌ی لاگین قبلاً فونت (Vazirmatn)، آیکون‌ها (Tabler) و
#   Chart.js را از CDNهای خارجی (googleapis / jsdelivr / cdnjs) لود می‌کردند —
#   در ایران این CDNها کند یا فیلترند؛ یعنی ادمین قبل از اولین اتصالِ
#   پروکسی، داشبوردی بی‌فونت و آهستجه می‌دید!
#   حالا همه‌ی assets از خود پنل سرو می‌شوند → لود فوری و آفلاین‌گونه.
#
# ⚡ GZip:
#   داشبورد ~۳۴۰KB است؛ با GZip حدود ۵ برابر کوچکتر می‌شود (HTML/CSS/JS/فونت
#   به‌صورت gzip روی سیم) → لود اولیه‌ی سریع‌تر روی شبکه‌ی ضعیف موبایل.
#
# 🔒 فلسفه جداسازی (مثل بقیه‌ی ماژول‌های افزودنی EMIX):
#   فقط یک mount و یک middleware اضافه می‌کند؛ اگر حذف شود، پنل کار می‌کند
#   (فقط مسیر /assets دیگر پاسخ نمی‌دهد و صفحه به CDN برمی‌گردد — fallback
#   در خود HTML تعبیه شده است).
# ══════════════════════════════════════════════════════════════════════════════

from pathlib import Path

from fastapi.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles

ASSETS_DIR = Path(__file__).parent / "assets"


def register(app) -> None:
    """سرو فایل‌های استاتیک از /assets + فعال‌سازی GZip روی همه‌ی پاسخ‌ها."""

    # ── GZip: هر پاسخ بزرگتر از 1KB فشرده می‌شود (HTML داشبورد، CSS، JS) ──
    app.add_middleware(GZipMiddleware, minimum_size=1024)

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
