# protocol_adapters/existing/zeus_socks5.py — wraps zeussocks5.py

import logging
from protocol_engine import (
    Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult
from ._base import ExistingAdapterBase

logger = logging.getLogger("EMIX.adapter.zeus_socks5")


class ZeusSocks5Adapter(ExistingAdapterBase):
    name = "zeus-socks5"
    version = "1.0.0"
    description = "SOCKS5 proxy (RFC1929 user/pass auth, traffic quotas, per-IP limits)"

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.TCP,),
            supports_tcp=True,
            supports_ipv4=True, supports_ipv6=False,
            supports_link_generation=True,  # generates socks5://user:pass@host:port
            supports_subscription=False,
            supports_health_check=True,
            supports_inbound=True, supports_outbound=True,
            supports_password_auth=True,  # RFC1929 username/password
            status=ProtocolStatus.STABLE, maturity="stable",
        )

    def generate_link(self, params: dict) -> LinkResult:
        try:
            from zeussocks5 import zeus_proxy_state
            result = zeus_proxy_state.get("result")
            if not result:
                return LinkResult(ok=False, error="no zeus proxy configured")
            host = result.get("domain")
            port = result.get("port")
            user = result.get("user", "")
            passwd = result.get("password", "")
            if not (host and port and user and passwd):
                return LinkResult(ok=False, error="zeus proxy missing credentials")
            link = f"socks5://{user}:{passwd}@{host}:{port}"
            return LinkResult(ok=True, link=link, protocol="socks5", qr_text=link)
        except Exception as exc:
            return LinkResult(ok=False, error=str(exc))

    async def health_check(self) -> HealthResult:
        try:
            from zeussocks5 import zeus_proxy_state
            running = zeus_proxy_state.get("running", False)
            phase = zeus_proxy_state.get("phase", "idle")
            active = zeus_proxy_state.get("active_connections", 0)
            ok = running and phase == "done"
            return HealthResult(
                ok=ok,
                error=None if ok else f"phase={phase}",
                detail=f"active_connections={active}",
            )
        except Exception as exc:
            return HealthResult(ok=False, error=f"{type(exc).__name__}: {exc}")


register_protocol(ZeusSocks5Adapter())
