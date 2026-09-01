# central.py — ارتباط با سرویس مرکزی روی Cloudflare Worker
# SECURITY (audit fix 2026-09):
#   * این module دیگر password_hash را به بیرون نمی‌فرستد — هرگز.
#   * با EMIX_CENTRAL_ENABLED=0 می‌توان کل ارتباط را خاموش کرد.
#   * خطاها به Diagnostics Center گزارش می‌شوند (نه silent pass).
import os
import asyncio
import httpx

# Kill switch: با "0" کل ارتباط با سرویس مرکزی غیرفعال می‌شود (fail-closed).
_CENTRAL_ENABLED = os.environ.get("EMIX_CENTRAL_ENABLED", "1").strip().lower() not in ("0", "false", "off", "no")
CENTRAL_URL = (os.environ.get("CENTRAL_URL", "https://panel-rvg.arvin341az.workers.dev").rstrip("/")
               if _CENTRAL_ENABLED else "")


def _report(component: str, error) -> None:
    """ثبت خطای ارتباط مرکزی در Diagnostics Center (به‌جای silent pass)."""
    try:
        import diagnostics
        diagnostics.record_error_sync(
            code=f"CENTRAL_{component.upper().replace('-', '_')}",
            message=str(error)[:300],
            component=f"central:{component}",
            severity="warning",
            context={"url": CENTRAL_URL},
        )
    except Exception:
        pass  # خود diagnostics هم نباید پنل را زمین بزند


async def register_instance():
    if not CENTRAL_URL:
        return
    from main import get_host
    from updater import get_current_version
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            # SECURITY: domain/version/description فقط — هیچ credential ای ارسال نمی‌شود.
            await c.post(f"{CENTRAL_URL}/api/register", json={
                "domain": get_host(),
                "version": get_current_version(),
                "description": "EMIX instance",
            })
    except Exception as e:
        _report("register", e)


async def heartbeat_loop():
    while True:
        await register_instance()
        await asyncio.sleep(300)


async def fetch_announcements():
    if not CENTRAL_URL:
        return []
    from main import get_host
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{CENTRAL_URL}/api/announcements", params={"domain": get_host()})
            r.raise_for_status()
            return r.json().get("announcements", [])
    except Exception as e:
        _report("announcements", e)
        return []


async def report_announcement_views(ids: list[str]):
    """اعلام می‌کند این instance این لیست از اعلان‌ها را دیده است (برای شمارش بازدید در ادمین مرکزی)."""
    if not CENTRAL_URL or not ids:
        return
    from main import get_host
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(f"{CENTRAL_URL}/api/announcements/view", json={
                "domain": get_host(),
                "ids": ids,
            })
    except Exception as e:
        _report("announcement-views", e)


async def fetch_support_messages():
    """برمی‌گرداند: (messages, blocked)"""
    if not CENTRAL_URL:
        return [], False
    from main import get_host
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{CENTRAL_URL}/api/support/messages", params={"domain": get_host()})
            r.raise_for_status()
            d = r.json()
            return d.get("messages", []), bool(d.get("blocked", False))
    except Exception:
        return [], False


async def send_support_message(body: str) -> dict:
    if not CENTRAL_URL:
        return {"ok": False, "blocked": False, "error": "CENTRAL_URL تنظیم نشده"}
    from main import get_host
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{CENTRAL_URL}/api/support/send", json={"domain": get_host(), "body": body})
            if r.status_code == 403:
                return {"ok": False, "blocked": True}
            if r.status_code != 200:
                return {"ok": False, "blocked": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
            return {"ok": True, "blocked": False}
    except Exception as e:
        return {"ok": False, "blocked": False, "error": str(e)}


async def close_support_chat() -> bool:
    # عمداً حذف شد — بستن چت فقط از پنل ادمین مرکزی مجاز است
    return False