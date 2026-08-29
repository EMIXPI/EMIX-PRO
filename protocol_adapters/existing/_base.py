# protocol_adapters/existing/_base.py — common base for existing-protocol adapters
#
# Existing protocols already have working code. The adapter just exposes
# their state through the ProtocolAdapter interface — it does NOT replace
# any relay logic. All operations are read-only introspection OR
# delegation to existing endpoints.

from protocol_engine import ProtocolAdapter, Capabilities, Transport, ProtocolStatus
from protocol_engine.base import HealthResult, LinkResult


class ExistingAdapterBase(ProtocolAdapter):
    """Base class for adapters that wrap EXISTING production protocols.

    Subclasses override:
      - name, version, description (class attrs)
      - capabilities() → return truthful Capabilities
      - validate_config() / configure() — usually accept any dict (existing code already validates)
      - generate_link() — delegate to existing link generators (link_emit.py / main.generate_share_link)
      - health_check() — call the existing /api/links/{uuid}/ping path via local import
      - start()/stop() — usually no-ops (existing protocols are always started via main.py routes)
    """

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        # Existing protocols don't take per-adapter configuration through this
        # interface — link creation goes through /api/links. So accept anything.
        return True, []

    def configure(self, config: dict) -> None:
        # No-op — existing protocols are configured via the existing API endpoints.
        pass

    async def start(self) -> bool:
        # Existing protocols are started automatically by main.py's startup().
        # Mark our status as started to reflect reality.
        import time
        self._status.started = True
        self._status.last_started_at = time.time()
        return True

    async def stop(self) -> bool:
        # We don't actually stop the existing protocol — that would break the
        # panel. Just record the (notional) stop.
        import time
        self._status.started = False
        self._status.last_stopped_at = time.time()
        return True
