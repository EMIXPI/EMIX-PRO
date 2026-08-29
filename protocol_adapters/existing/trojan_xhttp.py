# protocol_adapters/existing/trojan_xhttp.py — wraps protocol/trojan/xhttp_*.py

import logging
from protocol_engine import (
    Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult
from ._base import ExistingAdapterBase

logger = logging.getLogger("EMIX.adapter.trojan_xhttp")


class TrojanXhttpAdapter(ExistingAdapterBase):
    name = "trojan-xhttp"
    version = "1.0.0"
    description = "Trojan over XHTTP (4 modes)"

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.TCP, Transport.XHTTP),
            supports_tcp=True, supports_tls=True, supports_http2=True,
            supports_xhttp=True, supports_multiplexing=True,
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
            mode = params.get("mode", "stream-up")
            proto = f"trojan-xhttp-{mode}"
            remark = params.get("remark") or f"EMIX-Trojan-XHTTP-{mode}"
            link = generate_share_link(uid, host, remark=remark, protocol=proto)
            return LinkResult(ok=True, link=link, protocol=proto, qr_text=link)
        except Exception as exc:
            return LinkResult(ok=False, error=str(exc))

    async def health_check(self) -> HealthResult:
        try:
            from main import LINKS, LINKS_LOCK
            async with LINKS_LOCK:
                candidates = [
                    (uid, d) for uid, d in LINKS.items()
                    if d.get("protocol", "").startswith("trojan-xhttp-") and d.get("active", True)
                ]
            if not candidates:
                return HealthResult(ok=True, detail="no trojan-xhttp links")
            uid, link = candidates[0]
            from link_health import _probe_xhttp_tunnel
            r = await _probe_xhttp_tunnel("trojan", uid, link)
            return HealthResult(
                ok=r.get("ok", False), rtt_ms=r.get("ws_ms"),
                handshake_ms=r.get("e2e_ms"),
                error=None if r.get("ok") else r.get("detail"),
                detail=r.get("reply", ""),
            )
        except Exception as exc:
            return HealthResult(ok=False, error=f"{type(exc).__name__}: {exc}")


register_protocol(TrojanXhttpAdapter())
