# protocol_adapters/naiveproxy.py — DEFERRED adapter
#
# STATUS: DEFERRED — IMPLEMENTATION DEPENDENCY REQUIRED
#
# Why: NaiveProxy is a Chromium-based HTTP/2 proxy with browser-like
# fingerprinting. The mature implementation is the official
# https://github.com/klzgrad/naiveproxy — a C++ binary built from the
# Chromium network stack. No Python implementation exists.
#
# Railway constraints:
#   - Cannot run a large Chromium-based binary
#   - NaiveProxy server requires compilation from Chromium source
#   - Not compatible with Railway's deployment model
#
# What we DO expose: capabilities + status = DEFERRED for documentation.

import logging
from protocol_engine import (
    ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult

logger = logging.getLogger("EMIX.adapter.naiveproxy")


class NaiveproxyAdapter(ProtocolAdapter):
    name = "naiveproxy"
    version = "0.1.0"
    description = (
        "NaiveProxy (HTTP/2 + TLS with Chromium network stack). DEFERRED — "
        "requires C++ binary built from Chromium. Not Railway-compatible."
    )

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.TCP,),
            supports_tcp=True,
            supports_tls=True,
            supports_http2=True,
            supports_ipv4=True,
            supports_ipv6=False,
            supports_link_generation=False,
            supports_health_check=False,
            supports_inbound=False,
            supports_outbound=False,
            supports_password_auth=True,
            status=ProtocolStatus.DEFERRED,
            maturity="deferred",
        )

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        return False, ["NaiveProxy adapter is DEFERRED — needs Chromium-based binary"]

    def configure(self, config: dict) -> None:
        raise NotImplementedError("NaiveProxy is DEFERRED — see docs/PROTOCOLS.md")

    def generate_link(self, params: dict) -> LinkResult:
        return LinkResult(
            ok=False,
            error="NaiveProxy link emission is DEFERRED — requires external binary",
        )

    async def health_check(self) -> HealthResult:
        return HealthResult(
            ok=False, error="DEFERRED — no implementation available",
        )

    async def start(self) -> bool:
        logger.warning("[naiveproxy] start() called but adapter is DEFERRED")
        return False

    async def stop(self) -> bool:
        return True


register_protocol(NaiveproxyAdapter())
