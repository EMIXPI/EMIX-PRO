# protocol_adapters/existing/vless_xhttp.py — wraps protocol/vless/xhttp_*.py
#
# The existing XHTTP implementation has 4 modes (stream-up, packet-up,
# stream-on, packet-up-on). All are real and functional. This adapter
# exposes them through the ProtocolAdapter interface.

import logging
from protocol_engine import (
    ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult
from ._base import ExistingAdapterBase

logger = logging.getLogger("EMIX.adapter.vless_xhttp")


class VlessXhttpAdapter(ExistingAdapterBase):
    name = "vless-xhttp"
    version = "1.0.0"
    description = "VLESS over XHTTP (4 modes: stream-up, packet-up, stream-on, packet-up-on)"

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.TCP, Transport.XHTTP),
            supports_tcp=True,
            supports_tls=True,
            supports_http2=True,
            supports_xhttp=True,
            supports_multiplexing=True,  # via session_id in path
            supports_ipv4=True,
            supports_ipv6=False,
            supports_link_generation=True,
            supports_subscription=True,
            supports_health_check=True,
            supports_inbound=True,
            supports_outbound=True,
            supports_uuid_auth=True,
            status=ProtocolStatus.STABLE,
            maturity="stable",
        )

    def generate_link(self, params: dict) -> LinkResult:
        try:
            from main import generate_share_link, get_host
            uid = params.get("uuid") or params.get("uid")
            if not uid:
                return LinkResult(ok=False, error="uuid required")
            host = params.get("host") or get_host()
            mode = params.get("mode", "stream-up")
            proto = f"xhttp-{mode}"
            remark = params.get("remark") or f"EMIX-VLESS-XHTTP-{mode}"
            link = generate_share_link(uid, host, remark=remark, protocol=proto)
            return LinkResult(ok=True, link=link, protocol=proto, qr_text=link)
        except Exception as exc:
            logger.warning(f"generate_link failed: {exc}")
            return LinkResult(ok=False, error=str(exc))

    async def health_check(self) -> HealthResult:
        try:
            from main import LINKS, LINKS_LOCK
            async with LINKS_LOCK:
                candidates = [
                    (uid, d) for uid, d in LINKS.items()
                    if d.get("protocol", "").startswith("xhttp-") and d.get("active", True)
                ]
            if not candidates:
                return HealthResult(ok=True, detail="no vless-xhttp links to check")
            uid, link = candidates[0]
            from link_health import _probe_xhttp_tunnel
            r = await _probe_xhttp_tunnel("vless", uid, link)
            ok = r.get("ok", False)
            ws_ms = r.get("ws_ms")
            return HealthResult(
                ok=ok, rtt_ms=ws_ms, handshake_ms=r.get("e2e_ms"),
                error=None if ok else r.get("detail"),
                detail=r.get("reply", ""),
            )
        except Exception as exc:
            return HealthResult(ok=False, error=f"{type(exc).__name__}: {exc}")


register_protocol(VlessXhttpAdapter())
