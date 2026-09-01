# endpoint_profiles.py — Endpoint & Transport Profile Engine
#
# REFARCH (Phases 4 & 25): this module REPLACES the legacy "SNI Spoofing"
# concept with a structured endpoint configuration engine.
#
# Migration compatibility (Phase 33 — do not break existing users):
#   * Legacy per-link fields `spoof_sni` / `spoof_sni_enabled` keep working.
#     resolve() reads them and produces exactly the same Mode-A (CDN) /
#     Mode-B (direct + allowInsecure) semantics as before.
#   * New links may instead reference a named EndpointProfile
#     (`endpoint_profile_id`) or inline endpoint dict.
#   * The legacy `_get_effective_sni` / `_validate_sni` helpers in main.py
#     remain functional; this module is their canonical successor.
#
# Honesty rules (Phase 32):
#   * SNI override only applies where the client link actually carries an
#     sni/host parameter (compat.sni_override_supported). For SS/MTProto it
#     is rejected with an actionable error instead of being silently dropped.
#   * We never claim SNI changes the network path: Mode A routes through a
#     CDN edge (address change), Mode B only changes the ClientHello value.

from __future__ import annotations
import re
import time
import asyncio
import secrets
from dataclasses import dataclass, field, asdict
from typing import Optional, List

import compat

# ── Validation (superset of the legacy _validate_sni rules) ─────────────────

_HOSTNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9\-\.]*[a-z0-9])?$", re.IGNORECASE)
_IPV4_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
_BLOCKED_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", "ip6-localhost"})
_VALID_IP_VERSIONS = {"ipv4", "ipv6", "auto"}
_VALID_DNS_MODES = {"auto", "system", "doh"}


def validate_hostname(value, allow_ip: bool = False) -> tuple[bool, Optional[str]]:
    """Validate a hostname (or IP when allow_ip=True). Returns (ok, normalized)."""
    if not value or not isinstance(value, str):
        return False, None
    s = value.strip().lower().rstrip(".")
    if not s or len(s) > 253:
        return False, None
    if not _IPV4_RE.match(s) and not _HOSTNAME_RE.match(s):
        return False, None
    if _IPV4_RE.match(s) and not allow_ip:
        return False, None
    if s in _BLOCKED_HOSTS:
        return False, None
    if "." not in s and not allow_ip:
        return False, None
    return True, s


def validate_port(value) -> tuple[bool, Optional[int]]:
    try:
        p = int(value)
    except (TypeError, ValueError):
        return False, None
    if not (1 <= p <= 65535):
        return False, None
    return True, p


# ── Profile model ───────────────────────────────────────────────────────────

@dataclass
class EndpointProfile:
    """A structured endpoint / transport profile.

    Field semantics:
      address       — where the client actually connects (CDN edge, bridge IP, panel host)
      sni           — TLS ServerName sent in ClientHello (defaults to address)
      host_header   — HTTP Host / WS Host header (defaults to address)
      port          — TLS port (default 443)
      path_prefix   — prefix injected before the protocol path (e.g. /loc/auto for worker gateway)
      security      — tls | none (reality is validated by compat, not stored here)
      alpn          — list of ALPN values offered by the client
      min_tls       — "1.2" | "1.3"
      allow_insecure— skip cert verification (Mode-B legacy; surfaced explicitly)
      ip_version    — ipv4 | ipv6 | auto preference for resolution
      dns_mode      — auto | system | doh
      node_id       — optional association to a managed node
      transport     — optional transport hint validated against compat
    """
    id: str
    name: str
    address: str
    sni: Optional[str] = None
    host_header: Optional[str] = None
    port: int = 443
    path_prefix: str = ""
    security: str = "tls"
    alpn: List[str] = field(default_factory=lambda: ["h2", "http/1.1"])
    min_tls: str = "1.3"
    allow_insecure: bool = False
    ip_version: str = "auto"
    dns_mode: str = "auto"
    node_id: Optional[str] = None
    transport: Optional[str] = None
    description: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Resolved endpoint (the single output consumed by the Config Compiler) ──

@dataclass
class ResolvedEndpoint:
    address: str            # connection host
    sni: str                # TLS server name
    host_header: str        # HTTP Host header
    port: int
    path_prefix: str
    security: str
    alpn: List[str]
    allow_insecure: bool
    mode: str               # "standard" | "cdn" | "direct-sni" | "profile"
    profile_id: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── In-memory profile store (persisted via main.save_state snapshot) ───────

_profiles: dict[str, EndpointProfile] = {}
_profiles_lock = asyncio.Lock()


async def list_profiles() -> List[EndpointProfile]:
    async with _profiles_lock:
        return list(_profiles.values())


async def get_profile(profile_id: str) -> Optional[EndpointProfile]:
    async with _profiles_lock:
        return _profiles.get(profile_id)


async def create_profile(p: EndpointProfile) -> EndpointProfile:
    errors = validate_profile(p)
    if errors:
        raise ValueError("; ".join(errors))
    async with _profiles_lock:
        if p.id in _profiles:
            raise ValueError(f"profile id already exists: {p.id}")
        for existing in _profiles.values():
            if existing.name == p.name:
                raise ValueError(f"profile name already exists: {p.name}")
        _profiles[p.id] = p
    return p


async def update_profile(profile_id: str, updates: dict) -> Optional[EndpointProfile]:
    async with _profiles_lock:
        p = _profiles.get(profile_id)
        if p is None:
            return None
        snapshot = p.to_dict()
        snapshot.update({k: v for k, v in updates.items() if k in (
            "name", "address", "sni", "host_header", "port", "path_prefix",
            "security", "alpn", "min_tls", "allow_insecure", "ip_version",
            "dns_mode", "node_id", "transport", "description",
        )})
        candidate = EndpointProfile(**snapshot)
        errors = validate_profile(candidate)
        if errors:
            raise ValueError("; ".join(errors))
        _profiles[profile_id] = candidate
        return candidate


async def delete_profile(profile_id: str) -> bool:
    async with _profiles_lock:
        if profile_id in _profiles:
            del _profiles[profile_id]
            return True
        return False


def validate_profile(p: EndpointProfile) -> List[str]:
    """Structural + compatibility validation. Returns list of errors (empty = ok)."""
    errors: List[str] = []
    if not p.id or not re.fullmatch(r"[a-z0-9\-_]{3,40}", (p.id or "").lower()):
        errors.append("id must be 3-40 chars of a-z0-9-_")
    if not p.name or len(p.name) > 60:
        errors.append("name required, max 60 chars")
    ok, addr = validate_hostname(p.address, allow_ip=True)
    if not ok:
        errors.append(f"invalid address: {p.address!r}")
    else:
        p.address = addr
    for optional_host_field in ("sni", "host_header"):
        v = getattr(p, optional_host_field)
        if v:
            ok_h, h = validate_hostname(v)
            if not ok_h:
                errors.append(f"invalid {optional_host_field}: {v!r} (must be hostname, not IP)")
            else:
                setattr(p, optional_host_field, h)
    ok_p, port = validate_port(p.port)
    if not ok_p:
        errors.append(f"invalid port: {p.port!r}")
    else:
        p.port = port
    if p.path_prefix and not p.path_prefix.startswith("/"):
        errors.append("path_prefix must start with '/'")
    if p.security not in ("tls", "none"):
        errors.append("security must be tls|none")
    if p.min_tls not in ("1.2", "1.3"):
        errors.append("min_tls must be 1.2|1.3")
    if not isinstance(p.alpn, (list, tuple)) or not p.alpn or len(set(p.alpn)) != len(p.alpn):
        errors.append("alpn must be a non-empty list without duplicates")
    else:
        for a in p.alpn:
            if a not in ("h2", "http/1.1", "h3"):
                errors.append(f"invalid alpn value: {a!r}")
    if p.ip_version not in _VALID_IP_VERSIONS:
        errors.append(f"ip_version must be one of {sorted(_VALID_IP_VERSIONS)}")
    if p.dns_mode not in _VALID_DNS_MODES:
        errors.append(f"dns_mode must be one of {sorted(_VALID_DNS_MODES)}")
    # Cross-compat: if the profile declares a transport hint, validate it.
    if p.transport:
        c = compat.validate("vless", p.transport, p.security)
        if not c.ok and "no server runtime" in " ".join(c.reasons):
            errors.append(f"transport hint incompatible: {c.reasons[0]}")
    return errors


def validate_profile_for_protocol(profile: EndpointProfile, fused_protocol: str) -> List[str]:
    """Compatibility between a profile and a protocol/transport combo."""
    errors: List[str] = []
    p, t = compat.decompose(fused_protocol)
    if p not in compat.PRODUCTION_PROTOCOLS and p not in compat.PROTOCOLS:
        errors.append(f"unknown protocol: {fused_protocol}")
        return errors
    if profile.sni and not compat.sni_override_supported(fused_protocol):
        errors.append(
            f"SNI override not applicable to {fused_protocol} "
            f"(link carries no sni parameter — override would be silently ignored)"
        )
    if profile.transport and profile.transport != t:
        errors.append(
            f"profile transport '{profile.transport}' != protocol transport '{t}'"
        )
    if profile.security == "none" and compat.decompose(fused_protocol)[0] != "mtproto":
        c = compat.validate(p, t, "none")
        if not c.ok:
            errors.append(f"security 'none' rejected for {fused_protocol}: {c.reasons}")
    return errors


# ── Persistence bridge (called from main.save_state / load_state) ───────────

def persist_snapshot() -> dict:
    return {"endpoint_profiles": [p.to_dict() for p in _profiles.values()]}


def restore_snapshot(data: dict) -> None:
    _profiles.clear()
    for d in (data or {}).get("endpoint_profiles", []):
        try:
            _profiles[d["id"]] = EndpointProfile(**{
                k: v for k, v in d.items()
                if k in EndpointProfile.__dataclass_fields__
            })
        except Exception:
            continue


def new_profile_id() -> str:
    return f"ep-{secrets.token_hex(4)}"


# ── The resolver — canonical successor of the inline SNI-spoof logic ────────

def resolve(link: dict, host: str, cdn_domain: str = "") -> ResolvedEndpoint:
    """Resolve the effective endpoint for a link record.

    Precedence:
      1. endpoint_profile_id → named profile (new API)
      2. inline link["endpoint"] dict (new API)
      3. legacy spoof_sni/spoof_sni_enabled (Mode A / Mode B — wire compat)
      4. standard: everything = host

    Never raises; invalid pieces fall back with a note (legacy links must
    keep working), while NEW profile application is strictly validated at
    the API layer beforehand.
    """
    notes: List[str] = []

    # 1. named profile
    pid = link.get("endpoint_profile_id")
    if pid:
        profile = _profiles.get(pid)
        if profile is None:
            notes.append(f"endpoint profile '{pid}' not found — falling back to standard")
        else:
            return ResolvedEndpoint(
                address=profile.address,
                sni=profile.sni or profile.address,
                host_header=profile.host_header or profile.address,
                port=profile.port,
                path_prefix=profile.path_prefix or "",
                security=profile.security,
                alpn=list(profile.alpn),
                allow_insecure=profile.allow_insecure,
                mode="profile",
                profile_id=profile.id,
                notes=notes,
            )

    # 2. inline endpoint dict
    inline = link.get("endpoint")
    if isinstance(inline, dict) and inline.get("address"):
        ok, addr = validate_hostname(inline.get("address"), allow_ip=True)
        if ok:
            sni = inline.get("sni") or addr
            ok_s, sni_n = validate_hostname(sni)
            if not ok_s:
                sni_n, notes = addr, notes + [f"invalid inline sni {sni!r} — using address"]
            hh = inline.get("host_header") or addr
            return ResolvedEndpoint(
                address=addr,
                sni=sni_n,
                host_header=hh,
                port=inline.get("port") or 443,
                path_prefix=inline.get("path_prefix") or "",
                security=inline.get("security") or "tls",
                alpn=inline.get("alpn") or ["h2", "http/1.1"],
                allow_insecure=bool(inline.get("allow_insecure")),
                mode="profile",
                profile_id=inline.get("profile_id"),
                notes=notes,
            )
        notes.append("invalid inline endpoint.address — falling back")

    # 3. legacy spoof fields (exact wire-compat with the old inline logic)
    spoof_enabled = bool(link.get("spoof_sni_enabled"))
    spoof_value = link.get("spoof_sni")
    spoof_valid = spoof_enabled and validate_hostname(spoof_value)[0]
    spoof = validate_hostname(spoof_value)[1] if spoof_valid else None
    cdn = (cdn_domain or "").strip().lower()

    if spoof_enabled and spoof and cdn:
        # Mode A — CDN routing: client connects to the CDN edge, cert is the
        # CDN's, SNI carries the profile domain.
        return ResolvedEndpoint(
            address=cdn, sni=spoof, host_header=cdn, port=443, path_prefix="",
            security="tls", alpn=["h2", "http/1.1"], allow_insecure=False,
            mode="cdn", notes=notes,
        )
    if spoof_enabled and spoof and not cdn:
        # Mode B — direct + allowInsecure (legacy semantics, surfaced honestly)
        return ResolvedEndpoint(
            address=host, sni=spoof, host_header=host, port=443, path_prefix="",
            security="tls", alpn=["h2", "http/1.1"], allow_insecure=True,
            mode="direct-sni",
            notes=notes + ["allowInsecure=1: client skips cert verification (no MITM protection)"],
        )

    # 4. standard
    return ResolvedEndpoint(
        address=host, sni=host, host_header=host, port=443, path_prefix="",
        security="tls", alpn=["h2", "http/1.1"], allow_insecure=False,
        mode="standard", notes=notes,
    )
