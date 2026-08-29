# central.py — ارتباط با سرویس مرکزی روی Cloudflare Worker
import os
import asyncio
import httpx

CENTRAL_URL = os.environ.get("CENTRAL_URL", "https://panel-rvg.arvin341az.workers.dev").rstrip("/")


async def register_instance():
    if not CENTRAL_URL:
        return
    from main import AUTH, get_host
    from updater import get_current_version
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(f"{CENTRAL_URL}/api/register", json={
                "domain": get_host(),
                "version": get_current_version(),
                "panel_password_hash": AUTH["password_hash"],
                "description": "EMIX instance",
            })
    except Exception:
        pass


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
    except Exception:
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
    except Exception:
        pass


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