# node_health.py — circuit breaker for outbound node requests (Phase 4.10)
#
# State machine:
#   HEALTHY → DEGRADED → OPEN → HALF_OPEN → HEALTHY
#
# Behavior:
#   - HEALTHY:    requests go through normally
#   - DEGRADED:   last attempt failed; upcoming requests still go through
#                 but failure counter is incremented. After N=threshold
#                 consecutive failures, transition to OPEN.
#   - OPEN:       requests are short-circuited immediately (no network call);
#                 they raise NodeUnavailableError. After cooldown elapses,
#                 transition to HALF_OPEN.
#   - HALF_OPEN:  exactly one probe request is allowed. On success → HEALTHY
#                 + counters reset. On failure → OPEN + cooldown restarted.
#
# This is per-node, in-memory, process-local. No shared state. No persistence.
# Safe under asyncio because each mutation is under the node's own lock.

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, TypeVar, Generic
from enum import Enum

logger = logging.getLogger("EMIX.node_health")

T = TypeVar("T")


class NodeState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class NodeUnavailableError(Exception):
    """Raised when the circuit breaker is OPEN for a node."""


@dataclass
class _NodeStats:
    state: NodeState = NodeState.HEALTHY
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_at: float = 0.0
    last_success_at: float = 0.0
    last_latency_ms: float = 0.0
    opened_at: float = 0.0  # when we entered OPEN state (for cooldown)
    total_calls: int = 0
    total_failures: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


class NodeCircuitBreaker:
    """Per-process registry of circuit breakers, keyed by node_id."""

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: int = 30,
        max_retries: int = 2,
        backoff_base_ms: int = 250,
    ):
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = max(1, cooldown_seconds)
        self.max_retries = max(0, max_retries)
        self.backoff_base_ms = max(0, backoff_base_ms)
        self._nodes: dict[str, _NodeStats] = {}

    def _get(self, node_id: str) -> _NodeStats:
        s = self._nodes.get(node_id)
        if s is None:
            s = _NodeStats()
            self._nodes[node_id] = s
        return s

    def get_state(self, node_id: str) -> NodeState:
        s = self._get(node_id)
        # Lazy transition OPEN → HALF_OPEN after cooldown
        if s.state == NodeState.OPEN:
            if time.time() - s.opened_at >= self.cooldown_seconds:
                s.state = NodeState.HALF_OPEN
        return s.state

    def get_status(self, node_id: str) -> dict:
        s = self._get(node_id)
        return {
            "node_id": node_id,
            "state": self.get_state(node_id).value,
            "consecutive_failures": s.consecutive_failures,
            "consecutive_successes": s.consecutive_successes,
            "last_failure_at": s.last_failure_at,
            "last_success_at": s.last_success_at,
            "last_latency_ms": s.last_latency_ms,
            "total_calls": s.total_calls,
            "total_failures": s.total_failures,
        }

    def all_status(self) -> list[dict]:
        out = []
        for nid in list(self._nodes.keys()):
            out.append(self.get_status(nid))
        return out

    async def call(
        self,
        node_id: str,
        operation: Callable[[], Awaitable[T]],
        *,
        timeout: Optional[float] = None,
    ) -> T:
        """Run an async operation through the breaker.

        - Raises NodeUnavailableError immediately if OPEN (after lazy cooldown check).
        - In HALF_OPEN, allows exactly one probe; on failure re-opens.
        - On unexpected exception: counts as failure; on success: resets counters.
        - Retry: bounded (max_retries) with exponential backoff (250ms → 500ms → 1s).
        """
        s = self._get(node_id)
        async with s._lock:
            current_state = self.get_state(node_id)
            if current_state == NodeState.OPEN:
                s.total_calls += 1
                raise NodeUnavailableError(
                    f"node {node_id} circuit is OPEN (cooldown {self.cooldown_seconds}s)"
                )
            s.total_calls += 1

        # Exponential backoff retry loop
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                t0 = time.monotonic()
                if timeout is not None:
                    result = await asyncio.wait_for(operation(), timeout=timeout)
                else:
                    result = await operation()
                latency_ms = (time.monotonic() - t0) * 1000
                await self._record_success(node_id, latency_ms)
                return result
            except asyncio.TimeoutError as exc:
                last_exc = exc
                await self._record_failure(node_id, exc)
            except NodeUnavailableError:
                raise  # don't retry circuit-open errors
            except Exception as exc:  # noqa: BLE001 — breaker needs to count all failures
                last_exc = exc
                await self._record_failure(node_id, exc)
            # backoff before next attempt
            if attempt < self.max_retries:
                delay_ms = self.backoff_base_ms * (2 ** attempt)
                await asyncio.sleep(delay_ms / 1000.0)
        # All retries exhausted — last_exc is set
        raise last_exc  # type: ignore[misc]

    async def _record_success(self, node_id: str, latency_ms: float):
        s = self._get(node_id)
        async with s._lock:
            s.consecutive_failures = 0
            s.consecutive_successes += 1
            s.last_success_at = time.time()
            s.last_latency_ms = latency_ms
            # Recovery path: HALF_OPEN → HEALTHY (one success is enough)
            if s.state in (NodeState.HALF_OPEN, NodeState.DEGRADED):
                s.state = NodeState.HEALTHY
                logger.info(
                    f"[circuit-breaker] node {node_id} recovered → HEALTHY "
                    f"(latency {latency_ms:.1f}ms)"
                )

    async def _record_failure(self, node_id: str, exc: Exception):
        s = self._get(node_id)
        async with s._lock:
            s.consecutive_failures += 1
            s.consecutive_successes = 0
            s.last_failure_at = time.time()
            s.total_failures += 1
            if s.state == NodeState.HALF_OPEN:
                # Probe failed — reopen with fresh cooldown
                s.state = NodeState.OPEN
                s.opened_at = time.time()
                logger.warning(
                    f"[circuit-breaker] node {node_id} probe failed → OPEN "
                    f"({type(exc).__name__}: {exc})"
                )
            elif s.consecutive_failures >= self.failure_threshold:
                s.state = NodeState.OPEN
                s.opened_at = time.time()
                logger.warning(
                    f"[circuit-breaker] node {node_id} → OPEN "
                    f"({s.consecutive_failures} consecutive failures)"
                )
            elif s.state == NodeState.HEALTHY:
                s.state = NodeState.DEGRADED
                logger.info(
                    f"[circuit-breaker] node {node_id} → DEGRADED "
                    f"({type(exc).__name__}: {exc})"
                )


# Singleton (process-local)
from config_layer import CONFIG as _EMIX_CFG

_breaker = NodeCircuitBreaker(
    failure_threshold=_EMIX_CFG.node_failure_threshold,
    cooldown_seconds=_EMIX_CFG.node_cooldown_seconds,
    max_retries=_EMIX_CFG.node_max_retries,
    backoff_base_ms=_EMIX_CFG.node_backoff_base_ms,
)


def get_breaker() -> NodeCircuitBreaker:
    """Get the process-wide circuit breaker singleton."""
    return _breaker


async def call_with_breaker(
    node_id: str,
    operation: Callable[[], Awaitable[T]],
    *,
    timeout: Optional[float] = None,
) -> T:
    """Convenience: run an operation through the global breaker."""
    return await _breaker.call(node_id, operation, timeout=timeout)
