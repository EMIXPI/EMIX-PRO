# protocols_api.py — REST API for the protocol engine
#
# Endpoints (all authed via require_auth):
#   GET    /api/protocols                       — list all protocols + capabilities
#   GET    /api/protocols/{name}                — single protocol detail
#   GET    /api/protocols/{name}/health         — latest health + rolling metrics
#   POST   /api/protocols/{name}/test           — run a health check NOW
#   POST   /api/protocols/{name}/enable         — admin-enable a protocol
#   POST   /api/protocols/{name}/disable        — admin-disable a protocol
#   GET    /api/protocols/selector/rank          — rank by score (smart selector)
#   GET    /api/protocols/selector/best          — single best protocol
#   GET    /api/protocols/selector/profiles     — list network profiles
#   POST   /api/protocols/{name}/generate-link  — generate a share-link
#
# Never exposes secrets. Capabilities are public but the API is authed.

import logging
from fastapi import APIRouter, HTTPException, Request, Depends

from protocol_engine import (
    list_protocols, get_protocol, get_enabled_protocols,
    get_protocol_capabilities, get_metrics, all_health,
    score_protocol, select_best, rank_protocols,
    get_profile, list_profiles, SelectorWeights,
    register_protocol, unregister_protocol,
)
from protocol_engine.base import LinkResult
# main.py is in the same directory; use absolute import (works whether
# protocols_api is imported as 'protocols_api' or 'main.protocols_api')
from main import require_auth, log_activity

logger = logging.getLogger("EMIX.protocols_api")

router = APIRouter()


def _adapter_or_404(name: str):
    a = get_protocol(name)
    if a is None:
        raise HTTPException(status_code=404, detail=f"protocol {name!r} not registered")
    return a


@router.get("/api/protocols")
async def list_all_protocols(_=Depends(require_auth)):
    """List all registered protocols with their capabilities + status."""
    return {
        "protocols": [a.to_dict() for a in list_protocols()],
        "total": len(list_protocols()),
        "enabled_count": len(get_enabled_protocols()),
        "metrics": get_metrics().all(),
        "health": all_health(),
    }


@router.get("/api/protocols/{name}")
async def get_protocol_detail(name: str, _=Depends(require_auth)):
    a = _adapter_or_404(name)
    d = a.to_dict()
    d["metrics"] = get_metrics().get(name).to_dict()
    d["health"] = all_health().get(name, {})
    return d


@router.get("/api/protocols/{name}/health")
async def get_protocol_health(name: str, _=Depends(require_auth)):
    _adapter_or_404(name)  # raises 404 if unknown
    return {
        "name": name,
        "health": all_health().get(name, {}),
        "metrics": get_metrics().get(name).to_dict(),
    }


@router.post("/api/protocols/{name}/test")
async def test_protocol(name: str, _=Depends(require_auth)):
    """Run a health check immediately and return the result."""
    a = _adapter_or_404(name)
    result = await a.health_check()
    # Record in rolling metrics
    from protocol_engine.health import get_health, Sample
    import time
    get_health(name).record(Sample(
        timestamp=time.time(),
        ok=result.ok,
        rtt_ms=result.rtt_ms,
        handshake_ms=result.handshake_ms,
        error=result.error,
    ))
    # Update health_status in metrics
    from protocol_engine.metrics import get_metrics as _gm
    _gm().set_health_status(name, "healthy" if result.ok else "down")
    log_activity("protocol", f"تست سلامت {name}: {'موفق' if result.ok else 'ناموفق'}",
                 "ok" if result.ok else "err")
    return {"name": name, "result": result.to_dict()}


@router.post("/api/protocols/{name}/enable")
async def enable_protocol(name: str, _=Depends(require_auth)):
    a = _adapter_or_404(name)
    a.status.enabled = True
    log_activity("protocol", f"پروتکل {name} فعال شد", "ok")
    return {"ok": True, "name": name, "enabled": True}


@router.post("/api/protocols/{name}/disable")
async def disable_protocol(name: str, _=Depends(require_auth)):
    a = _adapter_or_404(name)
    a.status.enabled = False
    log_activity("protocol", f"پروتکل {name} غیرفعال شد", "warn")
    return {"ok": True, "name": name, "enabled": False}


@router.get("/api/protocols/selector/rank")
async def selector_rank(profile: str = "stable", _=Depends(require_auth)):
    """Rank all enabled protocols by smart-selector score."""
    if profile not in list_profiles():
        raise HTTPException(status_code=400, detail=f"unknown profile {profile!r}")
    return {
        "profile": profile,
        "ranked": rank_protocols(profile),
    }


@router.get("/api/protocols/selector/best")
async def selector_best(profile: str = "stable", _=Depends(require_auth)):
    """Return the single best protocol by smart-selector score."""
    if profile not in list_profiles():
        raise HTTPException(status_code=400, detail=f"unknown profile {profile!r}")
    best = select_best(profile)
    return {"profile": profile, "best": best}


@router.get("/api/protocols/selector/profiles")
async def selector_profiles(_=Depends(require_auth)):
    """List available network profiles."""
    return {"profiles": list_profiles()}


@router.post("/api/protocols/{name}/generate-link")
async def generate_link(name: str, request: Request, _=Depends(require_auth)):
    """Generate a share-link for the protocol. Body = link params."""
    a = _adapter_or_404(name)
    body = await request.json()
    result: LinkResult = a.generate_link(body)
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.error or "link generation failed")
    log_activity("protocol", f"لینک {name} تولید شد", "info")
    return result.to_dict()
