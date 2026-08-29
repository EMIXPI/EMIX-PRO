# turbo_boost.py
# ══════════════════════════════════════════════════════════════════════════════
# EMIX Turbo — لینک‌های 0-RTT + تست A/B خودکار
#
# 🚀 چیست؟
#   تکنیک استاندارد Early-Data (ed=2048) در xray: کلاینت بار اولیه را داخل
#   «هندشیکِ» WebSocket می‌فرستد → سرور بلافاصله بعد از هندشیک کار را شروع
#   می‌کند. نتیجه: حذف یک رفت‌وبرگشت (RTT) از هر اتصال جدید.
#   در شبکه‌ی واقعی ایران، هر RTT ≈ ۱۰۰ تا ۳۰۰ میلی‌ثانیه است؛ یعنی هر بار
#   باز کردن صفحه/اپ، یک RTT کامل صرفه‌جویی می‌شود.
#
# 🧪 تفاوت با بقیه پنل‌ها:
#   اینجا فقط ادعا نیست — تست A/B واقعی انجام می‌شود: همان کانفیگ، یک بار
#   مسیر عادی و یک بار مسیر توربو از مسیر عمومی تست می‌شود و تفاوتِ اندازه‌گیری‌شده
#   نمایش داده می‌شود. هیچ پنل دیگری این را ندارد.
#
# 🔒 فلسفه جداسازی:
#   این ماژول فقط «لینک تولیدشده توسط هسته» را بازنویسی می‌کند (مثل bridge_boost).
#   تولیدکننده‌ی لینک و منطق تونل دست نمی‌خورند. پشتیبانی سرور از Early-Data
#   در هندلرهای WS به‌صورت سازگار با گذشته اضافه شده (اگر هدر نبود = مسیر عادی).
#
# ⚙️ اندپوینت‌ها:
#   POST /api/turbo/links/{uid}/ab  → تست A/B: مسیر عادی در برابر 0-RTT + لینک توربو
#   GET  /api/turbo/links           → همه‌ی لینک‌های توربو‌دار (VLESS-WS / Trojan-WS)
# ══════════════════════════════════════════════════════════════════════════════

import re
from datetime import datetime
from urllib.parse import unquote, quote

from fastapi import Depends, HTTPException

from main import (
    LINKS,
    LINKS_LOCK,
    get_host,
    require_auth,
    is_link_allowed,
    generate_share_link,
)
import link_health

TURBO_PROTOCOLS = ("vless-ws", "trojan-ws")   # فقط WS از ed پشتیبانی می‌کند (پروتکل‌های xray)
ED_PATH_SUFFIX = quote("?ed=2048", safe="")


def _turbo_link(url: str) -> str | None:
    """افزودن ?ed=2048 به انتهای path داخل لینک (بازنویسی URL — بدون دست‌زدن به تولیدکننده)."""
    if not url.startswith(("vless://", "trojan://")):
        return None
    # فقط ترنسپورت ws سود می‌برد
    if "type=ws" not in url:
        return None
    m = re.search(r"([?&]path=)([^&#]+)", url)
    if not m:
        return None
    path_val = unquote(m.group(2))
    if "ed=" in path_val:
        return url  # از قبل توربوست
    new_path = m.group(2) + ED_PATH_SUFFIX
    return url[: m.start(2)] + new_path + url[m.end(2):]


async def _turbo_targets() -> list[dict]:
    """همه‌ی کانفیگ‌های محلیِ VLESS-WS / Trojan-WS مجاز + نسخه‌ی توربو."""
    host = get_host()
    async with LINKS_LOCK:
        snap = [(uid, dict(d)) for uid, d in LINKS.items()]
    out = []
    for uid, d in snap:
        proto = d.get("protocol", "vless-ws")
        if proto not in TURBO_PROTOCOLS:
            continue
        if not is_link_allowed(d):
            continue
        original = generate_share_link(uid, host, remark=f"EMIX-{d['label']}", protocol=proto)
        turbo = _turbo_link(original)
        if turbo:
            out.append({
                "uuid": uid,
                "label": d.get("label", uid[:8]),
                "protocol": proto,
                "original": original,
                "turbo": turbo,
            })
    return out


def _total_ms(r: dict) -> float | None:
    """مجموع زمان هندشیک + رفت‌وبرگشت تونل = زمان واقعی تا اولین بایت پاسخ."""
    if not r or not r.get("ok"):
        return None
    ws, e2e = r.get("ws_ms"), r.get("e2e_ms")
    if ws is None and e2e is None:
        return None
    return round((ws or 0) + (e2e or 0), 1)


def register_routes(app) -> None:

    @app.get("/api/turbo/links")
    async def turbo_links(_=Depends(require_auth)):
        return {"links": await _turbo_targets()}

    @app.post("/api/turbo/links/{uid}/ab")
    async def turbo_ab_test(uid: str, _=Depends(require_auth)):
        """تست A/B واقعی: همان تونل، یک بار عادی و یک بار 0-RTT — از مسیر عمومی."""
        async with LINKS_LOCK:
            link = LINKS.get(uid)
        if not link:
            raise HTTPException(status_code=404, detail="کانفیگ یافت نشد")
        proto = link.get("protocol", "vless-ws")
        if proto not in TURBO_PROTOCOLS:
            raise HTTPException(status_code=400, detail="توربو فقط برای کانفیگ‌های VLESS-WS و Trojan-WS در دسترس است")
        if not is_link_allowed(link):
            raise HTTPException(status_code=400, detail="کانفیگ غیرفعال است یا کوتای آن تمام شده")

        kind = "vless" if proto == "vless-ws" else "trojan"
        # هر حالت ۲ بار اجرا و کمینه گرفته می‌شود (حذف نوسان شبکه — مقایسه‌ی منصفانه)
        async def _best(use_ed: bool) -> dict:
            runs = [await link_health._probe_ws_tunnel(kind, uid, link, use_ed=use_ed) for _ in range(2)]
            ok_runs = [r for r in runs if r.get("ok")]
            if not ok_runs:
                return runs[0]
            return min(ok_runs, key=lambda r: (r.get("ws_ms") or 0) + (r.get("e2e_ms") or 0))

        normal_runs = await _best(False)
        turbo_runs = await _best(True)

        normal_total = _total_ms(normal_runs)
        turbo_total = _total_ms(turbo_runs)

        host = get_host()
        original = generate_share_link(uid, host, remark=f"EMIX-{link['label']}", protocol=proto)
        turbo_url = _turbo_link(original)

        return {
            "ok": bool(turbo_runs.get("ok") and turbo_url),
            "protocol": proto,
            "normal": {"ok": normal_runs.get("ok"), "ws_ms": normal_runs.get("ws_ms"), "e2e_ms": normal_runs.get("e2e_ms"), "total_ms": normal_total},
            "turbo": {"ok": turbo_runs.get("ok"), "ws_ms": turbo_runs.get("ws_ms"), "e2e_ms": turbo_runs.get("e2e_ms"), "total_ms": turbo_total},
            "improvement_ms": (round(normal_total - turbo_total, 1)
                               if normal_total is not None and turbo_total is not None else None),
            "turbo_url": turbo_url,
            "original_url": original,
            "note": "در شبکه‌ی محلی تفاوت کم است؛ در اینترنت واقعی، صرفه‌جویی ≈ یک RTT کامل (۱۰۰-۳۰۰ms در ایران) به‌ازای هر اتصال جدید است",
            "checked_at": datetime.now().isoformat(),
        }
