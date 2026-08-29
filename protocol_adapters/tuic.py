# protocol_adapters/tuic.py — DEFERRED adapter
#
# STATUS: DEFERRED — IMPLEMENTATION DEPENDENCY REQUIRED
#
# Why: TUIC v5 is a QUIC-based protocol with its own authentication and
# multiplexing. The mature, maintained implementation is the official
# tuic-v5 (https://github.com/ItsRyanTu/tuic). No production-grade
# Python implementation exists. Writing one from scratch would require
# implementing the TUIC wire protocol on top of aioquic — fragile and
# not safe.
#
# Path to enable: same as Hysteria2 — external Go binary as a sidecar
# on a host with UDP egress.

import logging
from protocol_engine import (
    Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult
from protocol_engine.base import ProtocolAdapter

logger = logging.getLogger("EMIX.adapter.tuic")


class TuicAdapter(ProtocolAdapter):
    name = "tuic"
    version = "0.1.0"
    description = (
        "TUIC v5 (QUIC + TLS + multiplexing). DEFERRED — requires external "
        "Go binary. No Python implementation."
    )

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.UDP, Transport.QUIC),
            supports_tcp=False, supports_udp=True, supports_tls=True,
            supports_quic=True, supports_multiplexing=True,
            supports_ipv4=True, supports_ipv6=False,
            supports_link_generation=False,
            supports_health_check=False,
            supports_inbound=False, supports_outbound=False,
            supports_uuid_auth=True,
            status=ProtocolStatus.DEFERRED, maturity="deferred",
        )

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        return False, ["TUIC adapter is DEFERRED — needs external Go binary"]

    def configure(self, config: dict) -> None:
        raise NotImplementedError("TUIC is DEFERRED — see docs/PROTOCOLS.md")

    def generate_link(self, params: dict) -> LinkResult:
        return LinkResult(
            ok=False,
            error="TUIC link emission is DEFERRED — requires external tuic binary",
        )

    async def health_check(self) -> HealthResult:
        return HealthResult(
            ok=False, error="DEFERRED — no implementation available",
            detail="see docs/PROTOCOLS.md for deployment path",
        )

    async def start(self) -> bool:
        logger.warning("[tuic] start() called but adapter is DEFERRED")
        return False

    async def stop(self) -> bool:
        return True


register_protocol(TuicAdapter())
