# protocol_adapters/vmess.py — VMess link emission adapter
#
# REAL implementation: emits VMess base64-JSON share-links using the existing
# link_emit.gen_vmess_link() helper. The adapter does NOT host a VMess
# inbound — that would require xray-core/v2ray-core, which is a heavy
# external binary dependency (deferred separately).
#
# Capability:
#   - supports_link_generation = True (real, tested)
#   - supports_inbound = False (would need xray-core binary)
#   - status = STABLE (for link emission only)

import logging
from protocol_engine import (
    ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult

logger = logging.getLogger("EMIX.adapter.vmess")


class VmessAdapter(ProtocolAdapter):
    name = "vmess"
    version = "1.0.0"
    description = "VMess link emission (base64-JSON share-link). No inbound."

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.TCP, Transport.WEBSOCKET),
            supports_tcp=True,
            supports_tls=True,
            supports_http2=True,
            supports_websocket=True,
            supports_ipv4=True,
            supports_ipv6=False,
            supports_link_generation=True,  # REAL — emits valid VMess links
            supports_subscription=True,  # via existing subscription endpoint
            supports_health_check=False,  # no inbound to ping
            supports_inbound=False,  # would need xray-core binary (DEFERRED)
            supports_outbound=False,
            supports_uuid_auth=True,
            status=ProtocolStatus.EXPERIMENTAL,  # link emission only; no full inbound
            maturity="experimental",
        )

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        errors = []
        if not isinstance(config, dict):
            return False, ["config must be a dict"]
        uid = config.get("uuid") or config.get("uid")
        if not uid:
            errors.append("uuid is required")
        elif len(uid) < 16:
            errors.append("uuid looks too short (expected 36-char UUID)")
        addr = config.get("address") or config.get("host")
        if not addr:
            errors.append("address/host is required")
        port = config.get("port")
        if port is not None:
            try:
                p = int(port)
                if not (1 <= p <= 65535):
                    errors.append("port must be 1-65535")
            except (TypeError, ValueError):
                errors.append("port must be an integer")
        return (len(errors) == 0), errors

    def configure(self, config: dict) -> None:
        # Stateless adapter — no configuration to apply.
        pass

    def generate_link(self, params: dict) -> LinkResult:
        try:
            import link_emit
            link = link_emit.gen_vmess_link(
                address=params.get("address", ""),
                port=int(params.get("port", 443)),
                uuid=params.get("uuid", ""),
                name=params.get("name", "EMIX-VMess"),
                aid=int(params.get("aid", 0)),
                net=params.get("net", "ws"),
                host=params.get("host", ""),
                path=params.get("path", "/"),
                tls=params.get("tls", "tls"),
                sni=params.get("sni", ""),
                alpn=params.get("alpn", ""),
                fp=params.get("fp", "chrome"),
            )
            return LinkResult(ok=True, link=link, protocol="vmess", qr_text=link)
        except Exception as exc:
            logger.warning(f"vmess generate_link failed: {exc}")
            return LinkResult(ok=False, error=str(exc))

    async def health_check(self) -> HealthResult:
        return HealthResult(
            ok=True,
            detail="link-emission only; no inbound to health-check",
        )

    async def start(self) -> bool:
        return True  # stateless

    async def stop(self) -> bool:
        return True


register_protocol(VmessAdapter())
