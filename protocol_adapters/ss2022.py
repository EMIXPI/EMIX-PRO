# protocol_adapters/ss2022.py — Shadowsocks-2022 link emission adapter
#
# REAL implementation: emits SS-2022 share-links using the AEAD-2022 ciphers
# (2022-blake3-aes-256-gcm, 2022-blake3-aes-128-gcm, 2022-blake3-chacha20-poly1305).
# Uses the existing link_emit.gen_ss2022_link() helper.
#
# The adapter does NOT host an SS-2022 inbound — would need a separate
# server implementation (deferred). Existing Shadowsocks AEAD (chacha20-ietf-poly1305
# and aes-256-gcm) remains the working inbound.

import logging
from protocol_engine import (
    ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult

logger = logging.getLogger("EMIX.adapter.ss2022")


class Ss2022Adapter(ProtocolAdapter):
    name = "shadowsocks-2022"
    version = "1.0.0"
    description = "Shadowsocks 2022 link emission (AEAD-2022 ciphers, base64url password)"

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.TCP,),
            supports_tcp=True,
            supports_tls=False,  # SS-2022 is plaintext-on-the-wire (cipher is the only protection)
            supports_ipv4=True,
            supports_ipv6=False,
            supports_link_generation=True,
            supports_subscription=True,
            supports_health_check=False,  # no inbound
            supports_inbound=False,  # existing SS-AEAD inbound remains for chacha20/aes-256-gcm
            supports_outbound=False,
            supports_password_auth=True,
            status=ProtocolStatus.EXPERIMENTAL,  # link emission only
            maturity="experimental",
        )

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        errors = []
        if not isinstance(config, dict):
            return False, ["config must be a dict"]
        method = config.get("method", "2022-blake3-aes-256-gcm")
        valid_methods = {
            "2022-blake3-aes-256-gcm",
            "2022-blake3-aes-128-gcm",
            "2022-blake3-chacha20-poly1305",
        }
        if method not in valid_methods:
            errors.append(f"method must be one of {sorted(valid_methods)}")
        password = config.get("password", "")
        if not password:
            errors.append("password is required (base64url-encoded 32-byte key)")
        elif len(password) < 32:
            errors.append("password looks too short for SS-2022 (expected 43-char base64url)")
        addr = config.get("address") or config.get("host")
        if not addr:
            errors.append("address/host is required")
        return (len(errors) == 0), errors

    def configure(self, config: dict) -> None:
        pass

    def generate_link(self, params: dict) -> LinkResult:
        try:
            import link_emit
            link = link_emit.gen_ss2022_link(
                method=params.get("method", "2022-blake3-aes-256-gcm"),
                password=params.get("password", ""),
                address=params.get("address", ""),
                port=int(params.get("port", 443)),
                name=params.get("name", "EMIX-SS-2022"),
            )
            return LinkResult(ok=True, link=link, protocol="ss-2022", qr_text=link)
        except Exception as exc:
            logger.warning(f"ss-2022 generate_link failed: {exc}")
            return LinkResult(ok=False, error=str(exc))

    async def health_check(self) -> HealthResult:
        # Zero-fake-features policy (Phase 32): no real inbound exists to
        # probe, so we return an honest NOT_TESTABLE instead of ok=True.
        return HealthResult(
            ok=False,
            error="NOT_TESTABLE",
            detail="link-emission only; no inbound (existing SS-AEAD inbound remains for chacha20/aes-256-gcm)",
        )

    async def start(self) -> bool:
        return True

    async def stop(self) -> bool:
        return True


register_protocol(Ss2022Adapter())
