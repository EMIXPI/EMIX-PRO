# smart_routing/metrics.py — اندازه‌گیری واقعی latency / jitter / packet loss
# ══════════════════════════════════════════════════════════════════════════════
# روش (واقعی — همان مسیر کلاینت):
#   برای هر endpoint چند بار (پیش‌فرض ۵) کل زنجیره طی می‌شود:
#     client → front (TLS + WS handshake) → بایت‌های واقعی پروتکل →
#     تونل TCP → مقصد تست → پاسخ HTTP واقعی از داخل تونل
#   متریک‌ها:
#     latency_ms = میانگین (ws_ms + e2e_ms) — Real Delay، نه TCP خام
#     jitter_ms  = انحراف معیار پروب‌ها (پایداری)
#     packet_loss = نسبت پروب‌های ناموفق (چند‌باره — ضد نتیجه‌ی تصادفی)
#   tcp_ms جداگانه گزارش می‌شود (تفکیک صادقانه — «TCP به‌تنهایی واقعی نیست»).
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import hashlib
import struct
import time
import uuid as _uuid_mod

import websockets

# نکته‌ی import: همه‌ی وابستگی‌ها به main/link_health «lazy» داخل توابع‌اند تا
# ترتیب import (چه main اول، چه smart_routing اول) هرگز circular نشود.


def _link_health():
    import link_health
    return link_health

# مقصد تست پیش‌فرض (anycast جهانی — همان موتور اثبات‌شده‌ی link_health)
TEST_HOST = "cp.cloudflare.com"
TEST_PORT = 80

def _defaults():
    import main
    return main

# مقصد تست پیش‌فرض از link_health (اگر بارگذاری شده باشد)
def _test_host_port():
    try:
        lh = _link_health()
        return lh.PING_TEST_HOST, lh.PING_TEST_PORT
    except Exception:
        return TEST_HOST, TEST_PORT

# پروتکل‌هایی که مسیر WS ازشان قابل پروب است (بقیه صادقانه مستثنا می‌شوند)
PROBEABLE_PROTOCOLS = ("vless-ws", "trojan-ws")


def _http_req(host: str, path: str = "/generate_204",
              extra_headers: dict | None = None) -> bytes:
    lines = [
        f"GET {path} HTTP/1.1",
        f"Host: {host}",
        "User-Agent: EMIX-SmartRouting/1.0",
        "Accept: application/json, */*",
    ]
    for k, v in (extra_headers or {}).items():
        lines.append(f"{k}: {v}")
    lines.append("Connection: close")
    return ("\r\n".join(lines) + "\r\n\r\n").encode()


def _vless_probe(uid: str, dest_host: str, dest_port: int, raw: bytes) -> bytes:
    head = (
        b"\x00"
        + _uuid_mod.UUID(uid).bytes
        + b"\x00"
        + b"\x01"
        + struct.pack(">H", dest_port)
        + b"\x02"
        + bytes([len(dest_host)])
        + dest_host.encode()
    )
    return head + raw


def _trojan_probe(uid: str, dest_host: str, dest_port: int, raw: bytes) -> bytes:
    pw_hash = hashlib.sha224(uid.encode()).hexdigest().encode()
    head = (
        pw_hash + b"\r\n" + b"\x01" + b"\x03"
        + bytes([len(dest_host)]) + dest_host.encode()
        + struct.pack(">H", dest_port) + b"\r\n"
    )
    return head + raw


def ws_base_for(front_host: str, front_port: int) -> str:
    """base درست WS — پورت غیر-۴۴۳ همیشه صریح داخل URL می‌آید."""
    p = int(front_port or 443)
    if p == 443:
        return f"wss://{front_host}"
    return f"ws://{front_host}:{p}"


def _kind_for(protocol: str) -> str | None:
    if protocol == "vless-ws":
        return "vless"
    if protocol == "trojan-ws":
        return "trojan"
    return None


# ── پروب کامل با مقصد دلخواه (برای egress از داخل تونل) ───────────────────────
async def http_through_tunnel(front_base: str, uid: str, protocol: str,
                              dest_host: str, dest_port: int = 80,
                              want_body: bool = True, timeout: float = 10.0,
                              path: str = "/generate_204",
                              extra_headers: dict | None = None) -> dict:
    """درخواست HTTP واقعی به مقصد دلخواه، از داخل تونل واقعی، از طریق فرانت.

    برمی‌گرداند: {ok, ws_ms, e2e_ms, status_line, body(bytes), tcp_ms}
    این پایه‌ی verify واقعی است: traffic واقعاً از مسیر عبور کرده است."""
    kind = _kind_for(protocol)
    if kind is None:
        return {"ok": False, "detail": f"پروتکل قابل‌پروب نیست: {protocol}"}
    uri = (f"{front_base}/ws/{uid}" if kind == "vless" else f"{front_base}/trojan-ws")
    req = _http_req(dest_host, path, extra_headers)
    payload = (_vless_probe(uid, dest_host, dest_port, req) if kind == "vless"
               else _trojan_probe(uid, dest_host, dest_port, req))
    # استیج TCP خام (تفکیک صادق)
    lh = _link_health()
    tcp = {}
    try:
        _body = front_base.split("://", 1)[-1].split("/", 1)[0]
        _hp = _body.rsplit(":", 1)
        if _hp[0]:
            tcp = await lh._tcp_ping_only(
                _hp[0], int(_hp[1]) if len(_hp) == 2 and _hp[1].isdigit() else 443)
    except Exception:
        tcp = {}
    t0 = time.perf_counter()
    ws_ms = e2e_ms = None
    try:
        async with lh._ws_connect(uri, timeout) as ws:
            ws_ms = lh._ping_ms(t0)
            await ws.send(payload)
            t1 = time.perf_counter()
            body = b""
            deadline = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except asyncio.TimeoutError:
                    break
                raw_b = raw.encode() if isinstance(raw, str) else raw
                if kind == "vless" and not body and raw_b[:2] == b"\x00\x00":
                    raw_b = raw_b[2:]          # هدر پاسخ VLESS (ver + addons_len)
                body += raw_b
                if b"\r\n\r\n" in body:
                    head, rest = body.split(b"\r\n\r\n", 1)
                    if b"content-length:" in head.lower():
                        try:
                            cl = int(
                                [l for l in head.lower().split(b"\r\n")
                                 if l.startswith(b"content-length:")][0].split(b":")[1])
                            if len(rest) >= cl:
                                break
                        except Exception:
                            break
                    elif not rest:          # body نرسیده — ادامه‌ی دریافت
                        continue
                    else:
                        break
            e2e_ms = lh._ping_ms(t1)
            if not body:
                return {"ok": False, "tcp_ms": tcp.get("tcp_ms"),
                        "detail": "پاسخی از داخل تونل نرسید"}
            status_line = body.split(b"\r\n", 1)[0].decode("latin1", "ignore")
            if b"HTTP" not in status_line.encode("latin1", "ignore"):
                return {"ok": False, "tcp_ms": tcp.get("tcp_ms"), "ws_ms": ws_ms,
                        "detail": f"پاسخ غیر HTTP: {status_line[:60]!r}"}
            out = {"ok": True, "tcp_ms": tcp.get("tcp_ms"), "ws_ms": ws_ms,
                   "e2e_ms": e2e_ms, "status_line": status_line}
            if want_body:
                parts = body.split(b"\r\n\r\n", 1)
                out["body"] = parts[1] if len(parts) == 2 else b""
            return out
    except Exception as exc:
        return {"ok": False, "tcp_ms": tcp.get("tcp_ms"), "ws_ms": ws_ms,
                "detail": f"{type(exc).__name__}: {str(exc)[:100]}"}


# ── دورد پروب برای latency/jitter/loss ───────────────────────────────────────
async def measure_front(front_host: str, front_port: int, uid: str, protocol: str,
                        rounds: int = 5, gap_s: float = 0.2) -> dict:
    """چند پروب واقعی (پیش‌فرض ۵) روی فرانت — نتیجه‌ی تجمیعی.

    {ok, latency_ms, jitter_ms, packet_loss, samples[], tcp_ms, replies}
    jitter = انحراف معیار نمونه‌ها؛ loss = نسبت شکست (چند‌باره — ضد تصادفی)."""
    kind = _kind_for(protocol)
    if kind is None:
        return {"ok": False, "packet_loss": 1.0, "samples": [],
                "detail": f"پروتکل قابل‌پروب نیست: {protocol}"}
    base = ws_base_for(front_host, front_port)
    lh = _link_health()
    samples: list[float] = []
    replies: list[str] = []
    tcp_ms: float | None = None
    details: list[str] = []
    for i in range(max(1, int(rounds))):
        r = await lh._probe_ws_tunnel(kind, uid, {}, ws_base=base)
        if r.get("ok"):
            total = (r.get("ws_ms") or 0.0) + (r.get("e2e_ms") or 0.0)
            samples.append(round(total, 1))
            replies.append(r.get("reply", ""))
            if r.get("tcp_ms") is not None:
                tcp_ms = r["tcp_ms"] if tcp_ms is None else min(tcp_ms, r["tcp_ms"])
        else:
            details.append(r.get("detail", "?"))
        if i < rounds - 1:
            await asyncio.sleep(gap_s)
    if not samples:
        return {"ok": False, "packet_loss": 1.0, "samples": [],
                "detail": "؛ ".join(details[:3]) or "همه‌ی پروب‌ها شکست خوردند"}
    lat = round(sum(samples) / len(samples), 1)
    if len(samples) > 1:
        mean = sum(samples) / len(samples)
        var = sum((x - mean) ** 2 for x in samples) / (len(samples) - 1)
        jitter = round(var ** 0.5, 1)
    else:
        jitter = 0.0
    loss = round(1 - len(samples) / max(1, int(rounds)), 3)
    return {"ok": len(samples) >= max(2, int(rounds) - 1), "latency_ms": lat,
            "jitter_ms": jitter, "packet_loss": loss, "samples": samples,
            "tcp_ms": tcp_ms, "replies": replies[:3], "fail_details": details[:3]}


# ── pick یک probe-link معتبر برای verify مسیر (لینک فعال WS پنل) ─────────────
async def pick_probe_link() -> tuple[str, dict] | None:
    """(uid, link) — یک لینک فعال vless-ws/trojan-ws برای پروب واقعی مسیر.

    بدون لینک معتبر، verify واقعی ممکن نیست (صداقت: endpoint → UNVERIFIED).
    اگر هیچ لینکی نیست، لینک پیش‌فرض پنل ساخته می‌شود (مثل بازدید dashboard)."""
    async def _candidates():
        m = _defaults()
        async with m.LINKS_LOCK:
            return [(uid, l) for uid, l in m.LINKS.items()
                    if l.get("active", True)
                    and l.get("protocol", m.DEFAULT_PROTOCOL) in PROBEABLE_PROTOCOLS]
    candidates = await _candidates()
    if not candidates:
        try:
            m = _defaults()
            await m.ensure_default_link()
            candidates = await _candidates()
        except Exception:
            pass
    if not candidates:
        return None
    # ترجیح: بدون expiry/limit یا مجازِ is_link_allowed
    m = _defaults()
    for uid, l in candidates:
        if m.is_link_allowed(l):
            return uid, l
    return candidates[0]
