# protocol_engine/fallback.py — automatic protocol fallback chain
#
# Primary → secondary → tertiary → next node
# Uses the node_health circuit breaker pattern for safety.

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Callable, Awaitable, TypeVar, Generic
from .registry import get_enabled_protocols, get_protocol
from . import selector as _selector
from . import metrics as _metrics

logger = logging.getLogger("EMIX.protocol_engine.fallback")

T = TypeVar("T")


@dataclass
class FallbackResult:
    """Result of a fallback chain execution."""
    ok: bool
    protocol_used: Optional[str] = None
    attempts: list[dict] = field(default_factory=list)  # [{protocol, ok, rtt_ms, error}]
    total_attempts: int = 0
    fallback_count: int = 0

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "protocol_used": self.protocol_used,
            "attempts": self.attempts,
            "total_attempts": self.total_attempts,
            "fallback_count": self.fallback_count,
        }


async def run_with_fallback(
    operation: Callable[[str], Awaitable[T]],
    *,
    profile_name: str = "stable",
    max_protocols: int = 3,
    max_retries_per_protocol: int = 1,
    backoff_base_ms: int = 250,
) -> FallbackResult:
    """Run an async operation across the top-N ranked protocols with fallback.

    For each protocol (in ranked order, up to max_protocols):
      - try up to (1 + max_retries_per_protocol) attempts
      - exponential backoff between attempts
      - on success: record metric, return FallbackResult(ok=True, protocol_used=name)
      - on failure: record metric, move to next protocol
    On all-fail: return FallbackResult(ok=False)
    """
    ranked = _selector.rank_protocols(profile_name)
    candidates = [c for c in ranked if c.get("score", 0) > 0 and "error" not in c][:max_protocols]
    result = FallbackResult(ok=False)
    for cand in candidates:
        proto_name = cand["name"]
        adapter = get_protocol(proto_name)
        if adapter is None:
            continue
        for attempt in range(max_retries_per_protocol + 1):
            result.total_attempts += 1
            t0 = time.monotonic()
            try:
                _metrics.get_metrics().record_connection_open(proto_name)
                out = await operation(proto_name)
                latency_ms = (time.monotonic() - t0) * 1000
                _metrics.get_metrics().record_connection_close(
                    proto_name, failed=False, bytes_in=0, bytes_out=0
                )
                result.attempts.append({
                    "protocol": proto_name,
                    "attempt": attempt + 1,
                    "ok": True,
                    "latency_ms": round(latency_ms, 2),
                })
                result.ok = True
                result.protocol_used = proto_name
                return result
            except Exception as exc:
                _metrics.get_metrics().record_connection_close(proto_name, failed=True)
                result.attempts.append({
                    "protocol": proto_name,
                    "attempt": attempt + 1,
                    "ok": False,
                    "error": f"{type(exc).__name__}: {str(exc)[:120]}",
                })
                if attempt < max_retries_per_protocol:
                    delay_ms = backoff_base_ms * (2 ** attempt)
                    await asyncio.sleep(delay_ms / 1000.0)
        # All attempts for this protocol failed → fallback to next
        if cand is not candidates[-1]:
            result.fallback_count += 1
            _metrics.get_metrics().record_fallback(proto_name)
            logger.info(f"[fallback] {proto_name} exhausted → trying next")
    return result
