# emix_pro.py
# ══════════════════════════════════════════════════════════════════════════════
# لایه‌ی هویت و سلامت EMIX-PRO روی هسته‌ی EMIX پایه (v13).
#
# 🧬 فلسفه (Phase 45 — بازسازی روی پایه):
#   هسته‌ی EMIX (05f2f2c «Restore to healthy original state») بایت‌به‌بایت
#   دست‌نخورده مانده است. این فایل فقط «ویژگی‌های سالمِ اثبات‌شده» را به‌صورت
#   افزودنی روی همان هسته سوار می‌کند: هویت نسخه، گزارش جامع سلامت، و
#   تست خروج واقعی (الهام از EgressTracer پروژه‌ی MLMVPN).
#
# 🔌 اندپوینت‌ها:
#   GET /api/deployment-version → هویت نسخه (بدون احراز هویت)
#   GET /api/system/health-all  → گزارش جامع سلامت همه‌ی بخش‌ها
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import Depends
from fastapi.responses import JSONResponse

from main import (
    LINKS,
    LINKS_LOCK,
    SUBS,
    SUBS_LOCK,
    CONFIG,
    DATA_DIR,
    DATA_FILE,
    PROTOCOLS,
    DEFAULT_PROTOCOL,
    connections,
    get_host,
    is_link_allowed,
    is_link_expired,
    require_auth,
    uptime,
)

EMIX_PRO_VERSION = "13.5.0-emix-pro"
EMIX_BASE_PANEL = "EMIX 9.2 (05f2f2c — healthy original state)"
EMIX_PRO_FEATURES = [
    "real-e2e-ping",          # تست واقعی مسیر کلاینت (link_health) — با Real Delay تفکیک‌شده از TCP
    "health-all",             # گزارش جامع سلامت همه‌ی بخش‌ها
    "egress-check",           # خروج واقعی IP/لوکیشن (الهام MLMVPN EgressTracer)
    "staged-ping-progress",   # پیشرفت/گزارش مرحله‌ای تست (الهام MLMVPN sweep)
    "best-links-ranking",     # رتبه‌بندی کانفیگ‌ها با زمان واقعی
    "turbo-0rtt",             # توربو per-link (ed=2048) + تست A/B واقعی + تک‌شانهای
    "sni-spoof-per-link",     # جعل SNI هر کانفیگ (Mode B) + پینگ صادق از همان مسیر
    "fresh-ui-no-store",      # HTML پنل هرگز از کش مرورگر نمی‌آید
    "smart-routing-v1",       # شبکه‌ی مسیریابی هوشمند (feature-flagged؛ discovery/verify/pool/failover/worker)
]


async def _section_egress() -> dict:
    """خروج واقعی دیپلوی — اندازه‌گیری‌شده از بیرون (هرگز IP تنظیمی را گزارش نمی‌کند).

    الهام از EgressTracer پروژه‌ی mlmvpn_android: پنل خودش به سرویس بیرونی
    وصل می‌شود و IP/کشوری که «واقعاً» از آن خارج می‌شود را می‌سنجد."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
            r = await client.get(
                "http://ip-api.com/json/",
                params={"fields": "status,message,query,country,countryCode,city,isp,as"},
            )
            d = r.json()
        if d.get("status") != "success":
            return {"ok": False, "error": d.get("message", "unknown")}
        return {
            "ok": True,
            "exit_ip": d.get("query"),
            "country": d.get("country"),
            "country_code": d.get("countryCode"),
            "city": d.get("city"),
            "isp": d.get("isp"),
            "asn": d.get("as"),
            "measurement_source": "ip-api.com (اندازه‌گیری بیرونی)",
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:100]}"}


def _section_volume() -> dict:
    """بخش‌های دیسک: دیتای پایدار روی Volume ریلوی."""
    try:
        dd = Path(DATA_DIR)
        exists = dd.exists()
        writable = False
        if exists:
            probe = dd / ".emix_pro_health_probe"
            try:
                probe.write_text("ok", encoding="utf-8")
                probe.unlink()
                writable = True
            except Exception:
                writable = False
        state_bytes = DATA_FILE.stat().st_size if (exists and Path(DATA_FILE).exists()) else 0
        return {
            "ok": exists and writable,
            "data_dir": str(DATA_DIR),
            "exists": exists,
            "writable": writable,
            "state_file_bytes": state_bytes,
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:100]}"}


def _section_links() -> dict:
    """خلاصه‌ی کانفیگ‌ها + شواهد آخرین تست واقعی (اگر وجود داشته باشد).

    خواندنِ snapshot بدون قفل — سازگار با الگوی base (dict(LINKS) در /stats)؛
    هم‌زمانی نوشتن فقط یک کلید اضافه/کم نشان می‌دهد، نه خطا."""
    links = dict(LINKS)
    total = len(links)
    active = sum(1 for l in links.values() if l.get("active", True) and not is_link_expired(l))
    expired = sum(1 for l in links.values() if is_link_expired(l))
    per_proto: dict[str, int] = {}
    healthy_evidence = 0
    last_check = None
    for l in links.values():
        p = l.get("protocol", DEFAULT_PROTOCOL)
        per_proto[p] = per_proto.get(p, 0) + 1
        lp = l.get("last_ping")
        if isinstance(lp, dict):
            if lp.get("ok"):
                healthy_evidence += 1
            ca = lp.get("checked_at")
            if ca and (last_check is None or ca > last_check):
                last_check = ca
    return {
        "ok": True,
        "total": total,
        "active": active,
        "expired": expired,
        "per_protocol": per_proto,
        "healthy_evidence": healthy_evidence,
        "last_real_check": last_check,
        "note": "healthy_evidence = تعداد لینک‌هایی که آخرین تست واقعی (پینگ E2E) آن‌ها موفق بوده",
    }


def _section_panel() -> dict:
    return {
        "ok": True,
        "version": EMIX_PRO_VERSION,
        "base_panel": EMIX_BASE_PANEL,
        "host": get_host(),
        "port": CONFIG.get("port"),
        "uptime": uptime(),
        "live_connections": len(connections),
    }


def _section_runtime() -> dict:
    try:
        import uvloop  # noqa: F401
        loop_name = "uvloop"
    except Exception:
        loop_name = "asyncio"
    return {
        "ok": True,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "event_loop": loop_name,
    }


def register_routes(app) -> None:
    """اندپوینت‌های هویت و سلامت — از انتهای main.py صدا زده می‌شود."""

    @app.get("/api/deployment-version")
    async def deployment_version():
        return JSONResponse(
            {
                "ok": True,
                "service": "EMIX-PRO",
                "version": EMIX_PRO_VERSION,
                "base_panel": EMIX_BASE_PANEL,
                "features": EMIX_PRO_FEATURES,
                "build": "rebuilt-on-healthy-base",
                "checked_at": datetime.now().isoformat(),
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/system/health-all")
    async def health_all(_=Depends(require_auth)):
        """گزارش جامع سلامت — همه‌ی بخش‌ها مستقل و fail-safe.

        هر بخش اگر خطا بخورد فقط همان بخش قرمز می‌شود؛ بقیه‌ی گزارش سالم می‌ماند."""
        t0 = time.perf_counter()

        async def _safe_async(fn):
            try:
                return await fn()
            except Exception as exc:
                return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:100]}"}

        def _safe(fn):
            try:
                return fn()
            except Exception as exc:
                return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:100]}"}

        egress = await _safe_async(_section_egress)
        report = {
            "ok": True,
            "version": EMIX_PRO_VERSION,
            "base_panel": EMIX_BASE_PANEL,
            "generated_at": datetime.now().isoformat(),
            "took_ms": round((time.perf_counter() - t0) * 1000, 1),
            "sections": {
                "panel": _safe(_section_panel),
                "links": _safe(_section_links),
                "protocols": {
                    "ok": True,
                    "supported": list(PROTOCOLS),
                    "note": "هسته‌ی پروتکل‌ها = EMIX پایه (دست‌نخورده)",
                },
                "egress": egress,
                "volume": _safe(_section_volume),
                "runtime": _safe(_section_runtime),
            },
            # خلاصه‌ی فارسی برای نمایش سریع
            "summary_fa": (
                f"پنل سالم · نسخه {EMIX_PRO_VERSION} روی هسته‌ی EMIX 9.2 · "
                f"{len(LINKS)} کانفیگ · {len(SUBS)} گروه ساب"
            ),
        }
        # یک بخش قرمز → کل گزارش ok=false (اما همیشه کامل برمی‌گردد)
        report["ok"] = all(s.get("ok") for s in report["sections"].values())
        return JSONResponse(report, headers={"Cache-Control": "no-store"})
