# turbo_boost.py
# ══════════════════════════════════════════════════════════════════════════════
# EMIX Turbo — لینک‌های 0-RTT + تست A/B خودکار (v13.2 — بازآورده از نسخه‌ی
# اثبات‌شده‌ی v12، هماهنگ با معماری افزودنی فاز ۴۵)
#
# 🚀 چیست؟
#   تکنیک استاندارد Early-Data (ed=2048) در xray: کلاینت بار اولیه را داخل
#   «هندشیکِ» WebSocket می‌فرستد (هدر Sec-WebSocket-Protocol، base64url) →
#   سرور بلافاصله بعد از هندشیک کار را شروع می‌کند. نتیجه: حذف یک رفت‌وبرگشت
#   (RTT) از هر اتصال جدید. در شبکه‌ی واقعی، هر RTT ≈ ۱۰۰ تا ۳۰۰ms است؛ یعنی
#   هر بار باز کردن صفحه/اپ، یک RTT کامل صرفه‌جویی می‌شود.
#
# 🧪 تفاوت با بقیه پنل‌ها:
#   فقط ادعا نیست — تست A/B واقعی انجام می‌شود: همان کانفیگ، یک بار مسیر عادی
#   و یک بار مسیر توربو از مسیر عمومی تست می‌شود و تفاوتِ اندازه‌گیری‌شده
#   نمایش داده می‌شود.
#
# ⚙️ اندپوینت‌ها:
#   POST /api/links/{uid}/turbo-ab → تست A/B: مسیر عادی در برابر 0-RTT + لینک توربو
# ══════════════════════════════════════════════════════════════════════════════

from datetime import datetime

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse

from main import (
    LINKS,
    LINKS_LOCK,
    get_host,
    require_auth,
    is_link_allowed,
    generate_share_link,
    _apply_link_features,
)
import link_health

TURBO_PROTOCOLS = ("vless-ws", "trojan-ws")   # فقط WS از ed پشتیبانی می‌کند (پروتکل‌های xray)


def _total_ms(r: dict) -> float | None:
    """مجموع زمان هندشیک + رفت‌وبرگشت تونل = زمان واقعی تا اولین بایت پاسخ."""
    if not r or not r.get("ok"):
        return None
    ws, e2e = r.get("ws_ms"), r.get("e2e_ms")
    if ws is None and e2e is None:
        return None
    return round((ws or 0) + (e2e or 0), 1)


def register_routes(app) -> None:

    @app.post("/api/links/{uid}/turbo-ab")
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
        # لینک توربو = همان لینک با ed=2048 روی path (تولید واقعی از همان هسته)
        turbo_link_data = dict(link)
        turbo_link_data["turbo_enabled"] = True
        params_probe: dict = {}
        if proto == "vless-ws":
            params_probe = {
                "encryption": "none", "security": "tls", "type": "ws", "host": host,
                "path": f"/ws/{uid}", "sni": host,
                "fp": turbo_link_data.get("fingerprint", "chrome"),
                "alpn": turbo_link_data.get("alpn", "h2"),
            }
        else:
            params_probe = {
                "security": "tls", "type": "ws", "host": host,
                "path": "/trojan-ws", "sni": host,
                "fp": turbo_link_data.get("fingerprint", "chrome"),
                "alpn": turbo_link_data.get("alpn", "h2"),
            }
        _apply_link_features(params_probe, turbo_link_data, proto)
        from urllib.parse import quote
        query = "&".join(f"{k}={quote(str(v))}" for k, v in params_probe.items())
        scheme_user = f"vless://{uid}" if proto == "vless-ws" else f"trojan://{uid}"
        turbo_url = f"{scheme_user}@{host}:443?{query}#{quote('EMIX-' + link['label'])}"

        return JSONResponse(
            {
                "ok": bool(turbo_runs.get("ok") and turbo_url),
                "protocol": proto,
                "turbo_enabled_now": bool(link.get("turbo_enabled")),
                "normal": {"ok": normal_runs.get("ok"), "ws_ms": normal_runs.get("ws_ms"),
                           "e2e_ms": normal_runs.get("e2e_ms"), "total_ms": normal_total},
                "turbo": {"ok": turbo_runs.get("ok"), "ws_ms": turbo_runs.get("ws_ms"),
                          "e2e_ms": turbo_runs.get("e2e_ms"), "total_ms": turbo_total},
                "improvement_ms": (round(normal_total - turbo_total, 1)
                                   if normal_total is not None and turbo_total is not None else None),
                "turbo_url": turbo_url,
                "original_url": original,
                "note": "صرفه‌جویی ≈ یک RTT کامل به‌ازای هر اتصال جدید (در اینترنت واقعی معنادار؛ در مسیر محلی کم)",
                "checked_at": datetime.now().isoformat(),
            },
            headers={"Cache-Control": "no-store"},
        )
