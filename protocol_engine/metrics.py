# protocol_engine/metrics.py — runtime per-protocol counters + I/O bytes
#
# Light-weight counters that don't require an external metrics backend.
# Exposed via /api/protocols and /api/health.

import threading
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class ProtocolCounters:
    connections_total: int = 0
    connections_failed: int = 0
    active_connections: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    fallback_total: int = 0
    health_status: str = "unknown"  # 'healthy', 'degraded', 'down', 'unknown'

    def to_dict(self) -> dict:
        return {
            "connections_total": self.connections_total,
            "connections_failed": self.connections_failed,
            "active_connections": self.active_connections,
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
            "fallback_total": self.fallback_total,
            "health_status": self.health_status,
        }


class MetricsCollector:
    """Per-protocol runtime counters. Thread-safe (GIL-protected)."""

    def __init__(self):
        self._counters: dict[str, ProtocolCounters] = defaultdict(ProtocolCounters)
        self._lock = threading.Lock()

    def record_connection_open(self, protocol: str) -> None:
        with self._lock:
            c = self._counters[protocol]
            c.connections_total += 1
            c.active_connections += 1

    def record_connection_close(self, protocol: str, failed: bool = False, bytes_in: int = 0, bytes_out: int = 0) -> None:
        with self._lock:
            c = self._counters[protocol]
            c.active_connections = max(0, c.active_connections - 1)
            if failed:
                c.connections_failed += 1
            c.bytes_in += bytes_in
            c.bytes_out += bytes_out

    def record_fallback(self, protocol: str) -> None:
        with self._lock:
            self._counters[protocol].fallback_total += 1

    def set_health_status(self, protocol: str, status: str) -> None:
        with self._lock:
            self._counters[protocol].health_status = status

    def get(self, protocol: str) -> ProtocolCounters:
        return self._counters.get(protocol, ProtocolCounters())

    def all(self) -> dict[str, dict]:
        with self._lock:
            return {name: c.to_dict() for name, c in self._counters.items()}

    def reset(self, protocol: str = None) -> None:
        with self._lock:
            if protocol:
                self._counters.pop(protocol, None)
            else:
                self._counters.clear()


# Singleton
_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    return _metrics
