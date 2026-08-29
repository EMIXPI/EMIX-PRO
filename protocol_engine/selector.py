# protocol_engine/selector.py — smart protocol selection
#
# Scores enabled protocols based on rolling metrics and user preferences.
# NO hard-coded "best protocol for X" — the system measures the actual network.
#
# Score = w_reliability * success_rate
#       + w_latency    * normalized_latency
#       + w_throughput * normalized_throughput
#       + w_availability * availability_flag
#
# All weights configurable via EMIX_SELECTOR_* env vars.

import os
import time
from dataclasses import dataclass, field
from typing import Optional, List
from . import health as _health
from .capabilities import Capabilities, ProtocolStatus, Transport
from .registry import get_enabled_protocols


def _env_float(name: str, default: float) -> float:
    v = os.environ.get(name)
    if not v:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class SelectorWeights:
    reliability: float = field(default_factory=lambda: _env_float("EMIX_SELECTOR_W_RELIABILITY", 0.40))
    latency: float = field(default_factory=lambda: _env_float("EMIX_SELECTOR_W_LATENCY", 0.25))
    throughput: float = field(default_factory=lambda: _env_float("EMIX_SELECTOR_W_THROUGHPUT", 0.15))
    availability: float = field(default_factory=lambda: _env_float("EMIX_SELECTOR_W_AVAILABILITY", 0.20))


# Network profile → preference hints. These are NOT hard requirements.
# The selector still applies metrics; profiles only bias the scoring.
NETWORK_PROFILES = {
    "mobile": {
        # Mobile networks often have higher packet loss → favor TCP
        "prefer_transports": ["tcp", "ws"],
        "avoid_transports": ["quic", "http3"],  # QUIC may be flaky on mobile
        "prefer_ipv": "ipv4",
        "conservative_timeouts": True,
    },
    "stable": {
        "prefer_transports": [],
        "avoid_transports": [],
        "prefer_ipv": "either",
        "conservative_timeouts": False,
    },
    "high_latency": {
        # Favor transports that tolerate loss well
        "prefer_transports": ["ws", "xhttp"],
        "avoid_transports": [],
        "prefer_ipv": "either",
        "conservative_timeouts": True,
    },
    "udp_friendly": {
        "prefer_transports": ["quic", "udp"],
        "avoid_transports": [],
        "prefer_ipv": "either",
        "conservative_timeouts": False,
    },
    "restricted": {
        # Use only transports with a successful recent health record
        "prefer_transports": [],
        "avoid_transports": [],
        "prefer_ipv": "either",
        "conservative_timeouts": True,
        "require_recent_success": True,
    },
}


def get_profile(name: str) -> dict:
    """Return the named network profile (or 'stable' fallback)."""
    return NETWORK_PROFILES.get(name, NETWORK_PROFILES["stable"])


def list_profiles() -> list[str]:
    return list(NETWORK_PROFILES.keys())


def _normalize_latency(avg_rtt_ms: Optional[float]) -> float:
    """Map RTT (ms) → 0..1 score. 0ms=1.0, 500ms=0.0, linear in between."""
    if avg_rtt_ms is None:
        return 0.0  # no data → neutral
    if avg_rtt_ms <= 0:
        return 1.0
    if avg_rtt_ms >= 500:
        return 0.0
    return 1.0 - (avg_rtt_ms / 500.0)


def _normalize_throughput(bytes_in_window: int) -> float:
    """Map bytes transferred in last window → 0..1. 0 bytes=0.0, 10MB+=1.0."""
    if bytes_in_window <= 0:
        return 0.0
    if bytes_in_window >= 10 * 1024 * 1024:
        return 1.0
    return bytes_in_window / (10 * 1024 * 1024)


def _transport_score(adapter_caps: Capabilities, profile: dict) -> float:
    """Bonus/penalty for transport match with profile preferences."""
    score = 0.0
    prefer = profile.get("prefer_transports", [])
    avoid = profile.get("avoid_transports", [])
    adapter_transports = {t.value for t in adapter_caps.transports}
    for t in prefer:
        if t in adapter_transports:
            score += 0.1
    for t in avoid:
        if t in adapter_transports:
            score -= 0.1
    # IPv preference
    prefer_ipv = profile.get("prefer_ipv", "either")
    if prefer_ipv == "ipv4" and adapter_caps.supports_ipv4 and not adapter_caps.supports_ipv6:
        score += 0.05
    elif prefer_ipv == "ipv6" and adapter_caps.supports_ipv6 and not adapter_caps.supports_ipv4:
        score += 0.05
    return score


def score_protocol(name: str, weights: SelectorWeights = None, profile_name: str = "stable") -> dict:
    """Compute a 0..1 score for a single protocol.
    Returns {score, success_rate, avg_rtt_ms, ...}"""
    weights = weights or SelectorWeights()
    profile = get_profile(profile_name)
    adapter = next((a for a in get_enabled_protocols() if a.name == name), None)
    if adapter is None:
        return {"name": name, "score": 0.0, "error": "not registered or disabled"}
    caps = adapter.capabilities()
    if caps.status in (ProtocolStatus.DEFERRED, ProtocolStatus.UNAVAILABLE):
        return {"name": name, "score": 0.0, "status": caps.status.value, "error": "deferred/unavailable"}
    h = _health.get_health(name)
    success_rate = h.success_rate(300)
    avg_rtt = h.avg_rtt_ms(300)
    lat_score = _normalize_latency(avg_rtt)
    # throughput proxy: total bytes_in over the last window (use metrics)
    from .metrics import get_metrics
    m = get_metrics().get(name)
    throughput_score = _normalize_throughput(m.bytes_in)
    # availability: did the protocol have at least one successful check?
    availability = 1.0 if h.total_successes > 0 else 0.0
    # profile bonus
    profile_bonus = _transport_score(caps, profile)
    # require_recent_success (for 'restricted' profile)
    if profile.get("require_recent_success") and h.consecutive_successes == 0:
        return {"name": name, "score": 0.0, "error": "no recent success"}
    score = (
        weights.reliability * success_rate
        + weights.latency * lat_score
        + weights.throughput * throughput_score
        + weights.availability * availability
        + profile_bonus
    )
    # Clamp to 0..1.1 (profile bonus can push slightly above 1.0)
    score = max(0.0, min(1.1, score))
    return {
        "name": name,
        "score": round(score, 4),
        "success_rate": round(success_rate, 4),
        "avg_rtt_ms": round(avg_rtt, 2) if avg_rtt else None,
        "p95_rtt_ms": h.p95_rtt_ms(300),
        "throughput_bytes": m.bytes_in,
        "active_connections": m.active_connections,
        "consecutive_failures": h.consecutive_failures,
        "consecutive_successes": h.consecutive_successes,
        "status": caps.status.value,
    }


def select_best(profile_name: str = "stable", weights: SelectorWeights = None) -> Optional[dict]:
    """Return the highest-scoring enabled protocol, or None if no candidates."""
    candidates = [score_protocol(a.name, weights, profile_name)
                  for a in get_enabled_protocols()]
    # Filter out zero-score or errored candidates
    candidates = [c for c in candidates if c.get("score", 0) > 0 and "error" not in c]
    if not candidates:
        return None
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[0]


def rank_protocols(profile_name: str = "stable", weights: SelectorWeights = None) -> list[dict]:
    """Return all enabled protocols ranked by score (best first)."""
    candidates = [score_protocol(a.name, weights, profile_name)
                  for a in get_enabled_protocols()]
    candidates.sort(key=lambda c: c.get("score", 0), reverse=True)
    return candidates
