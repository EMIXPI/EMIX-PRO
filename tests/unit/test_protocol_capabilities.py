"""Unit tests for protocol_engine capabilities (Batch 8)."""
from protocol_engine import Capabilities, Transport, ProtocolStatus


def test_capabilities_defaults_all_false():
    c = Capabilities()
    assert c.supports_tcp is False
    assert c.supports_udp is False
    assert c.supports_tls is False
    assert c.supports_quic is False
    assert c.status == ProtocolStatus.DEFERRED


def test_capabilities_to_dict_serializes_all_fields():
    c = Capabilities(
        transports=(Transport.TCP, Transport.WEBSOCKET),
        supports_tcp=True,
        supports_tls=True,
        supports_websocket=True,
        supports_ipv4=True,
        supports_ipv6=True,
        status=ProtocolStatus.STABLE,
    )
    d = c.to_dict()
    assert d["supports_tcp"] is True
    assert d["supports_tls"] is True
    assert d["supports_websocket"] is True
    assert d["supports_ipv4"] is True
    assert d["supports_ipv6"] is True
    assert d["status"] == "stable"
    assert "tcp" in d["transports"]
    assert "ws" in d["transports"]


def test_transport_enum_values():
    assert Transport.TCP.value == "tcp"
    assert Transport.UDP.value == "udp"
    assert Transport.WEBSOCKET.value == "ws"
    assert Transport.XHTTP.value == "xhttp"
    assert Transport.GRPC.value == "grpc"
    assert Transport.HTTP_UPGRADE.value == "httpupgrade"
    assert Transport.QUIC.value == "quic"
    assert Transport.HTTP3.value == "http3"
    assert Transport.WEBTRANSPORT.value == "webtransport"
    assert Transport.KCP.value == "kcp"
    assert Transport.SSH.value == "ssh"
    assert Transport.WIREGUARD.value == "wireguard"


def test_protocol_status_enum_values():
    assert ProtocolStatus.STABLE.value == "stable"
    assert ProtocolStatus.EXPERIMENTAL.value == "experimental"
    assert ProtocolStatus.DEFERRED.value == "deferred"
    assert ProtocolStatus.UNAVAILABLE.value == "unavailable"
