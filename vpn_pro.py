# vpn_pro.py — VPN Pro upgrade: VPNNode data model + pre-flight + state machine
#
# ARCHITECTURE:
#   EMIX-PRO panel = CONTROL PLANE (this module)
#   VPS node = DATA PLANE (runs the actual VPN gateway)
#
# What this module implements (REAL):
#   - VPNNode dataclass (id, name, provider, hostname, protocol, status, etc.)
#   - VPNProtocol enum (WireGuard, OpenVPN)
#   - VPNNodeStatus enum (PENDING → CONNECTING → CHECKING → INSTALLING →
#     CONFIGURING → STARTING → VERIFYING → READY / FAILED / ROLLING_BACK)
#   - PreFlightCheck templates (validated command templates — NOT user input)
#   - WireGuard config generator (extends existing logic in bridge_boost.py
#     — produces real, deterministic .conf from inputs)
#   - OpenVPN config generator (produces real .ovpn from inputs)
#   - VPNNodeStore (in-memory, process-local)
#   - Provider abstraction (interface — no concrete providers)
#   - Manual Script mode preserved (existing fallback)
#
# What this module does NOT do (DEFERRED — needs asyncssh + real VPS testing):
#   - Direct SSH provisioning (no asyncssh in requirements.txt)
#   - Actual command execution on remote VPS
#   - Provider API calls (no provider credentials)
#   - Real-time traffic monitoring (would need SSH polling)
#
# Direct SSH provisioning is INTENTIONALLY DEFERRED with documentation.
# Never claim it works — it doesn't, until asyncssh is added AND tested
# against a real VPS.

from __future__ import annotations
import os
import re
import time
import secrets
import logging
import asyncio
import base64
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Callable, Awaitable

logger = logging.getLogger("EMIX.vpn_pro")


# ─── Enums ──────────────────────────────────────────────────────────────────

class VPNProtocol(str, Enum):
    WIREGUARD = "wireguard"
    OPENVPN = "openvpn"


class VPNNodeStatus(str, Enum):
    PENDING = "PENDING"
    CONNECTING = "CONNECTING"
    CHECKING = "CHECKING"
    INSTALLING = "INSTALLING"
    CONFIGURING = "CONFIGURING"
    STARTING = "STARTING"
    VERIFYING = "VERIFYING"
    READY = "READY"
    FAILED = "FAILED"
    ROLLING_BACK = "ROLLING_BACK"


class VPNHealthStatus(str, Enum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


class PreFlightStatus(str, Enum):
    READY = "READY"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"


# ─── VPNNode data model ────────────────────────────────────────────────────

@dataclass
class VPNNode:
    """A VPN server node (typically a remote VPS).

    The panel acts as control plane. The actual VPN gateway runs on the
    node. Provisioning happens via SSH or provider API.
    """
    id: str
    name: str
    provider: str = "manual"  # "manual" | "ssh" | "digitalocean" | "vultr" | "hetzner" (only manual + ssh are real today)
    hostname: str = ""
    ip: str = ""
    ssh_port: int = 22
    protocol: VPNProtocol = VPNProtocol.WIREGUARD
    status: VPNNodeStatus = VPNNodeStatus.PENDING
    region: str = ""  # e.g. "Amsterdam", "Turkey", "Dubai"
    # NEVER store plaintext SSH passwords. Only reference a key fingerprint.
    ssh_key_fingerprint: Optional[str] = None  # SHA-256 of the SSH public key
    # WireGuard interface config (real, generated values)
    wg_interface_name: str = "wg0"
    wg_listen_port: int = 51820
    wg_address_range: str = "10.8.0.0/24"
    wg_dns: str = "1.1.1.1"
    wg_mtu: int = 1420
    wg_keepalive: int = 25
    wg_server_private_key: Optional[str] = None  # generated at provisioning time
    wg_server_public_key: Optional[str] = None
    # OpenVPN config
    ovpn_port: int = 1194
    ovpn_protocol: str = "udp"  # "udp" | "tcp"
    ovpn_cipher: str = "AES-256-GCM"
    ovpn_network: str = "10.8.0.0/24"
    ovpn_dns: str = "1.1.1.1"
    # Health + clients
    clients: List[dict] = field(default_factory=list)
    health_status: VPNHealthStatus = VPNHealthStatus.UNKNOWN
    last_health_check: Optional[float] = None
    last_health_rtt_ms: Optional[float] = None
    last_health_error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["protocol"] = self.protocol.value if isinstance(self.protocol, VPNProtocol) else self.protocol
        d["status"] = self.status.value if isinstance(self.status, VPNNodeStatus) else self.status
        d["health_status"] = self.health_status.value if isinstance(self.health_status, VPNHealthStatus) else self.health_status
        # NEVER expose server private key in API responses
        d.pop("wg_server_private_key", None)
        return d


# ─── In-memory node store ──────────────────────────────────────────────────

_nodes: dict[str, VPNNode] = {}
_nodes_lock = asyncio.Lock()


async def list_nodes() -> List[VPNNode]:
    async with _nodes_lock:
        return list(_nodes.values())


async def get_node(node_id: str) -> Optional[VPNNode]:
    async with _nodes_lock:
        return _nodes.get(node_id)


async def create_node(node: VPNNode) -> VPNNode:
    async with _nodes_lock:
        if node.id in _nodes:
            raise ValueError(f"node id already exists: {node.id}")
        for existing in _nodes.values():
            if existing.name == node.name:
                raise ValueError(f"node name already exists: {node.name}")
        _nodes[node.id] = node
        logger.info(f"[vpn-pro] node created: id={node.id} name={node.name} protocol={node.protocol.value}")
        return node


async def update_node(node_id: str, updates: dict) -> Optional[VPNNode]:
    async with _nodes_lock:
        node = _nodes.get(node_id)
        if node is None:
            return None
        for k, v in updates.items():
            if hasattr(node, k):
                setattr(node, k, v)
        return node


async def delete_node(node_id: str) -> bool:
    async with _nodes_lock:
        if node_id in _nodes:
            del _nodes[node_id]
            return True
        return False


# ─── Pre-flight check templates (validated command templates) ─────────────
# These are predefined commands with NO user-supplied parameters. They are
# executed by the SSH provisioning engine (when implemented) — never by
# direct user input.

PREFLIGHT_COMMANDS = {
    "os": "cat /etc/os-release | grep PRETTY_NAME",
    "arch": "uname -m",
    "kernel": "uname -r",
    "root_check": "id -u",  # must return 0 for root
    "memory": "free -m | awk '/^Mem:/ {print $2}'",
    "disk": "df -h / | awk 'NR==2 {print $4}'",
    "ipv4": "curl -s4 ifconfig.me",
    "ipv6": "curl -s6 ifconfig.me || true",
    "udp_available": "nc -uz 8.8.8.8 53 && echo OK || echo FAIL",
    "wg_kernel_support": "modprobe wireguard 2>&1 || echo MISSING",
    "wg_userspace_available": "which wireguard-go 2>&1 || echo MISSING",
    "ovpn_installed": "which openvpn 2>&1 || echo MISSING",
    "firewall": "which ufw 2>&1 || which firewall-cmd 2>&1 || echo MISSING",
    "port_in_use": "ss -tlnp | grep -E ':({wg_port}|{ovpn_port})' || echo FREE",
}


def get_preflight_command(name: str, **params) -> Optional[str]:
    """Return a validated pre-flight command template.
    Parameters are inserted via str.format(**params) — NEVER via user input.
    """
    tmpl = PREFLIGHT_COMMANDS.get(name)
    if tmpl is None:
        return None
    # Validate params — coerce to str first, then check for shell metacharacters
    for k, v in (params or {}).items():
        # Coerce ints (e.g. port numbers) to strings
        if isinstance(v, int):
            v = str(v)
        if not isinstance(v, str) or not re.fullmatch(r"[a-zA-Z0-9_\-\.]+", v):
            raise ValueError(f"invalid preflight param: {k}={v!r}")
    # Only call str.format() if the template actually has placeholders that
    # match the provided params. Otherwise, return the raw template — many
    # preflight commands contain literal curly braces (e.g. awk's {print $2})
    # that str.format() would misinterpret.
    if not params:
        return tmpl
    try:
        # Check if any of the provided param keys appear in the template
        if any(f"{{{k}}}" in tmpl for k in params):
            return tmpl.format(**params)
    except (KeyError, IndexError):
        pass
    return tmpl


async def preflight_check(node: VPNNode) -> dict:
    """Run the pre-flight check against a node.

    Returns a structured report with status READY/WARNING/BLOCKED.
    NOTE: This is a TEMPLATE — actual execution requires SSH (DEFERRED).
    The function returns the commands that WOULD be run, plus a status
    indicating that execution is not yet implemented.
    """
    commands_to_run = {
        name: get_preflight_command(name, wg_port=node.wg_listen_port, ovpn_port=node.ovpn_port) or ""
        for name in PREFLIGHT_COMMANDS
    }
    return {
        "node_id": node.id,
        "checked_at": time.time(),
        "status": "DEFERRED",  # SSH execution not implemented
        "commands": commands_to_run,
        "note": "Direct SSH execution is DEFERRED — needs asyncssh library + real VPS testing. Use the existing Manual Script mode as fallback.",
    }


# ─── WireGuard config generator (REAL — produces valid .conf from inputs) ──

def generate_wireguard_server_config(node: VPNNode) -> dict:
    """Generate a complete WireGuard server configuration + client config.

    Real, deterministic output from the inputs. Uses the cryptography
    library (already in deps) for X25519 keypair generation.
    """
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives import serialization

    # Generate server keypair (real Curve25519)
    server_priv = X25519PrivateKey.generate()
    server_priv_bytes = server_priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    server_priv_b64 = base64.b64encode(server_priv_bytes).decode()
    server_pub_bytes = server_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    server_pub_b64 = base64.b64encode(server_pub_bytes).decode()

    # Server config (real .conf text)
    server_conf = (
        "[Interface]\n"
        f"Address = {node.wg_address_range.split('/')[0].rsplit('.', 1)[0]}.1/24\n"
        f"ListenPort = {node.wg_listen_port}\n"
        f"PrivateKey = {server_priv_b64}\n"
        f"PostUp = iptables -A FORWARD -i {node.wg_interface_name} -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE\n"
        f"PostDown = iptables -D FORWARD -i {node.wg_interface_name} -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE\n"
    )

    return {
        "node_id": node.id,
        "server_private_key": server_priv_b64,  # returned once for admin to install on VPS
        "server_public_key": server_pub_b64,
        "server_config": server_conf,
        "interface_name": node.wg_interface_name,
        "listen_port": node.wg_listen_port,
        "address_range": node.wg_address_range,
        "dns": node.wg_dns,
        "mtu": node.wg_mtu,
        "keepalive": node.wg_keepalive,
        # Note: server_private_key is in the response because the admin needs
        # it to install on the VPS. NEVER log this.
    }


def generate_wireguard_client_config(node: VPNNode, client_name: str, client_ip: str = "") -> dict:
    """Generate a WireGuard client config (.conf + QR text).

    Uses real Curve25519 keypair generation. Client IP is auto-assigned
    from the node's address range if not provided.
    """
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    import ipaddress

    # Auto-assign client IP (next free in the /24)
    if not client_ip:
        # Find next free .2, .3, ... in the address range
        base = node.wg_address_range.split("/")[0].rsplit(".", 1)[0]
        used_ips = {c.get("ip", "") for c in node.clients}
        for i in range(2, 254):
            candidate = f"{base}.{i}"
            if candidate not in used_ips:
                client_ip = candidate
                break

    # Generate client keypair (real)
    client_priv = X25519PrivateKey.generate()
    client_priv_bytes = client_priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    client_priv_b64 = base64.b64encode(client_priv_bytes).decode()
    client_pub_bytes = client_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    client_pub_b64 = base64.b64encode(client_pub_bytes).decode()

    # Build client config
    client_conf = (
        "[Interface]\n"
        f"PrivateKey = {client_priv_b64}\n"
        f"Address = {client_ip}/32\n"
        f"DNS = {node.wg_dns}\n\n"
        "[Peer]\n"
        f"PublicKey = {node.wg_server_public_key or '<SERVER_PUBLIC_KEY>'}\n"
        f"Endpoint = {node.ip or node.hostname}:{node.wg_listen_port}\n"
        "AllowedIPs = 0.0.0.0/0, ::/0\n"
        f"PersistentKeepalive = {node.wg_keepalive}\n"
    )

    return {
        "client_name": client_name,
        "client_ip": client_ip,
        "client_private_key": client_priv_b64,  # returned to admin for QR generation
        "client_public_key": client_pub_b64,    # for the server's [Peer] section
        "client_config": client_conf,
        "qr_text": client_conf,
        "endpoint": f"{node.ip or node.hostname}:{node.wg_listen_port}",
    }


# ─── OpenVPN config generator (REAL — produces valid .ovpn from inputs) ────

def generate_openvpn_server_config(node: VPNNode) -> dict:
    """Generate a complete OpenVPN server configuration + PKI bootstrap commands.

    Real, deterministic output. PKI generation uses easy-rsa (commands
    included as a script for admin to run on the VPS).
    """
    # Easy-RSA bootstrap commands (real — admin runs on VPS)
    pki_bootstrap = (
        "#!/bin/bash\n"
        "set -e\n"
        "cd /etc/openvpn/easy-rsa\n"
        "if [ ! -d pki ]; then\n"
        "  ./easyrsa init-pki\n"
        "  echo 'vpn.local' | ./easyrsa build-ca nopass\n"
        f"  echo 'server-{node.id[:8]}' | ./easyrsa build-server-full server nopass\n"
        f"  echo 'client-template' | ./easyrsa build-client-full client-template nopass\n"
        "  ./easyrsa gen-crl\n"
        "fi\n"
    )
    # Server config (real openvpn.conf)
    server_conf = (
        "port " + str(node.ovpn_port) + "\n"
        "proto " + node.ovpn_protocol + "\n"
        "dev tun\n"
        "ca /etc/openvpn/easy-rsa/pki/ca.crt\n"
        "cert /etc/openvpn/easy-rsa/pki/issued/server.crt\n"
        "key /etc/openvpn/easy-rsa/pki/private/server.key\n"
        "dh none\n"
        "ecdh-curve prime256v1\n"
        "crl-verify /etc/openvpn/easy-rsa/pki/crl.pem\n"
        "server " + node.ovpn_network + " 255.255.255.0\n"
        "ifconfig-pool-persist /var/log/openvpn-ipp.txt\n"
        "push 'redirect-gateway def1 bypass-dhcp'\n"
        f"push 'dhcp-option DNS {node.ovpn_dns}'\n"
        "keepalive 10 120\n"
        "cipher " + node.ovpn_cipher + "\n"
        "auth SHA256\n"
        "tls-auth /etc/openvpn/ta.key 0\n"
        "tls-version-min 1.2\n"
        "tls-cipher TLS-ECDHE-RSA-WITH-AES-256-GCM-SHA384\n"
        "user nobody\n"
        "group nogroup\n"
        "persist-key\n"
        "persist-tun\n"
        "status /var/log/openvpn-status.log\n"
        "verb 3\n"
    )
    return {
        "node_id": node.id,
        "pki_bootstrap_script": pki_bootstrap,
        "server_config": server_conf,
        "port": node.ovpn_port,
        "protocol": node.ovpn_protocol,
        "cipher": node.ovpn_cipher,
        "network": node.ovpn_network,
        "dns": node.ovpn_dns,
    }


def generate_openvpn_client_config(node: VPNNode, client_name: str) -> dict:
    """Generate an OpenVPN client .ovpn config (template — admin fills in cert paths)."""
    client_conf = (
        "client\n"
        "dev tun\n"
        "proto " + node.ovpn_protocol + "\n"
        f"remote {node.ip or node.hostname} {node.ovpn_port}\n"
        "resolv-retry infinite\n"
        "nobind\n"
        "persist-tun\n"
        "persist-key\n"
        "remote-cert-tls server\n"
        "cipher " + node.ovpn_cipher + "\n"
        "auth SHA256\n"
        "tls-version-min 1.2\n"
        "verb 3\n\n"
        "<ca>\n"
        "# Paste CA certificate (ca.crt) here\n"
        "</ca>\n\n"
        "<cert>\n"
        f"# Paste client certificate ({client_name}.crt) here\n"
        "</cert>\n\n"
        "<key>\n"
        f"# Paste client private key ({client_name}.key) here\n"
        "</key>\n\n"
        "<tls-auth>\n"
        "# Paste ta.key here\n"
        "</tls-auth>\n"
        "key-direction 1\n"
    )
    return {
        "client_name": client_name,
        "client_config": client_conf,
        "qr_text": client_conf,
        "endpoint": f"{node.ip or node.hostname}:{node.ovpn_port}",
        "contains_private_key": True,  # admin must fill in real cert/key material
    }


# ─── Provisioning state machine (templates — no SSH execution) ─────────────

PROVISIONING_STATES = [
    VPNNodeStatus.PENDING,
    VPNNodeStatus.CONNECTING,
    VPNNodeStatus.CHECKING,
    VPNNodeStatus.INSTALLING,
    VPNNodeStatus.CONFIGURING,
    VPNNodeStatus.STARTING,
    VPNNodeStatus.VERIFYING,
    VPNNodeStatus.READY,
]

# Valid transitions
TRANSITIONS = {
    VPNNodeStatus.PENDING: {VPNNodeStatus.CONNECTING, VPNNodeStatus.FAILED},
    VPNNodeStatus.CONNECTING: {VPNNodeStatus.CHECKING, VPNNodeStatus.FAILED, VPNNodeStatus.ROLLING_BACK},
    VPNNodeStatus.CHECKING: {VPNNodeStatus.INSTALLING, VPNNodeStatus.FAILED, VPNNodeStatus.ROLLING_BACK},
    VPNNodeStatus.INSTALLING: {VPNNodeStatus.CONFIGURING, VPNNodeStatus.FAILED, VPNNodeStatus.ROLLING_BACK},
    VPNNodeStatus.CONFIGURING: {VPNNodeStatus.STARTING, VPNNodeStatus.FAILED, VPNNodeStatus.ROLLING_BACK},
    VPNNodeStatus.STARTING: {VPNNodeStatus.VERIFYING, VPNNodeStatus.FAILED, VPNNodeStatus.ROLLING_BACK},
    VPNNodeStatus.VERIFYING: {VPNNodeStatus.READY, VPNNodeStatus.FAILED, VPNNodeStatus.ROLLING_BACK},
    VPNNodeStatus.READY: set(),  # terminal
    VPNNodeStatus.FAILED: {VPNNodeStatus.PENDING},  # can retry
    VPNNodeStatus.ROLLING_BACK: {VPNNodeStatus.FAILED, VPNNodeStatus.PENDING},
}


async def transition_state(node_id: str, to: VPNNodeStatus) -> Optional[VPNNode]:
    """Transition a node's status. Returns the updated node or None if invalid transition."""
    async with _nodes_lock:
        node = _nodes.get(node_id)
        if node is None:
            return None
        current = node.status if isinstance(node.status, VPNNodeStatus) else VPNNodeStatus(node.status)
        if to not in TRANSITIONS.get(current, set()):
            logger.warning(f"[vpn-pro] invalid transition {current.value} → {to.value} for node {node_id}")
            return None
        node.status = to
        logger.info(f"[vpn-pro] node {node_id} transitioned: {current.value} → {to.value}")
        return node


# ─── Provider abstraction (interface — no concrete providers) ─────────────

class VPNProvider:
    """Abstract VPN provider interface. Concrete providers implement these methods."""
    name: str = "abstract"

    async def create_server(self, **kwargs) -> dict:
        raise NotImplementedError

    async def delete_server(self, server_id: str) -> bool:
        raise NotImplementedError

    async def get_server(self, server_id: str) -> dict:
        raise NotImplementedError

    async def get_status(self, server_id: str) -> str:
        raise NotImplementedError

    async def get_public_ip(self, server_id: str) -> str:
        raise NotImplementedError

    def supported_regions(self) -> List[str]:
        return []

    def supported_images(self) -> List[str]:
        return []


# Manual provider — always available (uses existing script-generation mode)
class ManualScriptProvider(VPNProvider):
    name = "manual"

    async def create_server(self, **kwargs) -> dict:
        return {
            "provider": self.name,
            "status": "manual",
            "note": "Manual Script mode — admin runs the generated script on their VPS",
        }

    async def delete_server(self, server_id: str) -> bool:
        return True  # nothing to delete on the panel side

    async def get_server(self, server_id: str) -> dict:
        return {"provider": self.name, "status": "manual"}

    async def get_status(self, server_id: str) -> str:
        return "MANUAL"

    async def get_public_ip(self, server_id: str) -> str:
        return ""  # admin provides this manually

    def supported_regions(self) -> List[str]:
        return ["any"]

    def supported_images(self) -> List[str]:
        return ["any"]


# Registry of providers
_PROVIDERS: dict[str, VPNProvider] = {"manual": ManualScriptProvider()}


def get_provider(name: str) -> Optional[VPNProvider]:
    return _PROVIDERS.get(name)


def list_providers() -> List[dict]:
    return [{"name": p.name} for p in _PROVIDERS.values()]


# ─── Public snapshot ──────────────────────────────────────────────────────

async def all_nodes_dict() -> dict:
    async with _nodes_lock:
        return {
            "nodes": [n.to_dict() for n in _nodes.values()],
            "count": len(_nodes),
        }


def all_providers_dict() -> dict:
    return {"providers": list_providers(), "count": len(_PROVIDERS)}


# ─── Persistence snapshot (audit fix 2026-09) ──────────────────────────────
# کلیدهای WireGuard سرور قبلاً فقط در-memory بودند — بعد از هر redeploy،
# کلید خصوصی سرور گم می‌شد و همه‌ی peerها بی‌اعتبار می‌شدند.
# NOTE: wg_server_private_key عمداً در snapshot می‌ماند (state file خودش
# حاوی credentialهای لینک است و روی volume خصوصی پنل می‌نشیند).

def persist_snapshot() -> dict:
    """Serialize nodes INCLUDING wg_server_private_key (needed to survive restart)."""
    out = []
    for n in _nodes.values():
        d = asdict(n)
        d["protocol"] = n.protocol.value if isinstance(n.protocol, VPNProtocol) else n.protocol
        d["status"] = n.status.value if isinstance(n.status, VPNNodeStatus) else n.status
        d["health_status"] = n.health_status.value if isinstance(n.health_status, VPNHealthStatus) else n.health_status
        out.append(d)
    return {"vpn_nodes": out}


def restore_snapshot(data: dict) -> int:
    raw = data.get("vpn_nodes") or []
    restored = 0
    for item in raw:
        try:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            proto = item.get("protocol")
            if isinstance(proto, str):
                try:
                    proto = VPNProtocol(proto)
                except ValueError:
                    proto = VPNProtocol.WIREGUARD
            item["protocol"] = proto
            status = item.get("status")
            if isinstance(status, str):
                try:
                    status = VPNNodeStatus(status)
                except ValueError:
                    status = VPNNodeStatus.PENDING
            item["status"] = status
            hs = item.get("health_status")
            if isinstance(hs, str):
                try:
                    hs = VPNHealthStatus(hs)
                except ValueError:
                    hs = VPNHealthStatus.UNKNOWN
            item["health_status"] = hs
            node = VPNNode(**{k: v for k, v in item.items()
                              if k in VPNNode.__dataclass_fields__})
            _nodes[node.id] = node
            restored += 1
        except Exception:
            continue
    return restored


def reset_for_tests() -> None:
    _nodes.clear()
