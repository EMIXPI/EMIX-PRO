# config_lifecycle.py — Config Lifecycle Engine (Phase 37.11)
#
# A configuration is a STATEFUL object, not a static string:
#
#   CREATED ─► VALIDATING ─► HEALTHY ⇄ DEGRADED ─► FAILED
#                                │
#                                ├─► EXPIRED    (time window elapsed)
#                                └─► REVOKED    (disabled by admin / quota cut)
#
# Rules:
#   * HEALTHY is never permanent — health evidence expires (network_health
#     TTL). An expired-health config reports VALIDATING again (unknown until
#     revalidated), which is derived, never stored.
#   * Policy states (EXPIRED / REVOKED) are derived from the link record
#     itself (expires_at / active / quota), so they are always current.
#   * derive_lifecycle() is a PURE function of (link, health) — deterministic,
#     unit-testable, and identical across restarts.
#
# The legacy `health.state` field (network_health engine) remains the network
# truth; this module is the user-facing lifecycle interpretation layer.

from __future__ import annotations
import time
from datetime import datetime
from typing import Optional, Tuple

LIFECYCLE_STATES = (
    "CREATED",      # compiled + stored, never probed yet
    "VALIDATING",   # probe requested / health evidence expired (re-check due)
    "HEALTHY",      # probe evidence fresh + good
    "DEGRADED",     # probe evidence fresh but below bar (loss / latency / flaky)
    "FAILED",       # probe evidence fresh and negative (unreachable)
    "EXPIRED",      # time window elapsed (link policy)
    "REVOKED",      # disabled / quota exhausted (link policy)
)

# How long a stored link stays in CREATED before it is considered stale
# (never probed at all). Informational only.
CREATED_STALE_S = 24 * 3600.0


def _parse_ts(value) -> Optional[float]:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except Exception:
        return None


def _is_expired_link(link: dict, now: float) -> bool:
    exp = _parse_ts(link.get("expires_at"))
    return exp is not None and now >= exp


def _quota_exhausted(link: dict) -> bool:
    lb = link.get("limit_bytes") or 0
    return lb > 0 and (link.get("used_bytes") or 0) >= lb


def derive_lifecycle(link: dict, health: Optional[dict], now: Optional[float] = None,
                     health_ttl: Optional[float] = None) -> Tuple[str, str]:
    """Derive the lifecycle state of a config. PURE — (state, reason).

    health — the dict from network_health.get_health_dict(uid) or
             link.get("health"); None when never probed.
    """
    now = time.time() if now is None else now
    if link is None:
        return "REVOKED", "link record missing"

    # ── policy layers first (they override network evidence) ──
    if not link.get("active", True):
        return "REVOKED", "disabled by operator"
    if _quota_exhausted(link):
        return "REVOKED", "quota exhausted"
    if _is_expired_link(link, now):
        return "EXPIRED", "expiry window elapsed"

    if not health:
        return "VALIDATING", "no probe evidence yet"

    state = health.get("state") or health.get("effective_state") or "UNKNOWN"
    checked_ts = health.get("checked_ts") or _parse_ts(health.get("checked_at"))
    ttl = health_ttl
    if ttl is None:
        # use the engine default when not overridden
        try:
            from network_health import HEALTH_TTL_SECONDS as _ttl
            ttl = _ttl
        except Exception:
            ttl = 900.0

    # ── health expiry: stale evidence is UNKNOWN, not healthy (37.11) ──
    if state in ("HEALTHY", "DEGRADED", "UNREACHABLE"):
        if checked_ts is None or (now - checked_ts) > ttl:
            return "VALIDATING", "health evidence expired — revalidation due"

    if state == "INVALID":
        return "REVOKED", health.get("error") or "marked invalid"
    if state == "UNREACHABLE":
        return "FAILED", health.get("error") or "probe failed"
    if state == "DEGRADED":
        return "DEGRADED", "below health bar (loss / latency / flakiness)"
    if state == "HEALTHY":
        return "HEALTHY", "fresh probe evidence"
    return "VALIDATING", "state unknown — awaiting probe"


def lifecycle_annotation(uid: str, link: dict, health: Optional[dict]) -> dict:
    """Machine-readable lifecycle block attached to link records / API rows."""
    state, reason = derive_lifecycle(link, health)
    return {
        "uid": uid,
        "lifecycle_state": state,
        "lifecycle_reason": reason,
        "health_checked_at": (health or {}).get("checked_at"),
        "health_expires_at": (health or {}).get("health_expires_at"),
    }
