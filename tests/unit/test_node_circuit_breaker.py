"""Unit tests for node_health circuit breaker (Phase 4.10).

Covers:
  - successful call → HEALTHY stays
  - failure → DEGRADED then OPEN after threshold
  - OPEN short-circuits (raises NodeUnavailableError)
  - cooldown elapses → HALF_OPEN → success → HEALTHY
  - HALF_OPEN → failure → OPEN
  - bounded retries
  - state inspection via all_status()
"""
import asyncio
import time
import pytest

from node_health import (
    NodeCircuitBreaker,
    NodeState,
    NodeUnavailableError,
)


def _breaker(**kwargs):
    """Construct a breaker with low thresholds for fast tests."""
    defaults = {
        "failure_threshold": 3,
        "cooldown_seconds": 1,  # short for tests
        "max_retries": 1,
        "backoff_base_ms": 10,
    }
    defaults.update(kwargs)
    return NodeCircuitBreaker(**defaults)


def test_successful_call_stays_healthy():
    async def run():
        b = _breaker()
        async def op():
            return "ok"
        result = await b.call("node-1", op)
        assert result == "ok"
        assert b.get_state("node-1") == NodeState.HEALTHY
        status = b.get_status("node-1")
        assert status["consecutive_successes"] == 1
        assert status["total_calls"] == 1
    asyncio.run(run())


def test_failure_transitions_to_degraded_then_open():
    async def run():
        b = _breaker(failure_threshold=3)
        async def op():
            raise RuntimeError("boom")
        # First failure → DEGRADED
        with pytest.raises(RuntimeError):
            await b.call("node-1", op)
        assert b.get_state("node-1") == NodeState.DEGRADED
        # Second failure → DEGRADED (still under threshold)
        with pytest.raises(RuntimeError):
            await b.call("node-1", op)
        assert b.get_state("node-1") == NodeState.DEGRADED
        assert b.get_status("node-1")["consecutive_failures"] == 2
        # Third failure → OPEN
        with pytest.raises(RuntimeError):
            await b.call("node-1", op)
        assert b.get_state("node-1") == NodeState.OPEN
    asyncio.run(run())


def test_open_short_circuits_without_calling_operation():
    async def run():
        # max_retries=0 to ensure op is called exactly once per call()
        b = _breaker(failure_threshold=1, max_retries=0)
        call_count = 0
        async def op():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("always fails")
        # First call fails, opens the circuit (threshold=1)
        with pytest.raises(RuntimeError):
            await b.call("node-1", op)
        assert call_count == 1  # one attempt (max_retries=0)
        # Second call: short-circuits without calling op
        with pytest.raises(NodeUnavailableError):
            await b.call("node-1", op)
        assert call_count == 1  # op was NOT called the second time
    asyncio.run(run())


def test_cooldown_to_half_open_then_success_recovers():
    async def run():
        b = _breaker(failure_threshold=1, cooldown_seconds=1, max_retries=0)
        async def failing_op():
            raise RuntimeError("fail")
        async def success_op():
            return "recovered"
        # Open the circuit
        with pytest.raises(RuntimeError):
            await b.call("node-1", failing_op)
        assert b.get_state("node-1") == NodeState.OPEN
        # Wait for cooldown
        await asyncio.sleep(1.1)
        # Now state should lazily transition to HALF_OPEN
        assert b.get_state("node-1") == NodeState.HALF_OPEN
        # Successful probe → HEALTHY
        result = await b.call("node-1", success_op)
        assert result == "recovered"
        assert b.get_state("node-1") == NodeState.HEALTHY
        assert b.get_status("node-1")["consecutive_failures"] == 0
    asyncio.run(run())


def test_half_open_failure_reopens():
    async def run():
        b = _breaker(failure_threshold=1, cooldown_seconds=1, max_retries=0)
        async def failing_op():
            raise RuntimeError("still failing")
        # Open
        with pytest.raises(RuntimeError):
            await b.call("node-1", failing_op)
        # Wait for cooldown
        await asyncio.sleep(1.1)
        assert b.get_state("node-1") == NodeState.HALF_OPEN
        # Probe fails → OPEN again
        with pytest.raises(RuntimeError):
            await b.call("node-1", failing_op)
        assert b.get_state("node-1") == NodeState.OPEN
    asyncio.run(run())


def test_bounded_retries():
    async def run():
        b = _breaker(max_retries=2, backoff_base_ms=10)
        call_count = 0
        async def op():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("always fails")
        with pytest.raises(RuntimeError):
            await b.call("node-1", op)
        # max_retries=2 → 3 total attempts (initial + 2 retries)
        assert call_count == 3
    asyncio.run(run())


def test_timeout_counts_as_failure():
    """A timeout is counted as a failure (not retried into oblivion).
    With failure_threshold=2, a single timeout transitions to DEGRADED."""
    async def run():
        b = _breaker(max_retries=0, failure_threshold=2)
        async def slow_op():
            await asyncio.sleep(0.5)
            return "ok"
        with pytest.raises(asyncio.TimeoutError):
            await b.call("node-1", slow_op, timeout=0.05)
        # One timeout → one failure → DEGRADED (under threshold of 2)
        assert b.get_state("node-1") == NodeState.DEGRADED
    asyncio.run(run())


def test_all_status_returns_per_node_info():
    async def run():
        b = _breaker(failure_threshold=1, max_retries=0)
        async def op_a():
            return "ok"
        async def op_b_fails():
            raise RuntimeError("nope")
        await b.call("a", op_a)
        with pytest.raises(RuntimeError):
            await b.call("b", op_b_fails)
        statuses = b.all_status()
        assert isinstance(statuses, list)
        assert len(statuses) == 2
        node_ids = {s["node_id"] for s in statuses}
        assert node_ids == {"a", "b"}
    asyncio.run(run())


def test_independent_nodes_dont_affect_each_other():
    async def run():
        b = _breaker(failure_threshold=1, max_retries=0)
        async def op_a_ok():
            return "ok"
        async def op_b_fails():
            raise RuntimeError("b fails")
        with pytest.raises(RuntimeError):
            await b.call("b", op_b_fails)
        assert b.get_state("b") == NodeState.OPEN
        # Node a should still be HEALTHY
        result = await b.call("a", op_a_ok)
        assert result == "ok"
        assert b.get_state("a") == NodeState.HEALTHY
    asyncio.run(run())
