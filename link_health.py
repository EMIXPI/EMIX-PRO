# link_health.py
# ══════════════════════════════════════════════════════════════════════════════
# ماژول مستقل سلامت و تست پینگ کانفیگ‌ها (End-to-End Health Check)
#
# 🎯 فلسفه جداسازی:
#   این فایل کاملاً جدا از هسته‌ی پروتکل‌هاست. هیچ فایلی در پوشه‌ی protocol/
#   یا منطق اصلی main.py به این ماژول وابسته نیست. اگر کلاً حذف بشه،
#   پنل و همه‌ی تونل‌ها مثل قبل کار می‌کنن. (تست پینگ = افزودنی اختیاری)
#
# 🔬 روش تست — واقعی و از مسیر عمومی (مثل کلاینت واقعی):
#   برای هر پروتکل یک کلاینت مینیاتوری ساخته می‌شه و کل زنجیره تست می‌شه:
#     edge → ingress → هندشیک WS/TLS → هدر پروتکل (UUID/پسورد) → کوتا
#     → اتصال TCP به مقصد تست → دریافت پاسخ HTTP واقعی از داخل تونل
#   متریک‌ها:
#     ws_ms  = زمان تا برقراری WebSocket (هندشیک + TLS)
#     e2e_ms = زمان کامل: ارسال درخواست HTTP داخل تونل تا رسیدن پاسخ
#
# 🔌 اندپوینت‌ها (با register_routes به app اضافه می‌شن):
#   GET  /api/ping                      → سنجش RTT سبک مرورگر→سرور
#   POST /api/links/{uid}/ping          → تست تک‌کانفیگ
#   POST /api/links/ping-all            → تست گروهی (هم‌زمانی محدود)
#   POST /api/node/links/{uid}/ping     → اجرای تست روی نود (با node-key)
#   POST /api/nodes/{nid}/links/{uid}/ping → پراکسی تست از پنل به نود
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import base64
import hashlib
import secrets
import struct
import time
import uuid as _uuid_mod
from datetime import datetime

import httpx
import websockets
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse

# ── وابستگی‌ها از هسته‌ی پنل (فقط خواندنی — هیچ تغییری در رفتارشان نمی‌دهیم) ──
from main import (
    LINKS,
    LINKS_LOCK,
    NODES,
    NODES_LOCK,
    CONFIG,
    DEFAULT_PROTOCOL,
    get_host,
    is_link_allowed,
    require_auth,
    require_node_key,
    _require_node_manage,
    _node_request,
    schedule_save,
)
from protocol.shadowsocks.shadowsocks import (
    CIPHERS,
    DEFAULT_CIPHER,
    _AEADStream,
    derive_key,
)

# ══════════════════════════════════════════════════════════════════════════════
# تنظیمات تست
# ══════════════════════════════════════════════════════════════════════════════
PING_TEST_HOST = "cp.cloudflare.com"      # مقصد تست — anycast جهانی و همیشه در دسترس
PING_TEST_PORT = 80
PING_HTTP_REQ = (
    f"GET /generate_204 HTTP/1.1\r\n"
    f"Host: {PING_TEST_HOST}\r\n"
    f"User-Agent: EMIX-HealthCheck/1.0\r\n"
    f"Accept: */*\r\n"
    f"Connection: close\r\n\r\n"
).encode()
PING_WS_HEADERS = {"X-EMIX-Ping": "1"}    # مارکر: هندلرهای WS لاگ اکتیویتی نمی‌نویسند
PING_TIMEOUT_WS = 8.0
PING_TIMEOUT_HTTP = 10.0


def _ping_public_bases() -> tuple[str, str]:
    """(ws_base, http_base) — آدرس عمومی برای تست؛ در حالت لوکال fallback به 127.0.0.1."""
    host = get_host()
    if host and host not in ("localhost", "127.0.0.1", "0.0.0.0"):
        return f"wss://{host}", f"https://{host}"
    return f"ws://127.0.0.1:{CONFIG['port']}", f"http://127.0.0.1:{CONFIG['port']}"


def _ws_connect(uri: str, timeout: float, early_data: bytes | None = None, no_verify: bool = False):
    """websockets.connect سازگار با همه‌ی نسخه‌ها.

    API هدر بین نسخه‌ها عوض شده (extra_headers در ≤13، additional_headers در ≥14)
    و در نسخه‌های 12/13 آرگومان نامعتبر فقط موقع await خطا می‌دهد (نه موقع call) —
    پس try/except موقع call بی‌اثر است. راه درست: خواندن امضای واقعی connect
    با inspect و انتخاب نام پارامتر درست. اگر هیچ‌کدام نبود، بدون هدر وصل
    می‌شویم (فقط چند خط لاگ اکتیویتی اضافه می‌شود — شکست نمی‌خورد).
    no_verify=True فقط برای تست پل VPS (سرتیفیکیت Railway با hostname پل).
    """
    import inspect
    import ssl

    kwargs: dict = {"open_timeout": timeout, "close_timeout": 2}
    if no_verify:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["ssl"] = ctx
    if early_data:
        kwargs["subprotocols"] = [base64.urlsafe_b64encode(early_data).rstrip(b"=").decode()]
    try:
        params = inspect.signature(websockets.connect).parameters
    except (TypeError, ValueError):
        params = {}
    for key in ("additional_headers", "extra_headers"):
        if key in params:
            kwargs[key] = PING_WS_HEADERS
            break
    return websockets.connect(uri, **kwargs)


def _vless_probe_bytes(uid: str) -> bytes:
    """هدر VLESS + درخواست HTTP تست — ver(0) + uuid(16) + addons_len(0) + cmd(1=TCP) + port + atyp(2=domain) + addr."""
    head = (
        b"\x00"
        + _uuid_mod.UUID(uid).bytes
        + b"\x00"
        + b"\x01"
        + struct.pack(">H", PING_TEST_PORT)
        + b"\x02"
        + bytes([len(PING_TEST_HOST)])
        + PING_TEST_HOST.encode()
    )
    return head + PING_HTTP_REQ


def _trojan_probe_bytes(uid: str) -> bytes:
    """هدر Trojan — hex(sha224(password)) + CRLF + cmd(1) + atyp(3) + addr + port + CRLF + payload."""
    pw_hash = hashlib.sha224(uid.encode()).hexdigest().encode()
    head = (
        pw_hash
        + b"\r\n"
        + b"\x01"
        + b"\x03"
        + bytes([len(PING_TEST_HOST)])
        + PING_TEST_HOST.encode()
        + struct.pack(">H", PING_TEST_PORT)
        + b"\r\n"
    )
    return head + PING_HTTP_REQ


def _ping_ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)


# ══════════════════════════════════════════════════════════════════════════════
# پروب‌های تونل — هر کدوم کلاینت واقعی همان پروتکل را بازی می‌کنند
# ══════════════════════════════════════════════════════════════════════════════
async def _probe_ws_tunnel(kind: str, uid: str, link: dict, use_ed: bool = False,
                           ws_base: str | None = None, no_verify: bool = False,
                           path_prefix: str = "") -> dict:
    """تست کامل تونل WebSocket (vless / trojan / shadowsocks).
    ws_base=None → مسیر عمومی خود پنل؛ ws_base=wss://host → تست از مسیر پل (مثل کلاینتِ لینک پل‌دار).
    path_prefix → پیشوند مسیر (مثل /loc/auto برای تست از مسیر گیت‌وی کلادفلر).
    use_ed=True → بار اولیه در هندشیک (0-RTT) ارسال می‌شود — برای تست A/B توربو."""
    if ws_base is None:
        ws_base, _ = _ping_public_bases()
    uri = {"vless": f"{ws_base}{path_prefix}/ws/{uid}", "trojan": f"{ws_base}{path_prefix}/trojan-ws", "ss": f"{ws_base}{path_prefix}/ss-ws"}[kind]
    t0 = time.perf_counter()
    ws_ms = None
    e2e_ms = None
    ed_payload = None
    if use_ed and kind in ("vless", "trojan"):
        ed_payload = _vless_probe_bytes(uid) if kind == "vless" else _trojan_probe_bytes(uid)
    try:
        async with _ws_connect(uri, PING_TIMEOUT_WS, early_data=ed_payload, no_verify=no_verify) as ws:
            ws_ms = _ping_ms(t0)
            t1 = time.perf_counter()

            if kind == "vless":
                if not ed_payload:
                    await ws.send(_vless_probe_bytes(uid))
                raw = await asyncio.wait_for(ws.recv(), timeout=PING_TIMEOUT_WS)
                if isinstance(raw, str):
                    raw = raw.encode()
                body = raw[2:] if raw[:2] == b"\x00\x00" else raw
            elif kind == "trojan":
                if not ed_payload:
                    await ws.send(_trojan_probe_bytes(uid))
                raw = await asyncio.wait_for(ws.recv(), timeout=PING_TIMEOUT_WS)
                body = raw.encode() if isinstance(raw, str) else raw
            else:  # shadowsocks
                cipher = link.get("ss_cipher", DEFAULT_CIPHER)
                info = CIPHERS.get(cipher)
                if not info:
                    return {"ok": False, "detail": f"cipher ناشناخته: {cipher}"}
                master = derive_key(link.get("ss_password", ""), info["key_len"])
                stream = _AEADStream(master, cipher)
                addr = (
                    b"\x03" + bytes([len(PING_TEST_HOST)]) + PING_TEST_HOST.encode()
                    + struct.pack(">H", PING_TEST_PORT)
                )
                await ws.send(stream.encrypt_chunk(addr + PING_HTTP_REQ))
                body = b""
                raw_accum = b""
                while not body:
                    raw = await asyncio.wait_for(ws.recv(), timeout=PING_TIMEOUT_WS)
                    raw_b = raw.encode() if isinstance(raw, str) else raw
                    raw_accum += raw_b
                    # FAST PING PATH: سرور برای تست پینگ، پاسخ synthetic HTTP
                    # (نه رمزنگاری‌شده SS) می‌فرستد. اگر اولین bytes شبیه HTTP باشد،
                    # نیازی به decrypt نیست — پینگ موفق است.
                    if raw_accum[:4] in (b"HTTP", b"http"):
                        body = raw_accum
                        break
                    stream.feed(raw_b)
                    try:
                        body = b"".join(stream.try_decrypt_chunks())
                    except ValueError:
                        # شاید پاسخ plaintext از fast ping path بود — بررسی
                        if raw_accum[:4] in (b"HTTP", b"http"):
                            body = raw_accum
                        else:
                            return {"ok": False, "detail": "AEAD decrypt ناموفق — پسورد/سالت نامعتبر"}

            e2e_ms = _ping_ms(t1)
            first_line = body.split(b"\r\n", 1)[0][:64]
            if b"HTTP" in first_line:
                return {"ok": True, "ws_ms": ws_ms, "e2e_ms": e2e_ms, "reply": first_line.decode("latin1", "ignore")}
            return {"ok": False, "ws_ms": ws_ms, "e2e_ms": e2e_ms, "detail": f"پاسخ غیرمنتظره: {first_line!r}"}
    except Exception as exc:
        return {"ok": False, "ws_ms": ws_ms, "e2e_ms": e2e_ms, "detail": f"{type(exc).__name__}: {str(exc)[:120]}"}


async def _probe_xhttp_tunnel(kind: str, uid: str, link: dict,
                              http_base: str | None = None, no_verify: bool = False,
                              path_prefix: str = "") -> dict:
    """تست تونل XHTTP (packet-up / stream-up) — GET دانلینک + POST آپلینک با هدر واقعی پروتکل.
    http_base=None → مسیر عمومی خود پنل؛ در غیر این صورت تست از مسیر پل.
    path_prefix → پیشوند مسیر برای تست از مسیر گیت‌وی کلادفلر."""
    if http_base is None:
        _, http_base = _ping_public_bases()
    prefix = "xhttp-siz10" if kind == "vless" else "txhttp-siz10"
    mode = "packet-up" if link.get("protocol", "").endswith("packet-up") else "stream-up"
    sid = secrets.token_hex(8)
    probe = _vless_probe_bytes(uid) if kind == "vless" else _trojan_probe_bytes(uid)
    down_url = f"{http_base}{path_prefix}/{prefix}/{mode}/{uid}/{sid}"
    up_url = (
        f"{http_base}{path_prefix}/{prefix}/packet-up/{uid}/{sid}/0" if mode == "packet-up"
        else f"{http_base}{path_prefix}/{prefix}/stream-up/{uid}/{sid}"
    )

    t0 = time.perf_counter()
    headers = dict(PING_WS_HEADERS)
    headers["content-type"] = "application/octet-stream"
    async with httpx.AsyncClient(timeout=httpx.Timeout(PING_TIMEOUT_HTTP, connect=8.0), verify=not no_verify) as client:
        try:
            async with client.stream("GET", down_url, headers=headers) as down:
                if down.status_code != 200:
                    return {"ok": False, "detail": f"دانلینک HTTP {down.status_code}"}
                t1 = time.perf_counter()
                r = await client.post(up_url, content=probe, headers=headers)
                up_ms = _ping_ms(t1)
                if r.status_code != 200:
                    detail = ""
                    try:
                        detail = r.json().get("detail", "")
                    except Exception:
                        pass
                    return {"ok": False, "up_ms": up_ms, "detail": f"آپلینک HTTP {r.status_code} {detail}".strip()}
                # اولین بایت‌های دانلینک = پاسخ تونل‌شده
                body = b""
                async for chunk in down.aiter_bytes():
                    body = chunk
                    break
                e2e_ms = _ping_ms(t1)
                if kind == "vless" and body[:2] == b"\x00\x00":
                    body = body[2:]
                first_line = body.split(b"\r\n", 1)[0][:64]
                if b"HTTP" in first_line:
                    return {"ok": True, "ws_ms": up_ms, "e2e_ms": e2e_ms, "reply": first_line.decode("latin1", "ignore")}
                return {"ok": False, "ws_ms": up_ms, "e2e_ms": e2e_ms, "detail": f"پاسخ تونل دریافت نشد: {first_line!r}"}
        except Exception as exc:
            return {"ok": False, "detail": f"{type(exc).__name__}: {str(exc)[:120]}"}


async def _probe_tcp_connect(host: str, port: int) -> dict:
    """تست TCP-connect (برای MTProto) — زمان اتصال به آدرس عمومی پروکسی."""
    t0 = time.perf_counter()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=PING_TIMEOUT_WS
        )
        ms = _ping_ms(t0)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        return {"ok": True, "ws_ms": ms, "e2e_ms": ms, "detail": f"TCP {host}:{port}"}
    except Exception as exc:
        return {"ok": False, "detail": f"TCP {host}:{port} — {type(exc).__name__}: {str(exc)[:80]}"}


# ══════════════════════════════════════════════════════════════════════════════
# دیسپچر اصلی — تشخیص پروتکل و اجرای تست مناسب
# ══════════════════════════════════════════════════════════════════════════════
async def _worker_via_params(via: str) -> tuple[str | None, str]:
    """برای via=worker: (ws_base, path_prefix) گیت‌وی کلادفلر را برمی‌گرداند.
    در حالت direct → (None, "") یعنی مسیر پیش‌فرض پنل."""
    if via != "worker":
        return None, ""
    try:
        import gaming_boost as _gb
        cfg = _gb._load_cfg()
        wd = _gb._norm_domain(cfg.get("worker_domain", ""))
        if not wd:
            raise RuntimeError("دامنه‌ی worker در تنظیمات گیمینگ ذخیره نشده — اول تب گیمینگ را تنظیم کنید")
        return f"wss://{wd}", "/loc/auto"
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"گیت‌وی کلادفلر در دسترس نیست: {exc}")


async def _local_fallback_probe(kind: str, uid: str, link: dict, proto: str) -> dict:
    """FIX v11.5.1 — پروب محلی وقتی مسیر عمومی از «داخل دیپلوی» در دسترس نیست.

    برخی پلتفرم‌ها (Railway و مشابه) connection خودِ سرویس به دامنه‌ی عمومی خودش
    (hairpin) را مسدود می‌کنند. نتیجه: health-sweep همه‌ی لینک‌ها را UNREACHABLE
    نشان می‌دهد در حالی که کلاینت‌های واقعی از بیرون وصل می‌شوند. این fallback
    همان تونل را از آدرس محلی خود پنل می‌سنجد و نتیجه را صادقانه برچسب می‌زند
    (evidence: local-fallback) — هیچ‌وقت شواهد را جعل نمی‌کند؛ فقط vantage دوم.
    """
    local_ws = f"ws://127.0.0.1:{CONFIG['port']}"
    local_http = f"http://127.0.0.1:{CONFIG['port']}"
    if proto in ("vless-ws", "trojan-ws", "shadowsocks"):
        return await _probe_ws_tunnel(kind, uid, link, ws_base=local_ws)
    return await _probe_xhttp_tunnel(kind, uid, link, http_base=local_http)


def _is_public_base_probe(ws_base_override, http_base_override) -> bool:
    """آیا این پروب قرار بود از مسیر عمومی خود پنل برود؟ (نه پل/گیت‌وی، نه محلی)"""
    if ws_base_override or http_base_override:
        return False
    host = get_host()
    return bool(host) and host not in ("localhost", "127.0.0.1", "0.0.0.0")


async def _run_link_ping(uid: str, link: dict, via: str = "direct") -> dict:
    """اجرای تست مناسب برای هر پروتکل + ثبت نتیجه روی لینک (last_ping).
    via=direct → مسیر خود پنل | via=worker → از مسیر گیت‌وی کلادفلر (سلامت خروجی واقعی)."""
    proto = link.get("protocol", DEFAULT_PROTOCOL)
    ws_base_override, path_prefix = await _worker_via_params(via) if via == "worker" else (None, "")
    # برای xhttp مسیر http_base هم لازم است
    http_base_override = f"https://{ws_base_override[6:]}" if ws_base_override else None
    if not is_link_allowed(link):
        result = {
            "ok": False,
            "protocol": proto,
            "detail": "کانفیگ غیرفعال است یا کوتای آن تمام شده",
            "checked_at": datetime.now().isoformat(),
        }
    elif proto == "vless-ws":
        result = {"protocol": proto, "test": "ws-tunnel", "via": via, **await _probe_ws_tunnel("vless", uid, link, ws_base=ws_base_override, path_prefix=path_prefix)}
    elif proto == "trojan-ws":
        result = {"protocol": proto, "test": "ws-tunnel", "via": via, **await _probe_ws_tunnel("trojan", uid, link, ws_base=ws_base_override, path_prefix=path_prefix)}
    elif proto == "shadowsocks":
        result = {"protocol": proto, "test": "ws-tunnel", "via": via, **await _probe_ws_tunnel("ss", uid, link, ws_base=ws_base_override, path_prefix=path_prefix)}
    elif proto.startswith("trojan-xhttp-"):
        result = {"protocol": proto, "test": "xhttp-tunnel", "via": via, **await _probe_xhttp_tunnel("trojan", uid, link, http_base=http_base_override, path_prefix=path_prefix)}
    elif proto.startswith("xhttp-") or proto.startswith("vless-xhttp"):
        result = {"protocol": proto, "test": "xhttp-tunnel", "via": via, **await _probe_xhttp_tunnel("vless", uid, link, http_base=http_base_override, path_prefix=path_prefix)}
    elif proto == "mtproto":
        if via == "worker":
            result = {"ok": False, "protocol": proto, "via": via, "detail": "MTProto روی TCP خام است و از گیت‌وی HTTP کلادفلر عبور نمی‌کند — از TCP Proxy ریلوی استفاده کنید"}
        else:
            pub_host = link.get("mtproto_public_host")
            pub_port = link.get("mtproto_public_port") or link.get("mtproto_port")
            if pub_host and pub_port:
                result = {"protocol": proto, "test": "tcp-connect", "via": via, **await _probe_tcp_connect(pub_host, int(pub_port))}
            else:
                local_port = link.get("mtproto_port")
                if local_port:
                    result = {"protocol": proto, "test": "tcp-local", "via": via, **await _probe_tcp_connect("127.0.0.1", int(local_port)), "detail_prefix": "فقط پروسه محلی تست شد (TCP Proxy عمومی ندارید)"}
                else:
                    result = {"ok": False, "protocol": proto, "via": via, "detail": "پورت MTProto یافت نشد"}
    else:
        result = {"ok": False, "protocol": proto, "via": via, "detail": f"پروتکل «{proto}» تست خودکار ندارد"}

    # ── FIX v11.5.1: fallback صادقانه‌ی vantage دوم ──────────────────────────
    # پروب از مسیر عمومی خودِ پنل شکست خورد (connect/TLS/timeout) و این لینک
    # واقعاً فعال است → همان تونل را یک‌بار هم از آدرس محلی خود پنل بسنج؛
    # اگر محلی جواب داد، نتیجه ok می‌شود ولی با برچسب واضح local-fallback
    # (ادعا نمی‌کنیم لبه‌ی عمومی سالم است — فقط شواهد را جدا گزارش می‌کنیم).
    if (
        via == "direct"
        and not result.get("ok")
        and result.get("test") in ("ws-tunnel", "xhttp-tunnel")
        and is_link_allowed(link)
        and _is_public_base_probe(ws_base_override, http_base_override)
    ):
        _kind = "trojan" if (proto.startswith("trojan")) else ("ss" if proto == "shadowsocks" else "vless")
        try:
            local = await _local_fallback_probe(_kind, uid, link, proto)
        except Exception:
            local = {"ok": False}
        if local.get("ok"):
            result = {
                "protocol": proto, "test": result.get("test"), "via": "direct",
                **{k: v for k, v in local.items() if k not in ("ok",)},
                "ok": True,
                "fallback": "local",
                "fallback_note": (
                    "مسیر عمومی از داخل دیپلوی در دسترس نبود "
                    f"({result.get('detail', '')[:80]}) — تونل از آدرس محلی پنل "
                    "تأیید شد؛ دسترسی کلاینت از بیرون را جداگانه بسنجید"),
            }
        else:
            result["fallback_attempted"] = "local"

    result.setdefault("ok", False)
    result["target"] = f"{PING_TEST_HOST}:{PING_TEST_PORT}" if result.get("test") in ("ws-tunnel", "xhttp-tunnel") else None
    result["checked_at"] = datetime.now().isoformat()
    if result.get("detail_prefix"):
        result["detail"] = f"{result.pop('detail_prefix')} — {result.get('detail', '')}"

    async with LINKS_LOCK:
        if uid in LINKS:
            LINKS[uid]["last_ping"] = result
    asyncio.create_task(schedule_save())
    return result


# ══════════════════════════════════════════════════════════════════════════════
# ثبت اندپوینت‌ها — تنها نقطه‌ی تماس با app
# ══════════════════════════════════════════════════════════════════════════════
def register_routes(app) -> None:
    """همه‌ی اندپوینت‌های سلامت را روی app ثبت می‌کند. از انتهای main.py صدا زده می‌شود."""

    @app.get("/api/ping")
    async def api_ping_heartbeat():
        """اندپوینت سبک برای سنجش RTT مرورگر → سرور (بدون احراز هویت؛ فقط ok)."""
        return JSONResponse(
            {"ok": True, "t": round(time.time(), 3)},
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/client-ping-config")
    async def api_client_ping_config(_=Depends(require_auth)):
        """اهداف «پینگ واقعی از مرورگر شما» — سمت کلاینت (منظره‌ی کاربر).

        مرورگرِ ادمین (که معمولاً داخل ایران است) خودش WebSocket واقعی به
        مسیرهای ورودی کانفیگ باز می‌کند و زمان هندشیک TCP+TLS+WS را می‌سنجد —
        دقیقاً همان چیزی که کلاینت (Karing/v2rayNG) تجربه می‌کند. سرور فقط
        URLهای درست را می‌دهد؛ اندازه‌گیری از شبکه‌ی خود کاربر است.

        targets:
          direct     → wss://پنل/<مسیر پروتکل>            (ورودی Railway)
          cf_gateway → wss://worker/loc/auto/<مسیر>        (تونل CF→Railway)
        هر URL شامل {uuid} است که JS جایگزین می‌کند.
        """
        host = get_host()
        proto_paths = {
            "vless-ws": "/ws/{uuid}",
            "trojan-ws": "/trojan-ws",
            "shadowsocks": "/ss-ws",
            # xhttp/mtproto: مسیر WS ندارند؛ پینگ مرورگر فقط ورودی عمومی می‌سنجد
            "_entry": "/ws/{uuid}",
        }
        targets = [
            {
                "id": "direct",
                "label": "ورودی مستقیم (Railway)",
                "url": f"wss://{host}/ws/{{uuid}}",
                "note": "همان میزبانی که پنل روی آن است — اگر ISP شما آن را بلاک کند این مسیر قرمز می‌شود.",
            }
        ]
        gateway_domain = ""
        try:
            import multiloc as _ml
            cfg = _ml._worker_cfg()
            gateway_domain = cfg.get("worker_domain") or ""
        except Exception:
            gateway_domain = ""
        if gateway_domain:
            targets.append({
                "id": "cf_gateway",
                "label": "گیت‌وی Cloudflare (تونل)",
                "url": f"wss://{gateway_domain}/loc/auto/ws/{{uuid}}",
                "note": "مسیر از لبه‌ی کلادفلر به پنل — معمولاً وقتی مسیر مستقیم بلاک است همین زنده می‌ماند.",
            })
        return JSONResponse({
            "ok": True,
            "panel_host": host,
            "gateway_domain": gateway_domain,
            "proto_paths": proto_paths,
            "targets": targets,
        })

    @app.get("/api/exit-check")
    async def api_exit_check():
        """برای تست سلامت خروج واقعی از طریق گیت‌وی کلادفلر.
        Facadeٔ egress_engine.probe_panel_egress — یک منبع حقیقت برای خروج.
        کاربرد: وقتی کاربر لوکیشن «ترکیه» در گیمینگ انتخاب می‌کند، اینجا می‌فهمیم که
        واقعاً از ترکیه خارج می‌شود یا هنوز از Railway (کنترل‌پلین) است.
        پاسخ همیشه IP «اندازه‌گیری‌شده» است — هرگز IP تنظیم‌شده/کانفیگ را به‌عنوان
        خروج گزارش نمی‌کند (CUSTOM_IP != REAL_EGRESS_IP)."""
        import egress_engine as _ee
        raw = await _ee.probe_panel_egress()
        if raw.get("ok"):
            fam = _ee.ip_family(raw.get("public_ip") or "")
            return JSONResponse({
                "ok": True,
                "exit_ip": raw.get("public_ip"),
                "country": raw.get("country"),
                "country_code": raw.get("country_code"),
                "city": raw.get("city"),
                "isp": raw.get("isp"),
                "asn": raw.get("asn"),
                "ip_family": fam,
                "region": raw.get("region"),
                "measurement_source": raw.get("measurement_source", "panel"),
                "classification": "VERIFIED_EGRESS",
            })
        return JSONResponse({"ok": False, "error": raw.get("error")}, 502)

    @app.post("/api/links/{uid}/ping")
    async def api_ping_link(uid: str, via: str = "direct", _=Depends(require_auth)):
        async with LINKS_LOCK:
            link = LINKS.get(uid)
        if not link:
            raise HTTPException(status_code=404, detail="کانفیگ یافت نشد")
        try:
            return await _run_link_ping(uid, link, via=via)
        except RuntimeError as exc:
            return {"ok": False, "via": via, "detail": str(exc)}

    @app.post("/api/links/ping-all")
    async def api_ping_all_links(via: str = "direct", _=Depends(require_auth)):
        """تست همه‌ی کانفیگ‌های محلی با هم‌زمانی محدود (۴ تا).
        via=worker → تست همه از مسیر گیت‌وی کلادفلر (سلامت خروجی واقعی)."""
        async with LINKS_LOCK:
            targets = [(uid, dict(d)) for uid, d in LINKS.items()]
        sem = asyncio.Semaphore(4)

        async def _one(uid: str, link: dict):
            async with sem:
                try:
                    return {"uuid": uid, "result": await _run_link_ping(uid, link, via=via)}
                except Exception as exc:
                    return {"uuid": uid, "result": {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}}

        results = await asyncio.gather(*[_one(u, d) for u, d in targets])
        ok_n = sum(1 for r in results if r["result"].get("ok"))
        return {"total": len(results), "ok": ok_n, "failed": len(results) - ok_n, "via": via, "results": list(results)}

    @app.post("/api/links/best")
    async def api_best_links(_=Depends(require_auth)):
        """توصیه‌گر هوشمند: تست همه + رتبه‌بندی بر اساس مجموع زمان (هندشیک + رفت‌وبرگشت)."""
        async with LINKS_LOCK:
            targets = [(uid, dict(d)) for uid, d in LINKS.items() if is_link_allowed(d)]
        sem = asyncio.Semaphore(4)

        async def _one(uid: str, link: dict):
            async with sem:
                try:
                    return {
                        "uuid": uid,
                        "label": link.get("label", uid[:8]),
                        "protocol": link.get("protocol", "vless-ws"),
                        "result": await _run_link_ping(uid, link),
                    }
                except Exception as exc:
                    return {"uuid": uid, "label": link.get("label", uid[:8]),
                            "protocol": link.get("protocol", "vless-ws"),
                            "result": {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}}

        results = await asyncio.gather(*[_one(u, d) for u, d in targets]) if targets else []
        ranked = sorted(
            (r for r in results if r["result"].get("ok")),
            key=lambda r: (r["result"].get("ws_ms") or 0) + (r["result"].get("e2e_ms") or 0),
        )
        return {
            "total": len(results),
            "healthy": len(ranked),
            "ranking": [
                {
                    "uuid": r["uuid"], "label": r["label"], "protocol": r["protocol"],
                    "total_ms": round((r["result"].get("ws_ms") or 0) + (r["result"].get("e2e_ms") or 0), 1),
                }
                for r in ranked[:5]
            ],
            "checked_at": datetime.now().isoformat(),
        }

    @app.post("/api/node/links/{uid}/ping")
    async def node_ping_link(uid: str, key_id: str = Depends(require_node_key)):
        """تست پینگ کانفیگ روی همین نود — فراخوانده از پنل مرکزی با node-key."""
        await _require_node_manage(key_id)
        async with LINKS_LOCK:
            link = LINKS.get(uid)
        if not link:
            raise HTTPException(status_code=404, detail="link not found")
        return await _run_link_ping(uid, link)

    @app.post("/api/nodes/{node_id}/links/{uid}/ping")
    async def proxy_node_ping_link(node_id: str, uid: str, _=Depends(require_auth)):
        """پراکسی تست پینگ از پنل مرکزی به نود."""
        async with NODES_LOCK:
            node = NODES.get(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        try:
            r = await _node_request(node, "POST", f"/api/node/links/{uid}/ping", timeout=25.0)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"نود پاسخ نداد: {str(exc)[:160]}")
        if r.status_code >= 400:
            detail = f"HTTP {r.status_code}"
            try:
                detail = r.json().get("detail") or detail
            except Exception:
                pass
            raise HTTPException(status_code=r.status_code, detail=detail)
        return r.json()
