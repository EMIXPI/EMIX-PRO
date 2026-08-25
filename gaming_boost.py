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
    "vps_ip": "185.164.73.192",   # سرور پارس‌پک — پیش‌فرض پر شده (ورودی پایدار)
    "vps_port": 443,
    "best_ip": "",           # نتیجه‌ی اسکن کلاینت
    "best_ip_ms": None,
    "best_ip_colo": "",      # PoP در لحظه‌ی اسکن (اگر قابل تشخیص بود)
    "last_scan_ts": None,    # timestamp آخرین اسکن
    "scan_results": [],      # ۱۰ نتیجه‌ی برتر
    "anti_dpi_mode": "balanced",  # ضد ضریب: speed | balanced | stealth
    "transport": "ws",            # ترنسپورت: ws | xhttp-stream-up | xhttp-packet-up
    "custom_sni": "",              # SNI سفارشی (وقتی دامنه‌ی شخصی به وورکر وصل شد)
}

# ══════════════════════════════════════════════════════════════════════════════
# ضد ضریب (Anti-DPI) — سه حالت جعل دیتا برای دور زدن/کم کردن ضریب ISP:
#
# «ضریب» چیست؟ DPI فیلترینگ، جریان‌های مشکوک (امضای handshake تونل) را با
# QoS مهار می‌کند و سرعت را تا چند برابر کم می‌کند. سه لایه‌ی مقابله:
#   ۱) fragment — شکستن ClientHello به تکه‌های تصادفی؛ DPI دیگر امضای
#      TLS مرجع (مثل fingerprint متن‌باز) را بازسازی نمی‌کند
#   ۲) uTLS fp — اثر انگشت handshake کلاینت دقیقاً مثل مرورگر واقعی
#   ۳) ترنسپورت xhttp — الگوی ترافیک مثل درخواست/پاسخ HTTP عادی؛
#      بدون امضای Upgrade وب‌سوکت (برای سرعت گیمینگ: stream-up)
# ══════════════════════════════════════════════════════════════════════════════

ANTI_DPI_MODES = {
    "speed": {
        "label": "⚡ حداکثر سرعت",
        "short": "سرعت",
        "desc": "بدون fragment — فقط بهینه‌سازی TCP (TFO + NoDelay + keepalive کوتاه). برای وقتی که ضریب نمی‌خورید یا فیلترینگ فعال نیست.",
        "fragment": None,
        "fp": "chrome",
        "alpn": ["h2", "http/1.1"],
    },
    "balanced": {
        "label": "⚖ متعادل — پیشنهادی",
        "short": "متعادل",
        "desc": "ClientHello به تکه‌های ۴۰ تا ۱۲۰ بایتی با فاصله‌ی تصادفی شکسته می‌شود + اثر انگشت کروم. افت سرعت تقریباً صفر، امضای DPI مخدوش.",
        "fragment": {"packets": "tlshello", "length": "40-120", "interval": "10-30"},
        "fp": "chrome",
        "alpn": ["http/1.1"],
    },
    "stealth": {
        "label": "🛡 پنهان‌کاری حداکثری — ضد ضریب",
        "short": "ضد ضریب",
        "desc": "سه لایه‌ی اول پکت به تکه‌های ریز ۲۰-۸۰ بایتی با فاصله‌ی تصادفی شکسته می‌شوند + اثر انگشت فایرفاکس — سخت‌ترین حالت برای DPI؛ کمی سربار در شروع اتصال.",
        "fragment": {"packets": "1-3", "length": "20-80", "interval": "5-25"},
        "fp": "firefox",
        "alpn": ["http/1.1"],
    },
}

TRANSPORT_OPTIONS = {
    "ws": {
        "label": "WebSocket — پایدار و سازگار",
        "protocols": ("vless-ws", "trojan-ws"),
        "desc": "سازگارترین گزینه با همه‌ی کلاینت‌ها. برای گیمینگ با حالت‌های ضد ضریب هم خوب است.",
    },
    "xhttp-stream-up": {
        "label": "XHTTP (stream-up) — بیشترین جعل ترافیک",
        "protocols": ("xhttp-stream-up", "trojan-xhttp-stream-up"),
        "desc": "ترافیک دقیقاً مثل رِیکوئست/رسپانس HTTP عادی به نظر می‌رسد (بدون امضای Upgrade وب‌سوکت) — بهترین انتخاب وقتی WS ضریب می‌خورد. برای گیمینگ مناسب.",
    },
    "xhttp-packet-up": {
        "label": "XHTTP (packet-up) — ضد DPI + حداکثر سازگاری فایروال",
        "protocols": ("xhttp-packet-up", "trojan-xhttp-packet-up"),
        "desc": "پکت‌محور — برای شبکه‌هایی که استریم طولانی را می‌بُرند. سرعت دانلود معمولاً کمتر از stream-up.",
    },
}


def _anti_dpi_cfg(mode: str) -> dict:
    """تنظیمات ضد ضریب برای یک حالت — همیشه یک dict سالم برمی‌گرداند"""
    return ANTI_DPI_MODES.get((mode or "balanced").strip().lower(), ANTI_DPI_MODES["balanced"])

# ══════════════════════════════════════════════════════════════════════════════
# اینباندهای همیشه‌سبز — IPهای معروف کلادفلر که روی اکثر ISPهای ایرانی سالم‌اند.
# حتی قبل از اسکن، این لیست در بخش اینباندها نمایش داده می‌شود (با تست سلامت زنده).
# ══════════════════════════════════════════════════════════════════════════════

KNOWN_GOOD_INBOUNDS = [
    "104.17.147.22", "104.18.32.115", "104.19.195.29", "104.16.160.3",
    "162.159.36.1", "162.159.192.1", "162.158.62.115", "172.64.36.1",
    "172.67.68.1", "172.65.195.15", "188.114.96.3", "188.114.97.1",
    "188.114.98.114", "141.101.113.5", "108.162.219.9", "190.93.246.9",
]

# ══════════════════════════════════════════════════════════════════════════════
# قالب‌های لوکیشن رایگان — روش‌های واقعاً رایگان برای خروج از کشورهای مختلف.
# نکته‌ی صادقانه: «جعل» لوکیشن بدون سرورِ خروجِ واقعی ممکن نیست — اما این
# سرویس‌ها سرور خروج واقعیِ رایگان می‌دهند. هر قالب = راهنمای استقرار کامل.
# ══════════════════════════════════════════════════════════════════════════════

LOCATION_TEMPLATES = {
    "railway-exit": {
        "label": "🥇 راه سریع — سرور خروج رایگان روی Railway خودت",
        "flag": "⚡",
        "code": "eu",
        "region_hint": "رژیون Frankfurt (eu-central1) — پینگ از ایران ۸۰-۱۲۰ms",
        "best_for": "همه‌ی بازی‌های اروپایی + سرورهای فرانکفورت",
        "free": "روی همان پلن ری‌یلوی فعلی‌ات — یک سرویس کوچک Node (بدون هزینه‌ی جدید قابل توجه)",
        "wizard": True,
        "steps": [
            "دکمه‌ی «بسته‌ی سرور خروج رایگان» را بزن — پنل فایل‌های آماده با UUID خودت می‌سازد",
            "فایل‌ها را در یک ریپوی جدید GitHub بریز (یا پوشه‌ی exit_node مخزن EMIX-PRO را deploy کن)",
            "Railway → New Service → GitHub Repo → همان ریپو → Root Directory: exit_node",
            "Region را Frankfurt بگذار و متغیر UUID را از ویزارد کپی کن",
            "دامنه‌ی xxx.up.railway.app که می‌گیری را در فرم پایین ثبت کن (کد: eu)",
        ],
    },
    "oracle-ae": {
        "label": "امارات/دبی — Oracle Cloud (رایگانِ همیشه‌سبز)",
        "flag": "🇦🇪",
        "code": "ae",
        "region_hint": "میانگین پینگ از ایران: ۳۰-۷۰ms",
        "best_for": "سرورهای MENA (بحرین/دبی) — بهترین گزینه برای Valorant/CS2/PUBG",
        "free": "Always Free: تا ۴ هسته ARM + ۲۴GB RAM — برای همیشه رایگان",
        "steps": [
            "در cloud.oracle.com ثبت‌نام کن (کارت لازم است ولی از Always Free پول کم نمی‌شود)",
            "Compute → Create Instance → Region: Dubai (me-dubai-1) → Shape: VM.Standard.A1.Flex",
            "ایمج: Ubuntu 22.04 + SSH key بساز",
            "در Security List اوراکل و فایروال سرور: پورت ۴۴۳ را باز کن",
            "ساب‌دامنه ae.emixpi.ir را در DNS به IP سرور اشاره کن (A Record)",
            "اسکریپت location_backend.sh مخزن EMIX را روی سرور اجرا کن و دامنه را بده",
            "اینجا: افزودن لوکیشن → کد: ae → دامنه: ae.emixpi.ir",
        ],
    },
    "oracle-de": {
        "label": "آلمان/فرانکفورت — Oracle Cloud (رایگانِ همیشه‌سبز)",
        "flag": "🇩🇪",
        "code": "de",
        "region_hint": "میانگین پینگ از ایران: ۸۰-۱۲۰ms",
        "best_for": "سرورهای اروپا (EA FC / COD / Rocket League / Overwatch)",
        "free": "همان Always Free — سقف اشتراکی با قالب امارات",
        "steps": [
            "همان اکانت اوراکل → Compute → Region: Frankfurt (eu-frankfurt-1)",
            "بقیه‌ی مراحل دقیقاً مثل قالب امارات (با ساب‌دامنه de.emixpi.ir)",
        ],
    },
    "koyeb": {
        "label": "اروپا (فرانکفورت/پاریس) — Koyeb (رایگان بدون کارت)",
        "flag": "🇪🇺",
        "code": "koy",
        "region_hint": "پینگ مشابه فرانکفورت",
        "best_for": "خروج اروپایی سبک بدون سرور مجازی",
        "free": "یک سرویس رایگان ۵۱۲MB — بدون نیاز به کارت اعتباری",
        "steps": [
            "در koyeb.com ثبت‌نام کن (بدون کارت)",
            "Create Service → GitHub → ریپوی بسته‌ی خروج (exit_node) را وصل کن",
            "Region: Frankfurt · متغیر UUID را از ویزارد کپی کن",
            "دامنه‌ی koyeb.app که می‌گیری را همینجا به‌عنوان لوکیشن اضافه کن",
        ],
    },
    "render": {
        "label": "اروپا — Render (۷۵۰ ساعت/ماه رایگان)",
        "flag": "🌍",
        "code": "rnd",
        "region_hint": "رژیون Frankfurt",
        "best_for": "تست و مصرف سبک",
        "free": "۷۵۰ ساعت در ماه — بعد از ۱۵ دقیقه بی‌کاری می‌خوابد (اولین اتصال ~۵۰ ثانیه)",
        "steps": [
            "در render.com ثبت‌نام کن → New Web Service",
            "ریپوی بسته‌ی خروج (exit_node) را وصل کن، رژیون Frankfurt",
            "دامنه‌ی onrender.com را همینجا اضافه کن",
        ],
    },
    "ru-vps": {
        "label": "روسیه — VPS ارزان (شبه‌رایگان)",
        "flag": "🇷🇺",
        "code": "ru",
        "region_hint": "پینگ از ایران: ۶۰-۱۰۰ms",
        "best_for": "بازی‌های روسی + آسیای میانه + دانلود",
        "free": "رایگان واقعی نیست — ارزان‌ترین‌ها ۱-۲ دلار/ماه",
        "steps": [
            "پرووایدر روسی بگیر (aeza و مشابه)",
            "اسکریپت location_backend.sh را اجرا کن",
            "کد لوکیشن: ru + دامنه",
        ],
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# بسته‌ی سرور خروج رایگان (EMIX Exit Node) — یک سرور VLESS-over-WS مینیمال
# Node.js که با UUID کاربر پخت می‌شود و روی هر پلتفرم رایگان (Railway/Koyeb/
# Render/Fly/Oracle) deploy می‌شود. بعد دامنه‌اش به‌عنوان لوکیشن ثبت می‌شود.
#
# چرا TCP-only؟ بک‌اند اصلی EMIX هم TCP-only است — رفتار یکسان، سازگاری کامل.
# TLS را خود پلتفرم (Railway/Koyeb/Render) terminate می‌کند؛ وورکر کلادفلر
# به https://دامنه وصل می‌شود و WS را passthrough می‌کند.
# ══════════════════════════════════════════════════════════════════════════════

EXIT_NODE_SERVER_JS = r"""// ═══════════════════════════════════════════════════════════════
// EMIX Exit Node — سرور خروج رایگان VLESS-over-WebSocket
// ساخته‌شده توسط پنل EMIX PRO — UUID شما از قبل داخلش پخت شده
// deploy روی: Railway / Koyeb / Render / Fly / هر Node.js
// ═══════════════════════════════════════════════════════════════
const http = require('http');
const net = require('net');
const { WebSocketServer } = require('ws');

// UUID: مقدار پخت‌شده یا متغیر محیطی UUID (اولویت با env)
const UUID = (process.env.UUID || '__EMIX_UUID__').toLowerCase();
const UUID_HEX = UUID.replace(/-/g, '');
const PORT = parseInt(process.env.PORT || '8080', 10);
const IDLE_MS = parseInt(process.env.IDLE_TIMEOUT_MS || '300000', 10);

if (!/^[0-9a-f]{32}$/.test(UUID_HEX)) {
  console.error('[emix-exit] UUID نامعتبر — env UUID را با UUID کانفیگ پنل ست کنید');
  process.exit(1);
}

let active = 0;
const server = http.createServer((req, res) => {
  // سلامت‌سنجی: وورکر و پنل این مسیرها را صدا می‌زنند
  if (req.url === '/api/ping' || req.url === '/health' || req.url === '/') {
    res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ ok: true, node: 'emix-exit', proto: 'vless-ws', active, ts: Date.now() }));
    return;
  }
  res.writeHead(404, { 'content-type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify({ ok: false }));
});

// پذیرش WS روی هر مسیری — احراز هویت داخل هدر VLESS انجام می‌شود
const wss = new WebSocketServer({ server, maxPayload: 8 * 1024 * 1024 });

wss.on('connection', (ws) => {
  ws.once('message', (first) => {
    try {
      const buf = Buffer.isBuffer(first) ? first : Buffer.from(first);
      if (buf.length < 24 || buf[0] !== 0x00) return ws.close();
      const uuidHex = buf.subarray(1, 17).toString('hex');
      if (uuidHex !== UUID_HEX) return ws.close();   // UUID غلط → قطع فوری
      let pos = 17;
      pos += 1 + buf[pos];                            // addons
      const cmd = buf[pos]; pos += 1;
      if (cmd !== 0x01) return ws.close();            // فقط TCP
      const port = buf.readUInt16BE(pos); pos += 2;
      const atyp = buf[pos]; pos += 1;
      let addr = '';
      if (atyp === 1) {
        addr = `${buf[pos]}.${buf[pos + 1]}.${buf[pos + 2]}.${buf[pos + 3]}`; pos += 4;
      } else if (atyp === 2) {
        const dl = buf[pos]; pos += 1;
        addr = buf.subarray(pos, pos + dl).toString('utf-8'); pos += dl;
      } else if (atyp === 3) {
        const parts = [];
        for (let i = 0; i < 16; i += 2) parts.push(buf.subarray(pos + i, pos + i + 2).toString('hex'));
        addr = parts.join(':'); pos += 16;
      } else {
        return ws.close();
      }
      const payload = buf.subarray(pos);

      active++;
      const remote = net.connect({ host: addr, port }, () => {
        try { ws.send(Buffer.from([0x00, 0x00])); } catch (e) { /* بسته شد */ }
        if (payload.length) remote.write(payload);
      });
      let closed = false;
      const finish = () => { if (!closed) { closed = true; active--; try { remote.destroy(); } catch (e) {} try { ws.close(); } catch (e) {} } };
      ws.on('message', (m) => {
        const d = Buffer.isBuffer(m) ? m : Buffer.from(m);
        if (d.length && !remote.destroyed) remote.write(d);
      });
      remote.on('data', (d) => { try { ws.send(d); } catch (e) { finish(); } });
      remote.on('error', finish);
      remote.on('close', finish);
      ws.on('close', finish);
      ws.on('error', finish);
      remote.setTimeout(IDLE_MS, () => { remote.destroy(); });
    } catch (e) {
      try { ws.close(); } catch (e2) { /* noop */ }
    }
  });
});

server.listen(PORT, () => console.log('[emix-exit] listening on :' + PORT));
"""

EXIT_NODE_PACKAGE_JSON = r"""{
  "name": "emix-exit-node",
  "version": "1.0.0",
  "private": true,
  "description": "EMIX Exit Node - free VLESS-over-WS exit server for EMIX PRO multi-location",
  "main": "server.js",
  "scripts": { "start": "node server.js" },
  "dependencies": { "ws": "^8.18.0" },
  "engines": { "node": ">=18" }
}
"""

EXIT_NODE_DOCKERFILE = r"""FROM node:20-alpine
WORKDIR /app
COPY package.json server.js ./
RUN npm install --omit=dev
EXPOSE 8080
ENV PORT=8080
CMD ["node", "server.js"]
"""

EXIT_NODE_RAILWAY_TOML = r"""[build]
builder = "NIXPACKS"

[deploy]
startCommand = "node server.js"
restartPolicyType = "ON_FAILURE"
"""


def _exit_node_files(uuid_value: str) -> dict:
    """ساخت فایل‌های بسته‌ی خروج با UUID پخت‌شده"""
    return {
        "server.js": EXIT_NODE_SERVER_JS.replace("__EMIX_UUID__", uuid_value),
        "package.json": EXIT_NODE_PACKAGE_JSON,
        "Dockerfile": EXIT_NODE_DOCKERFILE,
        "railway.toml": EXIT_NODE_RAILWAY_TOML,
    }


EXIT_NODE_README = """# EMIX Exit Node — سرور خروج رایگان

این بسته یک سرور VLESS-over-WebSocket مینیمال است که پنل EMIX PRO با UUID شما ساخته.
هر جا Node.js اجرا شود کار می‌کند و دامنه‌اش را در پنل به‌عنوان «لوکیشن خروج» ثبت کنید.

## استقرار روی Railway (سریع‌ترین راه)
1. این ۴ فایل را در یک ریپوی GitHub جدید بگذار (یا مخزن EMIX-PRO را deploy کن)
2. Railway → پروژه‌ی خودت → + New Service → GitHub Repo → این ریپو را انتخاب کن
3. اگر بسته جدا است Root Directory خالی بماند؛ اگر از مخزن EMIX-PRO می‌گیری: Root Directory = exit_node
4. Region را روی Frankfurt (eu-central1) بگذار (یا هر کشور دلخواه)
5. Settings → Variables → اضافه کن: `UUID` = همان UUID که در server.js پخت شده (برای پشتیبانی چند کانفیگ می‌توانی بعداً عوضش کنی و ری‌دیپلوی کنی)
6. بعد از دیپلوی، دامنه‌ی `xxx.up.railway.app` را کپی کن
7. در پنل EMIX → تب گیمینگ → لوکیشن‌ها → کد: `eu` → دامنه: همان xxx.up.railway.app → افزودن

## Koyeb (بدون کارت)
- Create Service → GitHub → این ریپو → Build: Dockerfile → Region: Frankfurt

## Render (۷۵۰ ساعت/ماه — بعد از ۱۵ دقیقه بی‌کاری می‌خوابد)
- New → Web Service → این ریپو → Region: Frankfurt

## نکته‌ها
- سرور TCP-only است (مثل بک‌اند اصلی EMIX) — بازی‌ها و مرور کامل کار می‌کنند
- TLS را خود پلتفرم terminate می‌کند؛ هیچ گواهی لازم نیست
- لینک کاربر از مسیر گیت‌وی کلادفلر عبور می‌کند: کاربر → CF Worker → این سرور → اینترنت
- برای عوض‌کردن UUID فقط env UUID را عوض کن (نیازی به ادیت کد نیست)
"""

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


def _gaming_link(url: str, entry_host: str, entry_port: int, worker_domain: str, location: str,
                 fp: str = "", sni_override: str = "") -> str | None:
    """بازنویسی لینک برای عبور از گیت‌وی کلادفلر با ورودی و لوکیشن دلخواه.
    fp: اثر انگشت uTLS حالت ضد ضریب · sni_override: SNI سفارشی (دامنه‌ی شخصی)"""
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

        # host و sni باید دامنه‌ی گیت‌وی باشند تا کلادفلر درست روت کند
        # (یا SNI سفارشی وقتی کاربر دامنه‌ی خودش را به وورکر وصل کرده)
        eff_sni = _norm_domain(sni_override) or worker_domain
        out = _replace_query_param(out, "host", worker_domain)
        out = _replace_query_param(out, "sni", eff_sni)

        # اثر انگشت uTLS حالت ضد ضریب — جعل handshake به مرورگر واقعی
        if fp:
            out = _replace_query_param(out, "fp", fp)
        return out
    except Exception:
        return None


async def _gaming_links(entry: str, location: str, override_ip: str = "",
                         mode: str = "balanced", transport: str = "ws") -> dict:
    """همه‌ی لینک‌های مجاز + نسخه‌ی گیمینگ‌شان.
    entry: direct=مستقیم کلادفلر | vps=سرور ایران | panel=خود پنل (بدون وورکر — سریع‌ترین اگر ریلوی برای شما فیلتر نباشد)
    mode: حالت ضد ضریب (speed/balanced/stealth) · transport: ws | xhttp-stream-up | xhttp-packet-up"""
    cfg = _load_cfg()
    worker_domain = _norm_domain(cfg.get("worker_domain", ""))
    anti = _anti_dpi_cfg(mode)
    transport = (transport or "ws").strip().lower()
    topt = TRANSPORT_OPTIONS.get(transport, TRANSPORT_OPTIONS["ws"])
    wanted_protos = set(topt["protocols"])

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
            continue  # گیمینگ فقط روی vless/trojan معنا دارد
        # ترنسپورت انتخابی: فقط پروتکل‌های همان خانواده را نگه دار
        if wanted_protos and proto not in wanted_protos:
            continue
        if not is_link_allowed(d):
            continue
        original = generate_share_link(uid, host, remark=f"EMIX-{d['label']}", protocol=proto)
        if entry == "panel":
            # حالت پنل: لینک اصلی بدون عبور از وورکر — بهینه‌سازی فقط در JSON گیمینگ اعمال می‌شود
            gaming = original
            if anti["fp"]:
                gaming = _replace_query_param(gaming, "fp", anti["fp"])
        else:
            gaming = _gaming_link(original, entry_host, entry_port, worker_domain, location,
                                  fp=anti.get("fp", ""), sni_override=cfg.get("custom_sni", ""))
        if gaming:
            # آپدیت remark برای تفکیک سریع در کلاینت
            tr_short = "WS" if transport == "ws" else "XHTTP"
            base = f"🎮 {d['label']}" if entry == "panel" else f"🎮 {d['label']} · {location}"
            suffix = f"{base} · {tr_short} · {anti['short']}"
            gaming = gaming.split("#")[0] + "#" + quote(suffix)
            out.append({
                "uuid": uid,
                "label": d.get("label", uid[:8]),
                "protocol": proto,
                "original": original,
                "gaming": gaming,
            })
    if not out:
        return {"ok": False, "error": f"کانفیگ «{topt['label']}» فعالی وجود ندارد — اول از صفحه‌ی کانفیگ‌ها یک کانفیگ {topt['protocols'][0]} بسازید یا ترنسپورت را WebSocket بگذارید"}
    return {"ok": True, "entry": entry_label, "location": location, "worker_domain": worker_domain,
            "mode": mode, "mode_label": anti["label"], "transport": transport,
            "transport_label": topt["label"], "links": out}


def _build_gaming_xray_json(entry: str, location: str, link_url: str, mode: str = "balanced") -> dict:
    """JSON کامل outbound گیمینگ برای کپی مستقیم در v2rayNG / Hiddify / v2rayN:
       بدون mux + fragment ضد DPI (بر اساس حالت ضد ضریب) + TCP Fast Open +
       keepalive کوتاه + IPv4 — WS و XHTTP هر دو پشتیبانی می‌شوند"""
    anti = _anti_dpi_cfg(mode)
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
    is_xhttp = (q.get("type") or "ws").lower() in ("xhttp", "splithttp")

    # ─── تنظیمات TLS + ضد ضریب ───
    tls_settings = {
        "serverName": sni,
        "allowInsecure": False,
        "alpn": anti["alpn"],
        "fingerprint": q.get("fp") or anti["fp"],
    }
    if anti.get("fragment"):
        # fragment با طول/فاصله‌ی تصادفی — امضای ClientHello برای DPI مخدوش می‌شود
        tls_settings["fragment"] = dict(anti["fragment"])

    # ─── ترنسپورت: WS یا XHTTP ───
    if is_xhttp:
        net_settings = {
            "network": "xhttp",
            "xhttpSettings": {
                "path": path,
                "host": host,
                "mode": q.get("mode") or "stream-up",
            },
        }
    else:
        net_settings = {
            "network": "ws",
            "wsSettings": {
                "path": path,
                "headers": {"Host": host},
            },
        }

    protocol = "trojan" if link_url.startswith("trojan://") else "vless"
    if protocol == "vless":
        proto_settings = {"vnext": [{
            "address": addr,
            "port": port,
            "users": [{
                "id": p.username or "",
                "encryption": "none",
                "level": 0,
            }],
        }]}
    else:
        proto_settings = {"servers": [{
            "address": addr,
            "port": port,
            "password": p.username or "",
            "level": 0,
        }]}

    outbound = {
        "tag": "emix-gaming",
        "protocol": protocol,
        "settings": proto_settings,
        "streamSettings": {
            "security": "tls",
            "tlsSettings": tls_settings,
            **net_settings,
            "sockopt": {
                "domainStrategy": "UseIPv4",        # IPv4 معمولاً تأخیر کمتری از ISPهای ایران دارد
                "tcpFastOpen": True,                 # صرفه‌جویی در یک RTT
                "tcpKeepAliveInterval": 15,          # نگه‌داشتن اتصال گرم برای گیم‌پلی پیوسته
                "tcpNoDelay": True,                  # غیرفعال‌کردن Nagle — حیاتی برای ریسپانسیو بودن
            },
        },
        "mux": {"enabled": False, "concurrency": -1},  # mux برای گیمینگ ممنوع — تأخیر اضافه می‌دهد
    }
    return {
        "_hint": (f"EMIX Gaming ({entry} · {location} · {anti['label']}) — این JSON را در v2rayNG: "
                  "تنظیمات > از کلیپ‌بورد import کنید. حالت ضد ضریب: " + anti["label"]),
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
        cfg["location_templates"] = LOCATION_TEMPLATES
        cfg["anti_dpi_modes"] = {k: {"label": v["label"], "short": v["short"], "desc": v["desc"]}
                                 for k, v in ANTI_DPI_MODES.items()}
        cfg["transport_options"] = {k: {"label": v["label"], "desc": v["desc"]}
                                    for k, v in TRANSPORT_OPTIONS.items()}
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
        if "anti_dpi_mode" in body:
            m = (body.get("anti_dpi_mode") or "balanced").strip().lower()
            cfg["anti_dpi_mode"] = m if m in ANTI_DPI_MODES else "balanced"
        if "transport" in body:
            t = (body.get("transport") or "ws").strip().lower()
            cfg["transport"] = t if t in TRANSPORT_OPTIONS else "ws"
        if "custom_sni" in body:
            s = _norm_domain(body.get("custom_sni") or "")
            cfg["custom_sni"] = s
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
    async def gaming_get_locations(request: Request, _=Depends(require_auth)):
        """لوکیشن‌های ثبت‌شده روی worker — با ?check=1 تست سلامت واقعی هر لوکیشن هم انجام می‌شود"""
        cfg = _load_cfg()
        want_check = request.query_params.get("check") == "1"
        path = "/gateway-status?check=1" if want_check else "/gateway-status"
        res = await _call_worker(cfg, path)
        if not res.get("ok"):
            return res
        return {"ok": True, "locations": res.get("locations", []),
                "location_health": res.get("location_health") or [],
                "kv_bound": res.get("kv_bound", False), "token_set": res.get("token_set", False)}

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

    @app.get("/api/gaming/exit-blueprint")
    async def gaming_exit_blueprint(request: Request, _=Depends(require_auth)):
        """بسته‌ی سرور خروج رایگان — فایل‌های آماده‌ی deploy با UUID کاربر پخت‌شده.
        ?format=zip → فایل ZIP قابل دانلود برای push به GitHub"""
        # اولین کانفیگ vless فعال → UUID آن در بسته پخت می‌شود
        async with LINKS_LOCK:
            snap = [(uid, dict(d)) for uid, d in LINKS.items()]
        pick = next(((u, d) for u, d in snap
                     if d.get("protocol", "vless-ws").startswith("vless") and is_link_allowed(d)), None)
        if not pick:
            pick = next(((u, d) for u, d in snap if is_link_allowed(d)), None)
        if not pick:
            return JSONResponse({"ok": False, "error": "کانفیگ فعالی وجود ندارد — اول یک کانفیگ بسازید"}, 400)
        uid, d = pick
        files = _exit_node_files(uid)
        files["README.md"] = EXIT_NODE_README

        if request.query_params.get("format") == "zip":
            import io
            import zipfile
            from fastapi.responses import Response as _Resp
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for fname, content in files.items():
                    zf.writestr(fname, content)
            return _Resp(
                content=buf.getvalue(),
                media_type="application/zip",
                headers={"content-disposition": 'attachment; filename="emix-exit-node.zip"'},
            )
        return {"ok": True, "uuid": uid, "label": d.get("label", uid[:8]),
                "files": files,
                "steps": [
                    "فایل‌ها را دانلود کن (دکمه‌ی ZIP) و در یک ریپوی GitHub جدید push کن — یا پوشه‌ی exit_node مخزن EMIX-PRO را deploy کن",
                    "Railway → پروژه → + New Service → GitHub Repo → ریپو → Root Directory = exit_node (برای ریپوی جدا: خالی)",
                    "Region را انتخاب کن: Frankfurt (eu-central1) برای اروپا / Singapore برای آسیا",
                    "Settings → Variables → UUID = " + uid + " (اگر بعداً کانفیگ جدید ساختی همین را عوض کن)",
                    "بعد از دیپلوی دامنه‌ی xxx.up.railway.app را بردار و در فرم «افزودن لوکیشن» ثبت کن (کد: eu)",
                ]}

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
        mode = (body.get("mode") or "").strip().lower()
        transport = (body.get("transport") or "").strip().lower()
        if entry not in ("direct", "vps", "panel"):
            entry = "direct"
        if not mode:
            mode = _load_cfg().get("anti_dpi_mode", "balanced")
        if not transport:
            transport = _load_cfg().get("transport", "ws")
        res = await _gaming_links(entry, location, override_ip, mode=mode, transport=transport)
        if not res.get("ok") and override_ip and entry == "direct":
            res = await _gaming_links(entry, location, "", mode=mode, transport=transport)
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
        mode = (body.get("mode") or "").strip().lower()
        transport = (body.get("transport") or "").strip().lower()
        if entry not in ("direct", "vps", "panel"):
            entry = "direct"
        saved = _load_cfg()
        if not mode:
            mode = saved.get("anti_dpi_mode", "balanced")
        if not transport:
            transport = saved.get("transport", "ws")
        res = await _gaming_links(entry, location, override_ip, mode=mode, transport=transport)
        if not res.get("ok"):
            return res
        links = res.get("links") or []
        if not links:
            return {"ok": False, "error": "کانفیگ فعالی برای تبدیل وجود ندارد"}
        # اولین لینک هم‌خانواده‌ی ترنسپورت انتخابی (برای گیمینگ مناسب‌ترین)
        pick = next((l for l in links if l["protocol"] == ("vless-ws" if transport == "ws" else f"vless-{transport}")), links[0])
        j = _build_gaming_xray_json(entry, location, pick["gaming"], mode=mode)
        return {"ok": True, "xray": j, "source_link": pick["gaming"], "label": pick["label"],
                "mode": mode, "transport": transport}

    logger.info("[gaming] ماژول مرکز گیمینگ فعال شد — اسکنر IP + پریست بازی + مولتی‌لوکیشن")
