# protocol_adapters/hysteria2.py — DEFERRED adapter
#
# STATUS: DEFERRED — IMPLEMENTATION DEPENDENCY REQUIRED
#
# Why: Hysteria2 requires a QUIC implementation. The mature, maintained
# Hysteria2 server is written in Go (https://github.com/apernet/hysteria).
# There is NO production-grade Python QUIC implementation suitable for
# hosting Hysteria2 inbounds. aioquic exists but is experimental and
# would require us to implement the Hysteria2 protocol on top of it —
# that's "writing a fragile QUIC implementation from scratch," which
# the user explicitly forbade.
#
# Path to enable:
#   1. Run the official hysteria-server binary as a sidecar on a host
#      with UDP egress. Railway supports UDP but the deployment model
#      would need to be expanded (Docker-in-Docker or external VPS).
#   2. EMIX would only emit configs + monitor health.
#   3. Licensing: Hysteria2 is Apache-2.0 — compatible.
#
# What we DO expose now:
#   - capabilities (UDP/QUIC/TLS/IPv4/IPv6) — for documentation
#   - status = DEFERRED — so the smart selector skips this

import logging
from protocol_engine import (
    ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult

logger = logging.getLogger("EMIX.adapter.hysteria2")


class Hysteria2Adapter(ProtocolAdapter):
    name = "hysteria2"
    version = "0.1.0"  # 0.x because not implemented
    description = (
        "Hysteria2 (QUIC + TLS + congestion control). DEFERRED — requires "
        "the official Go binary as a sidecar. No Python implementation."
    )

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.UDP, Transport.QUIC),
            supports_tcp=False,
            supports_udp=True,  # advertised but not yet implemented
            supports_tls=True,
            supports_quic=True,
            supports_ipv4=True,
            supports_ipv6=False,
            supports_link_generation=False,
            supports_subscription=False,
            supports_health_check=False,
            supports_inbound=False,
            supports_outbound=False,
            supports_password_auth=True,  # would-be auth model
            status=ProtocolStatus.DEFERRED,
            maturity="deferred",
        )

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        return False, ["Hysteria2 adapter is DEFERRED — needs external Go binary"]

    def configure(self, config: dict) -> None:
        raise NotImplementedError("Hysteria2 is DEFERRED — see docs/PROTOCOLS.md")

    def generate_link(self, params: dict) -> LinkResult:
        return LinkResult(
            ok=False,
            error="Hysteria2 link emission is DEFERRED — requires external hysteria binary",
        )

    async def health_check(self) -> HealthResult:
        return HealthResult(
            ok=False,
            error="DEFERRED — no implementation available",
            detail="see docs/PROTOCOLS.md for deployment path",
        )

    async def start(self) -> bool:
        logger.warning("[hysteria2] start() called but adapter is DEFERRED")
        return False

    async def stop(self) -> bool:
        return True


register_protocol(Hysteria2Adapter())
