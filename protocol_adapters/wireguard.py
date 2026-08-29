# protocol_adapters/wireguard.py — DEFERRED adapter
#
# STATUS: DEFERRED — IMPLEMENTATION DEPENDENCY REQUIRED
#
# Why: WireGuard requires either:
#   (a) kernel module + wireguard-tools (Linux root) — NOT available on Railway
#   (b) wireguard-go (userspace Go binary) — would need to be vendored
#
# Railway does NOT provide:
#   - privileged kernel access
#   - persistent /dev/net/tun
#   - the ability to load kernel modules
#   - the ability to run Docker-in-Docker
#
# So WireGuard cannot be safely hosted on Railway. We expose capabilities
# + emit client configs (so admins can deploy WireGuard elsewhere and
# distribute configs through EMIX), but the panel itself does not run
# a WireGuard endpoint.
#
# The previous "VPN Pro" section in pages.py already supports WireGuard
# config generation — that path is preserved.

import logging
from protocol_engine import (
    ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult

logger = logging.getLogger("EMIX.adapter.wireguard")


class WireguardAdapter(ProtocolAdapter):
    name = "wireguard"
    version = "0.1.0"
    description = (
        "WireGuard config generation only — no inbound on Railway "
        "(would need kernel module or wireguard-go userspace binary)."
    )

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.UDP, Transport.WIREGUARD),
            supports_tcp=False,
            supports_udp=True,  # advertised but not hosted here
            supports_ipv4=True,
            supports_ipv6=False,
            supports_link_generation=True,  # client config emission (real)
            supports_subscription=False,
            supports_health_check=False,  # can't ping an external WG endpoint from here
            supports_inbound=False,  # not on Railway
            supports_outbound=False,
            supports_public_key_auth=True,  # WireGuard uses Curve25519 keypairs
            status=ProtocolStatus.DEFERRED,
            maturity="deferred",
        )

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        errors = []
        if not isinstance(config, dict):
            return False, ["config must be a dict"]
        # For client config emission: need endpoint + peer public key + client private key
        if not config.get("endpoint"):
            errors.append("endpoint is required (host:port of external WG server)")
        if not config.get("peer_public_key"):
            errors.append("peer_public_key is required (base64 32-byte Curve25519)")
        if not config.get("client_private_key") and not config.get("generate_client_key"):
            errors.append("client_private_key or generate_client_key=True is required")
        return (len(errors) == 0), errors

    def configure(self, config: dict) -> None:
        pass

    def generate_link(self, params: dict) -> LinkResult:
        """Emit a WireGuard client config (not a URL — WG doesn't have a URL scheme).
        Returns config text in the `config` field of LinkResult."""
        try:
            import secrets
            import base64
            endpoint = params.get("endpoint", "")
            peer_pub = params.get("peer_public_key", "")
            client_priv = params.get("client_private_key", "")
            if params.get("generate_client_key") and not client_priv:
                # Generate a fresh Curve25519 keypair (uses cryptography lib already in deps)
                from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
                priv = X25519PrivateKey.generate()
                client_priv = base64.b64encode(priv.private_bytes_raw()).decode()
                peer_pub_actual = base64.b64encode(priv.public_key().public_bytes_raw()).decode()
                # Note: peer_pub_actual is OUR public key — the peer must add it to their allowed_ips.
                # We return it in config["client_public_key"] for the admin to register on the server.
            allowed_ips = params.get("allowed_ips", "0.0.0.0/0, ::/0")
            dns = params.get("dns", "1.1.1.1")
            keepalive = int(params.get("keepalive", 25))
            client_pub_for_peer = params.get("client_public_key_for_peer", "")
            conf = (
                "[Interface]\n"
                f"PrivateKey = {client_priv}\n"
                f"Address = {params.get('client_address', '10.0.0.2/32')}\n"
                f"DNS = {dns}\n\n"
                "[Peer]\n"
                f"PublicKey = {peer_pub}\n"
                f"Endpoint = {endpoint}\n"
                f"AllowedIPs = {allowed_ips}\n"
                f"PersistentKeepalive = {keepalive}\n"
            )
            # Never log private keys
            return LinkResult(
                ok=True,
                link=None,  # WireGuard has no URL scheme
                protocol="wireguard",
                qr_text=conf,  # QR encodes the config text
                config={
                    "client_config": conf,
                    "client_public_key": client_pub_for_peer,
                    "endpoint": endpoint,
                    "peer_public_key": peer_pub,
                },
            )
        except Exception as exc:
            logger.warning(f"wireguard generate_link failed: {exc}")
            return LinkResult(ok=False, error=str(exc))

    async def health_check(self) -> HealthResult:
        return HealthResult(
            ok=True,
            detail="config emission only; panel cannot host WireGuard on Railway",
        )

    async def start(self) -> bool:
        return True  # stateless

    async def stop(self) -> bool:
        return True


register_protocol(WireguardAdapter())
