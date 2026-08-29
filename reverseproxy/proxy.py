# reverseproxy/proxy.py — core HTTP reverse-proxy handler (Phase 31)
#
# Implements the actual proxy pass-through. Used as a FastAPI route or
# middleware when EMIX_REVERSE_PROXY_ENABLED=1 and routes are configured.
#
# Phase 33 — Load balancing + circuit breaker.
# Phase 34 — Upstream health checks (active probing).
# Phase 36 — Cache safety headers (no-store on tunnel paths).
# Phase 37 — Header sanitization.
# Phase 38 — SSRF protection on upstream URLs (defense in depth).
# Phase 39 — HMAC origin authentication.
#
# This is a SINGLE WORKER, in-process reverse proxy. It does NOT spawn
# subprocesses or use kernel features. Suitable for Railway deployment.

import asyncio
import time
import logging
from typing import Optional
from urllib.parse import urlparse, urljoin

import httpx
from fastapi import Request, HTTPException
from fastapi.responses import Response

from .config import get_proxy_config, Route, Upstream
from .headers import (
    add_cache_safety_headers, sanitize_forwarded_headers,
    check_header_injection, get_real_client_ip,
)
from .auth import verify_origin_signature, HMAC_ORIGIN_HEADER, HMAC_TIMESTAMP_HEADER
from .health import get_upstream_health, UpstreamSample
from .loadbalancer import get_balancer

logger = logging.getLogger("EMIX.reverseproxy")


async def reverse_proxy_handler(request: Request) -> Response:
    """Main reverse-proxy handler. Mounted at catch-all route when enabled."""
    cfg = get_proxy_config()
    if not cfg.enabled:
        # Should not happen (route is only mounted when enabled)
        raise HTTPException(status_code=404, detail="reverse proxy disabled")

    host = (request.headers.get("host") or "").split(":")[0].lower()
    path = request.url.path
    qs = request.url.query

    # Phase 39 — verify origin HMAC signature if origin auth is enabled
    body_bytes = b""
    if request.method in ("POST", "PUT", "PATCH"):
        body_bytes = await request.body()
    ok, err = verify_origin_signature(
        method=request.method,
        path=path,
        body=body_bytes,
        incoming_signature=request.headers.get(HMAC_ORIGIN_HEADER),
        incoming_timestamp=request.headers.get(HMAC_TIMESTAMP_HEADER),
    )
    if not ok:
        # Don't leak the specific reason to the client
        logger.warning(f"[reverseproxy] origin auth failed from {host}: {err}")
        raise HTTPException(status_code=401, detail="unauthorized origin")

    # Find matching route
    route = cfg.find_route(host, path)
    if route is None:
        raise HTTPException(status_code=404, detail="no route matches host/path")

    # Phase 33 — load-balance across upstreams (skip OPEN circuits)
    balancer = get_balancer(f"{route.host}|{route.path}", route.lb_strategy)
    upstream = balancer.select(list(route.upstreams))
    if upstream is None:
        raise HTTPException(status_code=503, detail="all upstreams unhealthy")

    # Build target URL
    target_url = upstream.url.rstrip("/") + path
    if qs:
        target_url += "?" + qs

    # Phase 37 — sanitize forwarded headers
    safe_headers = sanitize_forwarded_headers(request.headers)
    # Inject upstream Host if configured
    if upstream.upstream_host:
        safe_headers["Host"] = upstream.upstream_host
    # Add the real client IP (from trusted edge if applicable)
    real_ip = get_real_client_ip(request.headers, request.client.host if request.client else None)
    if real_ip:
        safe_headers["X-Forwarded-For"] = real_ip
        safe_headers["X-Real-IP"] = real_ip
    safe_headers["X-Forwarded-Proto"] = "https" if request.url.scheme == "https" else "http"
    safe_headers["X-Forwarded-Host"] = host

    # Phase 37 — CRLF injection check
    for k, v in safe_headers.items():
        if check_header_injection(v) or check_header_injection(k):
            logger.warning(f"[reverseproxy] CRLF injection detected in header {k!r}")
            raise HTTPException(status_code=400, detail="invalid header")

    # Phase 33 — track active connection
    balancer.connection_opened(upstream.url)
    t0 = time.monotonic()
    try:
        # Phase 31 — make the request to upstream
        # Use a per-request httpx client (could pool per upstream if perf needed)
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(route.connect_timeout + route.read_timeout, connect=route.connect_timeout),
            verify=upstream.verify_tls,
            follow_redirects=False,  # we revalidate each redirect (Phase 38)
        ) as client:
            upstream_resp = await client.request(
                method=request.method,
                url=target_url,
                headers=safe_headers,
                content=body_bytes if request.method in ("POST", "PUT", "PATCH") else None,
            )
        latency_ms = (time.monotonic() - t0) * 1000
        # Record success
        get_upstream_health(f"{route.host}|{route.path}", upstream.url).record(UpstreamSample(
            timestamp=time.time(),
            ok=True,
            latency_ms=latency_ms,
        ))
        # Phase 36 — cache safety headers
        out_headers = {k: v for k, v in upstream_resp.headers.items()
                       if k.lower() not in {"transfer-encoding", "content-encoding", "content-length"}}
        out_headers = add_cache_safety_headers(out_headers, path)
        return Response(
            content=upstream_resp.content,
            status_code=upstream_resp.status_code,
            headers=out_headers,
            media_type=upstream_resp.headers.get("content-type"),
        )
    except httpx.TimeoutException:
        # Record failure
        get_upstream_health(f"{route.host}|{route.path}", upstream.url).record(UpstreamSample(
            timestamp=time.time(),
            ok=False,
            error="timeout",
        ))
        raise HTTPException(status_code=504, detail="upstream timeout")
    except httpx.ConnectError as exc:
        get_upstream_health(f"{route.host}|{route.path}", upstream.url).record(UpstreamSample(
            timestamp=time.time(),
            ok=False,
            error=f"connect: {exc}",
        ))
        raise HTTPException(status_code=502, detail="upstream connect failed")
    except Exception as exc:
        get_upstream_health(f"{route.host}|{route.path}", upstream.url).record(UpstreamSample(
            timestamp=time.time(),
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        ))
        logger.warning(f"[reverseproxy] upstream {upstream.url} failed: {exc}")
        raise HTTPException(status_code=502, detail="upstream error")
    finally:
        balancer.connection_closed(upstream.url)


async def background_upstream_health_checks():
    """Background task that probes all configured upstreams periodically.
    Phase 34 — bounded health-check traffic (one probe per interval per upstream)."""
    cfg = get_proxy_config()
    if not cfg.enabled:
        return
    while True:
        try:
            for route in cfg.routes:
                for upstream in route.upstreams:
                    try:
                        await _probe_upstream(route, upstream)
                    except Exception as exc:
                        logger.debug(f"[reverseproxy] health check error for {upstream.url}: {exc}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"[reverseproxy] health-check loop iteration error: {exc}")
        # Sleep for the minimum interval across routes (default 30s)
        intervals = [r.health_check_interval for r in cfg.routes] or [30.0]
        await asyncio.sleep(min(intervals))


async def _probe_upstream(route: Route, upstream: Upstream) -> None:
    """One health-check probe. Records result in UpstreamHealth."""
    url = upstream.url.rstrip("/") + route.health_check_path
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(route.health_check_timeout, connect=route.health_check_timeout),
            verify=upstream.verify_tls,
            follow_redirects=False,
        ) as client:
            r = await client.get(url)
        latency_ms = (time.monotonic() - t0) * 1000
        # 2xx + 3xx = ok; 4xx + 5xx = fail
        ok = r.status_code < 400
        get_upstream_health(f"{route.host}|{route.path}", upstream.url).record(UpstreamSample(
            timestamp=time.time(),
            ok=ok,
            latency_ms=latency_ms,
            error=None if ok else f"HTTP {r.status_code}",
        ))
    except Exception as exc:
        get_upstream_health(f"{route.host}|{route.path}", upstream.url).record(UpstreamSample(
            timestamp=time.time(),
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        ))


# Background task handle (started by main.py startup if reverse proxy enabled)
_health_check_task: Optional[asyncio.Task] = None


def start_health_checks() -> None:
    """Launch the background health-check loop (idempotent)."""
    global _health_check_task
    if _health_check_task is not None and not _health_check_task.done():
        return
    cfg = get_proxy_config()
    if not cfg.enabled:
        return
    _health_check_task = asyncio.create_task(background_upstream_health_checks())
    logger.info("[reverseproxy] upstream health-check task started")


def stop_health_checks() -> None:
    """Cancel the health-check task (graceful shutdown)."""
    global _health_check_task
    if _health_check_task is None or _health_check_task.done():
        return
    _health_check_task.cancel()
    try:
        asyncio.get_event_loop().run_until_complete(_health_check_task)
    except (asyncio.CancelledError, RuntimeError):
        pass
    _health_check_task = None
