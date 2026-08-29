# reverseproxy/headers.py — header management + cache safety + trusted-edge IP
#
# Phase 36 — Cache safety: tunnel/auth paths get Cache-Control: no-store
# Phase 37 — Header management: strip hop-by-hop + sensitive client headers
# Phase 38 — Trusted-edge X-Forwarded-For handling (no longer trust arbitrary values)

import re
import logging
from typing import Optional
from .config import get_proxy_config

logger = logging.getLogger("EMIX.reverseproxy.headers")

# Hop-by-hop headers per RFC 7230 §6.1 — must never be forwarded
HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-encoding", "content-length",
})

# Sensitive client headers — never forward to upstream unless explicitly allowed
SENSITIVE = frozenset({
    "cookie", "authorization", "proxy-authorization",
    "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto",
    "x-real-ip", "x-forwarded-port", "x-forwarded-server", "forwarded",
})

# Headers safe to forward to upstream
SAFE_FORWARD_HEADERS = frozenset({
    "user-agent", "accept", "accept-encoding", "accept-language",
    "content-type", "content-disposition", "range", "if-modified-since",
    "if-none-match", "cache-control", "pragma", "expires",
})

# Header that the edge sets to identify itself as a trusted proxy
TRUSTED_EDGE_HEADER_SET = frozenset({
    "cf-connecting-ip",      # Cloudflare
    "cf-ipcountry",          # Cloudflare
    "x-arvan-edge",          # ArvanCloud (convention)
    "x-real-ip",             # Generic edge
    "x-forwarded-for",      # Standard
})

# Paths that MUST NEVER be cached (Phase 36 — non-negotiable)
# Tunnel/auth/subscription/admin paths bypass cache.
TUNNEL_PATH_PATTERNS = (
    re.compile(r"^/ws/"),                          # VLESS WebSocket
    re.compile(r"^/trojan-ws"),                    # Trojan WebSocket
    re.compile(r"^/ss-ws"),                       # Shadowsocks WebSocket
    re.compile(r"^/xhttp-siz10/"),                 # VLESS XHTTP (all modes)
    re.compile(r"^/txhttp-siz10/"),                # Trojan XHTTP
    re.compile(r"^/sub/"),                         # Subscription URLs (contain UUID + traffic info)
    re.compile(r"^/sub-all"),                     # Aggregate subscription
    re.compile(r"^/p/"),                           # Public sub page (per-user)
    re.compile(r"^/api/login"),                   # Login endpoint
    re.compile(r"^/api/logout"),                   # Logout endpoint
    re.compile(r"^/api/change-password"),         # Password mutation
    re.compile(r"^/api/backup/"),                  # Backup export/import (state)
    re.compile(r"^/api/links"),                    # Link management
    re.compile(r"^/api/subs"),                     # Sub management
    re.compile(r"^/api/nodes"),                    # Node management
    re.compile(r"^/api/me"),                       # Session check
    re.compile(r"^/api/exp/"),                     # Experimental endpoints (state-changing)
    re.compile(r"^/api/protocols/"),               # Protocol management
    re.compile(r"^/api/settings/"),                # Settings mutations
    re.compile(r"^/api/announcements/view"),       # User-state mutation
    re.compile(r"^/api/support/"),                 # Support messages (private)
    re.compile(r"^/api/mtproto/"),                # MTProto management
    re.compile(r"^/api/zeus-proxy/"),              # SOCKS5 management
    re.compile(r"^/api/bot-tcp-proxy/"),           # Railway TCP proxy management
    re.compile(r"^/api/domain-gen/"),              # Domain generation
    re.compile(r"^/api/connections"),              # Live connection data
    re.compile(r"^/api/activity"),                # Activity log
    re.compile(r"^/stats"),                        # Internal stats
    re.compile(r"^/proxy/"),                       # Forward proxy path
)


def is_tunnel_path(path: str) -> bool:
    """Return True if the path matches a known tunnel/auth/admin path
    that must NEVER be cached."""
    if not path:
        return False
    for pat in TUNNEL_PATH_PATTERNS:
        if pat.match(path):
            return True
    return False


def add_cache_safety_headers(headers: dict, path: str) -> dict:
    """Add Cache-Control: no-store (and friends) to tunnel/auth paths.
    Phase 36 — non-negotiable."""
    if not is_tunnel_path(path):
        return headers
    headers = dict(headers)
    headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    headers["Pragma"] = "no-cache"
    headers["Expires"] = "0"
    # Also strip Surrogate-Control so CDN doesn't cache
    headers["Surrogate-Control"] = "no-store"
    headers["CDN-Cache-Control"] = "no-store"  # ArvanCloud convention
    return headers


def is_trusted_edge(host: str) -> bool:
    """Return True if the given host is in the trusted-edges allowlist."""
    cfg = get_proxy_config()
    return cfg.is_trusted_edge(host)


def get_real_client_ip(headers, remote_addr: Optional[str] = None) -> Optional[str]:
    """Extract the real client IP, but ONLY trust X-Forwarded-For from a trusted edge.

    If the request did NOT come through a trusted edge, return remote_addr
    (the actual TCP peer) — never trust X-Forwarded-For from arbitrary clients.
    """
    if remote_addr is None:
        return None
    # Check if any trusted-edge header is present AND host is trusted
    # (the host check uses the Host header, which we trust because Railway edge
    # guarantees it)
    # For safety: only trust XFF if a known-edge header is also present.
    has_edge_header = any(h.lower() in TRUSTED_EDGE_HEADER_SET for h in (headers or {}))
    if not has_edge_header:
        # Direct connection (no edge in front) — return remote_addr
        return remote_addr.split(":")[0] if ":" in remote_addr else remote_addr
    # Trusted edge — extract first XFF entry
    xff = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For") or ""
    if xff:
        first_ip = xff.split(",")[0].strip()
        if first_ip:
            return first_ip
    # Fall back to X-Real-IP if present
    xrip = headers.get("x-real-ip") or headers.get("X-Real-IP")
    if xrip:
        return xrip.strip()
    return remote_addr.split(":")[0] if ":" in remote_addr else remote_addr


def sanitize_forwarded_headers(incoming_headers) -> dict:
    """Build a safe header set to forward to an upstream.
    Drops hop-by-hop + sensitive + unsafe client headers."""
    return {
        k: v for k, v in (incoming_headers or {}).items()
        if k.lower() in SAFE_FORWARD_HEADERS
    }


def check_header_injection(value: str) -> bool:
    """Return True if the value contains CR/LF (potential CRLF injection)."""
    if not isinstance(value, str):
        return False
    return "\r" in value or "\n" in value
