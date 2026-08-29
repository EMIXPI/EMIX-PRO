# protocol_engine/capabilities.py — protocol capability flags
#
# Each adapter exposes a Capabilities object describing what it can really do.
# The selector uses this to filter protocols by user/network requirements.
# NEVER lie about a capability — if it's not really supported, mark it False.

from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple


class Transport(str, Enum):
    """Wire-level transports an adapter can use."""
    TCP = "tcp"
    UDP = "udp"
    WEBSOCKET = "ws"
    XHTTP = "xhttp"
    GRPC = "grpc"
    HTTP_UPGRADE = "httpupgrade"
    QUIC = "quic"
    HTTP3 = "http3"
    WEBTRANSPORT = "webtransport"
    KCP = "kcp"
    SSH = "ssh"
    WIREGUARD = "wireguard"


class ProtocolStatus(str, Enum):
    """Operational status of an adapter in the current environment."""
    STABLE = "stable"           # real, tested, working
    EXPERIMENTAL = "experimental"  # real but untested in production
    DEFERRED = "deferred"       # needs external dependency/binary not available
    UNAVAILABLE = "unavailable"  # not implementable in this environment


@dataclass(frozen=True)
class Capabilities:
    """What an adapter can really do. Be honest — no marketing flags."""
    # Transport-level
    transports: Tuple[Transport, ...] = field(default_factory=tuple)
    supports_tcp: bool = False
    supports_udp: bool = False
    supports_tls: bool = False
    supports_quic: bool = False
    supports_http2: bool = False
    supports_http3: bool = False
    supports_websocket: bool = False
    supports_grpc: bool = False
    supports_xhttp: bool = False
    supports_http_upgrade: bool = False
    supports_multiplexing: bool = False
    supports_0rtt: bool = False
    # Network
    supports_ipv4: bool = True
    supports_ipv6: bool = False
    # Operational
    supports_link_generation: bool = False
    supports_subscription: bool = False
    supports_health_check: bool = False
    supports_inbound: bool = False  # can the adapter accept real client connections?
    supports_outbound: bool = False  # can the adapter initiate outbound connections?
    # Authentication model
    supports_uuid_auth: bool = False
    supports_password_auth: bool = False
    supports_public_key_auth: bool = False
    supports_token_auth: bool = False
    # Status
    status: ProtocolStatus = ProtocolStatus.DEFERRED
    maturity: str = "experimental"  # for display

    def to_dict(self) -> dict:
        return {
            "transports": [t.value for t in self.transports],
            "supports_tcp": self.supports_tcp,
            "supports_udp": self.supports_udp,
            "supports_tls": self.supports_tls,
            "supports_quic": self.supports_quic,
            "supports_http2": self.supports_http2,
            "supports_http3": self.supports_http3,
            "supports_websocket": self.supports_websocket,
            "supports_grpc": self.supports_grpc,
            "supports_xhttp": self.supports_xhttp,
            "supports_http_upgrade": self.supports_http_upgrade,
            "supports_multiplexing": self.supports_multiplexing,
            "supports_0rtt": self.supports_0rtt,
            "supports_ipv4": self.supports_ipv4,
            "supports_ipv6": self.supports_ipv6,
            "supports_link_generation": self.supports_link_generation,
            "supports_subscription": self.supports_subscription,
            "supports_health_check": self.supports_health_check,
            "supports_inbound": self.supports_inbound,
            "supports_outbound": self.supports_outbound,
            "supports_uuid_auth": self.supports_uuid_auth,
            "supports_password_auth": self.supports_password_auth,
            "supports_public_key_auth": self.supports_public_key_auth,
            "supports_token_auth": self.supports_token_auth,
            "status": self.status.value,
            "maturity": self.maturity,
        }
