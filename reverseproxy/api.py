# reverseproxy/api.py — REST API for reverse-proxy management (Phase 34)
#
# Endpoints (all authed via require_auth):
#   GET  /api/edge/config              — current reverse-proxy config (no secrets)
#   GET  /api/edge/routes              — list configured routes
#   GET  /api/edge/routes/{key}        — single route detail
#   GET  /api/edge/upstreams/health    — all upstream health snapshot
#   POST /api/edge/reload              — force-reload config from env vars
#   POST /api/edge/origin/test         — verify HMAC signature locally

import logging
from fastapi import APIRouter, HTTPException, Request, Depends

from .config import get_proxy_config, reload_proxy_config
from .health import all_upstream_health
from .auth import verify_origin_signature, build_origin_signature, HMAC_ORIGIN_HEADER, HMAC_TIMESTAMP_HEADER

logger = logging.getLogger("EMIX.reverseproxy.api")

router = APIRouter()


@router.get("/api/edge/config")
async def edge_config(_=Depends(lambda: None)):  # placeholder dependency — actual auth wired in main.py
    """Current reverse-proxy config (NO secrets)."""
    cfg = get_proxy_config()
    return cfg.to_dict()


@router.get("/api/edge/routes")
async def edge_routes(_=Depends(lambda: None)):
    cfg = get_proxy_config()
    return {"routes": [r.to_dict() for r in cfg.routes]}


@router.get("/api/edge/routes/{route_key}")
async def edge_route_detail(route_key: str, _=Depends(lambda: None)):
    cfg = get_proxy_config()
    for r in cfg.routes:
        if f"{r.host}|{r.path}" == route_key or r.host == route_key:
            return r.to_dict()
    raise HTTPException(status_code=404, detail="route not found")


@router.get("/api/edge/upstreams/health")
async def edge_upstream_health(_=Depends(lambda: None)):
    return {"upstreams": all_upstream_health()}


@router.post("/api/edge/reload")
async def edge_reload(_=Depends(lambda: None)):
    """Force-reload reverse-proxy config from env vars."""
    cfg = reload_proxy_config()
    log_activity_msg = f"reverse-proxy config reloaded: routes={len(cfg.routes)}"
    try:
        from main import log_activity
        log_activity("system", log_activity_msg, "info")
    except Exception:
        pass
    return {"ok": True, "config": cfg.to_dict()}


@router.post("/api/edge/origin/test")
async def edge_origin_test(request: Request, _=Depends(lambda: None)):
    """Verify a local HMAC signature (for testing the edge-side flow).
    Body: {method, path, body} — returns the signature + timestamp that
    the edge SHOULD send."""
    body = await request.json()
    method = body.get("method", "GET")
    path = body.get("path", "/")
    payload = body.get("body", "")
    if isinstance(payload, str):
        payload = payload.encode()
    cfg = get_proxy_config()
    if not cfg.origin_auth_enabled:
        return {"ok": False, "error": "origin auth not enabled (set EMIX_ORIGIN_AUTH_SECRET)"}
    sig, ts = build_origin_signature(cfg.origin_auth_secret, method, path, payload)
    return {
        "ok": True,
        "signature_header": HMAC_ORIGIN_HEADER,
        "timestamp_header": HMAC_TIMESTAMP_HEADER,
        "signature": sig,
        "timestamp": ts,
        "instructions": "Send these headers from the edge worker to EMIX",
    }
