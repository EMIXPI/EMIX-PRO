# protocol_adapters/existing/vless_ws.py — wraps protocol/vless/websocket.py
#
# This adapter exposes the EXISTING VLESS-over-WebSocket implementation through
# the ProtocolAdapter interface. It does NOT replace, modify, or shadow any
# of the relay logic. All real work is delegated to the existing code.

import logging
from protocol_engine import (
    ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult
from ._base import ExistingAdapterBase

logger = logging.getLogger("EMIX.adapter.vless_ws")


class VlessWsAdapter(ExistingAdapterBase):
    name = "vless-ws"
    version = "1.0.0"
    description = "VLESS over WebSocket (TLS 443) — production relay"

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.TCP, Transport.WEBSOCKET),
            supports_tcp=True,
            supports_tls=True,
            supports_http2=True,  # via Cloudflare in front
            supports_websocket=True,
            supports_ipv4=True,
            supports_ipv6=False,  # Railway single-region deployment today
            supports_link_generation=True,
            supports_subscription=True,
            supports_health_check=True,
            supports_inbound=True,
            supports_outbound=True,
            supports_uuid_auth=True,
            supports_0rtt=True,  # turbo 0-RTT support via WS early-data
            status=ProtocolStatus.STABLE,
            maturity="stable",
        )

    def generate_link(self, params: dict) -> LinkResult:
        """Generate a VLESS-WS share link. Delegates to main.generate_share_link."""
        try:
            from main import generate_share_link, get_host
            uid = params.get("uuid") or params.get("uid")
            if not uid:
                return LinkResult(ok=False, error="uuid required")
            host = params.get("host") or get_host()
            remark = params.get("remark") or "EMIX-VLESS-WS"
            link = generate_share_link(uid, host, remark=remark, protocol="vless-ws")
            return LinkResult(ok=True, link=link, protocol="vless-ws", qr_text=link)
        except Exception as exc:
            logger.warning(f"generate_link failed: {exc}")
            return LinkResult(ok=False, error=str(exc))

    async def health_check(self) -> HealthResult:
        """Health check delegates to the existing link_health module."""
        try:
            from main import LINKS, LINKS_LOCK
            import asyncio
            async with LINKS_LOCK:
                candidates = [
                    (uid, d) for uid, d in LINKS.items()
                    if d.get("protocol") == "vless-ws" and d.get("active", True)
                ]
            if not candidates:
                return HealthResult(ok=True, detail="no vless-ws links to check")
            # Use the first active link
            uid, _ = candidates[0]
            from link_health import _probe_ws_tunnel
            r = await _probe_ws_tunnel("vless", uid, candidates[0][1])
            ok = r.get("ok", False)
            ws_ms = r.get("ws_ms")
            return HealthResult(
                ok=ok,
                rtt_ms=ws_ms,
                handshake_ms=r.get("e2e_ms"),
                error=None if ok else r.get("detail"),
                detail=r.get("reply", ""),
            )
        except Exception as exc:
            return HealthResult(ok=False, error=f"{type(exc).__name__}: {exc}")


# Register on import
register_protocol(VlessWsAdapter())
