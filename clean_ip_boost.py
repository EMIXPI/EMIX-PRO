# clean_ip_boost.py
# ══════════════════════════════════════════════════════════════════════════════
# آی‌پی‌های تمیز (Clean IPs) — اسکن لبه‌های اروان + لینک‌های IP-دار
#
# 🎯 چیست؟ (تکنیک کلاسیک Clean IP، این‌بار برای لبه‌ی اروان)
#   وقتی پل CDN فعال است، کلاینت به دامنه‌ی اروان وصل می‌شود. بعضی IPهای لبه
#   برای ISP شما سریع‌تر و بعضی محدود/کندترند. این ماژول:
#     ۱) لیست IPهای رسمی اروان را می‌گیرد (arvancloud.ir/en/ips.txt)
#     ۲) سمت سرور فقط IPهایی را نگه می‌دارد که واقعاً دامنه‌ی شما را سرو می‌کنند
#        (اتصال TLS با SNI=دامنه‌ی پل و تایید گواهی)
#     ۳) سمت «مرورگر ادمین» (داخل ایران) تاخیر هر IP سنجیده می‌شود → واقعی‌ترین
#        معیار ممکن، چون از همان اینترنت کاربر تست می‌گیرد
#     ۴) برای هر کانفیگ، لینکِ «آی‌پی‌دار» می‌سازد: address=IP تمیز،
#        host/sni همان دامنه‌ی پل می‌ماند (مسیردهی با SNI انجام می‌شود)
#
# 🔒 فلسفه جداسازی: مثل بقیه‌ی ماژول‌ها — state خودش، فایل JSON خودش،
#   صفر تغییر در هسته. حذفش = فقط این بخش از UI غیب می‌شود.
#
# ⚙️ اندپوینت‌ها:
#   GET  /api/clean-ips/arvan           → IPهای معتبر اروان برای دامنه‌ی پل فعلی
#   GET  /api/clean-ips/custom          → لیست IPهای دستی کاربر
#   POST /api/clean-ips/custom          → افزودن IP دستی
#   DELETE /api/clean-ips/custom        → حذف IP دستی
#   GET  /api/clean-ips/links?ip=…      → لینک‌های IP-دار همه‌ی کانفیگ‌ها
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import ipaddress
import random
import re
import ssl
import time
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import Depends, HTTPException

from main import (
    LINKS,
    LINKS_LOCK,
    DATA_DIR,
    get_host,
    require_auth,
    generate_share_link,
    is_link_allowed,
    logger,
)

CLEAN_IP_FILE = DATA_DIR / "clean_ips.json"
ARVAN_IPS_URL = "https://www.arvancloud.ir/en/ips.txt"
VALIDATE_TIMEOUT = 6.0
MAX_VALIDATE = 48          # حداکثر IP برای اعتبارسنجی هم‌زمان در هر اسکن
ARVAN_CACHE_TTL = 3600 * 6  # کش لیست رنج‌های اروان: ۶ ساعت

# کش درون‌حافظه
_arvan_ranges_cache: list[str] | None = None
_arvan_cache_at: float = 0.0


def _load_custom() -> dict:
    try:
        if CLEAN_IP_FILE.exists():
            data = __import__("json").loads(CLEAN_IP_FILE.read_text(encoding="utf-8"))
            return {"ips": list(data.get("ips", [])), "updated_at": data.get("updated_at")}
    except Exception as exc:
        logger.warning(f"[clean-ip] load failed: {exc}")
    return {"ips": [], "updated_at": None}


def _save_custom(ips: list[str]) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CLEAN_IP_FILE.write_text(
            __import__("json").dumps({"ips": ips, "updated_at": datetime.now().isoformat()}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning(f"[clean-ip] save failed: {exc}")


async def _arvan_ranges() -> list[str]:
    """لیست رنج‌های رسمی اروان (کش‌شده)."""
    global _arvan_ranges_cache, _arvan_cache_at
    now = time.time()
    if _arvan_ranges_cache and now - _arvan_cache_at < ARVAN_CACHE_TTL:
        return _arvan_ranges_cache
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            r = await client.get(ARVAN_IPS_URL)
            r.raise_for_status()
            ranges = [ln.strip() for ln in r.text.splitlines() if "/" in ln.strip()]
            if ranges:
                _arvan_ranges_cache = ranges
                _arvan_cache_at = now
                return ranges
    except Exception as exc:
        logger.warning(f"[clean-ip] arvan list fetch failed: {exc}")
    return _arvan_ranges_cache or []


def _sample_ips(ranges: list[str], limit: int) -> list[str]:
    """نمونه‌گیری تصادفی از رنج‌ها (هر رنج چند IP اول + تصادفی)."""
    out: list[str] = []
    for rng in ranges:
        try:
            net = ipaddress.ip_network(rng, strict=False)
            hosts = list(net.hosts())
            if not hosts:
                continue
            picks = [hosts[0], hosts[len(hosts) // 2], hosts[-1]]
            if len(hosts) > 8:
                picks += random.sample(hosts, min(3, len(hosts)))
            out += [str(h) for h in picks]
        except ValueError:
            continue
    random.shuffle(out)
    # حذف تکراری + محدودیت
    return list(dict.fromkeys(out))[:limit]


async def _validate_ip(ip: str, sni_domain: str) -> dict:
    """آیا این IP واقعاً دامنه‌ی پل را سرو می‌کند؟ (TLS با SNI + تایید گواهی)"""
    t0 = time.perf_counter()
    ctx = ssl.create_default_context()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, 443, ssl=ctx, server_hostname=sni_domain),
            timeout=VALIDATE_TIMEOUT,
        )
        ms = round((time.perf_counter() - t0) * 1000)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        return {"ip": ip, "valid": True, "server_ms": ms}
    except Exception as exc:
        return {"ip": ip, "valid": False, "error": f"{type(exc).__name__}"}


async def _clean_ip_links(ip: str) -> list[dict]:
    """برای هر کانفیگ فعال، لینکی با address=IP (host/sni دست‌نخورده) می‌سازد.
    فقط وقتی پل CDN فعال است معنی دارد (مسیردهی با SNI روی لبه انجام می‌شود)."""
    import bridge_boost
    cfg = bridge_boost._load_cfg()
    if not cfg.get("bridge_host"):
        return []
    host = get_host()
    async with LINKS_LOCK:
        snap = [(uid, dict(d)) for uid, d in LINKS.items()]
    out = []
    for uid, d in snap:
        proto = d.get("protocol", "vless-ws")
        if proto == "mtproto" or not is_link_allowed(d):
            continue
        # لینک پل‌دار مبنا (آدرس=دامنه‌ی پل) — سپس آدرس با IP جایگزین می‌شود
        bridged = bridge_boost._rewrite_link(
            generate_share_link(uid, host, remark=f"EMIX-{d['label']}", protocol=proto),
            cfg["bridge_host"], int(cfg.get("bridge_port", 443)),
            cfg.get("mode", "vps"),
        )
        if not bridged:
            continue
        import re as _re
        # جایگزینی فقط آدرسِ اتصال (بخش @host:port) با IP
        m = _re.match(r"^([a-z0-9+]+://[^@]+@)([^:/]+):(\d+)", bridged)
        if not m:
            continue
        clean = m.group(1) + ip + ":" + m.group(3) + bridged[m.end(3):]
        out.append({
            "uuid": uid,
            "label": d.get("label", uid[:8]),
            "protocol": proto,
            "link": clean,
        })
    return out


def register_routes(app) -> None:

    @app.get("/api/clean-ips/arvan")
    async def clean_ips_arvan(limit: int = 32, _=Depends(require_auth)):
        """اسکن لبه‌های اروان: نمونه‌گیری از رنج‌های رسمی + اعتبارسنجی SNI سمت سرور."""
        import bridge_boost
        cfg = bridge_boost._load_cfg()
        if not cfg.get("bridge_host"):
            raise HTTPException(status_code=400, detail="ابتدا پل (حالت CDN) را فعال کنید")
        if cfg.get("mode", "vps") != "cdn":
            raise HTTPException(status_code=400, detail="آی‌پی تمیز فقط برای حالت CDN معنا دارد")
        sni = cfg["bridge_host"]
        ranges = await _arvan_ranges()
        if not ranges:
            raise HTTPException(status_code=502, detail="لیست IPهای اروان در دسترس نیست — بعداً تلاش کنید")
        candidates = _sample_ips(ranges, min(limit, MAX_VALIDATE))
        sem = asyncio.Semaphore(12)

        async def _one(ip: str):
            async with sem:
                return await _validate_ip(ip, sni)

        results = await asyncio.gather(*[_one(ip) for ip in candidates])
        valid = sorted([r for r in results if r["valid"]], key=lambda r: r["server_ms"])
        return {
            "sni": sni,
            "total_checked": len(results),
            "valid": valid,
            "checked_at": datetime.now().isoformat(),
            "note": "تایید سرور انجام شد؛ برای تاخیر واقعی از اینترنت خودتان، در پنل دکمه‌ی «اسکن از مرورگر» را بزنید",
        }

    @app.get("/api/clean-ips/custom")
    async def clean_ips_custom_get(_=Depends(require_auth)):
        return _load_custom()

    @app.post("/api/clean-ips/custom")
    async def clean_ips_custom_add(request, _=Depends(require_auth)):
        body = await request.json()
        raw = str(body.get("ip", "")).strip()
        if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", raw):
            raise HTTPException(status_code=400, detail="آی‌پی نامعتبر است")
        data = _load_custom()
        if raw not in data["ips"]:
            data["ips"].append(raw)
            _save_custom(data["ips"])
        return {"ok": True, "ips": data["ips"]}

    @app.delete("/api/clean-ips/custom")
    async def clean_ips_custom_del(ip: str, _=Depends(require_auth)):
        data = _load_custom()
        if ip in data["ips"]:
            data["ips"].remove(ip)
            _save_custom(data["ips"])
        return {"ok": True, "ips": data["ips"]}

    @app.get("/api/clean-ips/links")
    async def clean_ips_links(ip: str, _=Depends(require_auth)):
        if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
            raise HTTPException(status_code=400, detail="آی‌پی نامعتبر است")
        links = await _clean_ip_links(ip)
        return {"ip": ip, "links": links}
