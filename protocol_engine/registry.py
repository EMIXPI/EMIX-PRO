# protocol_engine/registry.py — protocol registry
#
# register_protocol() — add an adapter
# unregister_protocol() — remove
# get_protocol() — fetch one
# list_protocols() — list all
# get_enabled_protocols() — list only enabled
# get_protocol_capabilities() — fetch Capabilities for a name
#
# Rules:
#   - duplicate registration → rejected (ValueError)
#   - invalid adapters → rejected
#   - a broken optional adapter MUST NOT prevent EMIX from starting
#     (registrations are wrapped in try/except)

import logging
from typing import Optional, Dict, List
from .base import ProtocolAdapter, AdapterStatus
from .capabilities import Capabilities, ProtocolStatus

logger = logging.getLogger("EMIX.protocol_engine")


class ProtocolRegistry:
    """Process-local registry of protocol adapters."""

    def __init__(self):
        self._adapters: Dict[str, ProtocolAdapter] = {}
        self._lock_order: List[str] = []  # tracks registration order for list_protocols()

    def register_protocol(self, adapter: ProtocolAdapter) -> None:
        """Register an adapter. Raises ValueError on duplicate name."""
        name = getattr(adapter, "name", None)
        if not name or not isinstance(name, str):
            raise ValueError("adapter must have a non-empty string 'name' attribute")
        if name in self._adapters:
            raise ValueError(f"protocol already registered: {name}")
        if not isinstance(adapter, ProtocolAdapter):
            raise ValueError(f"adapter for {name!r} is not a ProtocolAdapter instance")
        self._adapters[name] = adapter
        self._lock_order.append(name)
        logger.info(f"[protocol-registry] registered: {name} ({adapter.version})")

    def unregister_protocol(self, name: str) -> bool:
        """Remove an adapter. Returns True if removed, False if not present."""
        if name in self._adapters:
            del self._adapters[name]
            self._lock_order.remove(name)
            return True
        return False

    def get_protocol(self, name: str) -> Optional[ProtocolAdapter]:
        return self._adapters.get(name)

    def list_protocols(self) -> List[ProtocolAdapter]:
        """Return all registered adapters in registration order."""
        return [self._adapters[n] for n in self._lock_order if n in self._adapters]

    def list_protocol_names(self) -> List[str]:
        return list(self._lock_order)

    def get_enabled_protocols(self) -> List[ProtocolAdapter]:
        """Return adapters that are admin-enabled AND can actually serve.
        Excludes DEFERRED and UNAVAILABLE adapters (they can't function)."""
        return [
            a for a in self.list_protocols()
            if a.status.enabled
            and a.capabilities().status not in (ProtocolStatus.DEFERRED, ProtocolStatus.UNAVAILABLE)
        ]

    def get_protocol_capabilities(self, name: str) -> Optional[Capabilities]:
        a = self._adapters.get(name)
        return a.capabilities() if a else None

    def safe_register(self, adapter_factory) -> bool:
        """Register an adapter, swallowing any startup error.
        adapter_factory: a callable that returns a ProtocolAdapter instance.
        Returns True on success, False on failure.
        A failure is logged but does NOT propagate — EMIX keeps starting."""
        try:
            adapter = adapter_factory()
            self.register_protocol(adapter)
            return True
        except Exception as exc:
            logger.warning(
                f"[protocol-registry] failed to register adapter: {type(exc).__name__}: {exc}"
            )
            return False

    def to_dict(self) -> dict:
        """Public registry view — NO secrets."""
        return {
            "protocols": [a.to_dict() for a in self.list_protocols()],
            "count": len(self._adapters),
            "enabled_count": len(self.get_enabled_protocols()),
        }


# Process-local singleton
_registry = ProtocolRegistry()


def get_registry() -> ProtocolRegistry:
    """Get the process-wide protocol registry singleton."""
    return _registry


# Convenience top-level functions
def register_protocol(adapter: ProtocolAdapter) -> None:
    _registry.register_protocol(adapter)


def unregister_protocol(name: str) -> bool:
    return _registry.unregister_protocol(name)


def list_protocol_names() -> List[str]:
    return _registry.list_protocol_names()


def get_protocol(name: str) -> Optional[ProtocolAdapter]:
    return _registry.get_protocol(name)


def list_protocols() -> List[ProtocolAdapter]:
    return _registry.list_protocols()


def get_enabled_protocols() -> List[ProtocolAdapter]:
    return _registry.get_enabled_protocols()


def get_protocol_capabilities(name: str) -> Optional[Capabilities]:
    return _registry.get_protocol_capabilities(name)
