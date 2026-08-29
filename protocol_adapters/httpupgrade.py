# protocol_adapters/httpupgrade.py — EXPERIMENTAL adapter
#
# STATUS: EXPERIMENTAL
#
# What this adapter does today:
#   - Reports capabilities (HTTP Upgrade is distinct from WebSocket!)
#   - Honest note: HTTP Upgrade is a generic mechanism (RFC 7230 §6.1 — Upgrade
#     header + 101 Switching Protocols response). WebSocket is a specific
#     use of HTTP Upgrade with the "websocket" token. xHTTP packet-up/stream-up
#     are completely different — they use HTTP POST bodies, not Upgrade.
#   - A real HTTP Upgrade transport for VLESS/Trojan would: send `Upgrade: vless`
#     (or similar), get a 101 response, then bidirectional bytes over the
#     upgraded connection.
#   - Currently we don't host such an inbound. This adapter is for documentation.
#
# Path to enable: add an `http_upgrade_vless` route in main.py that accepts
# the Upgrade header and switches to a raw byte stream (similar to WS).

import logging
from protocol_engine import (
    ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult

logger = logging.getLogger("EMIX.adapter.httpupgrade")


class HttpUpgradeAdapter(ProtocolAdapter):
    name = "httpupgrade"
    version = "0.1.0"
    description = (
        "HTTP Upgrade transport (distinct from WebSocket and XHTTP). "
        "EXPERIMENTAL — no inbound yet. Use VLESS-WS or VLESS-XHTTP in production."
    )

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.TCP, Transport.HTTP_UPGRADE),
            supports_tcp=True,
            supports_tls=True,
            supports_http2=False,  # HTTP Upgrade is HTTP/1.1
            supports_http_upgrade=True,  # advertised
            supports_ipv4=True,
            supports_ipv6=False,
            supports_link_generation=False,
            supports_health_check=False,
            supports_inbound=False,  # not implemented
            supports_outbound=False,
            status=ProtocolStatus.EXPERIMENTAL,
            maturity="experimental",
        )

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        errors = []
        if not config.get("host"):
            errors.append("host is required")
        if not config.get("path"):
            errors.append("path is required (e.g. /upgrade)")
        if not config.get("protocol"):
            errors.append("protocol is required (vless or trojan)")
        elif config["protocol"] not in ("vless", "trojan"):
            errors.append("protocol must be vless or trojan")
        return (len(errors) == 0), errors

    def configure(self, config: dict) -> None:
        pass

    def generate_link(self, params: dict) -> LinkResult:
        # Generate a VLESS link with type=httpupgrade (client-side hint)
        # This is a real share-link but the server doesn't host the inbound —
        # return a LinkResult.ok=False so callers know it's not functional.
        return LinkResult(
            ok=False,
            error="HTTP Upgrade inbound not implemented; use VLESS-WS or VLESS-XHTTP in production",
        )

    async def health_check(self) -> HealthResult:
        return HealthResult(
            ok=False,
            error="HTTP Upgrade inbound not implemented",
            detail="see docs/PROTOCOLS.md for the real-vs-advertised transport matrix",
        )

    async def start(self) -> bool:
        return True

    async def stop(self) -> bool:
        return True


register_protocol(HttpUpgradeAdapter())
