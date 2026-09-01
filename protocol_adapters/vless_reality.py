# protocol_adapters/vless_reality.py — VLESS-Reality link emission adapter
#
# REAL implementation: emits VLESS-Reality share-links with XTLS Vision flow,
# configurable SNI/shortID/public-key/fingerprint. The adapter does NOT host
# a Reality inbound — that requires xray-core 1.8+ (external binary, deferred).
#
# Security notes:
#   - NEVER logs private keys
#   - NEVER hard-codes a target website
#   - SNI / destination / shortID / fingerprint are all configurable
#   - Does NOT claim "anti-DPI guarantee"

import logging
from protocol_engine import (
    ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult

logger = logging.getLogger("EMIX.adapter.vless_reality")


class VlessRealityAdapter(ProtocolAdapter):
    name = "vless-reality"
    version = "1.0.0"
    description = "VLESS Reality link emission (XTLS Vision, configurable SNI/shortID/pbk/fp)"

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.TCP, Transport.GRPC),  # gRPC transport optional in link
            supports_tcp=True,
            supports_tls=True,
            supports_http2=True,  # Reality uses TLS 1.3 + HTTP/2
            supports_grpc=True,  # link supports gRPC variant
            supports_ipv4=True,
            supports_ipv6=False,
            supports_link_generation=True,
            supports_subscription=True,
            supports_health_check=False,  # no inbound
            supports_inbound=False,  # would need xray-core binary
            supports_outbound=False,
            supports_uuid_auth=True,
            supports_public_key_auth=True,  # pbk/sid
            status=ProtocolStatus.EXPERIMENTAL,  # link emission only
            maturity="experimental",
        )

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        errors = []
        if not isinstance(config, dict):
            return False, ["config must be a dict"]
        uid = config.get("uuid")
        if not uid:
            errors.append("uuid is required")
        pbk = config.get("pbk")  # public key (x25519)
        if not pbk:
            errors.append("pbk (x25519 public key) is required")
        elif len(pbk) < 32:
            errors.append("pbk looks too short (expected 43-char base64url x25519)")
        sni = config.get("sni")
        if not sni:
            errors.append("sni is required (e.g. www.cloudflare.com)")
        # shortID is optional but recommended
        sid = config.get("sid")
        if sid and len(sid) > 16:
            errors.append("sid (shortID) should be ≤ 16 hex chars")
        return (len(errors) == 0), errors

    def configure(self, config: dict) -> None:
        pass

    def generate_link(self, params: dict) -> LinkResult:
        try:
            import link_emit
            link = link_emit.gen_vless_reality_link(
                address=params.get("address", ""),
                port=int(params.get("port", 443)),
                uuid=params.get("uuid", ""),
                pbk=params.get("pbk", ""),
                sid=params.get("sid", ""),
                sni=params.get("sni", "www.cloudflare.com"),
                fp=params.get("fp", "chrome"),
                spx=params.get("spx", "/"),
                flow=params.get("flow", "xtls-rprx-vision"),
                name=params.get("name", "EMIX-VLESS-Reality"),
            )
            return LinkResult(ok=True, link=link, protocol="vless-reality", qr_text=link)
        except Exception as exc:
            logger.warning(f"vless-reality generate_link failed: {exc}")
            return LinkResult(ok=False, error=str(exc))

    async def health_check(self) -> HealthResult:
        # Zero-fake-features policy (Phase 32): no real inbound exists to
        # probe, so we return an honest NOT_TESTABLE instead of ok=True.
        return HealthResult(
            ok=False,
            error="NOT_TESTABLE",
            detail="link-emission only; no inbound to health-check (would need xray-core binary)",
        )

    async def start(self) -> bool:
        return True

    async def stop(self) -> bool:
        return True


register_protocol(VlessRealityAdapter())
