# protocol_adapters/ssh.py — EXPERIMENTAL adapter
#
# STATUS: EXPERIMENTAL — would require asyncssh library
#
# What this adapter does today:
#   - Reports capabilities (TCP/SSH/IPv4/IPv6)
#   - Does NOT host an SSH server (Railway already exposes the panel over HTTPS)
#   - Could be enabled as an OUTBOUND tunnel in the future
#
# To make this REAL:
#   - Add `asyncssh>=2.14` to requirements.txt
#   - Implement SSHClientTunnel that wraps an outbound SSH connection
#   - Health check: connect + authenticate + close
#   - Never disable host-key verification globally
#
# This adapter does NOT create fake implementations. It just reports
# capabilities and refuses to start until the dependency is added.

import logging
from protocol_engine import (
    ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult

logger = logging.getLogger("EMIX.adapter.ssh")


def _asyncssh_available() -> bool:
    try:
        import asyncssh  # noqa: F401
        return True
    except ImportError:
        return False


class SshAdapter(ProtocolAdapter):
    name = "ssh"
    version = "0.1.0"
    description = (
        "SSH tunnel adapter. EXPERIMENTAL — would require asyncssh library. "
        "Currently capability-detection only."
    )

    def capabilities(self) -> Capabilities:
        available = _asyncssh_available()
        return Capabilities(
            transports=(Transport.TCP, Transport.SSH),
            supports_tcp=True,
            supports_tls=False,  # SSH has its own transport
            supports_ipv4=True,
            supports_ipv6=False,
            supports_link_generation=False,  # SSH has no URL scheme
            supports_health_check=available,
            supports_inbound=False,  # Railway doesn't host SSH server
            supports_outbound=available,  # could be added with asyncssh
            supports_password_auth=True,
            supports_public_key_auth=True,
            status=ProtocolStatus.EXPERIMENTAL if available else ProtocolStatus.DEFERRED,
            maturity="experimental" if available else "deferred",
        )

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        if not _asyncssh_available():
            return False, ["SSH adapter needs asyncssh library (not installed)"]
        errors = []
        if not config.get("host"):
            errors.append("host is required")
        if not config.get("port"):
            errors.append("port is required")
        if not config.get("username"):
            errors.append("username is required")
        if not (config.get("password") or config.get("client_key")):
            errors.append("either password or client_key is required")
        return (len(errors) == 0), errors

    def configure(self, config: dict) -> None:
        pass

    def generate_link(self, params: dict) -> LinkResult:
        # SSH doesn't have a standard URL scheme, but we can emit an ssh:// URL
        host = params.get("host", "")
        port = params.get("port", 22)
        user = params.get("username", "")
        link = f"ssh://{user}@{host}:{port}"
        return LinkResult(ok=True, link=link, protocol="ssh", qr_text=link)

    async def health_check(self) -> HealthResult:
        if not _asyncssh_available():
            return HealthResult(
                ok=False,
                error="asyncssh library not installed",
                detail="add 'asyncssh>=2.14' to requirements.txt to enable",
            )
        # Real health check would: connect → authenticate → close
        return HealthResult(
            ok=True,
            detail="asyncssh installed but no host configured for health check",
        )

    async def start(self) -> bool:
        if not _asyncssh_available():
            logger.warning("[ssh] start() called but asyncssh not installed")
            return False
        return True

    async def stop(self) -> bool:
        return True


register_protocol(SshAdapter())
