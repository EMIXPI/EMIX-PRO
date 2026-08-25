# gaming_boost.py
# ══════════════════════════════════════════════════════════════════════════════
# ماژول مرکز گیمینگ EMIX — اسکنر IP + پریست بازی + کانفیگ گیمینگ + مولتی‌لوکیشن
#
# 🎯 هدف:
#   قدرتمندترین بخش گیمینگ بین همه‌ی پنل‌های مشابه:
#     ۱) اسکنر IP کلادفلر سمت کلاینت — کاربر IPهای آنیکست کلادفلر را از
#        مرورگر خودش تست می‌کند (چون فقط تأخیرِ «کاربر→لبه» مهم است، نه
#        تأخیر سرور پنل) و بهترین IP لحظه‌ای خودش را پیدا می‌کند
#     ۲) پریست بازی‌های پرطرفدار با اطلاعات واقعی سرورها و مسیر پیشنهادی
#     ۳) تولید لینک گیمینگ: بدون mux، fragment ضد DPI، اولویت IPv4،
#        keepalive کوتاه + JSON کامل Xray برای کپی مستقیم در کلاینت
#     ۴) مولتی‌لوکیشن از طریق Cloudflare Worker (cf_gateway_worker.js):
#        مسیر /loc/{name} روی worker به بک‌اند آن لوکیشن فوروارد می‌شود
#     ۵) تشخیص PoP کلادفلر (استانبول/فرانکفورت/بحرین/...) از /gateway-status
#
# 🔗 معماری:
#   کاربر ──► بهترین IP کلادفلر (یا VPS ایران) ──► Worker ──► لوکیشن ──► اینترنت
#   ورودی (entry): IP مستقیم کلادفلر = کمترین تأخیر | VPS ایران = پایدارترین
#
# 🔒 فلسفه جداسازی (مثل zeus_features.py و bridge_boost.py):
#   - state در gaming_config.json
#   - اگر این فایل حذف شود، پنل و همه‌ی تونل‌ها بدون تغییر کار می‌کنند
#
# ⚙️ اندپوینت‌ها:
#   GET    /api/gaming/config          → تنظیمات + وضعیت ماژول
#   POST   /api/gaming/config          → ذخیره‌ی دامنه‌ی worker / توکن / VPS
#   GET    /api/gaming/status          → تست سلامت worker + PoP + لوکیشن‌ها
#   GET    /api/gaming/locations       → لوکیشن‌های تعریف‌شده روی worker
#   POST   /api/gaming/locations       → افزودن لوکیشن (ترکیه/روسیه/...)
#   DELETE /api/gaming/locations/{nm}  → حذف لوکیشن
#   GET    /api/gaming/presets         → پریست بازی‌ها
#   GET    /api/gaming/candidates      → لیست IPهای کاندید برای اسکنر کلاینت
#   POST   /api/gaming/scan            → ثبت نتیجه‌ی اسکن + رتبه‌بندی
#   POST   /api/gaming/links           → لینک‌های گیمینگ (ورودی + لوکیشن)
#   POST   /api/gaming/xray-json       → JSON کامل Xray گیمینگ برای کلاینت
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import json
import re
import time
from datetime import datetime
from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx
from fastapi import Depends, Request
from fastapi.responses import JSONResponse

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

GAMING_FILE = DATA_DIR / "gaming_config.json"

DEFAULTS = {
    # پیش‌تنظیم‌شده: گیت‌وی کلادفلر این پروژه (دیپلوی خودکار شده)
    "worker_domain": "emix-gateway.personalemixone.workers.dev",
    "worker_token": "emix-gw-7f3a9c2e5b1d84f6a0c9e3d7b5f21h8k4",
    "vps_ip": "",            # IP سرور ایران (پارس‌پک) — ورودی پایدار
    "vps_port": 443,
    "best_ip": "",           # نتیجه‌ی اسکن کلاینت
    "best_ip_ms": None,
    "best_ip_colo": "",      # PoP در لحظه‌ی اسکن (اگر قابل تشخیص بود)
    "last_scan_ts": None,    # timestamp آخرین اسکن
    "scan_results": [],      # ۱۰ نتیجه‌ی برتر
}

# ══════════════════════════════════════════════════════════════════════════════
# پریست بازی‌ها — اطلاعات واقعی سرورها و مسیر بهینه برای کاربر ایرانی
# ping از ایران به‌صورت تخمینی و بر اساس تجربه‌ی میدانی؛ اعداد قطعی نیستند
# ══════════════════════════════════════════════════════════════════════════════

GAME_PRESETS = {
    "cs2": {
        "label": "Counter-Strike 2",
        "icon": "🔫",
        "server_regions": ["دبی/امارات (MENA)", "فرانکفورت (EU West)", "وین (EU)"],
        "est_ping_direct": "60-110ms به دبی",
        "best_location": "tr",
        "why": "ترافیک CS2 به SDR والو می‌رود؛ خروج از ترکیه بهترین تعادل پینگ به سرورهای MENA و اروپا را می‌دهد",
        "tips": [
            "rate 786432 را در کانفیگ بازی ست کنید",
            "mm_dedicated_search_maxping را 150 بگذارید تا مچ نزدیک بگیرید",
            "اگر پینگ دبی بالاست، سرور اروپا (وین) معمولاً پایدارتر است",
        ],
    },
    "valorant": {
        "label": "Valorant",
        "icon": "🎯",
        "server_regions": ["دبی/بحرین (MENA)", "فرانکفورت (EU)"],
        "est_ping_direct": "70-120ms به سرور MENA",
        "best_location": "tr",
        "why": "سرور MENA رایت در امارات/بحرین است؛ خروج ترکیه → کوتاه‌ترین مسیر بعد از خروج مستقیم",
        "tips": [
            "در تنظیمات بازی سرور Mumbai را انتخاب نکنید — مسیر از ایران بدترین حالت است",
            "برای مچ‌های اروپایی، خروج اروپا (فرانکفورت) بهتر است",
        ],
    },
    "dota2": {
        "label": "Dota 2",
        "icon": "⚔️",
        "server_regions": ["دبی (UAE)", "لوکزامبورگ (EU West)", "استانبول (TR)"],
        "est_ping_direct": "60-100ms به دبی",
        "best_location": "tr",
        "why": "Dota سرور استانبول SDR دارد؛ خروج ترکیه یعنی پینگ تک‌رقمی به سرور استانبول",
        "tips": [
            "در انتخاب سرور، UAE + Europe West را تیک بزنید",
            "سرور استانبول Dota برای کاربر ترک در نظر گرفته شده — بهترین گزینه برای پینگ پایین",
        ],
    },
    "pubg": {
        "label": "PUBG (PC)",
        "icon": "🪖",
        "server_regions": ["بحرین/دبی (MENA)", "فرانکفورت (EU)"],
        "est_ping_direct": "70-120ms به MENA",
        "best_location": "tr",
        "why": "سرور خاورمیانه PUBG در بحرین است؛ ترکیه نزدیک‌ترین خروج پایدار است",
        "tips": [
            "منطقه Matchmaking را روی Middle East قفل کنید",
            "پینگ زیر ۸۰ روی MENA کاملاً رقابتی است",
        ],
    },
    "fortnite": {
        "label": "Fortnite",
        "icon": "🏗️",
        "server_regions": ["بحرین (Middle East)", "فرانکفورت (EU)"],
        "est_ping_direct": "65-110ms به بحرین",
        "best_location": "tr",
        "why": "سرور Middle East فورتنایت در بحرین است — بعد از خروج مستقیم، ترکیه کوتاه‌ترین مسیر است",
        "tips": [
            "Region را روی Middle East قفل کنید تا Auto مچ دور ندهد",
            "در حالت Build اهمیت پینگ بیشتر از Aim است — پایداری را فدای ۵ms نکنید",
        ],
    },
    "apex": {
        "label": "Apex Legends",
        "icon": "🚀",
        "server_regions": ["بحرین (MENA)", "فرانکفورت (EU)", "لندن (EU)"],
        "est_ping_direct": "75-120ms به بحرین",
        "best_location": "tr",
        "why": "دیتاسنتر MENA اپکس در بحرین است؛ خروج ترکیه تعادل پینگ و پایداری",
        "tips": [
            "Data Center را دستی روی Bahrain قفل کنید",
            "پینگ‌های ۴۰-۶۰ms روی بحرین از ترکیه معمول است",
        ],
    },
    "eafc": {
        "label": "EA FC 25 (FIFA)",
        "icon": "⚽",
        "server_regions": ["فرانکفورت (EU)", "آمستردام (EU)"],
        "est_ping_direct": "90-130ms به اروپا",
        "best_location": "tr",
        "why": "سرور اختصاصی MENA ندارد — همه‌ی مچ‌ها روی اروپا برگزار می‌شود؛ ترکیه نزدیک‌ترین خروج به اروپای غربی است",
        "tips": [
            "پینگ‌های ۶۰-۹۰ از ترکیه به فرانکفورت طبیعی است",
            "حالت Rivals حساس‌ترین حالت به jitter است — ورودی VPS ایران را تست کنید",
        ],
    },
    "cod": {
        "label": "Call of Duty / Warzone",
        "icon": "🎖️",
        "server_regions": ["فرانکفورت (EU)", "آمستردام (EU)"],
        "est_ping_direct": "100-140ms به اروپا",
        "best_location": "tr",
        "why": "سرور MENA ندارد؛ خروج ترکیه کمترین مسیر تا دیتاسنترهای اروپای اکتیویژن است",
        "tips": [
            "Geo-filter کنسول را روی اروپای غربی تنظیم کنید",
            "برای Warzone، پایداری (ورودی VPS) مهم‌تر از پینگ خام است",
        ],
    },
    "rocket": {
        "label": "Rocket League",
        "icon": "🚗",
        "server_regions": ["فرانکفورت (EU)", "آمستردام (EU)"],
        "est_ping_direct": "90-130ms به اروپا",
        "best_location": "tr",
        "why": "سرور MENA ندارد؛ بازی به jitter خیلی حساس است — کیفیت مسیر کلید برنده شدن است",
        "tips": [
            "Preferred Server را روی EU قفل کنید",
            "این بازی بیش از همه از fragment ضد DPI سود می‌برد چون UDP را هم روی تونل پایدار می‌برد",
        ],
    },
    "ow2": {
        "label": "Overwatch 2",
        "icon": "🦸",
        "server_regions": ["فرانکفورت (EU)", "پاریس (EU)"],
        "est_ping_direct": "100-140ms به اروپا",
        "best_location": "tr",
        "why": "سرور خاورمیانه ندارد؛ خروج ترکیه کوتاه‌ترین مسیر تا فرانکفورت",
        "tips": [
            "بلیدزارد از UDP استفاده می‌کند — روی تونل WS، پایداری مسیر تعیین‌کننده است",
        ],
    },
    "roblox": {
        "label": "Roblox",
        "icon": "🧱",
        "server_regions": ["فرانکفورت (EU)", "آمستردام (EU)", "واشنگتن (US)"],
        "est_ping_direct": "100-150ms به اروپا",
        "best_location": "auto",
        "why": "سرورهای Roblox پراکنده‌اند؛ مسیر auto معمولاً کافی است چون حساسیت پینگ پایین است",
        "tips": [
            "برای اکسپرینس‌های رقابتی (سورد فایت) لوکیشن ترکیه بهتر است",
        ],
    },
    "mobile": {
        "label": "بازی‌های موبایل (Clash / CoD M / ...)",
        "icon": "📱",
        "server_regions": ["بحرین/دبی (MENA)", "فرانکفورت (EU)"],
        "est_ping_direct": "70-120ms به MENA",
        "best_location": "tr",
        "why": "اکثر بازی‌های موبایل سرور MENA دارند؛ خروج ترکیه تعادل بهترین پینگ/قیمت",
        "tips": [
            "روی موبایل از v2rayNG با تنظیم Fragment (در JSON گیمینگ) استفاده کنید",
            "باتری و CPU تلفن روی پینگ مؤثر است — حالت ذخیره انرژی را خاموش کنید",
        ],
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# IPهای کاندید کلادفلر برای اسکنر سمت کلاینت
# آنیکست هستند: هر IP به نزدیک‌ترین PoP کاربر مسیر می‌یابد؛ اسکن از مرورگرِ
# خود کاربر یعنی اندازه‌گیری مسیر واقعی «کاربر→لبه» — نه مسیر سرور پنل
# ══════════════════════════════════════════════════════════════════════════════

def _candidate_ips() -> list[str]:
    """تولید لیست IP کاندید از رنج‌های اصلی کلادفلر + IPهای شناخته‌شده"""
    out: list[str] = []
    # رنج‌های اصلی آنیکست کلادفلر (نمونه‌گیری پخش‌شده)
    ranges = [
        ("104.16", 3), ("104.17", 3), ("104.18", 3), ("104.19", 2),
        ("104.20", 2), ("104.21", 2), ("104.22", 2), ("104.24", 2),
        ("104.25", 2), ("104.26", 2), ("104.27", 2),
        ("162.159", 4), ("162.158", 2),
        ("172.64", 3), ("172.65", 2), ("172.66", 2), ("172.67", 3),
        ("172.68", 2), ("172.69", 2), ("172.70", 2),
        ("188.114", 4),
        ("141.101", 2), ("108.162", 2),
        ("190.93", 2), ("103.21", 1), ("103.22", 1), ("103.31", 1),
        ("198.41", 1), ("131.0", 1),
    ]
    seeds = [11, 47, 88, 132, 176, 200, 228, 244]
    for prefix, count in ranges:
        for i in range(count):
            out.append(f"{prefix}.{seeds[(hash(prefix) + i * 7) % len(seeds)]}.{(i * 61 + 37) % 251}")
    # IPهای شناخته‌شده‌ی خوب برای ISPهای ایرانی (تجربه‌ی میدانی)
    known_good = [
        "104.17.147.22", "104.18.32.115", "104.19.195.29",
        "162.159.36.1", "162.159.192.1", "172.64.36.1", "172.67.68.1",
        "188.114.96.3", "188.114.97.1", "104.16.160.3",
    ]
    out.extend(known_good)
    seen, uniq = set(), []
    for ip in out:
        if ip not in seen:
            seen.add(ip)
            uniq.append(ip)
    return uniq


# ══════════════════════════════════════════════════════════════════════════════
# State — بارگذاری/ذخیره‌ی gaming_config.json
# ══════════════════════════════════════════════════════════════════════════════

def _load_cfg() -> dict:
    try:
        if GAMING_FILE.exists():
            data = json.loads(GAMING_FILE.read_text(encoding="utf-8"))
            merged = {**DEFAULTS, **data}
            # مهاجرت: مقادیر خالی ذخیره‌شده نباید پیش‌فرض (وورکر دیپلوی‌شده) را خنثی کنند
            for k in ("worker_domain", "worker_token"):
                if not merged.get(k):
                    merged[k] = DEFAULTS.get(k, "")
            return merged
    except Exception as e:
        logger.warning(f"[gaming] خواندن تنظیمات ناموفق ({e}) — از پیش‌فرض شروع می‌شود")
    return dict(DEFAULTS)


def _save_cfg(cfg: dict) -> None:
    try:
        GAMING_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"[gaming] ذخیره‌ی تنظیمات ناموفق: {e}")


def _norm_domain(domain: str) -> str:
    d = (domain or "").strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = d.rstrip("/").split("/")[0]
    return d


# ══════════════════════════════════════════════════════════════════════════════
# ارتباط با Worker کلادفلر
# ══════════════════════════════════════════════════════════════════════════════

async def _call_worker(cfg: dict, path: str, method: str = "GET", payload: dict | None = None) -> dict:
    """فراخوانی اندپوینت گیت‌وی — خطاها به‌صورت dict با ok=False برمی‌گردند"""
    domain = _norm_domain(cfg.get("worker_domain", ""))
    if not domain:
        return {"ok": False, "error": "دامنه‌ی Worker تنظیم نشده — اول دامنه‌ی workers.dev را ذخیره کنید"}
    url = f"https://{domain}{path}"
    headers = {"x-emix-token": cfg.get("worker_token", "") or ""}
    try:
        async with httpx.AsyncClient(timeout=12.0) as cli:
            if method == "GET":
                r = await cli.get(url, headers=headers)
            else:
                r = await cli.request(method, url, headers=headers, json=payload)
        try:
            return r.json()
        except Exception:
            return {"ok": False, "error": f"پاسخ غیر JSON از worker (کد {r.status_code})", "status": r.status_code}
    except Exception as e:
        return {"ok": False, "error": f"اتصال به worker ناموفق: {type(e).__name__}: {e}"}


# ══════════════════════════════════════════════════════════════════════════════
# بازنویسی لینک برای گیمینگ
# ══════════════════════════════════════════════════════════════════════════════

def _replace_query_param(url: str, key: str, value: str) -> str:
    """جایگزینی پارامتر query بدون خراب‌کردن fragment (#remark)"""
    return re.sub(rf"([?&]{key}=)[^&#]*", rf"\g<1>{value}", url)


def _gaming_link(url: str, entry_host: str, entry_port: int, worker_domain: str, location: str) -> str | None:
    """بازنویسی لینک برای عبور از گیت‌وی کلادفلر با ورودی و لوکیشن دلخواه"""
    try:
        if not url.startswith(("vless://", "trojan://")):
            return None
        p = urlparse(url)
        userinfo = p.username or ""
        new_netloc = f"{userinfo}@{entry_host}:{entry_port}"
        out = url.replace(f"{p.scheme}://{p.netloc}", f"{p.scheme}://{new_netloc}", 1)

        # مسیر WS در query parameter «path» است (نه URL path) — مثل path=/ws/{uuid}
        qs = parse_qs(p.query)
        old_path = unquote((qs.get("path") or ["/"])[0])
        if not old_path.startswith("/"):
            old_path = "/" + old_path
        new_path = f"/loc/{location}{old_path}"
        out = _replace_query_param(out, "path", quote(new_path, safe=""))

        # host و sni باید دامنه‌ی worker باشند تا کلادفلر درست روت کند
        out = _replace_query_param(out, "host", worker_domain)
        out = _replace_query_param(out, "sni", worker_domain)
        return out
    except Exception:
        return None


async def _gaming_links(entry: str, location: str, override_ip: str = "") -> dict:
    """همه‌ی لینک‌های مجاز + نسخه‌ی گیمینگ‌شان.
    entry: direct=مستقیم کلادفلر | vps=سرور ایران | panel=خود پنل (بدون وورکر — سریع‌ترین اگر ریلوی برای شما فیلتر نباشد)"""
    cfg = _load_cfg()
    worker_domain = _norm_domain(cfg.get("worker_domain", ""))

    location = (location or "auto").strip().lower()

    if entry == "panel":
        # ورودی خود پنل: بدون گیت‌وی وورکر — کوتاه‌ترین مسیر اگر ریلوی مستقیم در دسترس باشد
        entry_host = get_host()
        entry_port = 443
        entry_label = f"ورودی مستقیم پنل ({entry_host}) — بدون وورکر"
    elif entry == "vps":
        if not cfg.get("vps_ip"):
            return {"ok": False, "error": "IP سرور ایران (VPS) تنظیم نشده"}
        entry_host, entry_port = cfg["vps_ip"], int(cfg.get("vps_port") or 443)
        entry_label = f"ورودی VPS ایران ({entry_host})"
    else:
        # direct: بهترین IP اسکن‌شده یا خود دامنه‌ی worker
        entry_host = override_ip or cfg.get("best_ip") or worker_domain
        entry_port = 443
        entry_label = f"ورودی مستقیم کلادفلر ({entry_host})"

    host = get_host()
    async with LINKS_LOCK:
        snap = [(uid, dict(d)) for uid, d in LINKS.items()]
    out = []
    for uid, d in snap:
        proto = d.get("protocol", "vless-ws")
        if proto in ("mtproto", "shadowsocks"):
            continue  # گیمینگ فقط روی vless/trojan با WS معنا دارد
        if not is_link_allowed(d):
            continue
        original = generate_share_link(uid, host, remark=f"EMIX-{d['label']}", protocol=proto)
        if entry == "panel":
            # حالت پنل: لینک اصلی بدون عبور از وورکر — بهینه‌سازی فقط در JSON گیمینگ اعمال می‌شود
            gaming = original
        else:
            gaming = _gaming_link(original, entry_host, entry_port, worker_domain, location)
        if gaming:
            # آپدیت remark برای تفکیک سریع در کلاینت
            suffix = f"🎮 {d['label']}" if entry == "panel" else f"🎮 {d['label']} · {location}"
            gaming = gaming.split("#")[0] + "#" + quote(suffix)
            out.append({
                "uuid": uid,
                "label": d.get("label", uid[:8]),
                "protocol": proto,
                "original": original,
                "gaming": gaming,
            })
    return {"ok": True, "entry": entry_label, "location": location, "worker_domain": worker_domain, "links": out}


def _build_gaming_xray_json(entry: str, location: str, link_url: str) -> dict:
    """JSON کامل outbound گیمینگ برای کپی مستقیم در v2rayNG / Hiddify / v2rayN:
       بدون mux + fragment ضد DPI + TCP Fast Open + keepalive کوتاه + IPv4"""
    p = urlparse(link_url)
    addr = p.hostname or ""
    port = p.port or 443
    q = {}
    for pair in (p.query or "").split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            q[unquote(k)] = unquote(v)
    path = q.get("path", "/")
    host = q.get("host") or q.get("sni") or ""
    sni = q.get("sni") or host
    alpn = (q.get("alpn") or "h2").split(",")

    outbound = {
        "tag": "emix-gaming",
        "protocol": "vless",
        "settings": {
            "vnext": [{
                "address": addr,
                "port": port,
                "users": [{
                    "id": p.username or "",
                    "encryption": "none",
                    "level": 0,
                }],
            }],
        },
        "streamSettings": {
            "network": "ws",
            "security": "tls",
            "tlsSettings": {
                "serverName": sni,
                "allowInsecure": False,
                "alpn": ["http/1.1"],
                "fingerprint": q.get("fp", "chrome"),
                # ─── ضد DPI: شکستن handshake به پکت‌های کوچک ───
                "fragment": {
                    "packets": "tlshello",
                    "length": "100-200",
                    "interval": "10-20",
                },
            },
            "wsSettings": {
                "path": path,
                "headers": {"Host": host},
            },
            "sockopt": {
                "domainStrategy": "UseIPv4",        # IPv4 معمولاً تأخیر کمتری از ISPهای ایران دارد
                "tcpFastOpen": True,                 # صرفه‌جویی در یک RTT
                "tcpKeepAliveInterval": 15,          # نگه‌داشتن اتصال گرم برای گیم‌پلی پیوسته
                "tcpNoDelay": True,                  # غیرفعال‌کردن Nagle — حیاتی برای ریسپانسیو بودن
                "dialerProxy": "",
            },
        },
        "mux": {"enabled": False, "concurrency": -1},  # mux برای گیمینگ ممنوع — تأخیر اضافه می‌دهد
    }
    return {
        "_hint": f"EMIX Gaming ({entry} · {location}) — این JSON را در v2rayNG: تنظیمات > از کلیپ‌بورد import کنید",
        "outbounds": [outbound],
    }


# ══════════════════════════════════════════════════════════════════════════════
# register_routes
# ══════════════════════════════════════════════════════════════════════════════

def register_routes(app) -> None:

    @app.get("/api/gaming/config")
    async def gaming_get_config(_=Depends(require_auth)):
        cfg = _load_cfg()
        cfg["worker_domain"] = _norm_domain(cfg.get("worker_domain", ""))
        # توکن کامل برنمی‌گردد — فقط ست بودن یا نبودنش
        cfg["has_worker_token"] = bool(cfg.get("worker_token"))
        cfg.pop("worker_token", None)
        cfg["presets"] = GAME_PRESETS
        cfg["ready"] = bool(cfg["worker_domain"])
        return cfg

    @app.post("/api/gaming/config")
    async def gaming_set_config(request: Request, _=Depends(require_auth)):
        body = await request.json()
        cfg = _load_cfg()
        if "worker_domain" in body:
            cfg["worker_domain"] = _norm_domain(body.get("worker_domain", ""))
        if "worker_token" in body:
            cfg["worker_token"] = (body.get("worker_token") or "").strip()
        if "vps_ip" in body:
            v = (body.get("vps_ip") or "").strip()
            if v and not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", v):
                return JSONResponse({"ok": False, "error": "فرمت IP سرور ایران معتبر نیست"}, 400)
            cfg["vps_ip"] = v
        if "vps_port" in body:
            try:
                cfg["vps_port"] = int(body.get("vps_port") or 443)
            except (TypeError, ValueError):
                cfg["vps_port"] = 443
        _save_cfg(cfg)
        return {"ok": True, "saved": True}

    @app.get("/api/gaming/status")
    async def gaming_status(_=Depends(require_auth)):
        cfg = _load_cfg()
        if not _norm_domain(cfg.get("worker_domain", "")):
            return {"ok": False, "configured": False, "error": "دامنه‌ی worker تنظیم نشده"}
        res = await _call_worker(cfg, "/gateway-status")
        res["configured"] = True
        res["checked_at"] = datetime.utcnow().isoformat()
        return res

    @app.get("/api/gaming/locations")
    async def gaming_get_locations(_=Depends(require_auth)):
        cfg = _load_cfg()
        res = await _call_worker(cfg, "/gateway-status")
        if not res.get("ok"):
            return res
        return {"ok": True, "locations": res.get("locations", []), "kv_bound": res.get("kv_bound", False), "token_set": res.get("token_set", False)}

    @app.post("/api/gaming/locations")
    async def gaming_add_location(request: Request, _=Depends(require_auth)):
        body = await request.json()
        name = (body.get("name") or "").strip().lower()
        upstream = (body.get("upstream") or "").strip().lower()
        label = (body.get("label") or "").strip()
        flag = (body.get("flag") or "📍").strip()
        if not re.match(r"^[a-z0-9-]{2,16}$", name or ""):
            return JSONResponse({"ok": False, "error": "نام لوکیشن باید ۲-۱۶ کاراکتر انگلیسی کوچک/خط تیره باشد (مثل: tr, ru, de)"}, 400)
        if not upstream or "." not in upstream:
            return JSONResponse({"ok": False, "error": "آدرس بک‌اند لوکیشن (دامنه) معتبر نیست"}, 400)
        cfg = _load_cfg()
        if not cfg.get("worker_token"):
            return JSONResponse({"ok": False, "error": "توکن worker تنظیم نشده — در Cloudflare: Settings → Variables → EMIX_TOKEN را اضافه کنید و همینجا ذخیره کنید"}, 400)
        res = await _call_worker(cfg, "/admin/locations", method="POST",
                                 payload={"name": name, "label": label or name, "flag": flag, "upstream": upstream})
        return res

    @app.delete("/api/gaming/locations/{name}")
    async def gaming_del_location(name: str, _=Depends(require_auth)):
        cfg = _load_cfg()
        if not cfg.get("worker_token"):
            return JSONResponse({"ok": False, "error": "توکن worker تنظیم نشده"}, 400)
        res = await _call_worker(cfg, f"/admin/locations?name={quote(name)}", method="DELETE")
        return res

    @app.get("/api/gaming/presets")
    async def gaming_presets(_=Depends(require_auth)):
        return {"ok": True, "presets": GAME_PRESETS}

    @app.get("/api/gaming/candidates")
    async def gaming_candidates(_=Depends(require_auth)):
        return {"ok": True, "ips": _candidate_ips()}

    @app.get("/api/gaming/inbounds")
    async def gaming_inbounds(_=Depends(require_auth)):
        """لیست اینباندهای ورودی گیت‌وی کلادفلر — بدون نیاز به سرور اضافه:
        هر IP آنیکست سالم = یک اینباند مستقل (همان وورکر، از لبه‌ی متفاوت).
        شامل ورودی VPS ایران (اگر تنظیم شده) و ورودی خودِ دامنه‌ی وورکر."""
        cfg = _load_cfg()
        wd = _norm_domain(cfg.get("worker_domain", ""))
        if not wd:
            return {"ok": False, "error": "دامنه‌ی worker تنظیم نشده"}

        inbounds = []
        # ۱) اینباند اصلی: دامنه‌ی وورکر (DNS خودکار کلادفلر → نزدیک‌ترین PoP)
        inbounds.append({
            "id": "worker-domain",
            "label": "گیت‌وی (خودکار — نزدیک‌ترین PoP)",
            "type": "domain",
            "entry": wd,
            "port": 443,
            "latency_ms": None,
            "note": "DNS کلادفلر خودش نزدیک‌ترین دیتاسنتر را برای هر کاربر انتخاب می‌کند",
        })
        # ۲) اینباندهای IP اسکن‌شده — هر IP سالم یک ورودی مستقل
        for i, r in enumerate((cfg.get("scan_results") or [])[:5]):
            inbounds.append({
                "id": f"scan-{i+1}",
                "label": f"IP اسکن‌شده #{i+1}",
                "type": "ip",
                "entry": r.get("ip", ""),
                "port": 443,
                "latency_ms": r.get("min_ms"),
                "jitter_ms": r.get("jitter_ms"),
                "note": "از اسکن مرورگر شما — مستقیم به همین IP وصل می‌شود",
            })
        # ۳) ورودی VPS ایران (اگر تنظیم شده) — پایدارترین
        if cfg.get("vps_ip"):
            inbounds.append({
                "id": "vps",
                "label": "VPS ایران (پایدار — ضد قطعی)",
                "type": "vps",
                "entry": cfg["vps_ip"],
                "port": int(cfg.get("vps_port") or 443),
                "latency_ms": None,
                "note": "از سرور ایران عبور می‌کند — مناسب وقتی IPهای کلادفلر قطع می‌شوند",
            })

        # تست سلامت فعال هر اینباند (اتصال TCP واقعی از پنل)
        async def _check(ib: dict) -> None:
            try:
                t0 = time.time()
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ib["entry"], int(ib["port"])), timeout=6.0)
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                ib["healthy"] = True
                ib["connect_ms"] = round((time.time() - t0) * 1000, 1)
            except Exception as exc:
                ib["healthy"] = False
                ib["error"] = f"{type(exc).__name__}: اتصال برقرار نشد"

        await asyncio.gather(*[_check(ib) for ib in inbounds], return_exceptions=True)
        healthy_count = sum(1 for ib in inbounds if ib.get("healthy"))
        return {"ok": True, "worker_domain": wd, "inbounds": inbounds,
                "healthy_count": healthy_count,
                "detail": "اینباندها روی خودِ وورکر کلادفلر هستند — بدون سرور اضافه؛ هر IP آنیکست کلادفلر یک ورودی مستقل است"}

    @app.post("/api/gaming/scan")
    async def gaming_scan(request: Request, _=Depends(require_auth)):
        """ثبت نتیجه‌ی اسکن کلاینت — رتبه‌بندی و ذخیره‌ی بهترین IP"""
        body = await request.json()
        results = body.get("results") or []
        # فیلتر نتایج سالم و مرتب‌سازی بر اساس کمینه‌ی تأخیر
        clean = [r for r in results if isinstance(r, dict) and r.get("ip") and isinstance(r.get("min_ms"), (int, float))]
        clean.sort(key=lambda r: r["min_ms"])
        top = clean[:10]
        cfg = _load_cfg()
        if top:
            cfg["best_ip"] = top[0]["ip"]
            cfg["best_ip_ms"] = round(top[0]["min_ms"], 1)
            cfg["best_ip_colo"] = top[0].get("colo") or ""
            cfg["scan_results"] = [
                {"ip": r["ip"], "min_ms": round(r.get("min_ms", 0), 1),
                 "avg_ms": round(r.get("avg_ms", 0), 1), "jitter_ms": round(r.get("jitter_ms", 0), 1)}
                for r in top
            ]
            cfg["last_scan_ts"] = time.time()
            _save_cfg(cfg)
        return {"ok": True, "best": cfg.get("best_ip"), "best_ms": cfg.get("best_ip_ms"), "top": cfg.get("scan_results", [])}

    @app.post("/api/gaming/links")
    async def gaming_links(request: Request, _=Depends(require_auth)):
        body = await request.json()
        entry = (body.get("entry") or "direct").strip().lower()
        location = (body.get("location") or "auto").strip().lower()
        override_ip = (body.get("ip") or "").strip()
        if entry not in ("direct", "vps", "panel"):
            entry = "direct"
        res = await _gaming_links(entry, location, override_ip)
        if not res.get("ok") and override_ip and entry == "direct":
            res = await _gaming_links(entry, location, "")
        return res

    @app.post("/api/gaming/compare")
    async def gaming_compare(request: Request, _=Depends(require_auth)):
        """مقایسه‌ی واقعی A/B: پینگ یک کانفیگ از سه مسیر (پنل مستقیم / گیت‌وی کلادفلر)
        تا کاربر ببیند کدام برای خودش سریع‌تر است — انتخاب بر اساس داده، نه حدس."""
        import link_health as _lh
        async with LINKS_LOCK:
            snap = [(uid, dict(d)) for uid, d in LINKS.items() if is_link_allowed(d)]
        # اولین vless-ws
        pick = next(((u, d) for u, d in snap if d.get("protocol", "vless-ws") == "vless-ws"), None)
        if not pick:
            return {"ok": False, "error": "کانفیگ VLESS فعالی برای مقایسه وجود ندارد"}
        uid, d = pick
        results = {}
        # مسیر ۱: مستقیم پنل
        try:
            r1 = await _lh._run_link_ping(uid, dict(d), via="direct")
            results["panel_direct"] = {
                "ok": r1.get("ok"),
                "total_ms": round((r1.get("ws_ms") or 0) + (r1.get("e2e_ms") or 0), 1),
                "detail": r1.get("detail"),
            }
        except Exception as exc:
            results["panel_direct"] = {"ok": False, "detail": str(exc)[:100]}
        # مسیر ۲: گیت‌وی کلادفلر
        try:
            r2 = await _lh._run_link_ping(uid, dict(d), via="worker")
            results["cf_gateway"] = {
                "ok": r2.get("ok"),
                "total_ms": round((r2.get("ws_ms") or 0) + (r2.get("e2e_ms") or 0), 1),
                "detail": r2.get("detail"),
            }
        except Exception as exc:
            results["cf_gateway"] = {"ok": False, "detail": str(exc)[:100]}
        # توصیه
        p_ok = results["panel_direct"].get("ok") and results["panel_direct"].get("total_ms")
        g_ok = results["cf_gateway"].get("ok") and results["cf_gateway"].get("total_ms")
        if p_ok and g_ok:
            winner = "panel" if results["panel_direct"]["total_ms"] <= results["cf_gateway"]["total_ms"] else "gateway"
            advice = ("مسیر مستقیم پنل برای شما سریع‌تر است — از ورودی «مستقیم پنل» در ساخت کانفیگ استفاده کنید"
                      if winner == "panel" else
                      "گیت‌وی کلادفلر برای شما سریع‌تر یا پایدارتر است — از ورودی «مستقیم کلادفلر» استفاده کنید")
        elif g_ok:
            winner = "gateway"
            advice = "مسیر مستقیم پنل در دسترس نیست — گیت‌وی کلادفلر (ضد فیلتر) گزینه‌ی شماست"
        elif p_ok:
            winner = "panel"
            advice = "گیت‌وی در دسترس نیست — مسیر مستقیم پنل را استفاده کنید"
        else:
            winner = None
            advice = "هیچ‌کدام از مسیرها پاسخ نداد — اتصال سرور را بررسی کنید"
        return {"ok": True, "uuid": uid, "label": d.get("label"), "results": results,
                "winner": winner, "advice": advice}

    @app.post("/api/gaming/xray-json")
    async def gaming_xray_json(request: Request, _=Depends(require_auth)):
        body = await request.json()
        entry = (body.get("entry") or "direct").strip().lower()
        location = (body.get("location") or "auto").strip().lower()
        override_ip = (body.get("ip") or "").strip()
        if entry not in ("direct", "vps", "panel"):
            entry = "direct"
        res = await _gaming_links(entry, location, override_ip)
        if not res.get("ok"):
            return res
        links = res.get("links") or []
        if not links:
            return {"ok": False, "error": "کانفیگ فعالی برای تبدیل وجود ندارد"}
        # اولین لینک vless-ws (برای گیمینگ مناسب‌ترین)
        pick = next((l for l in links if l["protocol"] == "vless-ws"), links[0])
        j = _build_gaming_xray_json(entry, location, pick["gaming"])
        return {"ok": True, "xray": j, "source_link": pick["gaming"], "label": pick["label"]}

    logger.info("[gaming] ماژول مرکز گیمینگ فعال شد — اسکنر IP + پریست بازی + مولتی‌لوکیشن")
