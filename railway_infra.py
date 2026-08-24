# railway_infra.py
# ══════════════════════════════════════════════════════════════════════════════
# ماژول زیرساخت Railway — Volume خودکار + وضعیت سرویس
#
# 🎯 هدف:
#   ۱) حفظ دیتای کاربران بین دیپلویها: بررسی اینکه DATA_DIR روی volume دائمی
#      است یا filesystem موقتِ کانتینر (os.path.ismount) + ساخت خودکارِ
#      volume از طریق GraphQL API ریلوی با توکن ذخیره‌شده‌ی کاربر
#   ۲) گزارش زیرساخت: volume / TCP proxies / سرویس
#
# 🔒 فلسفه جداسازی (مثل بقیه‌ی ماژول‌های boost):
#   - اگر این فایل حذف شود، پنل و همه‌ی تونل‌ها بدون تغییر کار می‌کنند
#   - توکن Railway از bottokentcpproxy خوانده می‌شود (فایل ذخیره‌شده)
#
# ⚙️ اندپوینت‌ها:
#   GET  /api/system/infra/status        → volume + سرویس + پروکسی‌ها
#   POST /api/system/infra/ensure-volume → ساخت volume روی DATA_DIR (اگر نباشد)
#   GET  /api/system/health-all          → سلامت همه‌ی بخش‌های پنل تا خروجی
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import os
import time
from pathlib import Path

import httpx
from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from main import (
    LINKS,
    LINKS_LOCK,
    DATA_DIR,
    require_auth,
    is_link_allowed,
    logger,
)
import bottokentcpproxy

GRAPHQL_URL = "https://backboard.railway.app/graphql/v2"

# زمان شروع پنل برای گزارش uptime
_STARTED_AT = time.time()

# ──────────────────────────────────────────────────────────────────────────────
# Volume helpers
# ──────────────────────────────────────────────────────────────────────────────

def volume_mounted() -> bool:
    """True اگر DATA_DIR یک mountpoint واقعی باشد (= volume ریلوی وصل است).
    بدون volume، /data فقط یک پوشه‌ی معمولی در filesystem موقتِ کانتینر است
    و با هر دیپلوی پاک می‌شود."""
    try:
        return os.path.ismount(str(DATA_DIR))
    except Exception:
        return False


def _service_ids() -> dict:
    """شناسه‌های سرویس/محیط/پروژه از متغیرهای runtime ریلوی"""
    return {
        "service_id": os.environ.get("RAILWAY_SERVICE_ID", ""),
        "environment_id": os.environ.get("RAILWAY_ENVIRONMENT_ID", ""),
        "project_id": os.environ.get("RAILWAY_PROJECT_ID", ""),
    }


async def _gql(token: str, query: str, variables: dict) -> dict:
    """فراخوانی GraphQL ریلوی — خطا به‌صورت Exception با پیام فارسی"""
    async with httpx.AsyncClient(timeout=25.0) as cli:
        r = await cli.post(
            GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
    if r.status_code == 401:
        raise RuntimeError("توکن Railway نامعتبر است یا دسترسی کافی ندارد")
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        msgs = "; ".join(e.get("message", "") for e in data["errors"])
        raise RuntimeError(f"خطای GraphQL: {msgs}")
    return data.get("data", {})


QUERY_PROJECT_VOLUMES = """
query ProjectVolumes($projectId: String!) {
  project(id: $projectId) {
    id
    name
    volumes { edges { node { id name } } }
  }
}
"""

MUTATION_VOLUME_CREATE = """
mutation VolumeCreate($projectId: String!, $environmentId: String!, $serviceId: String!, $mountPath: String!) {
  volumeCreate(input: {
    projectId: $projectId,
    environmentId: $environmentId,
    serviceId: $serviceId,
    mountPath: $mountPath
  }) {
    id
    name
  }
}
"""

QUERY_TCP_PROXIES = """
query TcpProxies($environmentId: String!, $serviceId: String!) {
  tcpProxies(environmentId: $environmentId, serviceId: $serviceId) {
    id
    domain
    proxyPort
    applicationPort
  }
}
"""


async def _list_volumes(token: str, project_id: str) -> list[dict]:
    """لیست volumeهای پروژه — اگر کوئری شکست خورد لیست خالی برمی‌گردد (غیر fatal)"""
    try:
        data = await _gql(token, QUERY_PROJECT_VOLUMES, {"projectId": project_id})
        edges = (((data.get("project") or {}).get("volumes") or {}).get("edges")) or []
        return [e.get("node") or {} for e in edges]
    except Exception as exc:
        logger.warning(f"[infra] خواندن لیست volumeها ناموفق: {exc}")
        return []


async def ensure_volume() -> dict:
    """ساخت volume روی DATA_DIR اگر وجود ندارد.
    بعد از ساخت، ریلوی سرویس را ری‌استارت می‌کند و از آن به بعد دیتا دائمی است."""
    ids = _service_ids()
    missing = [k for k, v in ids.items() if not v]
    if missing:
        return {"ok": False,
                "error": f"متغیرهای {', '.join(missing)} در محیط ریلوی یافت نشد — این قابلیت فقط روی دیپلوی ریلوی کار می‌کند"}

    token = bottokentcpproxy.load_token()
    if not token:
        return {"ok": False, "error": "توکن Railway ذخیره نشده — اول توکن را از بخش ساخت TCP Proxy ذخیره کنید (یا در همین درخواست بفرستید)"}

    if volume_mounted():
        existing = await _list_volumes(token, ids["project_id"])
        return {"ok": True, "already_mounted": True, "mount_path": str(DATA_DIR),
                "volumes": existing,
                "message": f"حجم (volume) از قبل روی {DATA_DIR} نصب است — دیتای شما دائمی است"}

    try:
        data = await _gql(token, MUTATION_VOLUME_CREATE, {
            "projectId": ids["project_id"],
            "environmentId": ids["environment_id"],
            "serviceId": ids["service_id"],
            "mountPath": str(DATA_DIR),
        })
        vol = data.get("volumeCreate") or {}
        return {
            "ok": True,
            "created": True,
            "volume": vol,
            "mount_path": str(DATA_DIR),
            "message": "حجم (volume) ساخته شد — ریلوی سرویس را ری‌استارت می‌کند؛ "
                       "بعد از بالا آمدن، همه‌ی دیتا (کانفیگ‌ها/توکن‌ها/تنظیمات) بین دیپلویها حفظ می‌شود. "
                       "⚠ نکته: اگر همین الان کانفیگ‌هایی دارید که می‌خواهید بمانند، قبل از ری‌استارت از بخش بکاپ‌گیری خروجی بگیرید.",
        }
    except RuntimeError as exc:
        msg = str(exc)
        if "already" in msg.lower() or "exists" in msg.lower() or "mount" in msg.lower():
            return {"ok": True, "already_mounted": False, "note": msg,
                    "message": "به‌نظر می‌رسد volume از قبل وجود دارد اما روی این مسیر mount نشده — در داشبورد ریلوی بخش Volume سرویس را بررسی کنید"}
        return {"ok": False, "error": msg}
    except Exception as exc:
        return {"ok": False, "error": f"ساخت volume ناموفق: {type(exc).__name__}: {exc}"}


async def _list_tcp_proxies() -> list[dict]:
    """لیست TCP Proxyهای فعال این سرویس از GraphQL"""
    ids = _service_ids()
    if not all([ids["environment_id"], ids["service_id"]]):
        return []
    token = bottokentcpproxy.load_token()
    if not token:
        return []
    try:
        data = await _gql(token, QUERY_TCP_PROXIES, {
            "environmentId": ids["environment_id"],
            "serviceId": ids["service_id"],
        })
        return data.get("tcpProxies") or []
    except Exception as exc:
        logger.warning(f"[infra] خواندن TCP proxies ناموفق: {exc}")
        return []


# ──────────────────────────────────────────────────────────────────────────────
# سلامت‌سنجی همه‌ی بخش‌های پنل تا خروجی
# ──────────────────────────────────────────────────────────────────────────────

async def health_all() -> dict:
    """گزارش سلامت کامل: هسته + ماژول‌ها + volume + پروکسی‌ها + لینک‌ها + گیت‌وی + پل.
    هر بخش به‌صورت isolate تست می‌شود؛ خطای یک بخش بقیه را نمی‌گیرد."""
    report: dict = {"ok": True, "checked_at": time.time(), "sections": {}}

    def sec(name: str, ok: bool, **kw):
        report["sections"][name] = {"ok": ok, **kw}
        if not ok:
            report["ok"] = False

    # ۱) هسته‌ی پنل
    import main as _main
    sec("panel", True, version=getattr(_main, "EMIX_VERSION", "?"),
        uptime_sec=round(time.time() - _STARTED_AT, 1),
        data_dir=str(DATA_DIR))

    # ۲) volume — دائمی بودن دیتا
    vm = volume_mounted()
    sec("volume", vm,
        mounted=vm,
        detail="دیتا روی volume دائمی است" if vm else
               "⚠ دیتا روی filesystem موقت است — با هر دیپلوی پاک می‌شود! از ensure-volume استفاده کنید")

    # ۳) ماژول‌ها
    import importlib
    for mod_name, label in [
        ("zeus_features", "ZEUS Pro"),
        ("gaming_boost", "مرکز گیمینگ"),
        ("bridge_boost", "پل ایران"),
        ("turbo_boost", "توربو"),
        ("clean_ip_boost", "آی‌پی تمیز"),
        ("link_health", "تست پینگ"),
    ]:
        try:
            m = importlib.import_module(mod_name)
            sec(f"module:{mod_name}", True, label=label)
            del m
        except Exception as exc:
            sec(f"module:{mod_name}", False, label=label, error=str(exc)[:120])

    # ۴) لینک‌ها — شمارش + پروتکل‌ها
    try:
        async with LINKS_LOCK:
            snap = [(uid, dict(d)) for uid, d in LINKS.items()]
        allowed = [(u, d) for u, d in snap if is_link_allowed(d)]
        by_proto: dict = {}
        for _, d in allowed:
            p = d.get("protocol", "vless-ws")
            by_proto[p] = by_proto.get(p, 0) + 1
        healthy = sum(1 for _, d in allowed if (d.get("last_ping") or {}).get("ok"))
        sec("links", len(allowed) > 0,
            total=len(snap), active=len(allowed),
            healthy_ping=healthy,
            by_protocol=by_proto,
            detail="همه‌ی لینک‌های فعال را از دکمه‌ی «تست همه» در صفحه‌ی کانفیگ‌ها پینگ کنید")
    except Exception as exc:
        sec("links", False, error=str(exc)[:120])

    # ۵) MTProto — پروسه‌های در حال اجرا
    try:
        from protocol.mtproto import mtproto_native as _mt
        running = [u for u, d in (snap if isinstance(snap, list) else [])
                   if d.get("protocol") == "mtproto"]
        mt_ok = 0
        mt_detail = []
        for uid in running:
            try:
                st = await asyncio.wait_for(_mt.get_stats(uid), timeout=4.0)
                conns = (st or {}).get("total_special_connections", 0)
                mt_ok += 1
                mt_detail.append({"uuid": uid[:8], "connections": conns})
            except Exception:
                mt_detail.append({"uuid": uid[:8], "error": "stats در دسترس نیست"})
        sec("mtproto", True, instances=len(running), detail=mt_detail)
    except Exception as exc:
        sec("mtproto", False, error=str(exc)[:120])

    # ۶) TCP Proxies ریلوی
    try:
        proxies = await _list_tcp_proxies()
        sec("tcp_proxies", True, count=len(proxies),
            detail=[{"domain": p.get("domain"), "port": p.get("proxyPort")} for p in proxies[:8]])
    except Exception as exc:
        sec("tcp_proxies", False, error=str(exc)[:120])

    # ۷) گیت‌وی کلادفلر (گیمینگ)
    try:
        import gaming_boost as _gb
        cfg = _gb._load_cfg()
        wd = cfg.get("worker_domain")
        if wd:
            res = await _gb._call_worker(cfg, "/gateway-status?check=1")
            sec("cf_gateway", bool(res.get("ok")),
                worker=wd, version=res.get("version"),
                location_health=res.get("location_health"),
                detail="گیت‌وی کلادفلر فعال" if res.get("ok") else res.get("error", "گیت‌وی پاسخ نداد"))
        else:
            sec("cf_gateway", True, configured=False,
                detail="گیت‌وی کلادفلر تنظیم نشده (اختیاری) — تب گیمینگ")
    except Exception as exc:
        sec("cf_gateway", True, configured=False, error=str(exc)[:120])

    # ۸) پل ایران
    try:
        import bridge_boost as _bb
        bcfg = _bb._load_cfg()
        sec("bridge", True, configured=bool(bcfg.get("bridge_host")),
            mode=bcfg.get("mode"), host=bcfg.get("bridge_host") or None,
            detail="پل تنظیم نشده (اختیاری)" if not bcfg.get("bridge_host") else "پل ایران فعال")
    except Exception as exc:
        sec("bridge", True, configured=False, error=str(exc)[:120])

    return report


# ══════════════════════════════════════════════════════════════════════════════
# register_routes
# ══════════════════════════════════════════════════════════════════════════════

def register_routes(app) -> None:

    @app.get("/api/system/infra/status")
    async def infra_status(_=Depends(require_auth)):
        ids = _service_ids()
        return {
            "ok": True,
            "volume_mounted": volume_mounted(),
            "data_dir": str(DATA_DIR),
            "on_railway": bool(ids["service_id"]),
            "service_ids": {k: (v[:8] + "…" if v else None) for k, v in ids.items()},
            "has_railway_token": bottokentcpproxy.has_saved_token(),
            "uptime_sec": round(time.time() - _STARTED_AT, 1),
        }

    @app.post("/api/system/infra/ensure-volume")
    async def infra_ensure_volume(request: Request, _=Depends(require_auth)):
        # توکن را می‌توان در همین درخواست هم فرستاد
        try:
            body = await request.json()
        except Exception:
            body = {}
        token = str(body.get("token", "")).strip()
        if token:
            bottokentcpproxy.save_token(token)
        return await ensure_volume()

    @app.get("/api/system/health-all")
    async def infra_health_all(_=Depends(require_auth)):
        return await asyncio.wait_for(health_all(), timeout=45.0)

    logger.info("[infra] ماژول زیرساخت ریلوی فعال شد — volume خودکار + سلامت‌سنجی کامل")
