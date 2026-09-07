# link_health.py
# ══════════════════════════════════════════════════════════════════════════════
# ماژول مستقل سلامت و تست پینگ کانفیگ‌ها (End-to-End Health Check)
# ادغام‌شده از EMIX-PRO (نسخه‌ی اثبات‌شده در پروداکشن) روی هسته‌ی EMIX پایه.
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
# 🔌 اندپوینت‌ها (با register_routes به app اضافه می‌شن؛ از انتهای main.py):
#   GET  /api/ping               → heartbeat سبک (healthcheck دیپلوی)
#   POST /api/links/{uid}/ping   → تست تک‌کانفیگ (مسیر واقعی کلاینت)
#   POST /api/links/ping-all     → تست گروهی (هم‌زمانی محدود) + پیشرفت مرحله‌ای
#   POST /api/links/best         → تست همه + رتبه‌بندی بر اساس زمان واقعی
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import base64
import hashlib
import secrets
import socket
import ssl
import struct
import time
import uuid as _uuid_mod
from datetime import datetime

import httpx
import websockets
from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse

# ── وابستگی‌ها از هسته‌ی پنل (فقط خواندنی — هیچ تغییری در رفتارشان نمی‌دهیم) ──
from main import (
    LINKS,
    LINKS_LOCK,
    CONFIG,
    DEFAULT_PROTOCOL,
    get_host,
    is_link_allowed,
    require_auth,
    save_state,
    _validate_spoof_sni,
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
PING_WS_HEADERS = {"X-EMIX-Ping": "1"}    # مارکر: شناسایی ترافیک تست سلامت در لاگ‌ها
PING_TIMEOUT_WS = 8.0
PING_TIMEOUT_HTTP = 10.0


def _ping_public_bases() -> tuple[str, str]:
    """(ws_base, http_base) — آدرس عمومی برای تست؛ در حالت لوکال fallback به 127.0.0.1."""
    host = get_host()
    if host and host not in ("localhost", "127.0.0.1", "0.0.0.0"):
        return f"wss://{host}", f"https://{host}"
    return f"ws://127.0.0.1:{CONFIG['port']}", f"http://127.0.0.1:{CONFIG['port']}"


def _ws_connect(uri: str, timeout: float, early_data: bytes | None = None):
    """websockets.connect سازگار با همه‌ی نسخه‌ها.

    API هدر بین نسخه‌ها عوض شده (extra_headers در ≤13، additional_headers در ≥14)
    و در نسخه‌های 12/13 آرگومان نامعتبر فقط موقع await خطا می‌دهد (نه موقع call) —
    پس try/except موقع call بی‌اثر است. راه درست: خواندن امضای واقعی connect
    با inspect و انتخاب نام پارامتر درست. اگر هیچ‌کدام نبود، بدون هدر وصل
    می‌شویم (فقط چند خط لاگ اکتیویتی اضافه می‌شود — شکست نمی‌خورد).

    early_data: بار اولیه 0-RTT در هدر Sec-WebSocket-Protocol (base64url بدون
    padding — دقیقاً همان کاری که xray با ed=2048 می‌کند؛ برای تست A/B توربو)."""
    import inspect

    kwargs: dict = {"open_timeout": timeout, "close_timeout": 2}
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
async def _tcp_ping_only(host: str, port: int = 443) -> dict:
    """استیج TCP خام (بدون TLS/پروتکل) — فقط برای نمایش تفکیک‌شده.

    این همان «TCP ping» است که به‌تنهایی واقعی نیست؛ کنارش Real Delay
    (HTTP از داخل تونل) گزارش می‌شود تا تفاوت دیده شود."""
    t0 = time.perf_counter()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=5.0
        )
        ms = _ping_ms(t0)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        return {"ok": True, "tcp_ms": ms}
    except Exception as exc:
        return {"ok": False, "detail": f"TCP({host}): {type(exc).__name__}: {str(exc)[:60]}"}


async def _probe_ws_tunnel(kind: str, uid: str, link: dict, use_ed: bool = False,
                            ws_base: str | None = None) -> dict:
    """تست کامل تونل WebSocket (vless / trojan / shadowsocks).
    ws_base=None → مسیر عمومی خود پنل؛ ws_base=ws://127.0.0.1 → پروب محلی (vantage دوم).
    use_ed=True → بار اولیه در هندشیک (0-RTT) ارسال می‌شود — برای تست A/B توربو."""
    if ws_base is None:
        ws_base, _ = _ping_public_bases()
    uri = {"vless": f"{ws_base}/ws/{uid}", "trojan": f"{ws_base}/trojan-ws", "ss": f"{ws_base}/ss-ws"}[kind]
    # استیج TCP خام — تفکیک «TCP ping» از «Real Delay» (مرجع نمایشی)
    tcp_stage = {}
    if ws_base:
        _body = ws_base.split("://", 1)[-1].split("/", 1)[0]
        _hostport = _body.rsplit(":", 1)
        _h = _hostport[0]
        _p = int(_hostport[1]) if len(_hostport) == 2 and _hostport[1].isdigit() else (443 if ws_base.startswith("wss://") else 80)
        if _h:
            tcp_stage = await _tcp_ping_only(_h, _p)
    t0 = time.perf_counter()
    ws_ms = None
    e2e_ms = None
    ed_payload = None
    if use_ed and kind in ("vless", "trojan"):
        ed_payload = _vless_probe_bytes(uid) if kind == "vless" else _trojan_probe_bytes(uid)
    try:
        async with _ws_connect(uri, PING_TIMEOUT_WS, early_data=ed_payload) as ws:
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
                    # اگر اولین bytes شبیه HTTP باشد (پاسخ plaintext)، نیازی به
                    # decrypt نیست — پینگ موفق است؛ در غیر این صورت decrypt واقعی.
                    if raw_accum[:4] in (b"HTTP", b"http"):
                        body = raw_accum
                        break
                    stream.feed(raw_b)
                    try:
                        body = b"".join(stream.try_decrypt_chunks())
                    except ValueError:
                        if raw_accum[:4] in (b"HTTP", b"http"):
                            body = raw_accum
                        else:
                            return {"ok": False, "detail": "AEAD decrypt ناموفق — پسورد/سالت نامعتبر"}

            e2e_ms = _ping_ms(t1)
            first_line = body.split(b"\r\n", 1)[0][:64]
            out = {"tcp_ms": tcp_stage.get("tcp_ms")} if tcp_stage.get("ok") else {}
            if b"HTTP" in first_line:
                return {"ok": True, "ws_ms": ws_ms, "e2e_ms": e2e_ms, **out, "reply": first_line.decode("latin1", "ignore")}
            return {"ok": False, "ws_ms": ws_ms, "e2e_ms": e2e_ms, **out, "detail": f"پاسخ غیرمنتظره: {first_line!r}"}
    except Exception as exc:
        out = {"tcp_ms": tcp_stage.get("tcp_ms")} if tcp_stage.get("ok") else {}
        return {"ok": False, "ws_ms": ws_ms, "e2e_ms": e2e_ms, **out, "detail": f"{type(exc).__name__}: {str(exc)[:120]}"}


async def _probe_xhttp_tunnel(kind: str, uid: str, link: dict, http_base: str | None = None) -> dict:
    """تست تونل XHTTP (packet-up / stream-up) — GET دانلینک + POST آپلینک با هدر واقعی پروتکل.
    http_base=None → مسیر عمومی خود پنل؛ http_base=http://127.0.0.1 → پروب محلی."""
    if http_base is None:
        _, http_base = _ping_public_bases()
    prefix = "xhttp-siz10" if kind == "vless" else "txhttp-siz10"
    mode = "packet-up" if link.get("protocol", "").endswith("packet-up") else "stream-up"
    sid = secrets.token_hex(8)
    probe = _vless_probe_bytes(uid) if kind == "vless" else _trojan_probe_bytes(uid)
    down_url = f"{http_base}/{prefix}/{mode}/{uid}/{sid}"
    up_url = (
        f"{http_base}/{prefix}/packet-up/{uid}/{sid}/0" if mode == "packet-up"
        else f"{http_base}/{prefix}/stream-up/{uid}/{sid}"
    )

    t0 = time.perf_counter()
    headers = dict(PING_WS_HEADERS)
    headers["content-type"] = "application/octet-stream"
    async with httpx.AsyncClient(timeout=httpx.Timeout(PING_TIMEOUT_HTTP, connect=8.0)) as client:
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
                    return {"ok": False, "ws_ms": up_ms, "detail": f"آپلینک HTTP {r.status_code} {detail}".strip()}
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
# پروب مسیر کلاینت برای لینک‌های SNI-جعلی (Mode B) — بازآورده از v12.4.2
# (در پروداکشن اثبات‌شده: TLS با server_hostname=جعلی → Host=دامنه‌ی واقعی →
#  هندشیک WS → بایت‌های واقعی پروتکل → HTTP واقعی از داخل تونل)
# SS عمداً نیست — emitter برای SS spoof را اعمال نمی‌کند (فرمت لینک SNI ندارد).
# ══════════════════════════════════════════════════════════════════════════════
_SPOOF_WS_KINDS = {"vless-ws": "vless", "trojan-ws": "trojan"}


def _link_spoof_sni(link: dict) -> str | None:
    """SNI جعلیِ فعالِ این لینک (Mode B) — فقط وقتی spoof روشن و مقدار معتبر باشد."""
    if not link.get("spoof_sni_enabled"):
        return None
    return _validate_spoof_sni(link.get("spoof_sni"))


def _client_ws_frame(payload: bytes, opcode: int = 2) -> bytes:
    """فریم WebSocket سمت کلاینت — mask اجباری طبق RFC 6455 (همان کاری که Xray می‌کند)."""
    mask = secrets.token_bytes(4)
    n = len(payload)
    if n < 126:
        hdr = struct.pack("!BB", 0x80 | opcode, 0x80 | n)
    elif n < 65536:
        hdr = struct.pack("!BBH", 0x80 | opcode, 0x80 | 126, n)
    else:
        hdr = struct.pack("!BBQ", 0x80 | opcode, 0x80 | 127, n)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return hdr + mask + masked


async def _read_ws_frame_srv(reader: asyncio.StreamReader, timeout: float) -> bytes:
    """خواندن یک فریم WebSocket سمت سرور (unmasked) — payload برمی‌گرداند."""
    hdr = await asyncio.wait_for(reader.readexactly(2), timeout)
    length = hdr[1] & 0x7F
    if length == 126:
        (length,) = struct.unpack("!H", await asyncio.wait_for(reader.readexactly(2), timeout))
    elif length == 127:
        (length,) = struct.unpack("!Q", await asyncio.wait_for(reader.readexactly(8), timeout))
    if hdr[1] & 0x80:  # سرور نباید mask کند؛ اگر کرد، هوشمندانه بخوان
        mask = await asyncio.wait_for(reader.readexactly(4), timeout)
        data = await asyncio.wait_for(reader.readexactly(length), timeout)
        return bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return await asyncio.wait_for(reader.readexactly(length), timeout)


async def _spoof_tls_stream(host: str, spoof: str, port: int = 443,
                            connect_timeout: float = 8.0):
    """اتصال TCP+TLS دقیقاً مثل کلاینتِ لینکِ SNI-جعلی:
    مقصد = IP دامنه‌ی پنل، server_hostname = SNI جعلی، بدون verify cert
    (= allowInsecure=1 در لینک)."""
    infos = await asyncio.get_running_loop().getaddrinfo(
        host, port, family=socket.AF_INET, type=socket.SOCK_STREAM)
    ip = infos[0][4][0]
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # = allowInsecure=1 در کلاینت
    return await asyncio.wait_for(
        asyncio.open_connection(ip, port, ssl=ctx, server_hostname=spoof),
        timeout=connect_timeout,
    )


async def _spoof_client_probe(kind: str, uid: str, link: dict,
                              host: str | None = None, port: int = 443) -> dict:
    """پروب کامل مسیر کلاینت برای لینک‌های ws (VLESS/Trojan) با SNI جعلی.

    host/port فقط برای تست داخلی override می‌شوند؛ در عمل = دامنه‌ی عمومی پنل:443."""
    target_host = host or get_host()
    spoof = _link_spoof_sni(link)
    if not spoof:
        return {"ok": False, "detail": "SNI جعلی فعال/معتبر نیست"}
    if host is None and target_host in ("localhost", "127.0.0.1", "0.0.0.0"):
        return {"ok": False, "detail": "پروب مسیر کلاینت فقط روی دامنه‌ی عمومی معتبر است (Host لوکال)"}
    ws_ms = e2e_ms = None
    t0 = time.perf_counter()
    try:
        reader, writer = await _spoof_tls_stream(target_host, spoof, port)
    except Exception as exc:
        return {"ok": False, "detail": f"TLS(SNI جعلی): {type(exc).__name__}: {str(exc)[:100]}"}
    try:
        # هندشیک WS — Host = دامنه‌ی واقعی پنل (پارامتر host لینک)
        path = {"vless": f"/ws/{uid}", "trojan": "/trojan-ws"}[kind]
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        req = (
            f"GET {path} HTTP/1.1\r\nHost: {target_host}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
            f"X-EMIX-Ping: 1\r\n\r\n"
        )
        writer.write(req.encode())
        await writer.drain()
        resp = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), PING_TIMEOUT_WS)
        ws_ms = _ping_ms(t0)
        status_line = resp.split(b"\r\n", 1)[0].decode("latin1", "ignore")[:60]
        if b"101" not in resp.split(b"\r\n", 1)[0]:
            return {"ok": False, "ws_ms": ws_ms, "detail": f"WS upgrade با Host واقعی: {status_line}"}
        # payload پروتکل — همان بایت‌هایی که کلاینت واقعی می‌فرستد
        t1 = time.perf_counter()
        if kind == "vless":
            payload = _vless_probe_bytes(uid)
        else:
            payload = _trojan_probe_bytes(uid)
        writer.write(_client_ws_frame(payload))
        await writer.drain()
        data = await _read_ws_frame_srv(reader, PING_TIMEOUT_WS)
        e2e_ms = _ping_ms(t1)
        body = data[2:] if (kind == "vless" and data[:2] == b"\x00\x00") else data
        first_line = body.split(b"\r\n", 1)[0][:64]
        if b"HTTP" in first_line:
            return {"ok": True, "ws_ms": ws_ms, "e2e_ms": e2e_ms,
                    "reply": first_line.decode("latin1", "ignore")}
        return {"ok": False, "ws_ms": ws_ms, "e2e_ms": e2e_ms,
                "detail": f"پاسخ غیرمنتظره از مسیر کلاینت: {first_line!r}"}
    except Exception as exc:
        return {"ok": False, "ws_ms": ws_ms, "e2e_ms": e2e_ms,
                "detail": f"مسیر کلاینت: {type(exc).__name__}: {str(exc)[:100]}"}
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _spoof_xhttp_client_probe(kind: str, uid: str, link: dict,
                                    host: str | None = None, port: int = 443) -> dict:
    """پروب مسیر کلاینت برای لینک‌های xhttp با SNI جعلی — دو اتصال TLS با SNI جعلی:
    GET دانلینک + POST آپلینک (همان الگوی _probe_xhttp_tunnel اما با TLS جعلی)."""
    target_host = host or get_host()
    spoof = _link_spoof_sni(link)
    if not spoof:
        return {"ok": False, "detail": "SNI جعلی فعال/معتبر نیست"}
    if host is None and target_host in ("localhost", "127.0.0.1", "0.0.0.0"):
        return {"ok": False, "detail": "پروب مسیر کلاینت فقط روی دامنه‌ی عمومی معتبر است (Host لوکال)"}
    prefix = "xhttp-siz10" if kind == "vless" else "txhttp-siz10"
    proto = link.get("protocol", "")
    mode = "packet-up" if proto.endswith("packet-up") else "stream-up"
    sid = secrets.token_hex(8)
    probe = _vless_probe_bytes(uid) if kind == "vless" else _trojan_probe_bytes(uid)
    down_path = f"/{prefix}/{mode}/{uid}/{sid}"
    up_path = (f"/{prefix}/packet-up/{uid}/{sid}/0" if mode == "packet-up"
               else f"/{prefix}/stream-up/{uid}/{sid}")
    t0 = time.perf_counter()
    try:
        r1, w1 = await _spoof_tls_stream(target_host, spoof, port)
        r2, w2 = await _spoof_tls_stream(target_host, spoof, port)
    except Exception as exc:
        return {"ok": False, "detail": f"TLS(SNI جعلی): {type(exc).__name__}: {str(exc)[:100]}"}
    try:
        # 1) دانلینک — GET با Host واقعی
        get_req = (f"GET {down_path} HTTP/1.1\r\nHost: {target_host}\r\n"
                   f"User-Agent: EMIX-HealthCheck/1.0\r\nX-EMIX-Ping: 1\r\n"
                   f"Accept: */*\r\n\r\n")
        w1.write(get_req.encode())
        await w1.drain()
        hdr = await asyncio.wait_for(r1.readuntil(b"\r\n\r\n"), PING_TIMEOUT_HTTP)
        down_status = hdr.split(b"\r\n", 1)[0].decode("latin1", "ignore")[:60]
        if b" 200 " not in hdr.split(b"\r\n", 1)[0]:
            return {"ok": False, "detail": f"دانلینک از مسیر کلاینت: {down_status}"}
        t1 = time.perf_counter()
        # 2) آپلینک — POST با Host واقعی و بدنه‌ی پروتکل
        post = (f"POST {up_path} HTTP/1.1\r\nHost: {target_host}\r\n"
                f"Content-Type: application/octet-stream\r\nX-EMIX-Ping: 1\r\n"
                f"Content-Length: {len(probe)}\r\n\r\n").encode() + probe
        w2.write(post)
        await w2.drain()
        up_resp = await asyncio.wait_for(r2.readuntil(b"\r\n\r\n"), PING_TIMEOUT_HTTP)
        up_status = up_resp.split(b"\r\n", 1)[0].decode("latin1", "ignore")[:60]
        if b" 200 " not in up_resp.split(b"\r\n", 1)[0]:
            return {"ok": False, "detail": f"آپلینک از مسیر کلاینت: {up_status}"}
        # 3) اولین بایت‌های دانلینک = پاسخ تونل‌شده
        try:
            body = await asyncio.wait_for(r1.read(512), PING_TIMEOUT_HTTP)
        except asyncio.TimeoutError:
            body = b""
        e2e_ms = _ping_ms(t1)
        body = body[2:] if (kind == "vless" and body[:2] == b"\x00\x00") else body
        first_line = body.split(b"\r\n", 1)[0][:64]
        if b"HTTP" in first_line:
            return {"ok": True, "ws_ms": e2e_ms, "e2e_ms": e2e_ms,
                    "reply": first_line.decode("latin1", "ignore")}
        return {"ok": True, "ws_ms": e2e_ms, "e2e_ms": e2e_ms,
                "reply": "TLS+HTTP OK (پاسخ تونل کامل دریافت نشد)",
                "detail": f"مسیر SNI جعلی تا HTTP پاس شد؛ پاسخ تونل: {first_line!r}"}
    except Exception as exc:
        return {"ok": False, "detail": f"مسیر کلاینت xhttp: {type(exc).__name__}: {str(exc)[:100]}"}
    finally:
        for w in (w1, w2):
            try:
                w.close()
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════════════
# دیسپچر اصلی — تشخیص پروتکل و اجرای تست مناسب
# ══════════════════════════════════════════════════════════════════════════════
async def _local_fallback_probe(kind: str, uid: str, link: dict, proto: str) -> dict:
    """پروب محلی وقتی مسیر عمومی از «داخل دیپلوی» در دسترس نیست.

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
    """آیا این پروب قرار بود از مسیر عمومی خود پنل برود؟ (نه محلی)"""
    if ws_base_override or http_base_override:
        return False
    host = get_host()
    return bool(host) and host not in ("localhost", "127.0.0.1", "0.0.0.0")


async def _run_link_ping(uid: str, link: dict) -> dict:
    """اجرای تست مناسب برای هر پروتکل + ثبت نتیجه روی لینک (last_ping).

    برای لینک‌های SNI-جعلی (Mode B) مسیر اولیه = همان مسیر کلاینت واقعی
    (TLS با SNI جعلی + Host واقعی) — همان مسیری که لینک طی می‌کند؛
    شواهد مسیر تمیز جداگانه زیر clean_path حفظ می‌شود."""
    proto = link.get("protocol", DEFAULT_PROTOCOL)
    spoof = _link_spoof_sni(link)

    if not is_link_allowed(link):
        result = {
            "ok": False,
            "protocol": proto,
            "detail": "کانفیگ غیرفعال است یا کوتای آن تمام شده",
            "checked_at": datetime.now().isoformat(),
        }
    elif spoof and proto in _SPOOF_WS_KINDS:
        # ── مسیر کلاینت با SNI جعلی (Mode B) — primary verdict ──────────
        client = await _spoof_client_probe(_SPOOF_WS_KINDS[proto], uid, link)
        result = {"protocol": proto, "test": "ws-tunnel", "spoof_sni": spoof,
                  "client_path": "spoofed-sni", **client}
        # شواهد مسیر تمیز (تفکیک: کدام مسیر مشکل دارد)
        try:
            clean = await _probe_ws_tunnel(_SPOOF_WS_KINDS[proto], uid, link)
            clean_path = {k: v for k, v in clean.items()
                          if k in ("ok", "ws_ms", "e2e_ms", "tcp_ms", "reply")}
        except Exception:
            clean_path = None
        if clean_path:
            result["clean_path"] = clean_path
    elif spoof and (proto.startswith("xhttp-") or proto.startswith("trojan-xhttp-")):
        kind = "trojan" if proto.startswith("trojan-") else "vless"
        client = await _spoof_xhttp_client_probe(kind, uid, link)
        result = {"protocol": proto, "test": "xhttp-tunnel", "spoof_sni": spoof,
                  "client_path": "spoofed-sni", **client}
    elif proto == "vless-ws":
        result = {"protocol": proto, "test": "ws-tunnel", **await _probe_ws_tunnel("vless", uid, link)}
    elif proto == "trojan-ws":
        result = {"protocol": proto, "test": "ws-tunnel", **await _probe_ws_tunnel("trojan", uid, link)}
    elif proto == "shadowsocks":
        result = {"protocol": proto, "test": "ws-tunnel", **await _probe_ws_tunnel("ss", uid, link)}
    elif proto.startswith("trojan-xhttp-"):
        result = {"protocol": proto, "test": "xhttp-tunnel", **await _probe_xhttp_tunnel("trojan", uid, link)}
    elif proto.startswith("xhttp-"):
        result = {"protocol": proto, "test": "xhttp-tunnel", **await _probe_xhttp_tunnel("vless", uid, link)}
    elif proto == "mtproto":
        pub_host = link.get("mtproto_public_host")
        pub_port = link.get("mtproto_public_port") or link.get("mtproto_port")
        if pub_host and pub_port:
            result = {"protocol": proto, "test": "tcp-connect", **await _probe_tcp_connect(pub_host, int(pub_port))}
        else:
            local_port = link.get("mtproto_port")
            if local_port:
                result = {"protocol": proto, "test": "tcp-local", **await _probe_tcp_connect("127.0.0.1", int(local_port)), "detail_prefix": "فقط پروسه محلی تست شد (TCP Proxy عمومی ندارید)"}
            else:
                result = {"ok": False, "protocol": proto, "detail": "پورت MTProto یافت نشد"}
    else:
        result = {"ok": False, "protocol": proto, "detail": f"پروتکل «{proto}» تست خودکار ندارد"}

    # ── fallback صادقانه‌ی vantage دوم ─────────────────────────────────────────
    # پروب از مسیر عمومی خودِ پنل شکست خورد (connect/TLS/timeout) و این لینک
    # واقعاً فعال است → همان تونل را یک‌بار هم از آدرس محلی خود پنل بسنج؛
    # اگر محلی جواب داد، نتیجه ok می‌شود ولی با برچسب واضح local-fallback
    # (ادعا نمی‌کنیم لبه‌ی عمومی سالم است — فقط شواهد را جدا گزارش می‌کنیم).
    if (
        not result.get("ok")
        and result.get("test") in ("ws-tunnel", "xhttp-tunnel")
        and not result.get("client_path")  # مسیر کلاینت SNI-جعلی با fallback جعل نمی‌شود
        and is_link_allowed(link)
        and _is_public_base_probe(None, None)
    ):
        _kind = "trojan" if (proto.startswith("trojan")) else ("ss" if proto == "shadowsocks" else "vless")
        try:
            local = await _local_fallback_probe(_kind, uid, link, proto)
        except Exception:
            local = {"ok": False}
        if local.get("ok"):
            result = {
                "protocol": proto, "test": result.get("test"),
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
    asyncio.create_task(save_state())
    return result


# ══════════════════════════════════════════════════════════════════════════════
# ثبت اندپوینت‌ها — تنها نقطه‌ی تماس با app
# ══════════════════════════════════════════════════════════════════════════════
def register_routes(app) -> None:
    """همه‌ی اندپوینت‌های سلامت را روی app ثبت می‌کند. از انتهای main.py صدا زده می‌شود."""

    @app.get("/api/ping")
    async def api_ping_heartbeat():
        """اندپوینت سبک برای healthcheck دیپلوی (بدون احراز هویت؛ فقط ok)."""
        return JSONResponse(
            {"ok": True, "t": round(time.time(), 3)},
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/links/{uid}/ping")
    async def api_ping_link(uid: str, _=Depends(require_auth)):
        async with LINKS_LOCK:
            link = LINKS.get(uid)
        if not link:
            raise HTTPException(status_code=404, detail="کانفیگ یافت نشد")
        try:
            return await _run_link_ping(uid, link)
        except RuntimeError as exc:
            return {"ok": False, "detail": str(exc)}

    @app.post("/api/links/ping-all")
    async def api_ping_all_links(_=Depends(require_auth)):
        """تست همه‌ی کانفیگ‌های محلی با هم‌زمانی محدود (۴ تا) + گزارش مرحله‌ای.

        هر نتیجه شامل مراحل واقعی است (الهام از اسکنر مرحله‌ای MLMVPN):
        connect → tls/ws → protocol → tunnel — با ms واقعی هر مرحله."""
        async with LINKS_LOCK:
            targets = [(uid, dict(d)) for uid, d in LINKS.items()]
        sem = asyncio.Semaphore(4)

        async def _one(uid: str, link: dict):
            async with sem:
                try:
                    return {"uuid": uid, "label": link.get("label", uid[:8]), "result": await _run_link_ping(uid, link)}
                except Exception as exc:
                    return {"uuid": uid, "label": link.get("label", uid[:8]), "result": {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}}

        results = await asyncio.gather(*[_one(u, d) for u, d in targets]) if targets else []
        ok_n = sum(1 for r in results if r["result"].get("ok"))
        return {
            "total": len(results),
            "ok": ok_n,
            "failed": len(results) - ok_n,
            "stages": ["connect", "ws-handshake", "protocol", "tunnel-reply"],
            "results": list(results),
            "checked_at": datetime.now().isoformat(),
        }

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
