# protocol_adapters/openvpn.py — DEFERRED adapter
#
# STATUS: DEFERRED — IMPLEMENTATION DEPENDENCY REQUIRED
#
# Why: OpenVPN is a C binary with its own TLS stack, TUN device handling,
# and routing logic. There is no Python implementation. Running an OpenVPN
# server requires:
#   - the openvpn binary (Debian/Ubuntu package)
#   - root access for TUN device creation
#   - kernel module for tun
#   - certificate authority management
#
# Railway does NOT provide:
#   - the openvpn binary (no apt-get)
#   - root / TUN device access
#   - persistent storage for CA/private keys
#
# What we DO expose: client config generation (.ovpn files) for admins
# who run OpenVPN elsewhere and want to distribute configs via EMIX.

import logging
from protocol_engine import (
    ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult

logger = logging.getLogger("EMIX.adapter.openvpn")


class OpenvpnAdapter(ProtocolAdapter):
    name = "openvpn"
    version = "0.1.0"
    description = (
        "OpenVPN client config generation only — no server on Railway "
        "(needs openvpn binary + root + TUN device)."
    )

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.UDP, Transport.TCP),
            supports_tcp=True,
            supports_udp=True,  # advertised for client config emission
            supports_tls=True,
            supports_ipv4=True,
            supports_ipv6=False,
            supports_link_generation=True,  # client .ovpn emission (real)
            supports_subscription=False,
            supports_health_check=False,
            supports_inbound=False,  # not on Railway
            supports_outbound=False,
            supports_public_key_auth=True,  # x509 cert auth
            status=ProtocolStatus.DEFERRED,
            maturity="deferred",
        )

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        errors = []
        if not isinstance(config, dict):
            return False, ["config must be a dict"]
        if not config.get("remote"):
            errors.append("remote (host:port) is required")
        if not config.get("ca_cert"):
            errors.append("ca_cert is required (PEM-encoded CA certificate)")
        if not config.get("client_cert"):
            errors.append("client_cert is required (PEM-encoded client certificate)")
        if not config.get("client_key"):
            errors.append("client_key is required (PEM-encoded client private key)")
        return (len(errors) == 0), errors

    def configure(self, config: dict) -> None:
        pass

    def generate_link(self, params: dict) -> LinkResult:
        """Emit an OpenVPN .ovpn client config.
        Returns config text in `config.client_config`."""
        try:
            remote = params.get("remote", "")
            ca_cert = params.get("ca_cert", "")
            client_cert = params.get("client_cert", "")
            client_key = params.get("client_key", "")
            proto = params.get("proto", "udp")
            # Build the .ovpn config — embedded certs
            conf = (
                "client\n"
                f"dev tun\n"
                f"proto {proto}\n"
                f"remote {remote}\n"
                "resolv-retry infinite\n"
                "nobind\n"
                "persist-tun\n"
                "persist-key\n"
                "remote-cert-tls server\n"
                "cipher AES-256-GCM\n"
                "auth SHA256\n"
                "verb 3\n\n"
                "<ca>\n"
                f"{ca_cert}\n"
                "</ca>\n\n"
                "<cert>\n"
                f"{client_cert}\n"
                "</cert>\n\n"
                "<key>\n"
                f"{client_key}\n"
                "</key>\n"
            )
            # WARNING: contains private key material — caller is responsible
            # for secure handling. Never logged by this adapter.
            return LinkResult(
                ok=True,
                link=None,
                protocol="openvpn",
                qr_text=conf,
                config={
                    "client_config": conf,
                    "remote": remote,
                    "proto": proto,
                    "contains_private_key": True,
                },
            )
        except Exception as exc:
            logger.warning(f"openvpn generate_link failed: {exc}")
            return LinkResult(ok=False, error=str(exc))

    async def health_check(self) -> HealthResult:
        return HealthResult(
            ok=True,
            detail="config emission only; panel cannot host OpenVPN on Railway",
        )

    async def start(self) -> bool:
        return True

    async def stop(self) -> bool:
        return True


register_protocol(OpenvpnAdapter())
