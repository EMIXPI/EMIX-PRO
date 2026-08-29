# xhttshadpacketup.py (trojan)
# ══════════════════════════════════════════════════════════════════════════════
# XHTTP — آپلینک packet-up (با seq) اختصاصی Trojan.
# مستقل از موتور VLESS، مسیر با پیشوند /txhttp-siz10.
# ══════════════════════════════════════════════════════════════════════════════

import time
import traceback
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException
from starlette.requests import ClientDisconnect

from main import stats, connections, error_logs, logger
from protocol.trojan.xhttp_core import (
    TROJAN_PACKET_UP_HIGH_WATER,
    _TrojanQuotaGate,
    ensure_reaper,
    _get_or_create_session,
    _open_tcp_for_session,
    _req_client_ip,
    _teardown,
)

router = APIRouter()


@router.post("/txhttp-siz10/packet-up/{uuid}/{session_id}/{seq}")
async def trojan_packet_up_upload(uuid: str, session_id: str, seq: int, request: Request):
    await ensure_reaper()
    sess = await _get_or_create_session(uuid, "packet-up", session_id, _req_client_ip(request))
    if sess.get("closed"):
        raise HTTPException(status_code=404, detail="session closed")

    sess["last_seen"] = time.time()
    try:
        body = await request.body()
    except ClientDisconnect:
        logger.info(f"Trojan-XHTTP[packet-up] [{session_id[:8]}] client disconnected mid-body (seq={seq}), session kept alive")
        return {"ok": True, "aborted": True}

    if not body:
        return {"ok": True}

    # به همون دلیلی که در نسخه‌ی VLESS توضیح داده شده: batch کردن کوتا به‌جای
    # await روی هر پکت کوچیک، تا قفل سراسری هر پکت رو گلوگاه نکنه.
    gate = sess.get("gate")
    if gate is None:
        gate = _TrojanQuotaGate(uuid)
        sess["gate"] = gate
    if not await gate.add(len(body)):
        await _teardown(session_id, reason="quota/disabled/unknown")
        raise HTTPException(status_code=403, detail="quota/disabled/unknown")

    stats["total_requests"] += 1
    connections[sess["conn_id"]]["bytes"] += len(body)

    # ── Phase 2.7 — seq_buf memory bound (mirror of vless) ──────────────────
    try:
        from config_layer import CONFIG as _EMIX_CFG
        seq_buf_max = _EMIX_CFG.xhttp_seq_buf_max_bytes
    except Exception:
        seq_buf_max = 4 * 1024 * 1024
    current_buf_bytes = sum(len(v) for v in sess["seq_buf"].values())
    if current_buf_bytes + len(body) > seq_buf_max:
        logger.warning(
            f"XHTTP[packet-up/trojan] [{session_id[:8]}] seq_buf overflow "
            f"({current_buf_bytes + len(body)} > {seq_buf_max} bytes) — tearing down"
        )
        from datetime import datetime as _dt
        error_logs.append({
            "error": "seq_buf overflow",
            "session": session_id[:8],
            "bytes": current_buf_bytes + len(body),
            "limit": seq_buf_max,
            "time": _dt.now().isoformat(),
        })
        await _teardown(session_id, reason="seq_buf overflow")
        raise HTTPException(status_code=413, detail="seq_buf overflow — connection terminated")
    # ────────────────────────────────────────────────────────────────────────

    try:
        if sess["writer"] is None:
            if seq != 0:
                sess["seq_buf"][seq] = body
                return {"ok": True, "buffered": True}
            await _open_tcp_for_session(session_id, uuid, sess, body)
            nxt = 1
            while nxt in sess["seq_buf"]:
                pending = sess["seq_buf"].pop(nxt)
                if sess["writer"].is_closing():
                    raise ConnectionError("transport closing")
                sess["writer"].write(pending)
                nxt += 1
            sess["next_seq"] = nxt
            return {"ok": True, "connected": True}

        if seq == sess["next_seq"]:
            if sess["writer"].is_closing():
                raise ConnectionError("transport closing")
            sess["writer"].write(body)
            sess["next_seq"] += 1
            while sess["next_seq"] in sess["seq_buf"]:
                pending = sess["seq_buf"].pop(sess["next_seq"])
                if sess["writer"].is_closing():
                    raise ConnectionError("transport closing")
                sess["writer"].write(pending)
                sess["next_seq"] += 1
        else:
            sess["seq_buf"][seq] = body

        if sess["writer"].transport.get_write_buffer_size() > TROJAN_PACKET_UP_HIGH_WATER:
            await sess["writer"].drain()
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error(f"Trojan-XHTTP[packet-up] [{session_id[:8]}] upload FAILED seq={seq}: {type(exc).__name__}: {exc}\n{tb}")
        error_logs.append({"error": f"trojan packet-up write failed: {type(exc).__name__}: {exc}", "time": datetime.now().isoformat()})
        await _teardown(session_id, reason=f"write-failed: {type(exc).__name__}")
        raise HTTPException(status_code=502, detail="write failed")

    return {"ok": True}
