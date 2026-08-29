# protocol_adapters/existing/http_proxy.py — wraps main.py:/proxy endpoint

import logging
from protocol_engine import (
    Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult
from ._base import ExistingAdapterBase

logger = logging.getLogger("EMIX.adapter.http_proxy")


class HttpProxyAdapter(ExistingAdapterBase):
    name = "http-proxy"
    version = "1.0.0"
    description = "Internal HTTP forward-proxy (SSRF-protected, Phase 7.14)"

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.TCP,),
            supports_tcp=True, supports_tls=True,
            supports_ipv4=True, supports_ipv6=False,
            supports_link_generation=False,  # HTTP proxy has no share-link
            supports_subscription=False,
            supports_health_check=True,
            supports_inbound=True, supports_outbound=True,
            supports_token_auth=False,  # authed via session cookie
            status=ProtocolStatus.STABLE, maturity="stable",
        )

    def generate_link(self, params: dict) -> LinkResult:
        return LinkResult(ok=False, error="HTTP proxy does not have a share-link format")

    async def health_check(self) -> HealthResult:
        """Health = can we make an outbound HTTPS request to a public host?"""
        try:
            import time
            import httpx
            t0 = time.monotonic()
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get("https://www.cloudflare.com/cdn-cgi/trace")
                ok = r.status_code == 200
                rtt_ms = (time.monotonic() - t0) * 1000
                return HealthResult(
                    ok=ok, rtt_ms=round(rtt_ms, 2),
                    error=None if ok else f"HTTP {r.status_code}",
                    detail="cloudflare trace endpoint",
                )
        except Exception as exc:
            return HealthResult(ok=False, error=f"{type(exc).__name__}: {exc}")


register_protocol(HttpProxyAdapter())
