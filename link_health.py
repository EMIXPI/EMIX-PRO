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


def _ws_connect(uri: str, timeout: float):
    """websockets.connect سازگار با نسخه‌های مختلف (additional_headers / extra_headers)."""
    try:
        return websockets.connect(uri, open_timeout=timeout, close_timeout=2, additional_headers=PING_WS_HEADERS)
    except TypeError:
        return websockets.connect(uri, open_timeout=timeout, close_timeout=2, extra_headers=PING_WS_HEADERS)


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
async def _probe_ws_tunnel(kind: str, uid: str, link: dict) -> dict:
    """تست کامل تونل WebSocket (vless / trojan / shadowsocks) از مسیر عمومی."""
    ws_base, _ = _ping_public_bases()
    uri = {"vless": f"{ws_base}/ws/{uid}", "trojan": f"{ws_base}/trojan-ws", "ss": f"{ws_base}/ss-ws"}[kind]
    t0 = time.perf_counter()
    ws_ms = None
    e2e_ms = None
    try:
        async with _ws_connect(uri, PING_TIMEOUT_WS) as ws:
            ws_ms = _ping_ms(t0)
            t1 = time.perf_counter()

            if kind == "vless":
                await ws.send(_vless_probe_bytes(uid))
                raw = await asyncio.wait_for(ws.recv(), timeout=PING_TIMEOUT_WS)
                if isinstance(raw, str):
                    raw = raw.encode()
                body = raw[2:] if raw[:2] == b"\x00\x00" else raw
            elif kind == "trojan":
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
                while not body:
                    raw = await asyncio.wait_for(ws.recv(), timeout=PING_TIMEOUT_WS)
                    stream.feed(raw.encode() if isinstance(raw, str) else raw)
                    try:
                        body = b"".join(stream.try_decrypt_chunks())
                    except ValueError:
                        return {"ok": False, "detail": "AEAD decrypt ناموفق — پسورد/سالت نامعتبر"}

            e2e_ms = _ping_ms(t1)
            first_line = body.split(b"\r\n", 1)[0][:64]
            if b"HTTP" in first_line:
                return {"ok": True, "ws_ms": ws_ms, "e2e_ms": e2e_ms, "reply": first_line.decode("latin1", "ignore")}
            return {"ok": False, "ws_ms": ws_ms, "e2e_ms": e2e_ms, "detail": f"پاسخ غیرمنتظره: {first_line!r}"}
    except Exception as exc:
        return {"ok": False, "ws_ms": ws_ms, "e2e_ms": e2e_ms, "detail": f"{type(exc).__name__}: {str(exc)[:120]}"}


async def _probe_xhttp_tunnel(kind: str, uid: str, link: dict) -> dict:
    """تست تونل XHTTP (packet-up / stream-up) — GET دانلینک + POST آپلینک با هدر واقعی پروتکل."""
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
    async with httpx.AsyncClient(timeout=httpx.Timeout(PING_TIMEOUT_HTTP, connect=8.0), verify=True) as client:
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
async def _run_link_ping(uid: str, link: dict) -> dict:
    """اجرای تست مناسب برای هر پروتکل + ثبت نتیجه روی لینک (last_ping)."""
    proto = link.get("protocol", DEFAULT_PROTOCOL)
    if not is_link_allowed(link):
        result = {
            "ok": False,
            "protocol": proto,
            "detail": "کانفیگ غیرفعال است یا کوتای آن تمام شده",
            "checked_at": datetime.now().isoformat(),
        }
    elif proto == "vless-ws":
        result = {"protocol": proto, "test": "ws-tunnel", **await _probe_ws_tunnel("vless", uid, link)}
    elif proto == "trojan-ws":
        result = {"protocol": proto, "test": "ws-tunnel", **await _probe_ws_tunnel("trojan", uid, link)}
    elif proto == "shadowsocks":
        result = {"protocol": proto, "test": "ws-tunnel", **await _probe_ws_tunnel("ss", uid, link)}
    elif proto.startswith("trojan-xhttp-"):
        result = {"protocol": proto, "test": "xhttp-tunnel", **await _probe_xhttp_tunnel("trojan", uid, link)}
    elif proto.startswith("xhttp-") or proto.startswith("vless-xhttp"):
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

    @app.post("/api/links/{uid}/ping")
    async def api_ping_link(uid: str, _=Depends(require_auth)):
        async with LINKS_LOCK:
            link = LINKS.get(uid)
        if not link:
            raise HTTPException(status_code=404, detail="کانفیگ یافت نشد")
        return await _run_link_ping(uid, link)

    @app.post("/api/links/ping-all")
    async def api_ping_all_links(_=Depends(require_auth)):
        """تست همه‌ی کانفیگ‌های محلی با هم‌زمانی محدود (۴ تا)."""
        async with LINKS_LOCK:
            targets = [(uid, dict(d)) for uid, d in LINKS.items()]
        sem = asyncio.Semaphore(4)

        async def _one(uid: str, link: dict):
            async with sem:
                try:
                    return {"uuid": uid, "result": await _run_link_ping(uid, link)}
                except Exception as exc:
                    return {"uuid": uid, "result": {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}}

        results = await asyncio.gather(*[_one(u, d) for u, d in targets])
        ok_n = sum(1 for r in results if r["result"].get("ok"))
        return {"total": len(results), "ok": ok_n, "failed": len(results) - ok_n, "results": list(results)}

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
