# protocol_engine/base.py — ProtocolAdapter abstract interface
#
# Every protocol adapter implements this interface. Existing implementations
# are wrapped by adapter classes that delegate to the existing code — NO
# wire-level changes. New protocols implement this directly where safe.

from __future__ import annotations
import abc
from dataclasses import dataclass, field
from typing import Any, Optional, Awaitable, Callable
from .capabilities import Capabilities, ProtocolStatus


@dataclass
class HealthResult:
    """Result of a single health check invocation."""
    ok: bool
    rtt_ms: Optional[float] = None
    handshake_ms: Optional[float] = None
    error: Optional[str] = None
    detail: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "rtt_ms": self.rtt_ms,
            "handshake_ms": self.handshake_ms,
            "error": self.error,
            "detail": self.detail,
        }


@dataclass
class LinkResult:
    """Result of generate_link()."""
    ok: bool
    link: Optional[str] = None
    protocol: Optional[str] = None
    qr_text: Optional[str] = None  # text to encode as QR
    error: Optional[str] = None
    config: Optional[dict] = None  # extra client config (e.g. Clash YAML)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "link": self.link,
            "protocol": self.protocol,
            "qr_text": self.qr_text,
            "error": self.error,
            "config": self.config,
        }


@dataclass
class AdapterStatus:
    """Runtime status of an adapter."""
    enabled: bool = True
    started: bool = False  # has start() been called?
    last_started_at: Optional[float] = None
    last_stopped_at: Optional[float] = None
    last_health: Optional[HealthResult] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "started": self.started,
            "last_started_at": self.last_started_at,
            "last_stopped_at": self.last_stopped_at,
            "last_health": self.last_health.to_dict() if self.last_health else None,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
        }


class ProtocolAdapter(abc.ABC):
    """Abstract base for every protocol adapter.

    Implementations MUST:
      - report truthful Capabilities
      - validate_config() rejects invalid input
      - generate_link() works iff Capabilities.supports_link_generation
      - health_check() works iff Capabilities.supports_health_check
      - start()/stop() are idempotent
      - never log credentials, private keys, or auth tokens
    """

    # Subclasses override these as class attributes
    name: str = "base"
    version: str = "0.0.0"
    description: str = ""

    def __init__(self):
        self._status = AdapterStatus()

    # ── Identity ─────────────────────────────────────────────────────────
    @abc.abstractmethod
    def capabilities(self) -> Capabilities:
        """Return truthful capabilities. NEVER lie about a capability."""
        ...

    @property
    def status(self) -> AdapterStatus:
        return self._status

    # ── Configuration ────────────────────────────────────────────────────
    @abc.abstractmethod
    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        """Validate a configuration dict.
        Returns (ok, errors). Never raises — always returns a result.
        """
        ...

    @abc.abstractmethod
    def configure(self, config: dict) -> None:
        """Apply a configuration. May raise on invalid input."""
        ...

    # ── Link generation ──────────────────────────────────────────────────
    @abc.abstractmethod
    def generate_link(self, params: dict) -> LinkResult:
        """Generate a client share-link. Returns LinkResult; never raises."""
        ...

    # ── Health ───────────────────────────────────────────────────────────
    @abc.abstractmethod
    async def health_check(self) -> HealthResult:
        """Run a health check. Returns HealthResult; never raises."""
        ...

    # ── Lifecycle ───────────────────────────────────────────────────────
    @abc.abstractmethod
    async def start(self) -> bool:
        """Start the adapter (start accepting connections / open outbound).
        Idempotent — calling on an already-started adapter returns True.
        Returns True on success, False on failure.
        """
        ...

    @abc.abstractmethod
    async def stop(self) -> bool:
        """Stop the adapter. Idempotent. Returns True on success."""
        ...

    # ── Optional overrides ───────────────────────────────────────────────
    def generate_subscription(self, links: list[dict], fmt: str = "raw") -> Optional[str]:
        """Generate a subscription document. None if not supported."""
        return None

    def generate_client_config(self, params: dict) -> Optional[dict]:
        """Generate a client config (e.g. Clash YAML, sing-box JSON)."""
        return None

    # ── Public introspection ─────────────────────────────────────────────
    def to_dict(self) -> dict:
        """Public adapter info — NO secrets."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "capabilities": self.capabilities().to_dict(),
            "status": self._status.to_dict(),
        }
