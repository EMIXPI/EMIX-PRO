# diagnostics.py — EMIX Diagnostics Center (Phase 21)
#
# Structured error records + aggregated system diagnostics.
#
# Error record shape (every error, everywhere, should carry these):
#   code        — stable machine-readable identifier ("HEALTH_PROBE_FAIL")
#   message     — human summary (never contains secrets)
#   component   — "protocol-engine" / "health" / "jobs" / "api" / ...
#   severity    — INFO / WARNING / ERROR / CRITICAL
#   context     — dict of non-secret metadata (uid, protocol, ms, ...)
#   request_id  — correlation id when raised inside a request
#   timestamp   — epoch seconds
#
# The /api/diagnostics endpoint aggregates:
#   app, persistence, jobs, network-health, ip-quality, nodes,
#   protocol registry, recent errors — one call, no secrets.

from __future__ import annotations
import time
import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List


logger = logging.getLogger("EMIX.diagnostics")


ERROR_HISTORY = 100
SEVERITIES = ("INFO", "WARNING", "ERROR", "CRITICAL")

# ── Structured error store ──────────────────────────────────────────────────

@dataclass
class ErrorRecord:
    code: str
    message: str
    component: str
    severity: str = "ERROR"
    context: dict = field(default_factory=dict)
    request_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.timestamp))
        return d


_errors: deque = deque(maxlen=ERROR_HISTORY)
_error_counts: Dict[str, int] = {}
_lock = asyncio.Lock()


async def record_error(code: str, message: str, component: str,
                       severity: str = "ERROR", context: Optional[dict] = None,
                       request_id: Optional[str] = None) -> ErrorRecord:
    """Record a structured error. Message must already be secret-free."""
    severity = severity if severity in SEVERITIES else "ERROR"
    rec = ErrorRecord(code=code[:64], message=str(message)[:300],
                      component=component[:40], severity=severity,
                      context={k: str(v)[:80] for k, v in (context or {}).items()},
                      request_id=request_id)
    async with _lock:
        _errors.append(rec)
        _error_counts[code] = _error_counts.get(code, 0) + 1
    log_fn = (logger.info if severity == "INFO" else
              logger.warning if severity == "WARNING" else
              logger.critical if severity == "CRITICAL" else logger.error)
    log_fn("[diag] %s/%s: %s %s", component, code, message, rec.context or "")
    return rec


def record_error_sync(code: str, message: str, component: str,
                      severity: str = "ERROR", context: Optional[dict] = None,
                      request_id: Optional[str] = None) -> ErrorRecord:
    """Sync variant for code paths without a running event loop."""
    rec = ErrorRecord(code=code[:64], message=str(message)[:300],
                      component=component[:40], severity=severity,
                      context={k: str(v)[:80] for k, v in (context or {}).items()},
                      request_id=request_id)
    _errors.append(rec)
    _error_counts[code] = _error_counts.get(code, 0) + 1
    return rec


async def recent_errors(limit: int = 25, component: Optional[str] = None,
                        severity: Optional[str] = None) -> List[dict]:
    async with _lock:
        items = list(_errors)
    out = []
    for rec in reversed(items):
        if component and rec.component != component:
            continue
        if severity and rec.severity != severity:
            continue
        out.append(rec.to_dict())
        if len(out) >= limit:
            break
    return out


async def error_stats() -> dict:
    async with _lock:
        return {"distinct_codes": len(_error_counts),
                "total": sum(_error_counts.values()),
                "top_codes": sorted(_error_counts.items(), key=lambda kv: -kv[1])[:10]}


# ── Middleware: request timing + slow-request + unhandled-error capture ─────

SLOW_REQUEST_MS = 2000.0


async def diagnostics_middleware(request, call_next):
    """FastAPI HTTP middleware — adds request-id header, tracks slow requests
    and records unhandled exceptions as structured errors."""
    import uuid as _uuid
    request_id = request.headers.get("X-Request-Id") or _uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        await record_error(
            code="API_UNHANDLED",
            message=f"{type(exc).__name__}: {str(exc)[:200]}",
            component="api",
            severity="CRITICAL",
            context={"path": request.url.path, "method": request.method},
            request_id=request_id,
        )
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "internal error", "request_id": request_id}, status_code=500)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
    if elapsed_ms > SLOW_REQUEST_MS:
        await record_error(
            code="API_SLOW_REQUEST",
            message=f"{request.method} {request.url.path} took {elapsed_ms}ms",
            component="api",
            severity="WARNING",
            context={"ms": elapsed_ms, "method": request.method},
            request_id=request_id,
        )
    return response


# ── Late wiring (main.py sets these at bootstrap) ───────────────────────

_persistence_probe: Optional[callable] = None


def set_persistence_probe(fn) -> None:
    """main.py injects an async fn returning the persistence health dict."""
    global _persistence_probe
    _persistence_probe = fn


# ── Aggregated diagnostics overview (route registered in main.py with auth) ─

async def diagnostics_overview() -> dict:
    """One-shot system snapshot: app, persistence, jobs, health engines,
    protocol registry, recent structured errors. No secrets."""
    from datetime import datetime
    checks: Dict[str, dict] = {}

    # app
    checks["app"] = {"status": "OK", "time": datetime.now().isoformat(),
                     "engine": "emix-diagnostics/1.0"}

    # persistence
    if _persistence_probe is not None:
        try:
            checks["persistence"] = await _persistence_probe()
        except Exception as exc:
            checks["persistence"] = {"status": "ERROR", "error": str(exc)[:120]}
    else:
        checks["persistence"] = {"status": "UNKNOWN"}

    # jobs
    try:
        from job_system import jobs
        checks["jobs"] = jobs.status()
    except Exception as exc:
        checks["jobs"] = {"status": "UNKNOWN", "error": str(exc)[:120]}

    # network health
    try:
        import network_health
        checks["network_health"] = network_health.summary()
    except Exception as exc:
        checks["network_health"] = {"status": "UNKNOWN", "error": str(exc)[:120]}

    # ip quality
    try:
        import ip_quality
        checks["ip_quality"] = ip_quality.summary()
    except Exception as exc:
        checks["ip_quality"] = {"status": "UNKNOWN", "error": str(exc)[:120]}

    # protocol registry
    try:
        from protocol_engine import registry as _reg
        names = _reg.protocol_names() if hasattr(_reg, "protocol_names") else []
        checks["protocols"] = {"registered": len(names), "names": names[:30]}
    except Exception as exc:
        checks["protocols"] = {"status": "UNKNOWN", "error": str(exc)[:120]}

    return {
        "ok": True,
        "checks": checks,
        "errors": await error_stats(),
        "recent_errors": await recent_errors(limit=15),
    }
