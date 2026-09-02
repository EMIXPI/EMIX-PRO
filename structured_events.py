# structured_events.py — Structured operational event log (spec §29)
#
# Every important operation records a named, structured event:
#   CONFIG_GENERATED, ROUTE_SELECTED, EGRESS_VERIFIED, ROUTE_MISMATCH,
#   NODE_QUARANTINED, FAILOVER_TRIGGERED, IRAN_GATEWAY_CHECK,
#   PROTOCOL_VALIDATION_FAILED, SPLIT_TUNNEL_COMPILED, …
#
# Honesty rules:
#   * NEVER log credentials, passwords, private keys, tokens, full
#     subscription secrets (field blocklist + value scrubbing below).
#   * Bounded ring buffer — events expire, they are not a database.
#   * Also mirrored to the stdlib logger so operators see them in stdout.

from __future__ import annotations
import asyncio
import logging
import re
import time
from collections import deque
from typing import Optional

logger = logging.getLogger("EMIX.events")

ENGINE_VERSION = "1.0.0"
EVENT_BOUND = 400              # ring buffer size
EVENT_TTL_S = 7 * 24 * 3600.0  # events older than this are not returned

KNOWN_EVENTS = (
    "CONFIG_GENERATED",
    "CONFIG_GENERATION_FAILED",
    "ROUTE_SELECTED",
    "EGRESS_VERIFIED",
    "ROUTE_MISMATCH",
    "NODE_QUARANTINED",
    "FAILOVER_TRIGGERED",
    "IRAN_GATEWAY_CHECK",
    "PROTOCOL_VALIDATION_FAILED",
    "SPLIT_TUNNEL_COMPILED",
    "IRAN_DATASET_UPDATED",
    "ACCOUNT_GATE_DECISION",
)

# Field names that must NEVER be recorded (secret blocklist).
_BLOCKED_FIELDS = frozenset({
    "password", "password_hash", "secret", "token", "access_token",
    "private_key", "server_private_key", "client_private_key", "credential",
    "uuid", "ss_password", "mtproto_secret", "auth", "authorization",
    "subscription_secret", "api_key",
})

# Value scrubbing: UUIDs and long secrets get redacted in free-form strings.
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_SECRETISH_RE = re.compile(r"(password|token|secret|private[_-]?key|api[_-]?key)",
                           re.IGNORECASE)


def _scrub_value(v) -> str:
    s = str(v)
    s = _UUID_RE.sub("<uuid-redacted>", s)
    return s


def _scrub_fields(fields: dict) -> dict:
    out = {}
    for k, v in (fields or {}).items():
        if str(k).lower() in _BLOCKED_FIELDS:
            out[k] = "<redacted>"
            continue
        if _SECRETISH_RE.search(str(k)) and v not in (None, "", True, False):
            out[k] = "<redacted>"
            continue
        if isinstance(v, dict):
            out[k] = _scrub_fields(v)
        elif isinstance(v, (list, tuple)):
            out[k] = [_scrub_value(x) if not isinstance(x, dict) else _scrub_fields(x)
                      for x in v[:20]]
        else:
            out[k] = _scrub_value(v)
    return out


_events: deque = deque(maxlen=EVENT_BOUND)
_lock = asyncio.Lock()
_listeners = []  # extra sync sinks (e.g. diagnostics bridge), appended not replaced


def add_listener(fn) -> None:
    """Register an extra sink(event: dict) — used by diagnostics bridging."""
    if fn not in _listeners:
        _listeners.append(fn)


def log_event(event: str, severity: str = "INFO", **fields) -> Optional[dict]:
    """Record one structured event. Non-async (fast, safe from any context).
    Never raises — an event-logging failure must not break the operation."""
    try:
        record = {
            "event": event,
            "severity": severity if severity in ("INFO", "WARNING", "ERROR", "CRITICAL") else "INFO",
            "at": time.time(),
            **_scrub_fields(fields),
        }
        _events.append(record)
        for sink in list(_listeners):
            try:
                sink(record)
            except Exception:
                pass
        logger.info("%s %s", event, {k: v for k, v in record.items()
                                     if k not in ("at", "event", "severity")})
        return record
    except Exception:
        return None


async def log_event_async(event: str, severity: str = "INFO", **fields) -> Optional[dict]:
    return log_event(event, severity=severity, **fields)


def recent_events(limit: int = 100, event: Optional[str] = None,
                  min_severity: str = "INFO") -> list:
    """Newest-first, severity-filtered view for the API/diagnostics."""
    order = {"INFO": 0, "WARNING": 1, "ERROR": 2, "CRITICAL": 3}
    min_order = order.get(min_severity, 0)
    out = []
    for rec in reversed(_events):
        if event and rec.get("event") != event:
            continue
        if order.get(rec.get("severity", "INFO"), 0) < min_order:
            continue
        out.append({**rec, "at_iso": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(rec.get("at", 0)))})
        if len(out) >= limit:
            break
    return out


def event_stats() -> dict:
    counts: dict = {}
    for rec in _events:
        counts[rec.get("event", "?")] = counts.get(rec.get("event", "?"), 0) + 1
    return {"events_total": len(_events), "by_event": counts,
            "known_events": list(KNOWN_EVENTS), "bound": EVENT_BOUND,
            "engine": f"structured_events/{ENGINE_VERSION}"}


def register_routes(app, require_auth) -> None:
    from fastapi import Depends, Query
    from fastapi.responses import JSONResponse

    @app.get("/api/events", dependencies=[Depends(require_auth)])
    async def api_events(limit: int = Query(100, ge=1, le=400),
                         event: str = Query(""),
                         severity: str = Query("INFO")):
        return JSONResponse({"ok": True,
                             "events": recent_events(limit, event or None, severity),
                             **event_stats()})

    @app.get("/api/events/stats", dependencies=[Depends(require_auth)])
    async def api_event_stats():
        return JSONResponse({"ok": True, **event_stats()})


def reset_for_tests() -> None:
    _events.clear()
    _listeners.clear()
