# reverseproxy/config.py — reverse-proxy route configuration
#
# Configuration is loaded from env vars (or a JSON env var blob) at startup.
# Empty config = no routes = reverse proxy is a no-op (EMIX behaves as before).
#
# Example env vars:
#   EMIX_REVERSE_PROXY_ENABLED=1
#   EMIX_REVERSE_PROXY_ROUTES_JSON='[
#     {"host":"emix.example.com","path":"/","upstreams":[{"url":"http://127.0.0.1:8000","weight":1,"priority":1}],"transport":"http"},
#     {"host":"tunnel.emix.example.com","transport":"websocket","upstreams":[{"url":"http://127.0.0.1:8000"}]}
#   ]'
#   EMIX_TRUSTED_EDGES="cloudflare.com,*.workers.dev,arvancloud.com"
#   EMIX_ORIGIN_AUTH_SECRET="<32-byte secret shared with edge>"

import os
import json
import fnmatch
import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple, List
from urllib.parse import urlparse

logger = logging.getLogger("EMIX.reverseproxy")


@dataclass(frozen=True)
class Upstream:
    """A single upstream server endpoint."""
    url: str
    weight: int = 1
    priority: int = 1
    # TLS verification — NEVER disable in production
    verify_tls: bool = True
    # Host header to send to upstream (empty = pass through)
    upstream_host: str = ""

    @property
    def scheme(self) -> str:
        return urlparse(self.url).scheme

    @property
    def host(self) -> str:
        return urlparse(self.url).hostname or ""

    @property
    def port(self) -> int:
        p = urlparse(self.url).port
        if p:
            return p
        return 443 if self.scheme == "https" else 80

    def to_dict(self) -> dict:
        return {
            "url": self.url, "weight": self.weight, "priority": self.priority,
            "verify_tls": self.verify_tls, "upstream_host": self.upstream_host,
            "scheme": self.scheme, "host": self.host, "port": self.port,
        }


@dataclass(frozen=True)
class Route:
    """A reverse-proxy route match rule + its upstreams."""
    host: str = ""                       # match by Host header ("" = match any)
    path: str = ""                       # match by path prefix ("" = match any)
    transport: str = "http"              # http | websocket | grpc | httpupgrade
    upstreams: Tuple[Upstream, ...] = field(default_factory=tuple)
    # Load-balancing strategy: round_robin | weighted | least_connections | latency_aware | priority
    lb_strategy: str = "round_robin"
    # Timeouts (seconds)
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    # WebSocket idle timeout
    ws_idle_timeout: float = 300.0
    # Health-check config
    health_check_path: str = "/api/ping"
    health_check_interval: float = 30.0
    health_check_timeout: float = 5.0

    def matches(self, host: str, path: str) -> bool:
        if self.host and self.host != host and not fnmatch.fnmatch(host, self.host):
            return False
        if self.path and not path.startswith(self.path):
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "host": self.host, "path": self.path, "transport": self.transport,
            "upstreams": [u.to_dict() for u in self.upstreams],
            "lb_strategy": self.lb_strategy,
            "connect_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
            "ws_idle_timeout": self.ws_idle_timeout,
            "health_check_path": self.health_check_path,
            "health_check_interval": self.health_check_interval,
            "health_check_timeout": self.health_check_timeout,
        }


@dataclass(frozen=True)
class ReverseProxyConfig:
    """Top-level reverse-proxy config + edge/CDN settings."""
    enabled: bool = False
    routes: Tuple[Route, ...] = field(default_factory=tuple)
    # Trusted edge/CDN hostnames — only these may set X-Forwarded-For etc.
    trusted_edges: Tuple[str, ...] = field(default_factory=tuple)
    # Origin HMAC authentication (shared secret between edge and EMIX)
    origin_auth_secret: str = ""
    origin_auth_enabled: bool = False
    # Cache safety — never cache tunnel/auth paths
    cache_safety_enabled: bool = True
    # Minimum TLS version (1.2 or 1.3)
    min_tls_version: str = "1.2"

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "routes": [r.to_dict() for r in self.routes],
            "trusted_edges": list(self.trusted_edges),
            "origin_auth_enabled": self.origin_auth_enabled,
            "cache_safety_enabled": self.cache_safety_enabled,
            "min_tls_version": self.min_tls_version,
        }

    def is_trusted_edge(self, host: str) -> bool:
        """Return True if the given host matches a trusted-edge pattern."""
        if not host:
            return False
        host = host.lower().rstrip(".")
        for pattern in self.trusted_edges:
            if pattern.startswith("*"):
                # Suffix match
                suffix = pattern[1:].lstrip("*").lower()
                if host.endswith(suffix):
                    return True
            elif fnmatch.fnmatch(host, pattern.lower()):
                return True
            elif host == pattern.lower():
                return True
        return False

    def find_route(self, host: str, path: str) -> Optional[Route]:
        """Find the first route matching (host, path)."""
        for r in self.routes:
            if r.matches(host, path):
                return r
        return None


def _load_routes_from_env() -> Tuple[Route, ...]:
    """Load routes from EMIX_REVERSE_PROXY_ROUTES_JSON env var."""
    raw = os.environ.get("EMIX_REVERSE_PROXY_ROUTES_JSON", "").strip()
    if not raw:
        return ()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error(f"[reverseproxy] invalid EMIX_REVERSE_PROXY_ROUTES_JSON: {exc}")
        return ()
    if not isinstance(data, list):
        logger.error("[reverseproxy] routes JSON must be a list")
        return ()
    routes = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            upstreams = tuple(
                Upstream(
                    url=str(u.get("url", "")),
                    weight=int(u.get("weight", 1)),
                    priority=int(u.get("priority", 1)),
                    verify_tls=bool(u.get("verify_tls", True)),
                    upstream_host=str(u.get("upstream_host", "")),
                )
                for u in (item.get("upstreams") or [])
                if isinstance(u, dict) and u.get("url")
            )
            if not upstreams:
                continue
            routes.append(Route(
                host=str(item.get("host", "")),
                path=str(item.get("path", "")),
                transport=str(item.get("transport", "http")),
                upstreams=upstreams,
                lb_strategy=str(item.get("lb_strategy", "round_robin")),
                connect_timeout=float(item.get("connect_timeout", 10.0)),
                read_timeout=float(item.get("read_timeout", 30.0)),
                ws_idle_timeout=float(item.get("ws_idle_timeout", 300.0)),
                health_check_path=str(item.get("health_check_path", "/api/ping")),
                health_check_interval=float(item.get("health_check_interval", 30.0)),
                health_check_timeout=float(item.get("health_check_timeout", 5.0)),
            ))
        except Exception as exc:
            logger.warning(f"[reverseproxy] skipping invalid route: {exc}")
    return tuple(routes)


def _load_config() -> ReverseProxyConfig:
    """Load the reverse-proxy config from env vars."""
    enabled = os.environ.get("EMIX_REVERSE_PROXY_ENABLED", "0").strip() in ("1", "true", "yes", "on")
    routes = _load_routes_from_env() if enabled else ()
    trusted = tuple(
        x.strip() for x in os.environ.get("EMIX_TRUSTED_EDGES", "").split(",")
        if x.strip()
    )
    origin_secret = os.environ.get("EMIX_ORIGIN_AUTH_SECRET", "").strip()
    return ReverseProxyConfig(
        enabled=enabled,
        routes=routes,
        trusted_edges=trusted,
        origin_auth_secret=origin_secret,
        origin_auth_enabled=bool(origin_secret),
        cache_safety_enabled=os.environ.get("EMIX_CACHE_SAFETY", "1").strip() not in ("0", "false", "no", "off"),
        min_tls_version=os.environ.get("EMIX_MIN_TLS_VERSION", "1.2").strip(),
    )


# Singleton + reload
_current_config: ReverseProxyConfig = ReverseProxyConfig()


def get_proxy_config() -> ReverseProxyConfig:
    """Get the current reverse-proxy config (singleton)."""
    global _current_config
    if _current_config is None:
        _current_config = _load_config()
    return _current_config


def reload_proxy_config() -> ReverseProxyConfig:
    """Force-reload the config from env vars (e.g. after env var change)."""
    global _current_config
    _current_config = _load_config()
    logger.info(
        f"[reverseproxy] config reloaded: enabled={_current_config.enabled} "
        f"routes={len(_current_config.routes)} "
        f"trusted_edges={len(_current_config.trusted_edges)} "
        f"origin_auth={_current_config.origin_auth_enabled}"
    )
    return _current_config


# Auto-load on first import
_current_config = _load_config()
