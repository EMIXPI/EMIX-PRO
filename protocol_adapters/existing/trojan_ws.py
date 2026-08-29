# protocol_adapters/existing/trojan_ws.py — wraps protocol/trojan/websocket.py

import logging
from protocol_engine import (
    Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult
from ._base import ExistingAdapterBase

logger = logging.getLogger("EMIX.adapter.trojan_ws")


class TrojanWsAdapter(ExistingAdapterBase):
    name = "trojan-ws"
    version = "1.0.0"
    description = "Trojan over WebSocket (TLS 443) — production relay"

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.TCP, Transport.WEBSOCKET),
            supports_tcp=True, supports_tls=True, supports_http2=True,
            supports_websocket=True,
            supports_ipv4=True, supports_ipv6=False,
            supports_link_generation=True, supports_subscription=True,
            supports_health_check=True,
            supports_inbound=True, supports_outbound=True,
            supports_password_auth=True,  # Trojan uses SHA224(password)
            status=ProtocolStatus.STABLE, maturity="stable",
        )

    def generate_link(self, params: dict) -> LinkResult:
        try:
            from main import generate_share_link, get_host
            uid = params.get("uuid") or params.get("uid")
            if not uid:
                return LinkResult(ok=False, error="uuid required")
            host = params.get("host") or get_host()
            remark = params.get("remark") or "EMIX-Trojan-WS"
            link = generate_share_link(uid, host, remark=remark, protocol="trojan-ws")
            return LinkResult(ok=True, link=link, protocol="trojan-ws", qr_text=link)
        except Exception as exc:
            return LinkResult(ok=False, error=str(exc))

    async def health_check(self) -> HealthResult:
        try:
            from main import LINKS, LINKS_LOCK
            async with LINKS_LOCK:
                candidates = [
                    (uid, d) for uid, d in LINKS.items()
                    if d.get("protocol") == "trojan-ws" and d.get("active", True)
                ]
            if not candidates:
                return HealthResult(ok=True, detail="no trojan-ws links")
            uid, link = candidates[0]
            from link_health import _probe_ws_tunnel
            r = await _probe_ws_tunnel("trojan", uid, link)
            ok = r.get("ok", False)
            return HealthResult(
                ok=ok, rtt_ms=r.get("ws_ms"), handshake_ms=r.get("e2e_ms"),
                error=None if ok else r.get("detail"),
                detail=r.get("reply", ""),
            )
        except Exception as exc:
            return HealthResult(ok=False, error=f"{type(exc).__name__}: {exc}")


register_protocol(TrojanWsAdapter())
