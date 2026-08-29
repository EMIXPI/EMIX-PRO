"""Unit tests for VPN Pro upgrade (Phase 1-12).

Covers:
  - VPNNode dataclass + CRUD
  - VPNProtocol enum (wireguard/openvpn)
  - VPNNodeStatus state machine (valid transitions only)
  - Pre-flight check command templates (no shell metacharacters allowed in params)
  - WireGuard server config generation (real Curve25519 keypair, valid .conf)
  - WireGuard client config generation (auto-assigned IP, real keys)
  - OpenVPN server config generation (real .conf with secure defaults)
  - OpenVPN client config generation (.ovpn template with cert placeholders)
  - ManualScriptProvider (always available, no actual VPS interaction)
  - VPNNode.to_dict() never exposes wg_server_private_key
"""
import os
import asyncio
import re
import pytest

os.environ.setdefault("PORT", "8765")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PASSWORD", "test-password")
os.environ.setdefault("RAILWAY_PUBLIC_DOMAIN", "test.example.com")
os.environ.setdefault("DATA_DIR", "/tmp/emix-test-vpn-pro-data")
os.makedirs(os.environ["DATA_DIR"], exist_ok=True)

import vpn_pro
from vpn_pro import (
    VPNNode, VPNProtocol, VPNNodeStatus, VPNHealthStatus, PreFlightStatus,
    create_node, get_node, update_node, delete_node, list_nodes,
    preflight_check, get_preflight_command, PREFLIGHT_COMMANDS,
    generate_wireguard_server_config, generate_wireguard_client_config,
    generate_openvpn_server_config, generate_openvpn_client_config,
    transition_state, TRANSITIONS, PROVISIONING_STATES,
    VPNProvider, ManualScriptProvider, get_provider, list_providers,
    all_nodes_dict, all_providers_dict,
)


# ── VPNNode dataclass + CRUD tests ────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_store():
    vpn_pro._nodes.clear()
    yield
    vpn_pro._nodes.clear()


def _make_node(name="test-node", nid="node-1", protocol=VPNProtocol.WIREGUARD):
    return VPNNode(
        id=nid, name=name, protocol=protocol,
        hostname="vps.example.com", ip="203.0.113.5", region="Amsterdam",
    )


def test_create_and_get_node():
    n = asyncio.run(create_node(_make_node()))
    assert n.id == "node-1"
    fetched = asyncio.run(get_node("node-1"))
    assert fetched is n


def test_create_duplicate_id_rejected():
    asyncio.run(create_node(_make_node(nid="dup")))
    with pytest.raises(ValueError, match="id already exists"):
        asyncio.run(create_node(_make_node(nid="dup")))


def test_create_duplicate_name_rejected():
    asyncio.run(create_node(_make_node(name="same", nid="a")))
    with pytest.raises(ValueError, match="name already exists"):
        asyncio.run(create_node(_make_node(name="same", nid="b")))


def test_update_node_changes_fields():
    asyncio.run(create_node(_make_node()))
    updated = asyncio.run(update_node("node-1", {"name": "renamed", "region": "Turkey"}))
    assert updated.name == "renamed"
    assert updated.region == "Turkey"


def test_update_nonexistent_returns_none():
    assert asyncio.run(update_node("nope", {"name": "x"})) is None


def test_delete_node():
    asyncio.run(create_node(_make_node()))
    assert asyncio.run(delete_node("node-1")) is True
    assert asyncio.run(get_node("node-1")) is None


def test_delete_nonexistent_returns_false():
    assert asyncio.run(delete_node("nope")) is False


def test_list_nodes():
    asyncio.run(create_node(_make_node(nid="a")))
    asyncio.run(create_node(_make_node(name="other", nid="b")))
    nodes = asyncio.run(list_nodes())
    assert len(nodes) == 2


def test_node_to_dict_never_exposes_private_key():
    """CRITICAL: to_dict() must NEVER include wg_server_private_key."""
    n = _make_node()
    n.wg_server_private_key = "super-secret-private-key-base64"
    d = n.to_dict()
    assert "wg_server_private_key" not in d, f"to_dict() leaked private key: {d.keys()}"
    assert "wg_server_public_key" in d  # public key is OK


def test_node_to_dict_includes_protocol_and_status():
    n = _make_node()
    d = n.to_dict()
    assert d["protocol"] == "wireguard"
    assert d["status"] == "PENDING"
    assert d["health_status"] == "UNKNOWN"


# ── State machine tests ───────────────────────────────────────────────────

def test_provisioning_states_in_order():
    """The 8 expected states must be in the right order."""
    expected = ["PENDING", "CONNECTING", "CHECKING", "INSTALLING", "CONFIGURING", "STARTING", "VERIFYING", "READY"]
    actual = [s.value for s in PROVISIONING_STATES]
    assert actual == expected


def test_valid_transition_pending_to_connecting():
    asyncio.run(create_node(_make_node()))
    n = asyncio.run(transition_state("node-1", VPNNodeStatus.CONNECTING))
    assert n.status == VPNNodeStatus.CONNECTING


def test_invalid_transition_pending_to_ready_rejected():
    asyncio.run(create_node(_make_node()))
    n = asyncio.run(transition_state("node-1", VPNNodeStatus.READY))
    # PENDING → READY is not a valid direct transition → returns None
    assert n is None


def test_failed_can_retry_to_pending():
    asyncio.run(create_node(_make_node()))
    asyncio.run(transition_state("node-1", VPNNodeStatus.CONNECTING))
    asyncio.run(transition_state("node-1", VPNNodeStatus.FAILED))
    n = asyncio.run(transition_state("node-1", VPNNodeStatus.PENDING))
    assert n is not None
    assert n.status == VPNNodeStatus.PENDING


def test_rolling_back_can_reach_failed():
    asyncio.run(create_node(_make_node()))
    asyncio.run(transition_state("node-1", VPNNodeStatus.CONNECTING))
    asyncio.run(transition_state("node-1", VPNNodeStatus.ROLLING_BACK))
    n = asyncio.run(transition_state("node-1", VPNNodeStatus.FAILED))
    assert n is not None


def test_ready_is_terminal():
    """READY → anything should fail."""
    asyncio.run(create_node(_make_node()))
    # Get to READY via valid chain
    for s in [VPNNodeStatus.CONNECTING, VPNNodeStatus.CHECKING,
              VPNNodeStatus.INSTALLING, VPNNodeStatus.CONFIGURING,
              VPNNodeStatus.STARTING, VPNNodeStatus.VERIFYING, VPNNodeStatus.READY]:
        asyncio.run(transition_state("node-1", s))
    # Now READY → CONNECTING should be invalid (READY has no outgoing transitions)
    n = asyncio.run(transition_state("node-1", VPNNodeStatus.CONNECTING))
    assert n is None


# ── Pre-flight check tests ───────────────────────────────────────────────

def test_preflight_commands_all_defined():
    """14 pre-flight command templates must be defined."""
    expected_keys = {"os", "arch", "kernel", "root_check", "memory", "disk",
                     "ipv4", "ipv6", "udp_available", "wg_kernel_support",
                     "wg_userspace_available", "ovpn_installed", "firewall", "port_in_use"}
    assert set(PREFLIGHT_COMMANDS.keys()) == expected_keys


def test_get_preflight_command_returns_template():
    cmd = get_preflight_command("os")
    assert "os-release" in cmd


def test_get_preflight_command_unknown_returns_none():
    assert get_preflight_command("nonexistent") is None


def test_get_preflight_command_rejects_shell_metacharacters():
    """CRITICAL: parameters must NOT contain shell metacharacters."""
    with pytest.raises(ValueError, match="invalid preflight param"):
        get_preflight_command("port_in_use", wg_port="51820; rm -rf /")


def test_get_preflight_command_rejects_semicolon():
    with pytest.raises(ValueError):
        get_preflight_command("port_in_use", wg_port="51820;ls")


def test_get_preflight_command_rejects_pipe():
    with pytest.raises(ValueError):
        get_preflight_command("port_in_use", wg_port="51820|cat")


def test_get_preflight_command_accepts_alphanumeric():
    cmd = get_preflight_command("port_in_use", wg_port="51820", ovpn_port="1194")
    assert "51820" in cmd
    assert "1194" in cmd


def test_preflight_check_returns_deferred_status():
    """Direct SSH execution is DEFERRED — preflight must report that honestly."""
    n = _make_node()
    asyncio.run(create_node(n))
    result = asyncio.run(preflight_check(n))
    assert result["status"] == "DEFERRED"
    assert "commands" in result
    assert "note" in result
    assert "asyncssh" in result["note"].lower() or "deferred" in result["note"].lower()


# ── WireGuard config generator tests ─────────────────────────────────────

def test_wg_server_config_generates_real_keys():
    n = _make_node()
    result = generate_wireguard_server_config(n)
    assert "server_private_key" in result
    assert "server_public_key" in result
    # Keys are base64-encoded 32-byte Curve25519
    import base64
    priv_bytes = base64.b64decode(result["server_private_key"])
    pub_bytes = base64.b64decode(result["server_public_key"])
    assert len(priv_bytes) == 32
    assert len(pub_bytes) == 32


def test_wg_server_config_includes_interface_and_listen_port():
    n = _make_node()
    n.wg_listen_port = 51820
    result = generate_wireguard_server_config(n)
    assert "ListenPort = 51820" in result["server_config"]
    assert "[Interface]" in result["server_config"]
    assert "PrivateKey = " in result["server_config"]


def test_wg_server_config_includes_iptables_routing():
    n = _make_node()
    result = generate_wireguard_server_config(n)
    assert "iptables" in result["server_config"]
    assert "MASQUERADE" in result["server_config"]


def test_wg_client_config_generates_real_keys():
    n = _make_node()
    n.wg_server_public_key = "server-pub-key-base64"
    result = generate_wireguard_client_config(n, "test-client")
    assert "client_private_key" in result
    assert "client_public_key" in result
    import base64
    assert len(base64.b64decode(result["client_private_key"])) == 32


def test_wg_client_config_auto_assigns_ip():
    n = _make_node()
    n.wg_address_range = "10.8.0.0/24"
    n.wg_server_public_key = "server-pub"
    result = generate_wireguard_client_config(n, "client1")
    assert result["client_ip"].startswith("10.8.0.")
    assert result["client_ip"] != "10.8.0.1"  # .1 is the server


def test_wg_client_config_avoids_duplicate_ips():
    n = _make_node()
    n.wg_address_range = "10.8.0.0/24"
    n.wg_server_public_key = "server-pub"
    # Pre-populate clients with .2 and .3
    n.clients = [
        {"ip": "10.8.0.2", "name": "c1"},
        {"ip": "10.8.0.3", "name": "c2"},
    ]
    result = generate_wireguard_client_config(n, "c3")
    assert result["client_ip"] == "10.8.0.4"


def test_wg_client_config_includes_endpoint():
    n = _make_node()
    n.wg_server_public_key = "server-pub-key-base64"
    result = generate_wireguard_client_config(n, "client")
    assert "Endpoint = 203.0.113.5:51820" in result["client_config"]


def test_wg_client_config_includes_keepalive():
    n = _make_node()
    n.wg_keepalive = 30
    n.wg_server_public_key = "server-pub"
    result = generate_wireguard_client_config(n, "client")
    assert "PersistentKeepalive = 30" in result["client_config"]


def test_wg_client_config_uses_hostname_when_no_ip():
    n = _make_node()
    n.ip = ""
    n.wg_server_public_key = "server-pub"
    result = generate_wireguard_client_config(n, "client")
    assert "Endpoint = vps.example.com:51820" in result["client_config"]


# ── OpenVPN config generator tests ───────────────────────────────────────

def test_ovpn_server_config_includes_port_and_protocol():
    n = _make_node(protocol=VPNProtocol.OPENVPN)
    n.ovpn_port = 1194
    n.ovpn_protocol = "udp"
    result = generate_openvpn_server_config(n)
    assert "port 1194" in result["server_config"]
    assert "proto udp" in result["server_config"]


def test_ovpn_server_config_includes_secure_defaults():
    n = _make_node(protocol=VPNProtocol.OPENVPN)
    result = generate_openvpn_server_config(n)
    assert "tls-version-min 1.2" in result["server_config"]
    assert "AES-256-GCM" in result["server_config"]
    assert "SHA256" in result["server_config"]


def test_ovpn_server_config_includes_pki_bootstrap():
    n = _make_node(protocol=VPNProtocol.OPENVPN)
    result = generate_openvpn_server_config(n)
    assert "easyrsa" in result["pki_bootstrap_script"]
    assert "build-ca" in result["pki_bootstrap_script"]


def test_ovpn_client_config_includes_remote():
    n = _make_node(protocol=VPNProtocol.OPENVPN)
    result = generate_openvpn_client_config(n, "client1")
    assert f"remote 203.0.113.5 1194" in result["client_config"]
    assert "client" in result["client_config"]
    assert "dev tun" in result["client_config"]


def test_ovpn_client_config_has_cert_placeholders():
    n = _make_node(protocol=VPNProtocol.OPENVPN)
    result = generate_openvpn_client_config(n, "client1")
    assert "<ca>" in result["client_config"]
    assert "<cert>" in result["client_config"]
    assert "<key>" in result["client_config"]
    assert result["contains_private_key"] is True  # admin fills in real cert


# ── Provider abstraction tests ────────────────────────────────────────────

def test_manual_provider_always_available():
    p = get_provider("manual")
    assert p is not None
    assert isinstance(p, ManualScriptProvider)


def test_list_providers_includes_manual():
    providers = list_providers()
    names = [p["name"] for p in providers]
    assert "manual" in names


def test_manual_provider_create_returns_status():
    p = get_provider("manual")
    result = asyncio.run(p.create_server())
    assert result["provider"] == "manual"
    assert result["status"] == "manual"


def test_unknown_provider_returns_none():
    assert get_provider("nonexistent") is None


# ── Public snapshot tests ────────────────────────────────────────────────

def test_all_nodes_dict_shape():
    asyncio.run(create_node(_make_node()))
    d = asyncio.run(all_nodes_dict())
    assert "nodes" in d
    assert d["count"] == 1


def test_all_nodes_dict_no_private_keys():
    n = _make_node()
    n.wg_server_private_key = "super-secret"
    asyncio.run(create_node(n))
    d = asyncio.run(all_nodes_dict())
    s = str(d)
    assert "super-secret" not in s
    assert "wg_server_private_key" not in s


def test_all_providers_dict_shape():
    d = all_providers_dict()
    assert "providers" in d
    assert d["count"] >= 1
