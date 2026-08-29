# reverseproxy/loadbalancer.py — upstream selection strategies (Phase 33)
#
# Implements:
#   - round_robin
#   - weighted_round_robin
#   - least_connections
#   - latency_aware
#   - priority
# Avoids OPEN-circuit upstreams.

import threading
from typing import Optional, List
from .config import Upstream
from .health import get_upstream_health


class LoadBalancer:
    """Stateful load balancer for a single route."""

    def __init__(self, route_key: str, strategy: str = "round_robin"):
        self.route_key = route_key
        self.strategy = strategy
        self._lock = threading.Lock()
        self._rr_counter = 0  # round-robin index
        # Track in-flight connection counts (least_connections strategy)
        self._active_connections: dict[str, int] = {}  # upstream_url → count

    def _is_healthy(self, upstream: Upstream) -> bool:
        """Skip upstreams whose circuit is OPEN (cooldown not elapsed)."""
        h = get_upstream_health(self.route_key, upstream.url)
        return not h.is_open()

    def _inc_connections(self, url: str) -> None:
        with self._lock:
            self._active_connections[url] = self._active_connections.get(url, 0) + 1

    def _dec_connections(self, url: str) -> None:
        with self._lock:
            n = self._active_connections.get(url, 0)
            if n > 0:
                self._active_connections[url] = n - 1

    def select(self, upstreams: List[Upstream]) -> Optional[Upstream]:
        """Pick the next upstream. Returns None if no healthy candidates."""
        healthy = [u for u in upstreams if self._is_healthy(u)]
        if not healthy:
            return None
        with self._lock:
            if self.strategy == "round_robin":
                return self._round_robin(healthy)
            elif self.strategy == "weighted":
                return self._weighted(healthy)
            elif self.strategy == "least_connections":
                return self._least_connections(healthy)
            elif self.strategy == "latency_aware":
                return self._latency_aware(healthy)
            elif self.strategy == "priority":
                return self._priority(healthy)
            else:
                return self._round_robin(healthy)

    def _round_robin(self, healthy: List[Upstream]) -> Upstream:
        idx = self._rr_counter % len(healthy)
        self._rr_counter += 1
        return healthy[idx]

    def _weighted(self, healthy: List[Upstream]) -> Upstream:
        # Expand each upstream weight times, then round-robin
        # Simpler: weighted-random
        import random
        total_weight = sum(max(1, u.weight) for u in healthy)
        r = random.uniform(0, total_weight)
        cumulative = 0
        for u in healthy:
            cumulative += max(1, u.weight)
            if r <= cumulative:
                return u
        return healthy[-1]

    def _least_connections(self, healthy: List[Upstream]) -> Upstream:
        return min(healthy, key=lambda u: self._active_connections.get(u.url, 0))

    def _latency_aware(self, healthy: List[Upstream]) -> Upstream:
        def _lat(u: Upstream) -> float:
            h = get_upstream_health(self.route_key, u.url)
            return h.avg_latency_ms(300) or float("inf")
        return min(healthy, key=_lat)

    def _priority(self, healthy: List[Upstream]) -> Upstream:
        # Higher priority first; among same priority, use round_robin
        max_pri = max(u.priority for u in healthy)
        top_tier = [u for u in healthy if u.priority == max_pri]
        return self._round_robin(top_tier)

    def connection_opened(self, url: str) -> None:
        self._inc_connections(url)

    def connection_closed(self, url: str) -> None:
        self._dec_connections(url)


# Per-route-key singletons
_balancers: dict[str, LoadBalancer] = {}
_balancers_lock = threading.Lock()


def get_balancer(route_key: str, strategy: str = "round_robin") -> LoadBalancer:
    with _balancers_lock:
        b = _balancers.get(route_key)
        if b is None:
            b = LoadBalancer(route_key, strategy)
            _balancers[route_key] = b
        return b
