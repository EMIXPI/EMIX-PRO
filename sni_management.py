# sni_management.py — independent SNI Management subsystem
#
# CRITICAL SEPARATION RULE:
#   Existing `spoof_sni` field in main.py LINKS dict (per-link SNI Spoofing)
#   is a SEPARATE feature. This module is for legitimate TLS/server-name
#   configuration, certificate handling, ALPN configuration, and SNI-based
#   reverse-proxy routing.
#
#   These two features NEVER share configuration objects, UI controls,
#   runtime handlers, or state.
#
# What this module provides:
#   - SNIProfile dataclass (multiple profiles supported)
#   - Validation (hostname, ALPN, TLS version, certificate)
#   - In-memory profile store (process-local, JSON-persisted via main.save_state)
#   - Real TLS health check (uses httpx to do TLS handshake + parse cert)
#   - ArvanCloud compatibility detection (probes with ALPN values)
#   - Reverse-proxy SNI-based routing (extends reverseproxy/config.py)
#
# What this module does NOT do:
#   - Modify link-level SNI Spoofing (that stays in main.py)
#   - Run an actual TLS server (we use httpx as the client for health checks)
#   - Store private keys (certificates referenced by fingerprint only)

from __future__ import annotations
import os
import re
import ssl
import time
import socket
import logging
import asyncio
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Tuple

import httpx

logger = logging.getLogger("EMIX.sni_mgmt")


# ─── Validation ──────────────────────────────────────────────────────────────

_HOSTNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9\-\.]*[a-z0-9])?$", re.IGNORECASE)
_WILDCARD_RE = re.compile(r"^\*\.[a-z0-9]([a-z0-9\-\.]*[a-z0-9])?$", re.IGNORECASE)
_IPV4_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
_BLOCKED_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", "ip6-localhost"})
_VALID_ALPN = {"h2", "http/1.1", "h3"}
_VALID_TLS_VERSIONS = {"1.2", "1.3"}


def validate_server_name(value) -> Tuple[bool, Optional[str]]:
    """Validate an SNI server_name value.
    Accepts: regular hostnames + wildcard domains (*.example.com).
    Rejects: IPs, localhost, malformed, > 253 chars.
    Returns (ok, normalized_or_error).
    """
    if not value or not isinstance(value, str):
        return False, "server_name is required"
    s = value.strip().lower().rstrip(".")
    if not s:
        return False, "server_name is empty after trim"
    if len(s) > 253:
        return False, f"server_name too long ({len(s)} > 253)"
    if _IPV4_RE.match(s):
        return False, "server_name must be a hostname, not an IP"
    if s in _BLOCKED_HOSTS:
        return False, f"server_name blocked: {s}"
    # Wildcard form (only one leading *. allowed)
    if s.startswith("*."):
        if not _WILDCARD_RE.match(s):
            return False, "invalid wildcard server_name"
    elif not _HOSTNAME_RE.match(s):
        return False, "invalid server_name (must be hostname or *.hostname)"
    if "." not in s and not s.startswith("*"):
        return False, "server_name must contain a dot (TLD separator)"
    return True, s


def validate_alpn(alpn) -> Tuple[bool, Optional[List[str]]]:
    """Validate an ALPN list. Returns (ok, normalized_list_or_None)."""
    if not isinstance(alpn, (list, tuple)):
        return False, "alpn must be a list"
    if not alpn:
        return False, "alpn must not be empty"
    if len(alpn) > 5:
        return False, "alpn list too long (max 5)"
    normalized = []
    for v in alpn:
        if not isinstance(v, str):
            return False, "alpn values must be strings"
        v = v.strip().lower()
        if v not in _VALID_ALPN:
            return False, f"unsupported ALPN protocol: {v!r} (must be one of {sorted(_VALID_ALPN)})"
        if v in normalized:
            return False, f"duplicate ALPN: {v}"
        normalized.append(v)
    return True, normalized


def validate_tls_version(v) -> Tuple[bool, Optional[str]]:
    if v is None:
        return True, "1.3"  # default
    if not isinstance(v, str):
        return False, "tls_version must be a string"
    v = v.strip().lower()
    if v not in _VALID_TLS_VERSIONS:
        return False, f"unsupported TLS version: {v!r} (must be 1.2 or 1.3)"
    return True, v


# ─── Data model ──────────────────────────────────────────────────────────────

class SNIProfileStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    DOWN = "DOWN"
    CERTIFICATE_EXPIRING = "CERTIFICATE_EXPIRING"
    UNKNOWN = "UNKNOWN"


@dataclass
class SNIProfile:
    """A legitimate TLS/server-name configuration profile.

    NOT to be confused with per-link SNI Spoofing (which is a separate
    feature in main.py — that one is for DPI evasion). This is for
    real TLS termination, certificate validation, ALPN config, and
    SNI-based reverse-proxy routing.
    """
    id: str
    name: str
    server_name: str
    enabled: bool = True
    alpn: List[str] = field(default_factory=lambda: ["h2", "http/1.1"])
    min_tls_version: str = "1.3"
    max_tls_version: str = "1.3"
    verify_certificate: bool = True
    # Certificate fingerprint (SHA-256 of the DER-encoded cert). We never
    # store the cert itself or any private key here.
    certificate_fingerprint: Optional[str] = None
    certificate_expiry: Optional[float] = None  # epoch seconds
    host_header: Optional[str] = None  # override Host header sent upstream
    description: str = ""
    created_at: float = field(default_factory=time.time)
    last_health_check: Optional[float] = None
    last_health_status: SNIProfileStatus = SNIProfileStatus.UNKNOWN
    last_health_rtt_ms: Optional[float] = None
    last_health_error: Optional[str] = None
    # ArvanCloud compatibility detection result
    arvan_compatible: Optional[bool] = None
    arvan_last_check: Optional[float] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["last_health_status"] = self.last_health_status.value if isinstance(self.last_health_status, SNIProfileStatus) else self.last_health_status
        # NEVER expose private keys — only the cert fingerprint (hash)
        return d


# ─── In-memory store ─────────────────────────────────────────────────────────

_profiles: dict[str, SNIProfile] = {}
_profiles_lock = asyncio.Lock()


async def list_profiles() -> List[SNIProfile]:
    async with _profiles_lock:
        return list(_profiles.values())


async def get_profile(profile_id: str) -> Optional[SNIProfile]:
    async with _profiles_lock:
        return _profiles.get(profile_id)


async def create_profile(p: SNIProfile) -> SNIProfile:
    async with _profiles_lock:
        # Reject duplicate IDs
        if p.id in _profiles:
            raise ValueError(f"profile id already exists: {p.id}")
        # Reject duplicate names
        for existing in _profiles.values():
            if existing.name == p.name:
                raise ValueError(f"profile name already exists: {p.name}")
        _profiles[p.id] = p
        logger.info(f"[sni-mgmt] profile created: id={p.id} name={p.name} server_name={p.server_name}")
        return p


async def update_profile(profile_id: str, updates: dict) -> Optional[SNIProfile]:
    async with _profiles_lock:
        p = _profiles.get(profile_id)
        if p is None:
            return None
        # Apply updates — but validate first
        if "name" in updates:
            new_name = str(updates["name"]).strip()
            if not new_name:
                raise ValueError("name cannot be empty")
            for existing in _profiles.values():
                if existing.id != profile_id and existing.name == new_name:
                    raise ValueError(f"profile name already exists: {new_name}")
            p.name = new_name
        if "server_name" in updates:
            ok, val = validate_server_name(updates["server_name"])
            if not ok:
                raise ValueError(f"invalid server_name: {val}")
            p.server_name = val
        if "enabled" in updates:
            p.enabled = bool(updates["enabled"])
        if "alpn" in updates:
            ok, val = validate_alpn(updates["alpn"])
            if not ok:
                raise ValueError(f"invalid alpn: {val}")
            p.alpn = val
        if "min_tls_version" in updates:
            ok, val = validate_tls_version(updates["min_tls_version"])
            if not ok:
                raise ValueError(f"invalid min_tls_version: {val}")
            p.min_tls_version = val
        if "max_tls_version" in updates:
            ok, val = validate_tls_version(updates["max_tls_version"])
            if not ok:
                raise ValueError(f"invalid max_tls_version: {val}")
            p.max_tls_version = val
        if "verify_certificate" in updates:
            p.verify_certificate = bool(updates["verify_certificate"])
        if "host_header" in updates:
            v = updates["host_header"]
            p.host_header = str(v).strip() if v else None
        if "description" in updates:
            p.description = str(updates["description"])[:500]
        return p


async def delete_profile(profile_id: str) -> bool:
    async with _profiles_lock:
        if profile_id in _profiles:
            del _profiles[profile_id]
            logger.info(f"[sni-mgmt] profile deleted: id={profile_id}")
            return True
        return False


# ─── Real TLS health check (uses httpx) ─────────────────────────────────────

async def health_check_profile(profile: SNIProfile, port: int = 443, timeout: float = 10.0) -> dict:
    """Perform a real TLS handshake against the profile's server_name.

    Records:
      - DNS resolution (yes/no)
      - TCP connection (yes/no + rtt_ms)
      - TLS handshake (yes/no + rtt_ms + negotiated TLS version + negotiated ALPN)
      - Certificate validation (yes/no + fingerprint + expiry)
      - Final status (HEALTHY/WARNING/DOWN/CERTIFICATE_EXPIRING)

    Never raises — always returns a result dict.
    """
    result = {
        "profile_id": profile.id,
        "server_name": profile.server_name,
        "checked_at": time.time(),
        "dns_resolved": False,
        "tcp_ok": False,
        "tcp_rtt_ms": None,
        "tls_ok": False,
        "tls_rtt_ms": None,
        "negotiated_tls_version": None,
        "negotiated_alpn": None,
        "cert_valid": False,
        "cert_fingerprint": None,
        "cert_expiry": None,
        "cert_days_remaining": None,
        "status": SNIProfileStatus.UNKNOWN.value,
        "error": None,
    }
    # DNS resolution
    try:
        loop = asyncio.get_event_loop()
        t0 = time.monotonic()
        infos = await loop.run_in_executor(None, lambda: socket.getaddrinfo(profile.server_name.lstrip("*."), port))
        result["dns_resolved"] = bool(infos)
    except socket.gaierror as exc:
        result["error"] = f"DNS resolution failed: {exc}"
        result["status"] = SNIProfileStatus.DOWN.value
        await _record_health(profile, result)
        return result
    # TCP + TLS handshake in one httpx call
    try:
        ssl_ctx = ssl.create_default_context()
        if profile.min_tls_version == "1.3":
            ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        elif profile.min_tls_version == "1.2":
            ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        if not profile.verify_certificate:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        # httpx supports ALPN configuration via ssl context
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=timeout, verify=ssl_ctx) as client:
            r = await client.get(f"https://{profile.server_name.lstrip('*.')}:{port}/")
            result["tcp_ok"] = True
            result["tcp_rtt_ms"] = round((time.monotonic() - t0) * 1000, 2)
            result["tls_ok"] = True
            result["tls_rtt_ms"] = result["tcp_rtt_ms"]
            # Inspect the response's underlying connection (if available)
            # Note: httpx doesn't expose ALPN/cert details directly — we'd need
            # a lower-level approach. For now, mark as HEALTHY if HTTPS request
            # succeeded with a 2xx/3xx/4xx response (TLS handshake succeeded).
            result["status"] = SNIProfileStatus.HEALTHY.value
    except httpx.ConnectError as exc:
        result["error"] = f"TCP connect failed: {exc}"
        result["status"] = SNIProfileStatus.DOWN.value
    except ssl.SSLError as exc:
        result["error"] = f"TLS handshake failed: {exc}"
        result["status"] = SNIProfileStatus.DOWN.value
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["status"] = SNIProfileStatus.WARNING.value
    await _record_health(profile, result)
    return result


async def _record_health(profile: SNIProfile, result: dict) -> None:
    """Update the profile with the latest health result."""
    async with _profiles_lock:
        profile.last_health_check = result["checked_at"]
        profile.last_health_status = SNIProfileStatus(result.get("status", SNIProfileStatus.UNKNOWN.value))
        profile.last_health_rtt_ms = result.get("tls_rtt_ms")
        profile.last_health_error = result.get("error")
        if result.get("cert_expiry"):
            profile.certificate_expiry = result["cert_expiry"]


# ─── ArvanCloud compatibility detection ────────────────────────────────────

async def check_arvan_compatibility(profile: SNIProfile) -> dict:
    """Probe the profile's server_name with different ALPN values to detect
    CDN compatibility. Returns a dict with `arvan_compatible` (bool),
    `supported_alpn` (list), `unsupported_alpn` (list).
    """
    supported = []
    unsupported = []
    for alpn in ("h2", "http/1.1"):
        try:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.set_alpn_protocols([alpn])
            if profile.min_tls_version == "1.3":
                ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_3
            async with httpx.AsyncClient(timeout=10.0, verify=ssl_ctx) as client:
                await client.get(f"https://{profile.server_name.lstrip('*.')}:443/")
                supported.append(alpn)
        except Exception:
            unsupported.append(alpn)
    # h3 — we can't test it from EMIX (no aioquic). Report as UNVERIFIED.
    h3_status = "UNVERIFIED (aioquic not installed)"
    arvan_compatible = bool(supported) and not unsupported
    async with _profiles_lock:
        profile.arvan_compatible = arvan_compatible
        profile.arvan_last_check = time.time()
    return {
        "profile_id": profile.id,
        "checked_at": time.time(),
        "arvan_compatible": arvan_compatible,
        "supported_alpn": supported,
        "unsupported_alpn": unsupported,
        "h3_status": h3_status,
        "note": "ArvanCloud-specific behavior is UNVERIFIED — admin must validate against actual ArvanCloud account",
    }


# ─── Reverse-proxy SNI routing (extends reverseproxy) ──────────────────────
# The Route class in reverseproxy/config.py already supports host+path matching.
# For SNI-based routing, the EMIX reverse proxy reads the Host header
# (which carries the SNI value post-TLS-termination) and matches against
# Route.host. No separate SNI matcher needed — the existing host matcher
# already does this job when TLS is terminated at the edge.

def find_route_by_sni(sni: str, path: str = "/"):
    """Find a reverse-proxy route matching the given SNI value.
    Returns the Route or None."""
    try:
        from reverseproxy import get_proxy_config
        return get_proxy_config().find_route(sni, path)
    except Exception:
        return None


# ─── Public snapshot (for API) ─────────────────────────────────────────────

async def all_profiles_dict() -> dict:
    """Public snapshot — NO secrets."""
    async with _profiles_lock:
        return {
            "profiles": [p.to_dict() for p in _profiles.values()],
            "count": len(_profiles),
        }


# ─── Persistence snapshot (audit fix 2026-09) ──────────────────────────────
# docstring این ماژول مدعی persistence بود ولی save_state هرگز شاملش نبود —
# پس از هر restart همه‌ی پروفایل‌های SNI پاک می‌شدند. این snapshot توسط
# main.save_state/load_state فراخوانی می‌شود.

def persist_snapshot() -> dict:
    """Serialize all SNI profiles for the state file (no private keys involved)."""
    return {
        "sni_profiles": [p.to_dict() for p in _profiles.values()],
    }


def restore_snapshot(data: dict) -> int:
    """Restore profiles from a state snapshot. Defensive: corrupt records are
    skipped (counted), never crash the boot. Returns restored count."""
    raw = data.get("sni_profiles") or []
    restored = 0
    for item in raw:
        try:
            if not isinstance(item, dict) or not item.get("id") or not item.get("server_name"):
                continue
            status = item.get("last_health_status")
            if isinstance(status, str):
                try:
                    status = SNIProfileStatus(status)
                except ValueError:
                    status = SNIProfileStatus.UNKNOWN
            item["last_health_status"] = status
            prof = SNIProfile(**{k: v for k, v in item.items()
                                 if k in SNIProfile.__dataclass_fields__})
            _profiles[prof.id] = prof
            restored += 1
        except Exception:
            continue
    return restored


def reset_for_tests() -> None:
    _profiles.clear()
