# bridge_boost.py
# ══════════════════════════════════════════════════════════════════════════════
# ماژول پل ایران (Iran Bridge) — مصرف داخلی + شتاب‌دهی
#
# 🎯 مشکل:
#   اپراتورهای ایرانی ترافیک بین‌المللی را با ضریب ۲.۷ مالی می‌کنند.
#   چون EMIX روی Railway (خارج) است، تمام ترافیک کاربر «بین‌المللی» حساب می‌شود.
#   هیچ کدی روی Railway نمی‌تواند این را تغییر دهد — ضریب از سمت اپراتور و بر
#   اساس آی‌پی مقصد اعمال می‌شود.
#
# ✅ راه‌حل (تکنیک استاندارد و پرکاربرد):
#   یک سرور داخل ایران که ترافیک TCP را به Railway فوروارد می‌کند:
#     کاربر ──(ترافیک داخلی، ضریب ۱)──► سرور ایران ──(TCP)──► Railway/EMIX
#   مزیت دوم: معمولاً سرعت هم بالا می‌رود، چون یک استریم TCP پایدار و
#   پرسرعت ایران→خارج جایگزین مسیر ناپایدار موبایل→خارج می‌شود.
#
# 🔒 فلسفه جداسازی (مثل link_health.py):
#   این ماژول کاملاً جدا از هسته است؛ هیچ فایلی در protocol/ یا منطق اصلی
#   main.py تغییر نمی‌کند. لینک‌های پل با «بازنویسی آدرسِ» لینک‌های اصلی
#   ساخته می‌شوند — تولیدکننده‌ی اصلی لینک دست‌نخورده می‌ماند.
#   اگر این فایل حذف شود، پنل و همه‌ی تونل‌ها مثل قبل کار می‌کنند.
#
# ⚙️ اندپوینت‌ها:
#   GET  /api/bridge/config          → تنظیمات فعلی پل
#   POST /api/bridge/config          → ذخیره‌ی آدرس سرور ایران
#   POST /api/bridge/test            → تست واقعی TLS از مسیر پل (پنل→ایران→پنل)
#   GET  /api/bridge/links           → همه‌ی لینک‌ها با نسخه‌ی پل‌دار
#   GET  /api/bridge/script?format=… → اسکریپت نصب برای سرور ایران
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import json
import re
import ssl
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, quote, unquote

from fastapi import Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

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

BRIDGE_FILE = DATA_DIR / "bridge_config.json"

DEFAULTS = {
    "bridge_host": "",        # آدرس سرور داخل ایران (IP یا دامنه)
    "bridge_port": 443,       # پورت گوش‌دادن پل روی سرور ایران
    "target_host": "",        # مقصد فوروارد (پیش‌فرض: دامنه‌ی خود پنل)
    "target_port": 443,
    "tuned": False,           # آیا تنظیمات sysctl پیشنهاد شده؟ (فقط نمایش)
    "updated_at": None,
}


# ══════════════════════════════════════════════════════════════════════════════
# ذخیره‌سازی مستقل (فایل خودمان — state اصلی دست نمی‌خورد)
# ══════════════════════════════════════════════════════════════════════════════
def _load_cfg() -> dict:
    try:
        if BRIDGE_FILE.exists():
            data = json.loads(BRIDGE_FILE.read_text(encoding="utf-8"))
            cfg = dict(DEFAULTS)
            cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
            return cfg
    except Exception as exc:
        logger.warning(f"[bridge] could not load config: {exc}")
    return dict(DEFAULTS)


def _save_cfg(cfg: dict) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        BRIDGE_FILE.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        logger.warning(f"[bridge] could not save config: {exc}")


def _target_domain(cfg: dict) -> str:
    """دامنه‌ی مقصد فوروارد — پیش‌فرض دامنه‌ی عمومی خود پنل."""
    return cfg.get("target_host") or get_host()


# ══════════════════════════════════════════════════════════════════════════════
# بازنویسی لینک‌ها — آدرسِ اتصال عوض می‌شود، host/SNI همان دامنه‌ی Railway می‌ماند
# ══════════════════════════════════════════════════════════════════════════════
def _rewrite_link(url: str, bridge_host: str, bridge_port: int) -> str | None:
    """آدرس اتصال را به سرور پل تغییر می‌دهد؛ بقیه‌ی پارامترها دست‌نخورده."""
    try:
        if url.startswith(("vless://", "trojan://")):
            p = urlparse(url)
            # netloc = uuid@host:port → فقط host عوض شود
            userinfo = p.username or ""
            new_netloc = f"{userinfo}@{bridge_host}:{bridge_port}"
            return url.replace(f"{p.scheme}://{p.netloc}", f"{p.scheme}://{new_netloc}", 1)

        if url.startswith("ss://"):
            # ss://base64@host:port/?plugin=...#remark
            p = urlparse(url)
            m = re.match(r"^([^@]+@)?([^:]+):(\d+)$", p.netloc)
            if not m:
                return None
            userinfo = m.group(1) or ""
            new_netloc = f"{userinfo}{bridge_host}:{bridge_port}"
            return url.replace(f"ss://{p.netloc}", f"ss://{new_netloc}", 1)

        if url.startswith("tg://"):
            # tg://proxy?server=HOST&port=...&secret=...  (MTProto از سیستم TCP-Proxy خودش می‌گذرد؛ بازنویسی نمی‌شود)
            return None
    except Exception:
        return None
    return None


async def _bridged_links() -> list[dict]:
    """همه‌ی کانفیگ‌های محلیِ مجاز + نسخه‌ی پل‌دار لینک‌شان."""
    cfg = _load_cfg()
    if not cfg.get("bridge_host"):
        return []
    host = get_host()
    async with LINKS_LOCK:
        snap = [(uid, dict(d)) for uid, d in LINKS.items()]
    out = []
    for uid, d in snap:
        proto = d.get("protocol", "vless-ws")
        if proto == "mtproto":
            continue  # MTProto دامنه/پورت عمومی خودش را از TCP-Proxy می‌گیرد
        if not is_link_allowed(d):
            continue
        original = generate_share_link(uid, host, remark=f"EMIX-{d['label']}", protocol=proto)
        bridged = _rewrite_link(original, cfg["bridge_host"], int(cfg["bridge_port"]))
        if bridged:
            out.append({
                "uuid": uid,
                "label": d.get("label", uid[:8]),
                "protocol": proto,
                "original": original,
                "bridged": bridged,
                "remark": f"{d['label']} · پل ایران",
            })
    return out


# ══════════════════════════════════════════════════════════════════════════════
# تست واقعی پل — اتصال TLS از پنل به سرور ایران و برگشت به خود پنل
# اگر هندشیک TLS با گواهی Railway از مسیر پل موفق شود، کل زنجیره سالم است.
# ══════════════════════════════════════════════════════════════════════════════
async def _test_bridge(cfg: dict) -> dict:
    bridge_host = cfg.get("bridge_host")
    if not bridge_host:
        return {"ok": False, "detail": "ابتدا آدرس سرور ایران را ذخیره کنید"}
    target = _target_domain(cfg)
    t0 = time.perf_counter()
    ctx = ssl.create_default_context()
    try:
        # اگر پورت پل ≠ ۴۴۳ باشد باز هم SNI باید دامنه‌ی Railway باشد
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                bridge_host, int(cfg.get("bridge_port", 443)),
                ssl=ctx, server_hostname=target,
            ),
            timeout=10.0,
        )
        ms = round((time.perf_counter() - t0) * 1000, 1)
        cert = writer.get_extra_info("ssl_object").getpeercert()
        issuer = ""
        for rdn in (cert or {}).get("issuer", ()):
            for k, v in rdn:
                if k == "organizationName":
                    issuer = v
                    break
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        return {
            "ok": True,
            "ms": ms,
            "detail": f"TLS از مسیر پل برقرار شد — گواهی «{issuer or target}» دریافت شد",
            "chain": f"پنل → {bridge_host}:{cfg.get('bridge_port', 443)} → {target}:443",
        }
    except asyncio.TimeoutError:
        return {"ok": False, "detail": "پاسخی از سرور ایران دریافت نشد (timeout) — آیا socat روشن است؟"}
    except ssl.SSLCertVerificationError as exc:
        return {"ok": False, "detail": f"گواهی نامعتبر از مسیر پل: {str(exc)[:120]}"}
    except ConnectionRefusedError:
        return {"ok": False, "detail": "اتصال رد شد — پورت پل روی سرور ایران باز نیست"}
    except Exception as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}: {str(exc)[:120]}"}


# ══════════════════════════════════════════════════════════════════════════════
# اسکریپت نصب سرور ایران — socat + systemd (پایدار و سبک)
# ══════════════════════════════════════════════════════════════════════════════
def _setup_script(cfg: dict, fmt: str = "bash") -> str:
    target = _target_domain(cfg)
    listen = int(cfg.get("bridge_port", 443))
    tport = int(cfg.get("target_port", 443))

    if fmt == "nginx":
        return (
            "# ─── nginx stream — /etc/nginx/conf.d/emix-bridge.conf ───\n"
            "stream {\n"
            "    server {\n"
            f"        listen {listen};\n"
            f"        proxy_pass {target}:{tport};\n"
            "        proxy_connect_timeout 5s;\n"
            "        proxy_timeout 300s;\n"
            "    }\n"
            "}\n"
            "# نکته: worker_rlimit_nofile 65535; events { worker_connections 16384; }\n"
        )

    # اسکریپت bash — با جایگزینی پارامترها (بدون f-string برای جلوگیری از تداخل براکت systemd)
    tpl = """#!/bin/bash
# ================================================================
#  EMIX Iran Bridge — نصب خودکار پل فوروارد TCP
#  ▸ روی سرور داخل ایران اجرا کنید (Ubuntu/Debian، دسترسی root)
#  ▸ کار پل: گوش‌دادن روی پورت __LISTEN__ و فوروارد به __TARGET__:__TPORT__
#  ▸ ترافیک کاربر به این سرور = ترافیک داخلی (بدون ضریب ۲.۷)
# ================================================================
set -e
LISTEN_PORT=__LISTEN__
EMIX_DOMAIN=__TARGET__
EMIX_PORT=__TPORT__

echo "→ نصب socat..."
apt-get update -qq >/dev/null 2>&1 || true
apt-get install -y -qq socat >/dev/null 2>&1 || { echo "خطا در نصب socat"; exit 1; }

echo "→ تنظیم بافر شبکه برای throughput بهتر..."
cat >/etc/sysctl.d/99-emix-bridge.conf <<SYSCTL
net.core.rmem_max=16777216
net.core.wmem_max=16777216
net.ipv4.tcp_rmem=4096 87380 16777216
net.ipv4.tcp_wmem=4096 65536 16777216
net.ipv4.tcp_fastopen=3
net.ipv4.tcp_window_scaling=1
net.core.default_qdisc=fq
SYSCTL
# BBR اگر در کرنل موجود بود فعال شود
modprobe tcp_bbr 2>/dev/null || true
if modinfo tcp_bbr >/dev/null 2>&1; then
  echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.d/99-emix-bridge.conf
fi
sysctl -p /etc/sysctl.d/99-emix-bridge.conf >/dev/null 2>&1 || true

echo "→ ساخت سرویس systemd..."
cat >/etc/systemd/system/emix-bridge.service <<UNIT
[Unit]
Description=EMIX Iran Bridge (TCP forward)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/socat TCP-LISTEN:__LISTEN__,fork,reuseaddr,nodelay,rcvbuf=1048576,sndbuf=1048576 TCP:__TARGET__:__TPORT__
Restart=always
RestartSec=3
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now emix-bridge

sleep 1
if systemctl is-active --quiet emix-bridge; then
  echo ""
  echo "✅ پل نصب و روشن شد!"
  echo "   گوش‌دادن: پورت __LISTEN__  →  فوروارد به __TARGET__:__TPORT__"
  echo "   تست:  nc -vz 127.0.0.1 __LISTEN__"
  echo ""
  echo "⚠️  اگر فایروال دارید:  ufw allow __LISTEN__/tcp"
else
  echo "❌ سرویس بالا نیامد — لاگ: journalctl -u emix-bridge -n 20"
fi
"""
    return (
        tpl
        .replace("__LISTEN__", str(listen))
        .replace("__TARGET__", target)
        .replace("__TPORT__", str(tport))
    )


def register_routes(app) -> None:

    @app.get("/api/bridge/config")
    async def bridge_get_config(_=Depends(require_auth)):
        cfg = _load_cfg()
        cfg["target_default"] = get_host()
        cfg["active"] = bool(cfg.get("bridge_host"))
        return cfg

    @app.post("/api/bridge/config")
    async def bridge_set_config(request: Request, _=Depends(require_auth)):
        body = await request.json()
        cfg = _load_cfg()
        host = str(body.get("bridge_host", "")).strip()
        port = int(body.get("bridge_port", 443) or 443)
        if host and not re.match(r"^[a-zA-Z0-9._-]+$", host):
            raise HTTPException(status_code=400, detail="آدرس سرور نامعتبر است")
        if not (1 <= port <= 65535):
            raise HTTPException(status_code=400, detail="پورت نامعتبر است")
        cfg["bridge_host"] = host
        cfg["bridge_port"] = port
        if body.get("target_host"):
            t = str(body["target_host"]).strip()
            if re.match(r"^[a-zA-Z0-9._-]+$", t):
                cfg["target_host"] = t
        cfg["updated_at"] = datetime.now().isoformat()
        _save_cfg(cfg)
        return {"ok": True, "config": cfg}

    @app.post("/api/bridge/test")
    async def bridge_test(_=Depends(require_auth)):
        cfg = _load_cfg()
        result = await _test_bridge(cfg)
        result["checked_at"] = datetime.now().isoformat()
        return result

    @app.get("/api/bridge/links")
    async def bridge_links(_=Depends(require_auth)):
        return {"links": await _bridged_links()}

    @app.get("/api/bridge/script")
    async def bridge_script(fmt: str = "bash", _=Depends(require_auth)):
        cfg = _load_cfg()
        return PlainTextResponse(_setup_script(cfg, fmt), media_type="text/plain")
