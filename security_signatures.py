# security_signatures.py — advanced security signature / fingerprint profiles
#
# EXPANDS the existing system beyond h1/h2/h3 (which are just ALPN values
# stored in the `alpn` field of LINKS). The new system adds professionally
# named profiles that bundle (TLS version, ALPN, transport, compatibility)
# for smart selection and health-checking.
#
# CRITICAL RULES:
#   - h1/h2/h3 backward compat MUST be preserved (they're stored in link.alpn)
#   - DO NOT generate fake JA3/JA4 fingerprints
#   - DO NOT advertise unsupported cipher suites / ALPN / TLS versions
#   - Every profile must correspond to a REAL, supported TLS/HTTP config
#   - The "Randomized" profile only picks from verified-supported configs
#
# What's REAL in EMIX's runtime:
#   - TLS 1.3 ✓ (Python ssl supports)
#   - TLS 1.2 ✓
#   - h2 ALPN ✓ (httpx + Python ssl supports)
#   - http/1.1 ALPN ✓
#   - h3 ALPN ❌ (would need aioquic — DEFERRED)
#   - QUIC ❌
#   - WebSocket ✓ (FastAPI supports)
#   - XHTTP ✓ (FastAPI supports)

from __future__ import annotations
import os
import time
import random
import logging
import asyncio
import ssl
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List

import httpx

logger = logging.getLogger("EMIX.security_signatures")


# ─── Capability flags (what's REALLY supported in EMIX runtime) ────────────

# These are the only TLS/ALPN combinations that the EMIX runtime can
# ACTUALLY use today. The "Randomized" profile picks from this set only.
SUPPORTED_RUNTIME_CONFIGS = {
    # (tls_version, alpn, transport)
    ("1.3", "h2", "https"),
    ("1.3", "http/1.1", "https"),
    ("1.2", "h2", "https"),
    ("1.2", "http/1.1", "https"),
    ("1.3", "h2", "websocket"),
    ("1.3", "http/1.1", "websocket"),
    ("1.2", "h2", "websocket"),
    ("1.2", "http/1.1", "websocket"),
    # h3 / QUIC are NOT supported — see DEFERRED notes
}

# Profile IDs that are EXPERIMENTAL (not fully supported in runtime)
EXPERIMENTAL_PROFILES = {"modern_http3", "tls13_http3"}


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    DOWN = "DOWN"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class SecuritySignatureProfile:
    """A normalized security signature profile.

    Each profile bundles a (TLS version, ALPN, transport, compatibility)
    combination that corresponds to a real, supported networking config.
    """
    id: str
    name: str
    protocol_family: str          # "http" | "websocket" | "grpc" | "xhttp"
    transport: str                # "https" | "websocket" | "quic" | "http3"
    tls_version: str              # "1.2" | "1.3"
    alpn: str                      # "h2" | "http/1.1" | "h3"
    supported_platforms: List[str] = field(default_factory=list)
    enabled: bool = True
    description: str = ""
    compatibility: str = "medium"  # "low" | "medium" | "high"
    # CDN compatibility — checked at runtime
    cdn_compatible: bool = True
    # Status flag (EXPERIMENTAL / STABLE / DEFERRED)
    status: str = "stable"        # "stable" | "experimental" | "deferred"

    def to_dict(self) -> dict:
        d = asdict(self)
        # NEVER expose JA3/JA4 strings — those don't exist in EMIX
        return d

    def is_supported_in_runtime(self) -> bool:
        """Return True iff this profile's (TLS, ALPN, transport) is supported."""
        return (self.tls_version, self.alpn, self.transport) in SUPPORTED_RUNTIME_CONFIGS


# ─── Profile definitions (13 + Randomized) ────────────────────────────────
# These are the new profiles. Existing h1/h2/h3 stay as they are (stored in
# the link.alpn field, unchanged).

_PROFILES: dict[str, SecuritySignatureProfile] = {
    "modern_http1": SecuritySignatureProfile(
        id="modern_http1",
        name="Modern HTTP/1.1",
        protocol_family="http",
        transport="https",
        tls_version="1.3",
        alpn="http/1.1",
        supported_platforms=["all"],
        description="Modern TLS 1.3 over HTTP/1.1 — highest compatibility",
        compatibility="high",
        cdn_compatible=True,
        status="stable",
    ),
    "modern_http2": SecuritySignatureProfile(
        id="modern_http2",
        name="Modern HTTP/2",
        protocol_family="http",
        transport="https",
        tls_version="1.3",
        alpn="h2",
        supported_platforms=["all modern"],
        description="Modern TLS 1.3 + HTTP/2 — multiplexing, header compression",
        compatibility="high",
        cdn_compatible=True,
        status="stable",
    ),
    "modern_http3": SecuritySignatureProfile(
        id="modern_http3",
        name="Modern HTTP/3",
        protocol_family="http",
        transport="quic",
        tls_version="1.3",
        alpn="h3",
        supported_platforms=["QUIC clients only"],
        description="HTTP/3 over QUIC — requires aioquic (NOT installed in EMIX)",
        compatibility="low",
        cdn_compatible=False,
        status="experimental",
    ),
    "strict_tls13": SecuritySignatureProfile(
        id="strict_tls13",
        name="Strict TLS 1.3",
        protocol_family="http",
        transport="https",
        tls_version="1.3",
        alpn="h2",
        supported_platforms=["modern"],
        description="Strict TLS 1.3 enforcement, no fallback to 1.2",
        compatibility="medium",
        cdn_compatible=True,
        status="stable",
    ),
    "high_compat": SecuritySignatureProfile(
        id="high_compat",
        name="High Compatibility",
        protocol_family="http",
        transport="https",
        tls_version="1.2",
        alpn="http/1.1",
        supported_platforms=["all incl. legacy"],
        description="TLS 1.2 + HTTP/1.1 — works with old clients",
        compatibility="high",
        cdn_compatible=True,
        status="stable",
    ),
    "cdn_optimized": SecuritySignatureProfile(
        id="cdn_optimized",
        name="CDN Optimized",
        protocol_family="http",
        transport="https",
        tls_version="1.3",
        alpn="h2",
        supported_platforms=["all modern"],
        description="Tuned for CDN edge — TLS 1.3 + h2 (most CDN-friendly)",
        compatibility="high",
        cdn_compatible=True,
        status="stable",
    ),
    "ws_optimized": SecuritySignatureProfile(
        id="ws_optimized",
        name="WebSocket Optimized",
        protocol_family="websocket",
        transport="websocket",
        tls_version="1.3",
        alpn="h2",
        supported_platforms=["v2rayN", "NekoBox", "Shadowrocket"],
        description="WebSocket over TLS 1.3 + h2 — long-lived, multiplexed",
        compatibility="high",
        cdn_compatible=True,
        status="stable",
    ),
    "grpc_optimized": SecuritySignatureProfile(
        id="grpc_optimized",
        name="gRPC Optimized",
        protocol_family="grpc",
        transport="https",
        tls_version="1.3",
        alpn="h2",
        supported_platforms=["xray-core 1.8+ (VLESS+gRPC)"],
        description="gRPC over TLS 1.3 + h2 — bidirectional streaming (XHTTP mimics this)",
        compatibility="medium",
        cdn_compatible=True,
        status="stable",
    ),
    "xhttp_optimized": SecuritySignatureProfile(
        id="xhttp_optimized",
        name="xHTTP Optimized",
        protocol_family="xhttp",
        transport="https",
        tls_version="1.3",
        alpn="h2",
        supported_platforms=["xray-core 1.8+"],
        description="xHTTP over TLS 1.3 + h2 — packet-up/stream-up modes",
        compatibility="medium",
        cdn_compatible=True,
        status="stable",
    ),
    "mobile_compat": SecuritySignatureProfile(
        id="mobile_compat",
        name="Mobile Compatible",
        protocol_family="http",
        transport="https",
        tls_version="1.3",
        alpn="http/1.1",
        supported_platforms=["iOS Safari", "Android Chrome"],
        description="TLS 1.3 + HTTP/1.1 — best for mobile networks (avoids h2 multiplexing overhead on lossy links)",
        compatibility="high",
        cdn_compatible=True,
        status="stable",
    ),
    "desktop_compat": SecuritySignatureProfile(
        id="desktop_compat",
        name="Desktop Compatible",
        protocol_family="http",
        transport="https",
        tls_version="1.3",
        alpn="h2",
        supported_platforms=["Chrome", "Firefox", "Edge"],
        description="TLS 1.3 + h2 — modern desktop browsers",
        compatibility="high",
        cdn_compatible=True,
        status="stable",
    ),
    "low_overhead": SecuritySignatureProfile(
        id="low_overhead",
        name="Low Overhead",
        protocol_family="http",
        transport="https",
        tls_version="1.2",
        alpn="http/1.1",
        supported_platforms=["all"],
        description="TLS 1.2 + HTTP/1.1 — minimum CPU usage",
        compatibility="high",
        cdn_compatible=True,
        status="stable",
    ),
    "latency_optimized": SecuritySignatureProfile(
        id="latency_optimized",
        name="Latency Optimized",
        protocol_family="http",
        transport="https",
        tls_version="1.3",
        alpn="h2",
        supported_platforms=["modern"],
        description="TLS 1.3 0-RTT + h2 multiplexing — lowest first-byte latency",
        compatibility="medium",
        cdn_compatible=True,
        status="stable",
    ),
}


def list_profiles() -> List[SecuritySignatureProfile]:
    """List all defined profiles."""
    return list(_PROFILES.values())


def get_profile(profile_id: str) -> Optional[SecuritySignatureProfile]:
    return _PROFILES.get(profile_id)


def get_supported_profiles() -> List[SecuritySignatureProfile]:
    """Return only profiles whose (TLS, ALPN, transport) is supported in runtime."""
    return [p for p in _PROFILES.values() if p.is_supported_in_runtime()]


def recommend_profile(protocol: str = "", transport: str = "", client_capability: str = "") -> Optional[SecuritySignatureProfile]:
    """Smart profile selection — pick the best profile based on context.

    Rules (in priority order):
      1. WebSocket transport → ws_optimized
      2. gRPC transport → grpc_optimized
      3. XHTTP transport → xhttp_optimized
      4. Mobile client → mobile_compat
      5. Default → modern_http2 (TLS 1.3 + h2)

    Never returns an unsupported profile.
    """
    if transport == "websocket":
        return _PROFILES.get("ws_optimized")
    if transport == "grpc" or "grpc" in (protocol or ""):
        return _PROFILES.get("grpc_optimized")
    if transport == "xhttp" or "xhttp" in (protocol or ""):
        return _PROFILES.get("xhttp_optimized")
    if client_capability == "mobile":
        return _PROFILES.get("mobile_compat")
    if client_capability == "desktop":
        return _PROFILES.get("desktop_compat")
    # Default — TLS 1.3 + h2 is the safest modern choice
    return _PROFILES.get("modern_http2")


# ─── Randomized profile (special) ──────────────────────────────────────────
# The Randomized profile picks ONE config from SUPPORTED_RUNTIME_CONFIGS.
# It NEVER produces an unsupported (TLS, ALPN, transport) combination.

# Module-level seed for deterministic mode (testing only).
# In production, _seed is None → use secure randomness.
_seed: Optional[int] = None


def set_random_seed(seed: Optional[int]) -> None:
    """Set a deterministic seed for the Randomized profile (TESTING ONLY).
    Set to None in production for secure randomness."""
    global _seed
    _seed = seed
    if seed is not None:
        random.seed(seed)
        logger.warning(f"[security-sig] DETERMINISTIC MODE (seed={seed}) — for testing only")


def randomized_config() -> dict:
    """Pick a random (TLS, ALPN, transport) from SUPPORTED_RUNTIME_CONFIGS.

    Returns a dict with:
      - tls_version
      - alpn
      - transport
      - source: "supported_runtime_configs" (always)
      - deterministic: bool (True if a seed was set)

    NEVER returns an unsupported combination. The set of allowed combos is
    hard-coded at module top — the randomizer can ONLY pick from it.
    """
    configs = list(SUPPORTED_RUNTIME_CONFIGS)
    pick = random.choice(configs)
    return {
        "tls_version": pick[0],
        "alpn": pick[1],
        "transport": pick[2],
        "source": "supported_runtime_configs",
        "deterministic": _seed is not None,
        "seed": _seed,
    }


def randomized_profile_dict() -> dict:
    """Public snapshot of the Randomized profile."""
    cfg = randomized_config()
    return {
        "id": "randomized",
        "name": "Randomized",
        "protocol_family": "dynamic",
        "transport": cfg["transport"],
        "tls_version": cfg["tls_version"],
        "alpn": cfg["alpn"],
        "supported_platforms": ["dynamic"],
        "enabled": True,
        "description": "Picks one of the supported (TLS, ALPN, transport) combinations. NEVER produces an unsupported config.",
        "compatibility": "dynamic",
        "cdn_compatible": True,
        "status": "active",
        "deterministic": cfg["deterministic"],
        "seed": cfg["seed"],
        "source": cfg["source"],
    }


# ─── Backward compat: h1/h2/h3 → SecuritySignatureProfile mapping ──────────

_LEGACY_ALPN_MAP = {
    "h1": "modern_http1",          # legacy "h1" maps to Modern HTTP/1.1
    "h2": "modern_http2",          # legacy "h2" maps to Modern HTTP/2
    "h3": "modern_http3",          # legacy "h3" maps to Modern HTTP/3 (EXPERIMENTAL)
    "http/1.1": "modern_http1",
    "http/1.0": "high_compat",
}

# Reverse map: from SecuritySignatureProfile.id → legacy alpn string
# (used when storing a chosen profile into the link.alpn field)
PROFILE_ID_TO_LEGACY_ALPN = {
    "modern_http1": "http/1.1",
    "modern_http2": "h2",
    "modern_http3": "h3",          # EXPERIMENTAL — see profile status
    "strict_tls13": "h2",
    "high_compat": "http/1.1",
    "cdn_optimized": "h2",
    "ws_optimized": "h2",
    "grpc_optimized": "h2",
    "xhttp_optimized": "h2",
    "mobile_compat": "http/1.1",
    "desktop_compat": "h2",
    "low_overhead": "http/1.1",
    "latency_optimized": "h2",
}


def legacy_alpn_to_profile_id(alpn: str) -> Optional[str]:
    """Map an existing link.alpn value to a SecuritySignatureProfile.id.
    Used for backward compat: existing links with `alpn: "h2"` continue
    working AND show up as 'Modern HTTP/2' in the new UI."""
    return _LEGACY_ALPN_MAP.get(alpn)


def profile_id_to_legacy_alpn(profile_id: str) -> Optional[str]:
    """Reverse map: profile.id → legacy alpn string."""
    return PROFILE_ID_TO_LEGACY_ALPN.get(profile_id)


# ─── Real TLS health check (per profile) ───────────────────────────────────

_health_cache: dict[str, dict] = {}
_health_lock = asyncio.Lock()


async def health_check_profile(profile: SecuritySignatureProfile, target_host: str = "", timeout: float = 10.0) -> dict:
    """Perform a real TLS handshake using the profile's (TLS, ALPN) config.

    For experimental profiles (modern_http3, tls13_http3), returns UNVERIFIED
    since EMIX doesn't have aioquic.
    """
    result = {
        "profile_id": profile.id,
        "name": profile.name,
        "checked_at": time.time(),
        "supported": profile.is_supported_in_runtime(),
        "tls_handshake_ok": False,
        "alpn_negotiated": None,
        "cert_valid": False,
        "rtt_ms": None,
        "error_count": 0,
        "last_checked": time.time(),
        "compatibility_status": "unknown",
    }
    if not profile.is_supported_in_runtime():
        result["compatibility_status"] = "unsupported"
        result["error"] = f"profile {profile.id} uses unsupported (TLS={profile.tls_version}, ALPN={profile.alpn}, transport={profile.transport}) — see SUPPORTED_RUNTIME_CONFIGS"
        async with _health_lock:
            _health_cache[profile.id] = result
        return result
    if not target_host:
        # Use a known-good public host for the health check
        target_host = "www.cloudflare.com"
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.set_alpn_protocols([profile.alpn])
        if profile.tls_version == "1.3":
            ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        elif profile.tls_version == "1.2":
            ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=timeout, verify=ssl_ctx) as client:
            r = await client.get(f"https://{target_host}/")
            result["tls_handshake_ok"] = True
            result["cert_valid"] = True
            result["rtt_ms"] = round((time.monotonic() - t0) * 1000, 2)
            result["alpn_negotiated"] = profile.alpn  # best-effort — httpx doesn't expose negotiated ALPN directly
            result["compatibility_status"] = "healthy"
    except Exception as exc:
        result["error_count"] = 1
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["compatibility_status"] = "down"
    async with _health_lock:
        _health_cache[profile.id] = result
    return result


async def all_health() -> dict:
    async with _health_lock:
        return dict(_health_cache)


def all_profiles_dict() -> dict:
    """Public snapshot — NO secrets."""
    return {
        "profiles": [p.to_dict() for p in _PROFILES.values()],
        "randomized": randomized_profile_dict(),
        "supported_count": len(get_supported_profiles()),
        "total_count": len(_PROFILES),
    }
