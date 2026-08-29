# reverseproxy/health.py — per-upstream health tracking (Phase 34)
#
# Reuses the node_health circuit-breaker pattern but at a finer granularity
# per route+upstream. Tracks: success rate, latency, last failure time.
# Health-check traffic is bounded — only one check per interval per upstream.

import time
import threading
from collections import deque
from dataclasses import dataclass
from typing import Optional
from .config import Upstream, get_proxy_config


@dataclass
class UpstreamSample:
    timestamp: float
    ok: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class UpstreamHealth:
    """Rolling-window health for one (route, upstream) pair."""

    def __init__(self, route_key: str, upstream_url: str, max_samples: int = 50):
        self.route_key = route_key
        self.upstream_url = upstream_url
        self._samples: deque[UpstreamSample] = deque(maxlen=max_samples)
        self._lock = threading.Lock()
        self.total_checks = 0
        self.total_successes = 0
        self.total_failures = 0
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.last_check_at: Optional[float] = None
        self.last_success_at: Optional[float] = None
        self.last_failure_at: Optional[float] = None
        self.last_latency_ms: Optional[float] = None
        # Circuit state: closed | open | half_open
        self.state: str = "closed"
        self.opened_at: Optional[float] = None

    def record(self, sample: UpstreamSample) -> None:
        with self._lock:
            self._samples.append(sample)
            self.total_checks += 1
            self.last_check_at = sample.timestamp
            if sample.ok:
                self.total_successes += 1
                self.consecutive_successes += 1
                self.consecutive_failures = 0
                self.last_success_at = sample.timestamp
                self.last_latency_ms = sample.latency_ms
                # If we were OPEN/HALF_OPEN, close the circuit
                if self.state != "closed":
                    self.state = "closed"
                    self.opened_at = None
            else:
                self.total_failures += 1
                self.consecutive_failures += 1
                self.consecutive_successes = 0
                self.last_failure_at = sample.timestamp
                # Open circuit after 3 consecutive failures
                cfg = get_proxy_config()
                threshold = 3
                if self.consecutive_failures >= threshold:
                    self.state = "open"
                    self.opened_at = sample.timestamp

    def is_open(self, cooldown_seconds: int = 30) -> bool:
        """Return True if circuit is OPEN (and cooldown not elapsed)."""
        if self.state != "open":
            return False
        if self.opened_at is None:
            return False
        if time.time() - self.opened_at >= cooldown_seconds:
            # Cooldown elapsed — half_open (allow one probe)
            self.state = "half_open"
            return False
        return True

    def success_rate(self, window_seconds: float = 300.0) -> float:
        with self._lock:
            now = time.time()
            recent = [s for s in self._samples if now - s.timestamp <= window_seconds]
            if not recent:
                return 0.0
            return sum(1 for s in recent if s.ok) / len(recent)

    def avg_latency_ms(self, window_seconds: float = 300.0) -> Optional[float]:
        with self._lock:
            now = time.time()
            lats = [s.latency_ms for s in self._samples
                    if s.ok and s.latency_ms is not None and now - s.timestamp <= window_seconds]
            if not lats:
                return None
            return sum(lats) / len(lats)

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "route_key": self.route_key,
                "upstream_url": self.upstream_url,
                "total_checks": self.total_checks,
                "total_successes": self.total_successes,
                "total_failures": self.total_failures,
                "consecutive_failures": self.consecutive_failures,
                "consecutive_successes": self.consecutive_successes,
                "last_check_at": self.last_check_at,
                "last_success_at": self.last_success_at,
                "last_failure_at": self.last_failure_at,
                "last_latency_ms": self.last_latency_ms,
                "success_rate_5min": self.success_rate(300),
                "avg_latency_ms_5min": self.avg_latency_ms(300),
                "state": self.state,
            }


# Process-local per (route_key, upstream_url) registry
_upstream_health: dict[tuple[str, str], UpstreamHealth] = {}
_registry_lock = threading.Lock()


def get_upstream_health(route_key: str, upstream_url: str) -> UpstreamHealth:
    """Get or create the UpstreamHealth for a (route, upstream) pair."""
    key = (route_key, upstream_url)
    with _registry_lock:
        h = _upstream_health.get(key)
        if h is None:
            h = UpstreamHealth(route_key, upstream_url)
            _upstream_health[key] = h
        return h


def all_upstream_health() -> dict:
    """Public snapshot of all upstream health (no secrets)."""
    with _registry_lock:
        return {f"{k[0]}|{k[1]}": v.to_dict() for k, v in _upstream_health.items()}
