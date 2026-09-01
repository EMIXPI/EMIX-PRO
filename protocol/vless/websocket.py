# websocket.py
# ══════════════════════════════════════════════════════════════════════════════
# VLESS — اندپوینت WebSocket (/ws/{uuid})
# پارس هدر، relay و توابع کمکی در vless.py (هسته‌ی مشترک) قرار دارند.
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import base64
import secrets
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect

from main import (
    LINKS,
    LINKS_LOCK,
    stats,
    connections,
    error_logs,
    logger,
    is_link_allowed,
    save_state,
    schedule_save,
    log_activity,
)
from protocol.vless.vless import (
    _ws_client_ip,
    _tune_socket,
    parse_vless_header,
    check_and_use,
    relay_ws_to_tcp,
    relay_tcp_to_ws,
)
from protocol.net_connect import open_connection_v4first


def _early_data_chunk(ws: WebSocket) -> bytes:
    """Early-Data (0-RTT): بار اولیه از هندشیک خوانده می‌شود
    (هدر Sec-WebSocket-Protocol، base64url بدون padding — طبق xray ed=2048).
    اگر هدر نبود، خروجی خالی است و مسیر عادی (اولین فریم WS) طی می‌شود —
    ۱۰۰٪ سازگار با کلاینت‌های فعلی که ed ندارند."""
    try:
        val = (ws.headers.get("sec-websocket-protocol") or "").split(",")[0].strip()
        if not val:
            return b""
        return base64.urlsafe_b64decode(val + "=" * (-len(val) % 4))
    except Exception:
        return b""


async def websocket_tunnel(ws: WebSocket, uuid: str):
    await ws.accept()

    async with LINKS_LOCK:
        link = LINKS.get(uuid)

    if not is_link_allowed(link):
        logger.warning(f"🚫 WS rejected uuid={uuid[:8]}… (not allowed)")
        await ws.close(code=1008, reason="not authorized")
        return

    ip = _ws_client_ip(ws)
    is_ping_test = (ws.headers.get("x-emix-ping") == "1")
    conn_id = secrets.token_urlsafe(6)
    connections[conn_id] = {
        "uuid": uuid,
        "ip": ip,
        "transport": "vless-ws",
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "bytes": 0,
    }
    logger.info(f"✅ WS [{conn_id}] uuid={uuid[:8]}… ip={ip} total={len(connections)}")
    if not is_ping_test:
        log_activity("connection", f"اتصال جدید از {ip} (کانفیگ {link.get('label','?')})", "info")
    writer = None

    try:
        # Early-Data (0-RTT): اگر کلاینت بار اولیه را در هندشیک فرستاده باشد،
        # بدون صبر برای اولین فریم ادامه می‌دهیم؛ در غیر این صورت مسیر عادی.
        first_chunk = _early_data_chunk(ws)
        if not first_chunk:
            first_msg = await asyncio.wait_for(ws.receive(), timeout=15.0)
            if first_msg["type"] == "websocket.disconnect":
                return
            first_chunk = first_msg.get("bytes") or (first_msg.get("text") or "").encode()
        if not first_chunk:
            return

        command, address, port, payload = await parse_vless_header(first_chunk)

        if not await check_and_use(uuid, len(first_chunk)):
            await ws.close(code=1008, reason="quota/disabled")
            return

        stats["total_requests"] += 1
        connections[conn_id]["bytes"] += len(first_chunk)
        logger.info(f"➡️  [{conn_id}] → {address}:{port}")

        # ── FAST PING PATH ───────────────────────────────────────────────
        # اگر اینجا هدر X-EMIX-Ping فرستاده شده، فقط هدر VLESS پارس شده،
        # یعنی UUID معتبر و لینک فعال است. بدون TCP واقعی، پاسخ synthetic می‌فرستیم.
        if is_ping_test:
            try:
                await ws.send_bytes(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nX-EMIX-Ping: ok\r\n\r\n")
            except Exception:
                pass
            await ws.close()
            connections.pop(conn_id, None)
            return
        # ──────────────────────────────────────────────────────────────────

        # IPv4-first egress — فیکس Errno 101 روی Railway (بدون خروجی IPv6)
        reader, writer = await open_connection_v4first(address, port, timeout=10.0)
        _tune_socket(writer)

        if payload:
            writer.write(payload)
            await writer.drain()

        done, pending = await asyncio.wait(
            {
                asyncio.create_task(relay_ws_to_tcp(ws, writer, conn_id, uuid)),
                asyncio.create_task(relay_tcp_to_ws(ws, reader, conn_id, uuid)),
            },
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass

        asyncio.create_task(schedule_save())

    except WebSocketDisconnect:
        pass
    except asyncio.TimeoutError:
        stats["total_errors"] += 1
        error_logs.append({"error": "connection timeout", "time": datetime.now().isoformat()})
    except Exception as exc:
        stats["total_errors"] += 1
        error_logs.append({"error": str(exc), "time": datetime.now().isoformat()})
        logger.error(f"WS error [{conn_id}]: {exc}")
    finally:
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
        connections.pop(conn_id, None)
        logger.info(f"🔌 WS closed [{conn_id}] total={len(connections)}")