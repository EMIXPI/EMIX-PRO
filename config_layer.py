# config_layer.py — typed operational configuration for EMIX-PRO
#
# ▸ Centralizes the operationally-meaningful magic numbers that were previously
#   scattered as hardcoded constants in main.py and the protocol/* modules.
# ▸ Reads env-var overrides with `EMIX_` prefix where it makes sense.
# ▸ Defaults match the values that were in production before this layer was
#   introduced — so existing deployments behave identically unless an admin
#   explicitly overrides.
# ▸ NOT every internal constant becomes an env var. Only the ones an operator
#   might reasonably want to tune (TTL, retention, retry counts, breaker
#   thresholds, buffer sizes, timeouts).

import os
from dataclasses import dataclass, field
from typing import Tuple


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if not v:
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    v = os.environ.get(name)
    if not v:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class EmixConfig:
    # ── Auth & session ──
    session_ttl_seconds: int = field(
        default_factory=lambda: _env_int("EMIX_SESSION_TTL", 60 * 60 * 24 * 7)
    )
    session_cleanup_interval_seconds: int = field(
        default_factory=lambda: _env_int("EMIX_SESSION_CLEANUP_INTERVAL", 3600)
    )

    # ── Persistence ──
    save_debounce_seconds: float = field(
        default_factory=lambda: _env_float("EMIX_SAVE_DEBOUNCE", 2.0)
    )

    # ── Traffic / stats ──
    hourly_traffic_retention_hours: int = field(
        default_factory=lambda: _env_int("EMIX_HOURLY_RETENTION", 72)
    )

    # ── xHTTP ──
    xhttp_seq_buf_max_mb: int = field(
        default_factory=lambda: _env_int("EMIX_XHTTP_SEQ_BUF_MAX_MB", 4)
    )

    # ── Node circuit breaker ──
    node_request_timeout_seconds: float = field(
        default_factory=lambda: _env_float("EMIX_NODE_TIMEOUT", 10.0)
    )
    node_max_retries: int = field(
        default_factory=lambda: _env_int("EMIX_NODE_MAX_RETRIES", 2)
    )
    node_backoff_base_ms: int = field(
        default_factory=lambda: _env_int("EMIX_NODE_BACKOFF_BASE_MS", 250)
    )
    node_failure_threshold: int = field(
        default_factory=lambda: _env_int("EMIX_NODE_FAILURE_THRESHOLD", 3)
    )
    node_cooldown_seconds: int = field(
        default_factory=lambda: _env_int("EMIX_NODE_COOLDOWN", 30)
    )

    # ── HTTP proxy (SSRF protection) ──
    proxy_allow_private_targets: bool = field(
        default_factory=lambda: _env_bool("EMIX_PROXY_ALLOW_PRIVATE", False)
    )
    proxy_max_response_bytes: int = field(
        default_factory=lambda: _env_int("EMIX_PROXY_MAX_BYTES", 50 * 1024 * 1024)
    )

    # ── CORS ──
    cors_origins: Tuple[str, ...] = field(
        default_factory=lambda: tuple(
            x.strip() for x in os.environ.get("EMIX_CORS_ORIGINS", "").split(",")
            if x.strip()
        )
    )

    @property
    def cors_allow_credentials(self) -> bool:
        """Only allow credentials when origins are explicit (never with `*`)."""
        return bool(self.cors_origins)

    @property
    def cors_origins_list(self):
        """List of allowed origins, or `["*"]` if none configured (backward compat)."""
        return list(self.cors_origins) if self.cors_origins else ["*"]

    @property
    def xhttp_seq_buf_max_bytes(self) -> int:
        return self.xhttp_seq_buf_max_mb * 1024 * 1024


CONFIG = EmixConfig()
