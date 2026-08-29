# protocol_engine/health.py — per-protocol health state + rolling metrics
#
# Maintains per-protocol rolling metrics for the smart selector.
# All counters are bounded (rolling window).

import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Sample:
    """A single health-check sample."""
    timestamp: float
    ok: bool
    rtt_ms: Optional[float] = None
    handshake_ms: Optional[float] = None
    error: Optional[str] = None


class RollingHealth:
    """Rolling window of health samples for one protocol.
    Bounded memory (deque maxlen). Thread-safe via a single GIL-protected lock
    — we don't need asyncio.Lock here because the operations are O(1) dict/deque
    updates that complete in microseconds."""

    def __init__(self, max_samples: int = 50):
        self._samples: deque[Sample] = deque(maxlen=max_samples)
        self._lock = threading.Lock()
        # Aggregated counters (not just samples)
        self.total_checks = 0
        self.total_successes = 0
        self.total_failures = 0
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.last_success_at: Optional[float] = None
        self.last_failure_at: Optional[float] = None
        self.last_rtt_ms: Optional[float] = None
        self.last_handshake_ms: Optional[float] = None

    def record(self, sample: Sample) -> None:
        with self._lock:
            self._samples.append(sample)
            self.total_checks += 1
            if sample.ok:
                self.total_successes += 1
                self.consecutive_successes += 1
                self.consecutive_failures = 0
                self.last_success_at = sample.timestamp
                self.last_rtt_ms = sample.rtt_ms
                self.last_handshake_ms = sample.handshake_ms
            else:
                self.total_failures += 1
                self.consecutive_failures += 1
                self.consecutive_successes = 0
                self.last_failure_at = sample.timestamp

    def success_rate(self, window_seconds: float = 300.0) -> float:
        """Success rate over the last N seconds. Returns 0..1."""
        with self._lock:
            now = time.time()
            recent = [s for s in self._samples if now - s.timestamp <= window_seconds]
            if not recent:
                return 0.0
            return sum(1 for s in recent if s.ok) / len(recent)

    def avg_rtt_ms(self, window_seconds: float = 300.0) -> Optional[float]:
        """Average RTT over the last N seconds (only successful samples)."""
        with self._lock:
            now = time.time()
            recent_rtts = [
                s.rtt_ms for s in self._samples
                if s.ok and s.rtt_ms is not None and now - s.timestamp <= window_seconds
            ]
            if not recent_rtts:
                return None
            return sum(recent_rtts) / len(recent_rtts)

    def p95_rtt_ms(self, window_seconds: float = 300.0) -> Optional[float]:
        """95th percentile RTT over the last N seconds."""
        with self._lock:
            now = time.time()
            recent_rtts = sorted(
                s.rtt_ms for s in self._samples
                if s.ok and s.rtt_ms is not None and now - s.timestamp <= window_seconds
            )
            if not recent_rtts:
                return None
            idx = max(0, int(len(recent_rtts) * 0.95) - 1)
            return recent_rtts[idx]

    def failure_rate(self, window_seconds: float = 300.0) -> float:
        return 1.0 - self.success_rate(window_seconds)

    def to_dict(self) -> dict:
        return {
            "total_checks": self.total_checks,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "last_success_at": self.last_success_at,
            "last_failure_at": self.last_failure_at,
            "last_rtt_ms": self.last_rtt_ms,
            "last_handshake_ms": self.last_handshake_ms,
            "success_rate_5min": self.success_rate(300),
            "avg_rtt_ms_5min": self.avg_rtt_ms(300),
            "p95_rtt_ms_5min": self.p95_rtt_ms(300),
        }


# Process-local per-protocol health registry
_health_registry: dict[str, RollingHealth] = {}


def get_health(name: str) -> RollingHealth:
    """Get or create a RollingHealth for the given protocol name."""
    h = _health_registry.get(name)
    if h is None:
        h = RollingHealth()
        _health_registry[name] = h
    return h


def all_health() -> dict[str, dict]:
    """Public snapshot of all protocol health — NO secrets."""
    return {name: get_health(name).to_dict() for name in _health_registry}
