# reverseproxy/__init__.py — public API for the EMIX reverse-proxy subsystem
#
# This module implements a production-grade reverse-proxy layer that sits
# IN FRONT of the existing EMIX routes — it does NOT replace FastAPI's
# routing. It is opt-in: by default (no routes configured) it is a no-op
# and EMIX behaves exactly as before.
#
# Use cases:
#   1. Route external hostnames (e.g. api.emix.example.com) to internal EMIX paths
#   2. Load-balance across multiple EMIX instances
#   3. Forward WebSocket/gRPC upstreams to other services
#   4. Apply CDN-safe Cache-Control headers on tunnel paths
#   5. Verify HMAC origin authentication from a trusted edge (Cloudflare Worker, ArvanCloud)
#
# Public API:
#   from reverseproxy import (
#       Route, Upstream, ReverseProxyConfig,
#       get_proxy_config, reload_proxy_config,
#       is_tunnel_path, add_cache_safety_headers,
#       is_trusted_edge, get_real_client_ip,
#       verify_origin_signature, build_origin_signature,
#       reverse_proxy_handler, start_health_checks, stop_health_checks,
#   )

from .config import (
    Route, Upstream, ReverseProxyConfig,
    get_proxy_config, reload_proxy_config,
)
from .headers import (
    is_tunnel_path, add_cache_safety_headers,
    is_trusted_edge, get_real_client_ip,
    TRUSTED_EDGE_HEADER_SET,
)
from .auth import (
    verify_origin_signature, build_origin_signature,
    HMAC_ORIGIN_HEADER, HMAC_TIMESTAMP_HEADER,
)
from .health import UpstreamHealth, get_upstream_health, all_upstream_health
from .proxy import reverse_proxy_handler, start_health_checks, stop_health_checks
from . import api  # registers /api/edge/* routes via api.router

__all__ = [
    "Route", "Upstream", "ReverseProxyConfig",
    "get_proxy_config", "reload_proxy_config",
    "is_tunnel_path", "add_cache_safety_headers",
    "is_trusted_edge", "get_real_client_ip",
    "TRUSTED_EDGE_HEADER_SET",
    "verify_origin_signature", "build_origin_signature",
    "HMAC_ORIGIN_HEADER", "HMAC_TIMESTAMP_HEADER",
    "UpstreamHealth", "get_upstream_health", "all_upstream_health",
    "reverse_proxy_handler", "start_health_checks", "stop_health_checks",
    "api",
]
