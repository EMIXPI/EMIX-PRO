# protocol_adapters/existing/shadowsocks.py — wraps protocol/shadowsocks/

import logging
from protocol_engine import (
    Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult
from ._base import ExistingAdapterBase

logger = logging.getLogger("EMIX.adapter.shadowsocks")


class ShadowsocksAdapter(ExistingAdapterBase):
    name = "shadowsocks"
    version = "1.0.0"
    description = "Shadowsocks AEAD (chacha20-ietf-poly1305 / aes-256-gcm) over WebSocket"

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.TCP, Transport.WEBSOCKET),
            supports_tcp=True, supports_tls=True, supports_http2=True,
            supports_websocket=True,
            supports_ipv4=True, supports_ipv6=False,
            supports_link_generation=True, supports_subscription=True,
            supports_health_check=True,
            supports_inbound=True, supports_outbound=True,
            supports_password_auth=True,
            status=ProtocolStatus.STABLE, maturity="stable",
        )

    def generate_link(self, params: dict) -> LinkResult:
        try:
            from main import generate_share_link, get_host
            uid = params.get("uuid") or params.get("uid")
            if not uid:
                return LinkResult(ok=False, error="uuid required")
            host = params.get("host") or get_host()
            remark = params.get("remark") or "EMIX-Shadowsocks"
            link = generate_share_link(uid, host, remark=remark, protocol="shadowsocks")
            return LinkResult(ok=True, link=link, protocol="shadowsocks", qr_text=link)
        except Exception as exc:
            return LinkResult(ok=False, error=str(exc))

    async def health_check(self) -> HealthResult:
        try:
            from main import LINKS, LINKS_LOCK
            async with LINKS_LOCK:
                candidates = [
                    (uid, d) for uid, d in LINKS.items()
                    if d.get("protocol") == "shadowsocks" and d.get("active", True)
                ]
            if not candidates:
                return HealthResult(ok=True, detail="no shadowsocks links")
            uid, link = candidates[0]
            from link_health import _probe_ws_tunnel
            r = await _probe_ws_tunnel("ss", uid, link)
            return HealthResult(
                ok=r.get("ok", False), rtt_ms=r.get("ws_ms"),
                handshake_ms=r.get("e2e_ms"),
                error=None if r.get("ok") else r.get("detail"),
                detail=r.get("reply", ""),
            )
        except Exception as exc:
            return HealthResult(ok=False, error=f"{type(exc).__name__}: {exc}")


register_protocol(ShadowsocksAdapter())
