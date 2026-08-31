# multiloc.py — Multi-Location Bridge v2 (پل هوشمند چندلوکیشن)
# ══════════════════════════════════════════════════════════════════════════════
# 🎯 معماری «Worker-Terminated Egress» (WTE) — ۱۰۰٪ عملی، بدون سرور اضافه:
#
#   کاربر ──► IP آنیکست کلادفلر (ورودی انتخابی / colo-pinned) ──► Worker v2
#            ├── حالت «خروج CF»  : تونل VLESS داخل خود وورکر خاتمه می‌یابد؛
#            │   خروج اینترنت از همان colo اجرا → سایت‌ها IP کلادفلر می‌بینند
#            │   (نه IP ریلوی آمستردام!) — این همان «جعل خروجی» واقعی است.
#            └── حالت «تونل پایدار»: مسیر /loc/{name} → بک‌اند Railway (مثل قبل)
#
# 🧪 دیباگ فوق پیشرفته (شواهد زنده، نه حدس):
#   - اسکنر colo: پروب واقعی TLS + GET /cdn-cgi/trace روی IPهای کلادفلر →
#     نقشه‌ی تاییدشده‌ی IP → colo + RTT. هر ادعا با هندشیک واقعی اثبات می‌شود.
#   - SNI-Trace: کلاینتی با SNI جعلی به ingress ریلوی/لبه‌ی CF وصل می‌شود و
#     نتیجه‌ی هندشیک + کد HTTP برگردانده می‌شود → جعل SNI با مدرک، نه ادعا.
#   - Egress-check: از طریق IP پین‌شده، /egress-test وورکر صدا زده می‌شود →
#     IP و کشورِ خروج واقعی که سایت‌ها می‌بینند.
#
# 🔒 فلسفه‌ی جداسازی (مثل bridge_boost / link_health):
#   هیچ فایلی در protocol/ یا منطق اصلی تغییر نمی‌کند. اگر این فایل حذف شود
#   پنل و همه‌ی تونل‌ها مثل قبل کار می‌کنند. همه‌ی اندپوینت‌ها auth دارند.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import json
import re
import socket
import ssl
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote, unquote

import httpx
from fastapi import Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from main import (
    LINKS,
    LINKS_LOCK,
    DATA_DIR,
    get_host,
    generate_share_link,
    is_link_allowed,
    require_auth,
    logger,
)

MULTILOC_VERSION = "2.0.0"
SCAN_FILE = DATA_DIR / "multiloc_scan.json"
SCAN_TTL = 600.0          # کش اسکن: ۱۰ دقیقه
PROBE_TIMEOUT = 6.0
SCAN_CONCURRENCY = 12

# ─── استخر IPهای آنیکست کلادفلر (کاندیدای اسکن) ────────────────────────────
# اینها رنج‌های پایدار و منتشرشده‌ی CF هستند؛ اسکنر به‌صورت زنده سلامتشان را
# تأیید می‌کند و فقط IPهای «هندشیک موفق + سرو کردن دامنه‌ی وورکر ما» را نگه
# می‌دارد. هیچ IP بدون تایید به کاربر داده نمی‌شود.
CF_CANDIDATES_BASE = [
    "104.16.132.229", "104.16.133.229", "104.17.147.22", "104.17.4.4",
    "104.17.214.7", "104.17.25.7", "104.18.32.7", "104.18.43.7",
    "104.19.195.7", "104.20.7.7", "104.21.0.7", "104.21.16.7",
    "104.22.7.7", "104.24.7.7", "104.26.7.7", "104.27.7.7",
    "104.28.7.7", "172.64.36.1", "172.64.149.15", "172.64.150.15",
    "172.64.151.15", "172.66.0.1", "172.67.12.7", "162.159.136.7",
    "162.159.137.7", "162.159.140.10", "162.159.152.7", "188.114.96.3",
    "188.114.97.3", "188.114.98.3", "188.114.99.3", "190.93.244.7",
]

# ─── متادیتای coloها (شهر فارسی + پرچم) ─────────────────────────────────────
COLO_META = {
    "AMS": ("آمستردام", "🇳🇱"), "FRA": ("فرانکفورت", "🇩🇪"), "IST": ("استانبول", "🇹🇷"),
    "LHR": ("لندن", "🇬🇧"), "CDG": ("پاریس", "🇫🇷"), "MRS": ("مارسی", "🇫🇷"),
    "MIL": ("میلان", "🇮🇹"), "MXP": ("میلان", "🇮🇹"), "FCO": ("رم", "🇮🇹"),
    "VIE": ("وین", "🇦🇹"), "WAW": ("ورشو", "🇵🇱"), "PRG": ("پراگ", "🇨🇿"),
    "ZRH": ("زوریخ", "🇨🇭"), "MUC": ("مونیخ", "🇩🇪"), "BER": ("برلین", "🇩🇪"),
    "DUB": ("دوبلین", "🇮🇪"), "CPH": ("کپنهاگ", "🇩🇰"), "ARN": ("استکهلم", "🇸🇪"),
    "OSL": ("اسلو", "🇳🇴"), "HEL": ("هلسینکی", "🇫🇮"), "MAD": ("مادرید", "🇪🇸"),
    "BCN": ("بارسلونا", "🇪🇸"), "LIS": ("لیسبون", "🇵🇹"), "DXB": ("دبی", "🇦🇪"),
    "BAH": ("بحرین", "🇧🇭"), "DOH": ("دوحه", "🇶🇦"), "RUH": ("ریاض", "🇸🇦"),
    "KWI": ("کویت", "🇰🇼"), "TLV": ("تل‌آویو", "🇮🇱"), "AMM": ("امّان", "🇯🇴"),
    "BGW": ("بغداد", "🇮🇶"), "KIV": ("کیشیناو", "🇲🇩"), "DME": ("مسکو", "🇷🇺"),
    "SVO": ("مسکو", "🇷🇺"), "TAS": ("تاشکند", "🇺🇿"), "ALA": ("آلماتی", "🇰🇿"),
    "NUR": ("نورسلطان", "🇰🇿"), "SIN": ("سنگاپور", "🇸🇬"), "HKG": ("هنگ‌کنگ", "🇭🇰"),
    "NRT": ("توکیو", "🇯🇵"), "KIX": ("اوساکا", "🇯🇵"), "ICN": ("سئول", "🇰🇷"),
    "BOM": ("مومبای", "🇮🇳"), "DEL": ("دهلی", "🇮🇳"), "MAA": ("چنای", "🇮🇳"),
    "LAX": ("لس‌آنجلس", "🇺🇸"), "SJC": ("سان‌خوزه", "🇺🇸"), "SEA": ("سیاتل", "🇺🇸"),
    "DFW": ("دالاس", "🇺🇸"), "ORD": ("شیکاگو", "🇺🇸"), "IAD": ("واشنگتن", "🇺🇸"),
    "EWR": ("نیوجرسی", "🇺🇸"), "MIA": ("میامی", "🇺🇸"), "ATL": ("آتلانتا", "🇺🇸"),
    "YYZ": ("تورنتو", "🇨🇦"), "YVR": ("ونکوور", "🇨🇦"), "GRU": ("سائوپائولو", "🇧🇷"),
    "EZE": ("بوئنوس‌آیرس", "🇦🇷"), "SCL": ("سانتیاگو", "🇨🇱"), "JNB": ("ژوهانسبورگ", "🇿🇦"),
    "CPT": ("کیپ‌تاون", "🇿🇦"), "LOS": ("لاگوس", "🇳🇬"), "CAI": ("قاهره", "🇪🇬"),
    "TLV2": ("تل‌آویو", "🇮🇱"),
}

_scan_cache: dict = {"ts": 0.0, "locations": []}
_scan_lock = asyncio.Lock()


def _load_scan() -> dict:
    try:
        if SCAN_FILE.exists():
            raw = json.loads(SCAN_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("ts") and raw.get("locations"):
                return raw
    except Exception as exc:
        logger.warning(f"[multiloc] could not load scan cache: {exc}")
    return {"ts": 0.0, "locations": []}


def _save_scan(cache: dict) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SCAN_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"[multiloc] could not save scan cache: {exc}")


# ─── تنظیمات وورکر (هم‌living با بخش گیمینگ — بدون تغییر دوباره) ───────────
def _worker_cfg() -> dict:
    """دامنه/توکن وورکر از تنظیمات گیمینگ + env — یک منبع حقیقت برای کل پنل."""
    domain = ""
    token = ""
    try:
        import gaming_boost
        cfg = gaming_boost._load_cfg()
        domain = gaming_boost._norm_domain(cfg.get("worker_domain", ""))
        token = cfg.get("worker_token", "") or ""
    except Exception:
        pass
    if not domain:
        domain = ("" + __import__("os").environ.get("EMIX_CDN_DOMAIN", "")).strip().lower()
    return {"worker_domain": domain, "worker_token": token}


# ─── پروب خام: TCP + TLS (SNI دلخواه) + GET — قلب دیباگ زنده ───────────────
def _tls_probe_sync(ip: str, sni: str, path: str = "/", host_hdr: str | None = None,
                    timeout: float = PROBE_TIMEOUT, verify: bool = False) -> dict:
    out = {"ip": ip, "sni": sni, "path": path, "tcp_ok": False, "tls_ok": False,
           "tls_version": None, "rtt_ms": None, "http_status": None,
           "body": None, "colo": None, "error": None}
    sock = None
    try:
        t0 = time.monotonic()
        sock = socket.create_connection((ip, 443), timeout=timeout)
        out["tcp_ok"] = True
        ctx = ssl.create_default_context()
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        try:
            # مهم: فقط http/1.1 — اگر h2 مذاکره شود پاسخ باینری است و متن
            # trace/cdn-cgi قابل parse نیست. پروب ما HTTP/1.1 خام می‌فرستد.
            ctx.set_alpn_protocols(["http/1.1"])
        except Exception:
            pass
        s = ctx.wrap_socket(sock, server_hostname=sni)
        sock = s
        out["tls_ok"] = True
        out["tls_version"] = s.version()
        out["rtt_ms"] = round((time.monotonic() - t0) * 1000, 1)
        h = host_hdr or sni
        req = (f"GET {path} HTTP/1.1\r\nHost: {h}\r\nUser-Agent: EMIX-MultiLoc/2.0\r\n"
               f"Accept: */*\r\nConnection: close\r\n\r\n")
        s.sendall(req.encode())
        data = b""
        s.settimeout(timeout)
        try:
            while len(data) < 8192:
                chunk = s.recv(8192 - len(data))
                if not chunk:
                    break
                data += chunk
        except Exception:
            pass
        if data:
            text = data.decode("utf-8", "replace")
            out["http_status"] = text.split("\r\n")[0][:60] if "\r\n" in text else text[:60]
            out["body"] = text[-6000:]
            m = re.search(r"(?:^|\n)colo=([A-Z]{3})", text)
            if m:
                out["colo"] = m.group(1)
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"[:140]
    finally:
        try:
            if sock is not None:
                sock.close()
        except Exception:
            pass
    return out


async def _tls_probe(ip: str, sni: str, path: str = "/", host_hdr: str | None = None,
                    timeout: float = PROBE_TIMEOUT) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: _tls_probe_sync(ip, sni, path=path, host_hdr=host_hdr, timeout=timeout))


# ─── اسکن colo: نقشه‌ی تاییدشده‌ی IP → PoP ─────────────────────────────────
async def scan_colos(force: bool = False, deep: bool = False) -> dict:
    global _scan_cache
    async with _scan_lock:
        if not force and _scan_cache.get("ts") and time.time() - _scan_cache["ts"] < SCAN_TTL:
            return {"ok": True, "cached": True, **_scan_cache}
        cached = _load_scan()
        if not force and cached.get("ts") and time.time() - cached["ts"] < SCAN_TTL:
            _scan_cache = cached
            return {"ok": True, "cached": True, **cached}

        cfg = _worker_cfg()
        domain = cfg["worker_domain"]
        if not domain:
            return {
                "ok": False,
                "error": "دامنه‌ی Worker کلادفلر تنظیم نشده — در «مرکز گیمینگ» یا متغیر "
                         "EMIX_CDN_DOMAIN دامنه‌ی workers.dev را ذخیره کنید تا اسکنر بتواند "
                         "IPها را با SNI درست پروب کند.",
            }

        candidates = list(CF_CANDIDATES_BASE)
        if deep:
            extra = []
            for base in ("104.17.147", "104.21.16", "172.64.150", "172.67.12",
                         "162.159.136", "188.114.96", "188.114.97", "104.24.7"):
                for last in (7, 8, 12, 22, 45, 63, 111, 190):
                    extra.append(f"{base}.{last}")
            candidates += [ip for ip in extra if ip not in candidates]

        sem = asyncio.Semaphore(SCAN_CONCURRENCY)
        results: list[dict] = []

        async def one(ip: str):
            async with sem:
                r = await _tls_probe(ip, domain, "/cdn-cgi/trace", host_hdr=domain, timeout=PROBE_TIMEOUT)
                return r

        results = await asyncio.gather(*[one(ip) for ip in candidates], return_exceptions=True)
        errors = [r for r in results if not isinstance(r, dict)]
        results = [r for r in results if isinstance(r, dict)]
        if errors:
            logger.warning(f"[multiloc] scan: {len(errors)} probes raised — first: {type(errors[0]).__name__}: {errors[0]}")

        by_colo: dict[str, list[dict]] = {}
        dead = 0
        for r in results:
            if r.get("tls_ok") and r.get("colo"):
                by_colo.setdefault(r["colo"], []).append(
                    {"ip": r["ip"], "rtt_ms": r.get("rtt_ms")})
            else:
                dead += 1

        locations = []
        for colo, ips in by_colo.items():
            ips.sort(key=lambda x: x.get("rtt_ms") or 9999)
            city, flag = COLO_META.get(colo, (colo, "🌍"))
            locations.append({
                "key": colo.lower(),
                "colo": colo,
                "city": city,
                "flag": flag,
                "ips": ips[:4],
                "best_ip": ips[0]["ip"] if ips else None,
                "rtt_ms": ips[0].get("rtt_ms") if ips else None,
                "verified": True,
            })
        locations.sort(key=lambda x: x.get("rtt_ms") or 9999)

        # لوکیشن همیشه‌حاضر: خود دامنه‌ی وورکر (بدون پین IP — هر coloای که ISP کاربر بدهد)
        city0, flag0 = ("Auto — نزدیک‌ترین PoP به ISP شما", "🌍")
        auto_loc = {"key": "auto", "colo": None, "city": city0, "flag": flag0,
                    "ips": [], "best_ip": domain, "rtt_ms": None, "verified": True}
        locations.insert(0, auto_loc)

        payload = {"ts": time.time(), "domain": domain, "locations": locations,
                   "stats": {"probed": len(candidates), "alive": sum(len(v) for v in by_colo.values()),
                             "dead": dead, "colos": len(by_colo)}}
        _scan_cache = payload
        _save_scan(payload)
        logger.info(f"[multiloc] scan done: {len(candidates)} probed, "
                    f"{len(by_colo)} colos, {dead} dead")
        return {"ok": True, "cached": False, **payload}


# ─── SNI-Trace: دیباگ فوق پیشرفته‌ی جعل SNI با مدرک زنده ─────────────────────
async def sni_trace(spoof_sni: str) -> dict:
    """سه آزمون واقعی:
    A) کنترل — SNI واقعی پنل → باید OK باشد
    B) جعل مستقیم به ingress ریلوی با SNI جعلی → آیا هندشیک زنده می‌ماند؟
       (اگر OK: حالت allowInsecure واقعاً کار می‌کند و DPI دقیقاً SNI جعلی را می‌بیند)
    C) جعل به لبه‌ی کلادفلر با SNI جعلی → CF با SNI روت می‌کند؛
       انتظار: fail/403 → یعنی «حالت CDN» فقط با دامنه‌ی خودِ کاربر روی CF ممکن است.
    """
    spoof = (spoof_sni or "").strip().lower().rstrip(".")
    out = {"spoof_sni": spoof, "tests": {}, "verdicts": [], "ok": False}
    if not spoof or "." not in spoof:
        out["error"] = "دامنه‌ی SNI معتبر وارد کنید (مثل www.microsoft.com)"
        return out

    host = get_host()
    try:
        panel_ip = socket.gethostbyname(host)
    except Exception as exc:
        out["error"] = f"DNS پنل ناموفق: {exc}"
        return out

    # A) کنترل
    ctrl = await _tls_probe(panel_ip, host, "/api/ping", host_hdr=host)
    out["tests"]["panel_control"] = {
        "target": f"{panel_ip} ({host})", "sni": host,
        "tls_ok": ctrl["tls_ok"], "rtt_ms": ctrl["rtt_ms"],
        "http": ctrl["http_status"],
    }

    # B) جعل مستقیم ریلوی
    fake = await _tls_probe(panel_ip, spoof, "/api/ping", host_hdr=host)
    b_ok = bool(fake["tls_ok"] and fake["http_status"] and " 200 " in fake["http_status"])
    out["tests"]["railway_fake_sni"] = {
        "target": f"{panel_ip} ({host})", "sni": spoof,
        "tls_ok": fake["tls_ok"], "rtt_ms": fake["rtt_ms"],
        "http": fake["http_status"], "error": fake["error"],
    }
    if b_ok:
        out["verdicts"].append({
            "mode": "railway_direct", "ok": True,
            "msg": f"جعل SNI روی اتصال مستقیم ریلوی کار می‌کند: هندشیک TLS با SNI «{spoof}» "
                   f"کامل شد و لایه‌ی HTTP با Host درست به پنل رسید (HTTP 200). "
                   "لینک این حالت allowInsecure=1 دارد و DPI دقیقاً همین SNI جعلی را می‌بیند.",
        })
    else:
        out["verdicts"].append({
            "mode": "railway_direct", "ok": False,
            "msg": f"هندشیک با SNI «{spoof}» به ingress ریلوی کامل نشد "
                   f"({fake['error'] or fake['http_status']}) — این دامنه را با SNI-Trace دیگری تست کن.",
        })

    # C) جعل به لبه‌ی CF (اگر وورکر تنظیم شده)
    cfg = _worker_cfg()
    domain = cfg["worker_domain"]
    if domain:
        cf_ip = None
        cached = _scan_cache if _scan_cache.get("locations") else _load_scan()
        for loc in cached.get("locations", []):
            if loc.get("best_ip") and loc["key"] != "auto":
                cf_ip = loc["best_ip"]
                break
        if not cf_ip:
            cf_ip = "104.17.147.22"
        cf = await _tls_probe(cf_ip, spoof, "/gateway-status", host_hdr=domain)
        c_ok = bool(cf["tls_ok"] and cf["http_status"] and " 200 " in cf["http_status"])
        out["tests"]["cloudflare_fake_sni"] = {
            "target": f"{cf_ip} ({domain})", "sni": spoof,
            "tls_ok": cf["tls_ok"], "http": cf["http_status"], "error": cf["error"],
        }
        if c_ok:
            out["verdicts"].append({
                "mode": "cdn", "ok": True,
                "msg": f"دامنه‌ی «{spoof}» روی همین اکانت CF سرو می‌شود — حالت CDN با این "
                       "fronting واقعاً کار می‌کند (بدون allowInsecure).",
            })
        else:
            out["verdicts"].append({
                "mode": "cdn", "ok": False,
                "msg": "لبه‌ی کلادفلر با SNI جعلی روت نمی‌کند (انتظار: handshake-fail/403). "
                       "«حالت CDN» فقط وقتی SNI واقعاً روی اکانت CF شما سرو شود ممکن است؛ "
                       "در غیر این صورت حالت مستقیم (بالای) را با allowInsecure=1 استفاده کن. "
                       "این رفتار با SNI-Trace زنده اثبات شد، نه حدس.",
            })

    out["ok"] = any(v["ok"] for v in out["verdicts"])
    return out


# ─── فراخوانی وورکر ─────────────────────────────────────────────────────────
async def _worker_get(path: str, timeout: float = 12.0) -> dict:
    cfg = _worker_cfg()
    domain = cfg["worker_domain"]
    if not domain:
        return {"ok": False, "error": "دامنه‌ی Worker تنظیم نشده"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as cli:
            r = await cli.get(f"https://{domain}{path}")
            try:
                return r.json()
            except Exception:
                return {"ok": False, "error": f"پاسخ غیر JSON ({r.status_code})", "status": r.status_code}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def _worker_admin(path: str, payload: dict, timeout: float = 15.0) -> dict:
    cfg = _worker_cfg()
    domain, token = cfg["worker_domain"], cfg["worker_token"]
    if not domain:
        return {"ok": False, "error": "دامنه‌ی Worker تنظیم نشده"}
    if not token:
        return {"ok": False, "error": "توکن EMIX_TOKEN وورکر در بخش گیمینگ ذخیره نشده"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as cli:
            r = await cli.request("POST", f"https://{domain}{path}",
                                  json=payload, headers={"x-emix-token": token})
            try:
                return r.json()
            except Exception:
                return {"ok": False, "error": f"پاسخ غیر JSON ({r.status_code})", "status": r.status_code}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def worker_status() -> dict:
    st = await _worker_get("/gateway-status")
    if not st.get("ok"):
        return {"ok": False, "reachable": False, "error": st.get("error", "unreachable")}
    ver = str(st.get("version", ""))
    major = int(ver.split(".")[0]) if ver.split(".")[0].isdigit() else 0
    return {
        "ok": True, "reachable": True, "version": ver,
        "supports_wte": major >= 2,
        "kv_bound": st.get("kv_bound"), "token_set": st.get("token_set"),
        "colo": st.get("colo"), "locations_count": len(st.get("locations", [])),
    }


# ─── ساخت لینک‌های پل ───────────────────────────────────────────────────────
def _replace_query_param(url: str, key: str, value: str) -> str:
    return re.sub(rf"([?&]{key}=)[^&#]*", rf"\g<1>{value}", url)


def _forge_vless_link(uuid: str, worker_domain: str, addr: str, remark: str) -> str:
    """لینک VLESS با خاتمه‌ی تونل داخل وورکر (حالت WTE — خروج CF از colo اجرا)."""
    params = {
        "encryption": "none", "security": "tls", "sni": worker_domain,
        "host": worker_domain, "type": "ws", "path": "/vl",
        "fp": "chrome", "alpn": "h2,http/1.1",
    }
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return f"vless://{uuid}@{addr}:443?{query}#{quote(remark)}"


def _tunnel_link(original: str, loc_key: str, addr: str, worker_domain: str) -> str | None:
    """بازنویسی لینک موجود به مسیر /loc/{key} از طریق IP پین‌شده (خروج Railway)."""
    try:
        if not original.startswith(("vless://", "trojan://")):
            return None
        p = urlparse(original)
        userinfo = p.username or ""
        out = original.replace(f"{p.scheme}://{p.netloc}", f"{p.scheme}://{userinfo}@{addr}:443", 1)
        qs = parse_qs(p.query)
        old_path = unquote((qs.get("path") or ["/"])[0])
        if not old_path.startswith("/"):
            old_path = "/" + old_path
        new_path = f"/loc/{loc_key}{old_path}"
        out = _replace_query_param(out, "path", quote(new_path, safe=""))
        out = _replace_query_param(out, "host", worker_domain)
        out = _replace_query_param(out, "sni", worker_domain)
        out = _replace_query_param(out, "allowInsecure", "0")
        return out
    except Exception:
        return None


async def build_links(uuid: str | None, mode: str = "worker",
                      colos: list[str] | None = None) -> dict:
    """ساخت لینک‌های پل برای یک کانفیگ (یا همه‌ی کانفیگ‌های مجاز).
    mode=worker → خروج CF (WTE) · mode=railway → تونل پایدار از طریق /loc"""
    cfg = _worker_cfg()
    domain = cfg["worker_domain"]
    if not domain:
        return {"ok": False, "error": "دامنه‌ی Worker کلادفلر تنظیم نشده — از «مرکز گیمینگ» ذخیره کنید"}
    if mode not in ("worker", "railway"):
        return {"ok": False, "error": "mode باید worker یا railway باشد"}

    scan = _scan_cache if _scan_cache.get("locations") else _load_scan()
    locations = scan.get("locations", [])
    if not locations:
        sr = await scan_colos(force=False)
        locations = sr.get("locations", [])
    if not locations:
        return {"ok": False, "error": "اول اسکن لوکیشن‌ها را اجرا کن تا IPهای تاییدشده ساخته شوند"}

    wanted = {c.lower() for c in (colos or [])} if colos else None
    if wanted:
        locations = [l for l in locations if l["key"] in wanted] or locations

    host = get_host()
    async with LINKS_LOCK:
        snap = {uid: dict(d) for uid, d in LINKS.items() if is_link_allowed(d)}
    if uuid:
        if uuid not in snap:
            return {"ok": False, "error": "کانفیگ یافت نشد یا مجاز نیست"}
        targets = {uuid: snap[uuid]}
    else:
        targets = snap

    links_out = []
    auto_sync_note = None
    for uid, d in targets.items():
        proto = d.get("protocol", "vless-ws")
        base_label = d.get("label", uid[:8])
        for loc in locations:
            addr = loc.get("best_ip") or domain
            loc_key = loc["key"]
            city, flag = loc.get("city", loc_key), loc.get("flag", "🌍")
            rtt = f" · {int(loc['rtt_ms'])}ms" if loc.get("rtt_ms") else ""
            if mode == "worker":
                if not proto.startswith("vless"):
                    # trojan/ss → در وورکر خاتمه نمی‌یابد؛ مسیر tunnel
                    original = generate_share_link(uid, host, remark=base_label, protocol=proto)
                    url = _tunnel_link(original, "auto" if loc_key == "auto" else loc_key,
                                       addr, domain)
                    exit_label = "Railway"
                else:
                    url = _forge_vless_link(uid, domain, addr, f"{flag} {city}{rtt} · خروج CF")
                    exit_label = "Cloudflare (وورکر)"
                if not url:
                    continue
                links_out.append({
                    "uuid": uid, "label": base_label, "protocol": proto,
                    "location": loc_key, "city": city, "flag": flag,
                    "colo": loc.get("colo"), "addr": addr,
                    "rtt_ms": loc.get("rtt_ms"), "exit": exit_label,
                    "url": url,
                })
            else:  # railway tunnel
                original = generate_share_link(uid, host, remark=base_label, protocol=proto)
                url = original if loc_key == "auto" else _tunnel_link(
                    original, loc_key, addr, domain)
                if not url:
                    continue
                remark = quote(f"{flag} {city}{rtt} · تونل")
                url = url.split("#")[0] + "#" + remark
                links_out.append({
                    "uuid": uid, "label": base_label, "protocol": proto,
                    "location": loc_key, "city": city, "flag": flag,
                    "colo": loc.get("colo"), "addr": addr,
                    "rtt_ms": loc.get("rtt_ms"), "exit": "Railway (آمستردام)",
                    "url": url,
                })

    if not links_out:
        return {"ok": False, "error": "کانفیگ قابل پلی‌سازی پیدا نشد (حداقل یک VLESS/Trojan فعال لازم است)"}
    # سینک خودکار UUIDها به وورکر (حالت worker) — بدون دخالت کاربر؛
    # اگر توکن نبود یا وورکر v1 بود، فقط یادداشت اضافه می‌شود و ساخت لینک ادامه می‌یابد.
    if mode == "worker":
        try:
            sync = await sync_worker()
            if sync.get("ok"):
                auto_sync_note = f"{sync.get('pushed', 0)} UUID به وورکر سینک شد (خودکار)"
            else:
                auto_sync_note = f"سینک خودکار نشد: {sync.get('error', '')} — لینک‌ها ساخته شدند ولی تا سینک/آپگرید وورکر v2، حالت CF کار نمی‌کند."
        except Exception as exc:
            auto_sync_note = f"سینک خودکار ناموفق: {exc}"

    return {
        "ok": True, "mode": mode, "worker_domain": domain,
        "count": len(links_out), "links": links_out,
        "auto_sync": auto_sync_note,
        "mode_label": "خروج CF — جعل خروجی" if mode == "worker" else "تونل پایدار — خروج Railway",
    }


# ─── تست خروج واقعی از طریق IP پین‌شده ──────────────────────────────────────
async def egress_check(ip: str) -> dict:
    cfg = _worker_cfg()
    domain = cfg["worker_domain"]
    if not domain:
        return {"ok": False, "error": "دامنه‌ی Worker تنظیم نشده"}
    if ip in ("auto", "", domain):
        async with httpx.AsyncClient(timeout=15.0) as cli:
            try:
                r = await cli.get(f"https://{domain}/egress-test")
                return r.json()
            except Exception as exc:
                return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    r = await _tls_probe(ip, domain, "/egress-test", host_hdr=domain, timeout=12.0)
    if not r.get("tls_ok"):
        return {"ok": False, "error": f"اتصال به {ip} ناموفق: {r.get('error')}"}
    try:
        body = (r.get("body") or "")
        idx = body.find("{")
        data = json.loads(body[idx:]) if idx >= 0 else {}
        data["via_ip"] = ip
        data["http"] = r.get("http_status")
        return data
    except Exception:
        return {"ok": False, "via_ip": ip, "http": r.get("http_status"),
                "error": "وورکر /egress-test ندارد — Worker v2 (WTE) را دیپلوی کن"}


# ─── سینک UUIDها به وورکر ───────────────────────────────────────────────────
async def sync_worker() -> dict:
    async with LINKS_LOCK:
        snap = {uid: dict(d) for uid, d in LINKS.items()}
    uuids = [uid for uid, d in snap.items()
             if d.get("active", True) and d.get("protocol", "vless-ws").startswith("vless")]
    payload = {"uuids": uuids}
    scan = _scan_cache if _scan_cache.get("locations") else _load_scan()
    if scan.get("locations"):
        payload["pools"] = {
            l["key"]: [i["ip"] for i in l.get("ips", [])][:3]
            for l in scan["locations"] if l.get("ips")
        }
    res = await _worker_admin("/admin/vless-uuids", payload)
    res["pushed"] = len(uuids)
    return res


# ══════════════════════════════════════════════════════════════════════════════
# ثبت اندپوینت‌ها — تنها نقطه‌ی تماس با app
# ══════════════════════════════════════════════════════════════════════════════
def register_routes(app) -> None:

    @app.get("/api/multiloc/status")
    async def api_status(_=Depends(require_auth)):
        cfg = _worker_cfg()
        ws = await worker_status()
        scan = _scan_cache if _scan_cache.get("locations") else _load_scan()
        return JSONResponse({
            "ok": True, "multiloc_version": MULTILOC_VERSION,
            "panel_host": get_host(),
            "worker_domain": cfg["worker_domain"],
            "worker_token_set": bool(cfg["worker_token"]),
            "worker": ws,
            "last_scan": scan.get("ts"),
            "locations_cached": len(scan.get("locations", [])),
            "ready": bool(cfg["worker_domain"] and ws.get("reachable")),
        })

    @app.post("/api/multiloc/scan")
    async def api_scan(request: Request, _=Depends(require_auth)):
        try:
            body = await request.json()
        except Exception:
            body = {}
        res = await scan_colos(force=True, deep=bool(body.get("deep")))
        return JSONResponse(res)

    @app.get("/api/multiloc/locations")
    async def api_locations(_=Depends(require_auth)):
        res = await scan_colos(force=False)
        return JSONResponse(res)

    @app.post("/api/multiloc/links")
    async def api_links(request: Request, _=Depends(require_auth)):
        try:
            body = await request.json()
        except Exception:
            body = {}
        res = await build_links(
            body.get("uuid") or None,
            mode=body.get("mode", "worker"),
            colos=body.get("colos"),
        )
        return JSONResponse(res)

    @app.post("/api/multiloc/sni-trace")
    async def api_sni_trace(request: Request, _=Depends(require_auth)):
        try:
            body = await request.json()
        except Exception:
            body = {}
        res = await sni_trace(str(body.get("sni") or ""))
        return JSONResponse(res)

    @app.get("/api/multiloc/egress-check")
    async def api_egress(ip: str = "auto", _=Depends(require_auth)):
        res = await egress_check(ip)
        return JSONResponse(res)

    @app.post("/api/multiloc/sync-worker")
    async def api_sync(_=Depends(require_auth)):
        res = await sync_worker()
        return JSONResponse(res)

    @app.get("/api/multiloc/worker-code")
    async def api_worker_code(_=Depends(require_auth)):
        """کد کامل وورکر v2 (WTE) برای کپی مستقیم در dash.cloudflare.com."""
        try:
            f = Path(__file__).parent / "cf_gateway_worker.js"
            code = f.read_text(encoding="utf-8")
            return PlainTextResponse(code, media_type="text/javascript; charset=utf-8")
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
