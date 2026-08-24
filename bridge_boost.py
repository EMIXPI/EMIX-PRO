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
import link_health

BRIDGE_FILE = DATA_DIR / "bridge_config.json"

DEFAULTS = {
    "mode": "vps",            # "vps" = سرور شخصی ایران | "cdn" = CDN ایرانی (رایگان، بدون سرور)
    "bridge_host": "",        # VPS: IP سرور ایران | CDN: دامنه‌ی پشت ابر آروان
    "bridge_port": 443,       # VPS: پورت دلخواه | CDN: 443
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
# بازنویسی لینک‌ها
#   VPS:  فقط آدرس اتصال عوض می‌شود؛ host/SNI همان دامنه‌ی Railway می‌ماند
#          (TLS مستقیم از داخل سرور به Railway — گواهی Railway دیده می‌شود)
#   CDN:  آدرس + پارامترهای host/sni هم به دامنه‌ی CDN تغییر می‌کنند
#          (TLS در لبه‌ی اروان خاتمه می‌یابد — گواهی خود دامنه کاربر)
# ══════════════════════════════════════════════════════════════════════════════
def _replace_query_param(url: str, key: str, value: str) -> str:
    """جایگزینی پارامتر query بدون خراب‌کردن fragment (#remark) — پارامتر نباید داخل متن remark عوض شود."""
    return re.sub(rf"([?&]{key}=)[^&#]*", rf"\g<1>{value}", url)


def _rewrite_link(url: str, bridge_host: str, bridge_port: int, mode: str = "vps") -> str | None:
    """آدرس اتصال را به سرور پل تغییر می‌دهد؛ در حالت CDN پارامترهای host/sni هم بازنویسی می‌شوند."""
    try:
        if url.startswith(("vless://", "trojan://")):
            p = urlparse(url)
            # netloc = uuid@host:port → فقط host عوض شود
            userinfo = p.username or ""
            new_netloc = f"{userinfo}@{bridge_host}:{bridge_port}"
            out = url.replace(f"{p.scheme}://{p.netloc}", f"{p.scheme}://{new_netloc}", 1)
            if mode == "cdn":
                out = _replace_query_param(out, "host", bridge_host)
                out = _replace_query_param(out, "sni", bridge_host)
            return out

        if url.startswith("ss://"):
            # ss://base64@host:port/?plugin=...#remark
            p = urlparse(url)
            m = re.match(r"^([^@]+@)?([^:]+):(\d+)$", p.netloc)
            if not m:
                return None
            userinfo = m.group(1) or ""
            new_netloc = f"{userinfo}{bridge_host}:{bridge_port}"
            out = url.replace(f"ss://{p.netloc}", f"ss://{new_netloc}", 1)
            if mode == "cdn":
                # host داخل پارامتر plugin هم به دامنه‌ی CDN تغییر کند
                # نکته: داخل plugin، «=» و «;» به‌صورت %3D و %3B کدگذاری شده‌اند
                out = re.sub(r"(host%3D)[^&#]*", rf"\g<1>{bridge_host}", out)
                out = re.sub(r"(host=)[^;&#]*", rf"\g<1>{bridge_host}", out)
            return out

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
        bridged = _rewrite_link(original, cfg["bridge_host"], int(cfg["bridge_port"]), cfg.get("mode", "vps"))
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
    """
    تست واقعی زنجیره‌ی پل — اتصال TLS از مسیر پنل → پل → مقصد.
    حالت VPS:  SNI = دامنه‌ی Railway (گواهی Railway باید از مسیر سرور برگردد)
    حالت CDN:  SNI = دامنه‌ی خود کاربر (روی لبه‌ی اروان TLS خاتمه می‌یابد)
    """
    bridge_host = cfg.get("bridge_host")
    if not bridge_host:
        return {"ok": False, "detail": "ابتدا آدرس پل را ذخیره کنید"}
    target = _target_domain(cfg)
    mode = cfg.get("mode", "vps")

    # ── مرحله ۱: TLS (مثل قبل) ──
    if mode == "cdn":
        server_name = bridge_host
        chain = f"پنل → {bridge_host} (لبه‌ی CDN ایران) → {target}"
    else:
        server_name = target
        chain = f"پنل → {bridge_host}:{cfg.get('bridge_port', 443)} → {target}:443"
    t0 = time.perf_counter()
    ctx = ssl.create_default_context()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(
                bridge_host, int(cfg.get("bridge_port", 443)),
                ssl=ctx, server_hostname=server_name,
            ),
            timeout=10.0,
        )
        tls_ms = round((time.perf_counter() - t0) * 1000, 1)
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
    except asyncio.TimeoutError:
        return {"ok": False, "detail": "پاسخی از پل دریافت نشد (timeout) — آیا سرویس روشن است؟", "stage": "tls"}
    except ssl.SSLCertVerificationError as exc:
        return {"ok": False, "detail": f"گواهی نامعتبر: {str(exc)[:100]} — در حالت CDN گواهی SSL اروان را فعال کنید", "stage": "tls"}
    except ConnectionRefusedError:
        return {"ok": False, "detail": "اتصال رد شد — پورت پل باز نیست", "stage": "tls"}
    except Exception as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}: {str(exc)[:110]}", "stage": "tls"}

    # ── مرحله ۲: تونل کامل WebSocket از مسیر پل (دقیقاً مثل کلاینت) ──
    # این مرحله همان چیزی است که کلاینت واقعی انجام می‌دهد؛ اگر پاسخ داد،
    # کلاینت‌ها هم جواب می‌گیرند. اگر نه، علت دقیق برگردانده می‌شود.
    probe_link = await _first_probe_link()
    if probe_link is None:
        return {
            "ok": True,
            "ms": tls_ms,
            "stage": "tls-only",
            "detail": f"TLS سالم ({tls_ms}ms) — گواهی «{issuer or target}». برای تست کامل تونل، یک کانفیگ VLESS/Trojan-WS بسازید",
            "chain": chain,
        }
    uid, link, kind, is_xhttp = probe_link
    if mode == "cdn":
        ws_base, http_base = f"wss://{bridge_host}:{cfg.get('bridge_port', 443)}", f"https://{bridge_host}:{cfg.get('bridge_port', 443)}"
        no_verify = False
    else:
        ws_base, http_base = f"wss://{bridge_host}:{cfg.get('bridge_port', 443)}", f"https://{bridge_host}:{cfg.get('bridge_port', 443)}"
        no_verify = True  # سرتیفیکیت Railway با hostname پل — اتصال TCP واقعی همان است
    try:
        if is_xhttp:
            r = await link_health._probe_xhttp_tunnel(kind, uid, link, http_base=http_base, no_verify=no_verify)
        else:
            r = await link_health._probe_ws_tunnel(kind, uid, link, ws_base=ws_base, no_verify=no_verify)
    except Exception as exc:
        r = {"ok": False, "detail": f"{type(exc).__name__}: {str(exc)[:110]}"}

    total_ms = round(tls_ms + (r.get("e2e_ms") or 0), 1)
    if r.get("ok"):
        return {
            "ok": True,
            "ms": tls_ms,
            "e2e_ms": r.get("e2e_ms"),
            "total_ms": total_ms,
            "stage": "full-tunnel",
            "detail": f"✅ کل زنجیره کار می‌کند — TLS {tls_ms}ms + تونل {r.get('e2e_ms')}ms (تست واقعی مثل کلاینت: پاسخ {str(r.get('reply', ''))[:30]})",
            "chain": chain,
        }

    # ── تشخیص علت دقیق شکست تونل ──
    d = str(r.get("detail", ""))
    if "InvalidStatus" in d or "HTTP 200" in d or "rejected" in d:
        if mode == "cdn":
            return {
                "ok": False,
                "ms": tls_ms,
                "stage": "ws-rejected",
                "detail": ("⚠️ TLS سالم است ولی CDN درخواست WebSocket را عبور نمی‌دهد (HTTP 200 به‌جای 101). "
                           "دو ایراد رایج اروان: ۱) رکورد CNAME به مبدأ ثبت نشده (صفحه‌ی «Hello, World!» اروان برمی‌گردد) — "
                           "در پنل اروان → DNS → رکورد جدید: CNAME این ساب‌دامنه ← دامنه‌ی Railway خودتان با پروکسی روشن. "
                           "۲) WebSocket فعال نیست — پنل اروان → تنظیمات CDN → گزینه‌ی WebSocket را فعال کنید."),
                "chain": chain,
            }
        return {
            "ok": False, "ms": tls_ms, "stage": "ws-rejected",
            "detail": "TLS سالم است ولی WebSocket از مسیر سرور رد نمی‌شود — socat باید TCP خام را عبور دهد (اسکریپت نصب، خودش این کار را می‌کند)",
            "chain": chain,
        }
    if "1008" in d or "not authorized" in d:
        return {"ok": False, "ms": tls_ms, "stage": "auth",
                "detail": "تونل باز شد ولی UUID رد شد — کانفیگ غیرفعال است یا کوتایش تمام شده", "chain": chain}
    if "timeout" in d.lower() or "Timeout" in d:
        return {"ok": False, "ms": tls_ms, "stage": "tunnel-timeout",
                "detail": "هندشیک انجام شد ولی پاسخ تونل نیامد — اگر CDN: WebSocket و بازنویسی Host را در اروان فعال کنید", "chain": chain}
    return {"ok": False, "ms": tls_ms, "stage": "tunnel",
            "detail": f"TLS سالم ({tls_ms}ms) ولی تونل شکست خورد: {d[:140]}", "chain": chain}


async def _first_probe_link():
    """اولین کانفیگ مجاز مناسبِ تست تونل کامل → (uid, link, kind, is_xhttp)"""
    async with LINKS_LOCK:
        snap = [(uid, dict(d)) for uid, d in LINKS.items()]
    prio = {"vless-ws": 0, "trojan-ws": 1, "shadowsocks": 2}
    best = None
    for uid, d in snap:
        proto = d.get("protocol", "vless-ws")
        if not is_link_allowed(d):
            continue
        if proto in prio:
            cand = (prio[proto], uid, d, {"vless-ws": "vless", "trojan-ws": "trojan", "shadowsocks": "ss"}[proto], False)
            if best is None or cand[0] < best[0]:
                best = cand
        elif proto.startswith("xhttp-") or proto.startswith("vless-xhttp"):
            cand = (5, uid, d, "vless", True)
            if best is None:
                best = cand
        elif proto.startswith("trojan-xhttp-"):
            cand = (6, uid, d, "trojan", True)
            if best is None:
                best = cand
    if best is None:
        return None
    return best[1], best[2], best[3], best[4]


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


CDN_TLS_PORTS = (443, 2053, 2083, 2087, 2096, 8443)  # پورت‌های TLS استاندارد لبه (مثل آروان)


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
        mode = str(body.get("mode", cfg.get("mode", "vps")))
        if mode not in ("vps", "cdn"):
            mode = "vps"
        if host and not re.match(r"^[a-zA-Z0-9._-]+$", host):
            raise HTTPException(status_code=400, detail="آدرس سرور نامعتبر است")
        if not (1 <= port <= 65535):
            raise HTTPException(status_code=400, detail="پورت نامعتبر است")
        if mode == "cdn":
            if host and not host.startswith("api.") and "." not in host:
                raise HTTPException(status_code=400, detail="در حالت CDN باید دامنه (نه IP) وارد کنید")
            if port not in CDN_TLS_PORTS:
                raise HTTPException(status_code=400, detail=f"پورت CDN باید یکی از پورت‌های TLS استاندارد باشد: {', '.join(map(str, CDN_TLS_PORTS))}")
        cfg["mode"] = mode
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

    @app.post("/api/bridge/links/{uid}/ping")
    async def bridge_ping_link(uid: str, _=Depends(require_auth)):
        """پینگ واقعی کانفیگ «از مسیر پل» — دقیقاً همان مسیری که کلاینتِ لینک پل‌دار می‌رود."""
        cfg = _load_cfg()
        if not cfg.get("bridge_host"):
            raise HTTPException(status_code=400, detail="ابتدا پل را ذخیره و فعال کنید")
        async with LINKS_LOCK:
            link = LINKS.get(uid)
        if not link:
            raise HTTPException(status_code=404, detail="کانفیگ یافت نشد")
        if not is_link_allowed(link):
            return {"ok": False, "protocol": link.get("protocol"), "detail": "کانفیگ غیرفعال است یا کوتای آن تمام شده",
                    "checked_at": datetime.now().isoformat()}
        proto = link.get("protocol", "vless-ws")
        mode = cfg.get("mode", "vps")
        bh, bp = cfg["bridge_host"], int(cfg.get("bridge_port", 443))
        if mode == "cdn":
            ws_base, http_base, no_verify = f"wss://{bh}:{bp}", f"https://{bh}:{bp}", False
        else:
            ws_base, http_base, no_verify = f"wss://{bh}:{bp}", f"https://{bh}:{bp}", True
        if proto == "vless-ws":
            r = {"test": "ws-tunnel-via-bridge", **await link_health._probe_ws_tunnel("vless", uid, link, ws_base=ws_base, no_verify=no_verify)}
        elif proto == "trojan-ws":
            r = {"test": "ws-tunnel-via-bridge", **await link_health._probe_ws_tunnel("trojan", uid, link, ws_base=ws_base, no_verify=no_verify)}
        elif proto == "shadowsocks":
            r = {"test": "ws-tunnel-via-bridge", **await link_health._probe_ws_tunnel("ss", uid, link, ws_base=ws_base, no_verify=no_verify)}
        elif proto.startswith("trojan-xhttp-"):
            r = {"test": "xhttp-tunnel-via-bridge", **await link_health._probe_xhttp_tunnel("trojan", uid, link, http_base=http_base, no_verify=no_verify)}
        elif proto.startswith("xhttp-") or proto.startswith("vless-xhttp"):
            r = {"test": "xhttp-tunnel-via-bridge", **await link_health._probe_xhttp_tunnel("vless", uid, link, http_base=http_base, no_verify=no_verify)}
        else:
            raise HTTPException(status_code=400, detail="این پروتکل تست پل ندارد")
        r.setdefault("ok", False)
        r["protocol"] = proto
        r["via"] = f"{bh}:{bp}"
        r["checked_at"] = datetime.now().isoformat()
        async with LINKS_LOCK:
            if uid in LINKS:
                LINKS[uid]["last_bridge_ping"] = r
        return r

    @app.get("/api/bridge/links")
    async def bridge_links(_=Depends(require_auth)):
        return {"links": await _bridged_links()}

    @app.get("/api/bridge/script")
    async def bridge_script(fmt: str = "bash", _=Depends(require_auth)):
        cfg = _load_cfg()
        return PlainTextResponse(_setup_script(cfg, fmt), media_type="text/plain")
