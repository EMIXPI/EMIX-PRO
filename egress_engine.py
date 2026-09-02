# egress_engine.py — Egress & Route Truth Engine (v11.2.0-egress)
# ══════════════════════════════════════════════════════════════════════════════
# CRITICAL PRODUCTION DEFECT FIX — FALSE EGRESS / CUSTOM IP SEMANTICS
#
#   Observed in production:
#     Selected node      : Railway — Amsterdam
#     Configured custom IP: 185.164.73.192
#     Actual egress       : 208.77.244.84  (Railway, Amsterdam)
#
#   Therefore:
#     CUSTOM_IP  != REAL_EGRESS_IP
#     SNI        != ROUTING
#     HOSTNAME   != ROUTING
#     TLS_SERVER_NAME != ROUTING
#
# This module is the SINGLE SOURCE OF TRUTH for everything egress/route/role:
#
#   NODE ROLES      — CONTROL_PLANE / EXIT_NODE / RELAY_NODE / EDGE_NODE / HYBRID
#   EGRESS CLASS    — VERIFIED_EGRESS / CONFIGURED_ONLY / UNKNOWN
#   ROUTE STATUS    — DIRECT / RELAY / VERIFIED / UNKNOWN
#   ROUTE HEALTH    — HEALTHY / ROUTE_MISMATCH / NO_EXIT_NODE_AVAILABLE /
#                     DEGRADED / UNREACHABLE / UNKNOWN
#   HEALTH LAYERS   — APPLICATION_HEALTH / NODE_HEALTH / ROUTE_HEALTH /
#                     EGRESS_HEALTH  (a healthy Railway API says NOTHING about
#                     VPN egress health)
#   LATENCY LABELS  — control_plane_rtt / node_rtt / route_rtt /
#                     protocol_handshake_rtt  (never one unnamed "ping")
#
# Routing model represented explicitly:
#
#   Client → EMIX endpoint (entry) → relay → exit node → Internet → egress
#
# Rules enforced here (pure, unit-tested):
#   * A configured/advertised address is NEVER reported as the actual egress IP.
#   * SNI / hostname / TLS server name / DNS / HTTP Host never influence the
#     egress classification (they are endpoint-layer values, not routing).
#   * A Railway upstream always derives the CONTROL_PLANE role — it can never
#     masquerade as an arbitrary-country exit node; expected≠observed ⇒
#     ROUTE_MISMATCH, never HEALTHY.
#   * Country selection without a real exit node ⇒ NO_EXIT_NODE_AVAILABLE
#     (the location is not faked).
#
# Evidence lifecycle: every verification stores an EgressEvidence record with
# checked_at / expires_at. Stale evidence degrades to UNKNOWN — a configured
# IP never silently "becomes" the verified egress again.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import ipaddress
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable, Dict, List

import httpx
# NOTE: Request/Depends must be MODULE-level so FastAPI can resolve the
# string annotations produced by `from __future__ import annotations`.
from fastapi import Depends, Request
from fastapi.responses import JSONResponse

# ── Taxonomies (public contract — UI and tests consume these) ───────────────

NODE_ROLES = ("CONTROL_PLANE", "EXIT_NODE", "RELAY_NODE", "EDGE_NODE", "HYBRID")
EGRESS_CLASSIFICATIONS = ("VERIFIED_EGRESS", "CONFIGURED_ONLY", "UNKNOWN")
ROUTE_STATUSES = ("DIRECT", "RELAY", "VERIFIED", "UNKNOWN")
ROUTE_HEALTH_STATES = ("HEALTHY", "ROUTE_MISMATCH", "NO_EXIT_NODE_AVAILABLE",
                       "DEGRADED", "UNREACHABLE", "UNKNOWN")
HEALTH_LAYERS = ("APPLICATION_HEALTH", "NODE_HEALTH", "ROUTE_HEALTH",
                 "PROTOCOL_HEALTH", "EGRESS_HEALTH")
LATENCY_MEASURES = ("control_plane_rtt", "node_rtt", "route_rtt",
                    "protocol_handshake_rtt")

EGRESS_ENGINE_VERSION = "1.0.0"
EGRESS_EVIDENCE_TTL = 300.0        # s — verified egress older than this → UNKNOWN
ROUTE_HISTORY_BOUND = 50           # bounded memory of route verdicts

# Hosts that identify the Railway control plane (panel/application host).
CONTROL_PLANE_HOST_HINTS = ("railway.app", "up.railway", ".rwy.dev")

# Endpoint-layer keys that must NEVER influence egress classification.
NON_ROUTING_KEYS = ("sni", "host", "hostname", "tls_server_name", "server_name",
                    "http_host", "dns", "custom_sni", "spoof_sni", "host_header",
                    "alpn", "fp", "fingerprint")


# ── Small pure helpers ──────────────────────────────────────────────────────

def ip_family(ip: str) -> Optional[str]:
    """IPv4 / IPv6 / None for unparseable input."""
    if not ip or not isinstance(ip, str):
        return None
    try:
        return "IPv4" if ipaddress.ip_address(ip.strip()).version == 4 else "IPv6"
    except ValueError:
        return None


def is_control_plane_address(host: str) -> bool:
    """True when the host is the Railway application host (control plane).
    Only the deployment platform matters here — not labels someone typed."""
    h = (host or "").strip().lower()
    if not h:
        return False
    return any(hint in h for hint in CONTROL_PLANE_HOST_HINTS)


def derive_node_role(*, kind: str = "external", upstream: str = "",
                     terminates_tunnel: bool = False,
                     verified_egress: Optional[dict] = None) -> str:
    """Derive the node ROLE from physical reality, not from labels.

      kind="panel"                              → CONTROL_PLANE
      upstream is a Railway host                → RELAY_NODE (relays into the
                                                  control plane; egress = panel)
      worker that terminates the tunnel (WTE)   → EDGE_NODE (CF colo egress)
      upstream is a real non-Railway server     → EXIT_NODE (egress verified
                                                  on top of this role)
      relay AND exit at the same time           → HYBRID
    """
    kind = (kind or "external").strip().lower()
    if kind in ("panel", "control_plane"):
        return "CONTROL_PLANE"
    if is_control_plane_address(upstream):
        # An upstream pointing at Railway terminates traffic at the panel —
        # the panel is the control plane, so this hop is a relay into it.
        return "RELAY_NODE"
    if kind == "worker" and terminates_tunnel and not upstream:
        return "EDGE_NODE"
    if kind in ("vps",) and not upstream:
        # VPS configured as an entry bridge (Iran relay) — no exit claim.
        return "RELAY_NODE"
    if upstream and not is_control_plane_address(upstream):
        return "EXIT_NODE"
    return "RELAY_NODE" if kind in ("worker", "vps", "relay") else "HYBRID"


# ── Egress evidence ─────────────────────────────────────────────────────────

@dataclass
class EgressEvidence:
    """A MEASURED egress observation — never a configured value."""
    target_id: str                          # "panel" | "worker-wte" | "loc:tr"
    ok: bool = False
    public_ip: Optional[str] = None
    asn: Optional[str] = None
    isp: Optional[str] = None
    country: Optional[str] = None           # country name
    country_code: Optional[str] = None      # ISO-2 when known
    region: Optional[str] = None
    city: Optional[str] = None
    ip_family: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    measurement_source: str = ""            # e.g. "worker:/egress-test"
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["checked_at"] = self.timestamp
        d["expires_at"] = self.timestamp + EGRESS_EVIDENCE_TTL
        d["age_s"] = round(time.time() - self.timestamp, 1)
        d["expired"] = d["age_s"] > EGRESS_EVIDENCE_TTL
        d["ip_family"] = d["ip_family"] or ip_family(self.public_ip or "")
        return d


_evidence: Dict[str, EgressEvidence] = {}
_evidence_lock = asyncio.Lock()
_route_history: List[dict] = []


def evidence_for(target_id: str) -> Optional[dict]:
    ev = _evidence.get(target_id)
    if ev is None:
        return None
    d = ev.to_dict()
    if d.pop("expired"):
        return {**d, "valid": False}
    d["valid"] = True
    return d


async def store_evidence(ev: EgressEvidence) -> dict:
    async with _evidence_lock:
        _evidence[ev.target_id] = ev
    return ev.to_dict()


def classify_egress(target_id: str,
                    configured: Optional[dict] = None) -> dict:
    """VERIFIED_EGRESS / CONFIGURED_ONLY / UNKNOWN for a target.

    VERIFIED_EGRESS  — fresh measured evidence exists (ok=True, not expired).
    CONFIGURED_ONLY  — an upstream/advertised address exists but was never (or
                       no longer) measured. The configured value is returned
                       under `configured_address` and is NEVER a public_ip.
    UNKNOWN          — neither measurement nor configuration exists.
    """
    ev = _evidence.get(target_id)
    fresh = bool(ev and ev.ok and (time.time() - ev.timestamp) <= EGRESS_EVIDENCE_TTL)
    cfg = {k: v for k, v in (configured or {}).items()
           if k not in NON_ROUTING_KEYS} if configured else None
    has_cfg = bool(cfg and (cfg.get("upstream") or cfg.get("address")))
    if fresh:
        classification = "VERIFIED_EGRESS"
    elif has_cfg:
        classification = "CONFIGURED_ONLY"
    else:
        classification = "UNKNOWN"
    out: dict = {"target_id": target_id, "classification": classification,
                 "verified": classification == "VERIFIED_EGRESS"}
    if fresh:
        out["egress"] = ev.to_dict()
    elif ev is not None:
        out["egress"] = {**ev.to_dict(), "stale": True}
    if cfg:
        # explicitly NOT the egress IP — a preference/endpoint value only
        out["configured_address"] = cfg.get("upstream") or cfg.get("address")
        out["configured_note"] = ("endpoint/configuration preference — does NOT "
                                  "control the physical egress IP")
    return out


# ── Route verdict (pure) ────────────────────────────────────────────────────

def compare_route_expectations(expected_country: Optional[str],
                               observed: Optional[dict],
                               expected_asn: Optional[str] = None,
                               expected_ip: Optional[str] = None) -> dict:
    """Compare expected vs observed egress. Expected≠observed ⇒ ROUTE_MISMATCH,
    never HEALTHY. No observation ⇒ UNKNOWN (no fake verdicts)."""
    reasons: List[str] = []
    if not observed or not observed.get("ok"):
        return {"route_health": "UNKNOWN",
                "reason": "no measured egress evidence — nothing was verified"}
    obs_cc = (observed.get("country_code") or "").strip().upper()
    obs_country = (observed.get("country") or "").strip().lower()
    exp = (expected_country or "").strip()
    exp_cc = exp.upper() if len(exp) == 2 else ""
    country_match: Optional[bool] = None
    if exp:
        if exp_cc:
            country_match = obs_cc == exp_cc if obs_cc else None
        else:
            country_match = (exp.lower() in obs_country) if obs_country else None
        if country_match is False:
            shown = obs_cc or observed.get("country") or "?"
            reasons.append(f"expected country {exp.upper()} but observed {shown}")
    if expected_asn and observed.get("asn"):
        if expected_asn.upper() not in str(observed.get("asn", "")).upper():
            country_match = country_match if country_match else False
            reasons.append(f"expected ASN {expected_asn} but observed {observed.get('asn')}")
    if expected_ip and observed.get("public_ip"):
        if expected_ip != observed["public_ip"]:
            reasons.append(f"expected egress IP {expected_ip} but observed {observed['public_ip']}")
    if reasons:
        return {"route_health": "ROUTE_MISMATCH", "reasons": reasons,
                "expected": {"country": expected_country, "asn": expected_asn,
                             "ip": expected_ip},
                "observed": observed}
    if country_match is True:
        return {"route_health": "HEALTHY",
                "reason": f"observed egress matches expectation ({obs_cc or observed.get('country')})",
                "observed": observed}
    # nothing comparable was requested — verified egress, no expectation given
    return {"route_health": "HEALTHY",
            "reason": "egress verified; no country/ASN expectation was set",
            "observed": observed}


def _cc(country: str) -> str:
    return (country or "").strip().upper()


def select_exit_country(country: str,
                        exit_targets: Optional[List[dict]] = None) -> dict:
    """Pick exit targets that can actually produce `country` egress.
    Targets carry: name, role, upstream, egress{country_code}.
    Only VERIFIED egress country matches; configured-but-unverified nodes are
    returned separately as candidates — never as proof.
    Returns verdict NO_EXIT_NODE_AVAILABLE when none — never a fake label."""
    want = _cc(country)
    if not want:
        return {"ok": False, "route_health": "NO_EXIT_NODE_AVAILABLE",
                "reason": "no country requested", "targets": []}
    candidates = []
    unverified = []
    for t in (exit_targets or []):
        role = t.get("role")
        if role != "EXIT_NODE":
            continue  # control planes / relays can never satisfy a country wish
        e = t.get("egress") or {}
        tcc = _cc(e.get("country_code") or "")
        tcountry = (e.get("country") or "").strip().lower()
        if tcc == want or (not tcc and want.lower() in tcountry):
            candidates.append(t)
        elif want.lower() in tcountry or t.get("claimed_country") == want:
            unverified.append(t)
    if not candidates:
        return {"ok": False, "route_health": "NO_EXIT_NODE_AVAILABLE",
                "reason": (f"no verified exit node for country {want} — traffic "
                           "would exit from the control plane (Railway); the "
                           "location is not faked"),
                "targets": [], "unverified_candidates": unverified}
    return {"ok": True, "route_health": "HEALTHY",
            "reason": f"{len(candidates)} exit node(s) verified for {want}",
            "targets": candidates}


def route_status_for(role: str, verified: bool) -> str:
    """Client-facing route STATUS chip: DIRECT / RELAY / VERIFIED / UNKNOWN."""
    if verified:
        return "VERIFIED"
    if role == "CONTROL_PLANE":
        return "DIRECT"          # traffic exits from the current node
    if role in ("RELAY_NODE", "EDGE_NODE", "EXIT_NODE", "HYBRID"):
        return "RELAY"
    return "UNKNOWN"


def labeled_latency(measure: str, ms: Optional[float],
                    detail: str = "") -> dict:
    """One latency number must always identify WHAT it measured."""
    if measure not in LATENCY_MEASURES:
        measure = "route_rtt"
    return {"measure": measure, "ms": (round(float(ms), 1)
                                       if ms is not None else None),
            "detail": detail}


# ── Probes (async; injectable for tests — no main import at module top) ─────

_providers: Dict[str, Callable] = {}


def set_provider(name: str, fn: Callable) -> None:
    """Test/DI hook: 'worker_status', 'worker_exit_ip', 'worker_egress_test',
    'panel_egress', 'control_plane_rtt'."""
    _providers[name] = fn


def reset_for_tests() -> None:
    _evidence.clear()
    _route_history.clear()
    _providers.clear()


async def probe_panel_egress() -> dict:
    """Egress of the panel (control plane) as the Internet sees it.
    Single implementation — link_health /api/exit-check is a facade of this."""
    if "panel_egress" in _providers:
        return await _providers["panel_egress"]()
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            r = await cli.get("https://ipapi.co/json/",
                              headers={"User-Agent": "EMIX-EgressEngine/1.0"})
            data = r.json()
            ip = data.get("ip")
            if not ip:
                raise ValueError("ipapi.co returned no ip")
            return {"ok": True, "public_ip": ip, "country": data.get("country_name"),
                    "country_code": data.get("country"), "city": data.get("city"),
                    "region": data.get("region"), "isp": data.get("org"),
                    "asn": data.get("asn"), "measurement_source": "panel:ipapi.co"}
    except Exception as exc:
        try:
            async with httpx.AsyncClient(timeout=6.0) as cli:
                r = await cli.get("https://api.ipify.org?format=json")
                ip = r.json().get("ip")
                if ip:
                    return {"ok": True, "public_ip": ip, "country": None,
                            "measurement_source": "panel:ipify",
                            "fallback": True}
        except Exception:
            pass
        return {"ok": False, "error": f"panel egress probe failed: {exc}"}


async def verify_egress(target: str = "panel") -> dict:
    """Measure + classify egress for a target.
    target: 'panel' | 'worker' (WTE edge) | 'loc:<name>' (worker location)."""
    target = (target or "panel").strip()
    tid = target if target.startswith("loc:") else (
        "panel" if target == "panel" else "worker-wte")
    if target == "panel":
        raw = await probe_panel_egress()
        ev = EgressEvidence(
            target_id="panel", ok=bool(raw.get("ok")),
            public_ip=raw.get("public_ip"), asn=raw.get("asn"),
            isp=raw.get("isp"), country=raw.get("country"),
            country_code=raw.get("country_code"), region=raw.get("region"),
            city=raw.get("city"), ip_family=ip_family(raw.get("public_ip") or ""),
            measurement_source=raw.get("measurement_source", "panel"),
            error=raw.get("error"))
        await store_evidence(ev)
        out = classify_egress("panel")
        _emit_egress_event("panel", out)
        return out
    # worker targets need the gateway — resolve cfg lazily
    import gaming_boost  # local import (module registered after gaming in main)
    cfg = gaming_boost._load_cfg()
    wd = gaming_boost._norm_domain(cfg.get("worker_domain", ""))
    if not wd:
        return {"target_id": tid, "classification": "UNKNOWN",
                "error": "worker domain not configured"}
    if target == "worker":
        fn = _providers.get("worker_egress_test")
        if fn is not None:
            raw = await fn(cfg)
        else:
            raw = await gaming_boost._call_worker(cfg, "/egress-test")
        ev = _evidence_from_worker(tid, raw, "worker:/egress-test")
        await store_evidence(ev)
        out = classify_egress(tid)
        _emit_egress_event(tid, out)
        return out
    # loc:<name>
    name = target[4:]
    fn = _providers.get("worker_exit_ip")
    if fn is not None:
        raw = await fn(cfg, name)
    else:
        raw = await gaming_boost._call_worker(
            cfg, f"/exit-ip?loc={name}&via=upstream")
    ev = _evidence_from_worker(tid, raw, f"worker:/exit-ip?loc={name}")
    await store_evidence(ev)
    out = classify_egress(tid, configured={"upstream": raw.get("upstream") or ""})
    _emit_egress_event(tid, out)
    return out


def _emit_egress_event(target_id: str, classification: dict) -> None:
    """Structured event for egress verification (spec §29 — never secrets).
    ROUTE_MISMATCH is announced, never masked."""
    try:
        import structured_events as events
        cls = classification.get("classification", "UNKNOWN")
        ev = classification.get("egress") or {}
        events.log_event(
            "ROUTE_MISMATCH" if cls == "UNKNOWN" and classification.get("route_health") == "ROUTE_MISMATCH"
            else "EGRESS_VERIFIED",
            severity="INFO" if cls == "VERIFIED_EGRESS" else "WARNING",
            target=target_id, classification=cls,
            public_ip=ev.get("public_ip"), country=ev.get("country_code"),
            asn=ev.get("asn"), source=ev.get("measurement_source"))
    except Exception:
        pass


def _evidence_from_worker(target_id: str, raw: dict, source: str) -> EgressEvidence:
    ip = raw.get("exit_ip") or raw.get("ip")
    return EgressEvidence(
        target_id=target_id, ok=bool(raw.get("ok") and ip),
        public_ip=ip, asn=raw.get("exit_asn") or raw.get("asn"),
        isp=raw.get("exit_isp") or raw.get("isp"),
        country=raw.get("exit_country") or raw.get("country"),
        country_code=raw.get("exit_country_code") or raw.get("country_code"),
        region=raw.get("exit_region"), city=raw.get("exit_city") or raw.get("city"),
        ip_family=ip_family(ip or ""), measurement_source=source,
        error=raw.get("error"))



# ── Worker status (cached shape used for inventories) ──────────────────────

async def worker_topology() -> dict:
    """Worker locations + roles. Injected provider wins (tests); otherwise a
    live /gateway-status call via gaming_boost."""
    import gaming_boost
    cfg = gaming_boost._load_cfg()
    fn = _providers.get("worker_status")
    if fn is not None:
        raw = await fn(cfg)
    else:
        raw = await gaming_boost._call_worker(cfg, "/gateway-status")
    if not raw.get("ok"):
        return {"ok": False, "error": raw.get("error", "worker unreachable"),
                "locations": [], "wte": False}
    locs = []
    for l in raw.get("locations", []):
        upstream = (l.get("upstream") or "").strip().lower()
        # Location roles from PHYSICAL reality, not labels:
        #   no upstream      → worker terminates (EDGE_NODE, CF colo egress)
        #   railway upstream → relays into the CONTROL PLANE (egress = panel)
        #   real upstream    → EXIT_NODE (egress = that server, verify to prove)
        if not upstream:
            role = "EDGE_NODE"
        elif is_control_plane_address(upstream):
            role = "RELAY_NODE"
        else:
            role = "EXIT_NODE"
        cls = classify_egress(f"loc:{l.get('name')}",
                              configured={"upstream": upstream})
        locs.append({
            "name": l.get("name"), "label": l.get("label") or l.get("name"),
            "flag": l.get("flag") or "", "upstream": upstream,
            "is_control_plane": is_control_plane_address(upstream),
            "role": role,
            "pending": bool(l.get("pending")),
            "egress": cls,
        })
    return {"ok": True, "worker_domain": gaming_boost._norm_domain(
                cfg.get("worker_domain", "")),
            "wte": bool(raw.get("wte")), "version": raw.get("version"),
            "locations": locs}


def control_plane_info() -> dict:
    """Identity of the CONTROL PLANE (this Railway app)."""
    try:
        from main import get_host
        host = get_host()
    except Exception:
        host = ""
    return {"host": host, "role": "CONTROL_PLANE",
            "is_control_plane": True,
            "note": ("Railway hosts the control plane / application. Unless a "
                     "real exit node/relay is configured, traffic exits from "
                     "this node (its public IP) — entering another IP in the "
                     "endpoint field does NOT change that.")}


def build_route_inventory() -> dict:
    """Route inventory derived from the CURRENT topology (sync, cheap):
    every route exposes entry / relay / exit / egress / health / latency."""
    cp = control_plane_info()
    inv = {"ok": True, "engine": f"egress_engine/{EGRESS_ENGINE_VERSION}",
           "control_plane": cp, "routes": []}
    # panel-direct route (entry = panel itself)
    pe = classify_egress("panel")
    inv["routes"].append({
        "route": "panel-direct",
        "entry": {"kind": "panel", "host": cp["host"], "role": "CONTROL_PLANE"},
        "relay": None,
        "exit": {"kind": "panel", "host": cp["host"], "role": "CONTROL_PLANE"},
        "egress": pe,
        "route_status": route_status_for("CONTROL_PLANE", pe.get("verified", False)),
        "latencies": [],  # measured by /api/egress/verify & validate-route
        "note": "Traffic exits from the current node (control plane).",
    })
    return inv


async def route_inventory() -> dict:
    """Async inventory incl. worker locations and WTE edge route."""
    inv = build_route_inventory()
    topo = await worker_topology()
    if topo.get("ok"):
        for l in topo["locations"]:
            exit_role = l["role"]
            inv["routes"].append({
                "route": f"loc:{l['name']}",
                "entry": {"kind": "worker-location", "name": l["name"],
                          "label": l["label"], "role": "RELAY_NODE"},
                "relay": {"kind": "cf-worker", "domain": topo["worker_domain"]},
                "exit": {"kind": "worker-location", "name": l["name"],
                         "host": l["upstream"], "role": exit_role},
                "egress": l["egress"],
                "route_status": route_status_for(
                    exit_role, bool(l["egress"].get("verified"))),
                "latencies": [],
                "note": ("Traffic exits from the control plane (Railway) — "
                         "no real exit node for this location."
                         if l["is_control_plane"] else
                         f"Upstream {l['upstream']} terminates the tunnel."),
            })
        if topo.get("wte"):
            we = classify_egress("worker-wte")
            inv["routes"].append({
                "route": "worker-wte",
                "entry": {"kind": "cf-worker", "domain": topo["worker_domain"],
                          "role": "EDGE_NODE"},
                "relay": None,
                "exit": {"kind": "cf-worker", "domain": topo["worker_domain"],
                         "role": "EDGE_NODE"},
                "egress": we,
                "route_status": route_status_for(
                    "EDGE_NODE", bool(we.get("verified"))),
                "latencies": [],
                "note": ("Tunnel terminates inside the worker — egress is the "
                         "Cloudflare colo IP (verify with /api/egress/verify)."),
            })
    inv["exit_nodes"] = [l for l in topo.get("locations", [])
                         if l.get("role") == "EXIT_NODE"]
    return inv


async def measure_control_plane_rtt() -> dict:
    fn = _providers.get("control_plane_rtt")
    if fn is not None:
        return fn()
    try:
        host = control_plane_info()["host"]
        if not host:
            return labeled_latency("control_plane_rtt", None, "panel host unknown")
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=6.0) as cli:
            await cli.get(f"https://{host}/api/ping")
        return labeled_latency("control_plane_rtt", (time.monotonic() - t0) * 1000,
                               f"GET https://{host}/api/ping")
    except Exception as exc:
        return labeled_latency("control_plane_rtt", None, f"probe failed: {exc}")


# ── The 9-step route validation pipeline ────────────────────────────────────

async def validate_route(location: str = "auto",
                          expected_country: Optional[str] = None,
                          expected_asn: Optional[str] = None,
                          expected_ip: Optional[str] = None) -> dict:
    """Before a route is marked usable:
      1 resolve endpoint · 2 connect to node · 3 verify node · 4 verify route
      5 verify actual egress · 6 compare expected vs observed · 7 measure
      latency (labeled) · 8 store evidence · 9 assign health state.
    Expected country without a real exit node ⇒ NO_EXIT_NODE_AVAILABLE.
    Expected ≠ observed ⇒ ROUTE_MISMATCH (never HEALTHY)."""
    steps: List[dict] = []
    location = (location or "auto").strip().lower()
    topo = await worker_topology()

    # 1 — resolve endpoint / exit target
    target = None
    for l in topo.get("locations", []):
        if l["name"] == location:
            target = l
            break
    if location == "auto":
        target = next((l for l in topo.get("locations", []) if l["name"] == "auto"),
                      None)
    steps.append({"step": 1, "name": "resolve_endpoint",
                  "ok": target is not None,
                  "detail": (f"location {location} resolved → upstream "
                             f"{target['upstream']}" if target else
                             f"location {location} not found on worker")})
    if target is None:
        return _verdict(location, "UNKNOWN", steps, [],
                        error=f"location {location} not found on worker",
                        expected_country=expected_country)

    # exit-node reality gate BEFORE any measurement
    if location != "auto" and target["is_control_plane"]:
        verdict = select_exit_country(
            expected_country or "",
            [{"name": l["name"], "role": l["role"],
              "egress": (l["egress"].get("egress") or {})}
             for l in topo.get("locations", [])])
        if not verdict.get("ok"):
            steps.append({"step": 2, "name": "exit_node_check", "ok": False,
                          "detail": verdict["reason"]})
            return _verdict(location, "NO_EXIT_NODE_AVAILABLE", steps, [],
                            error=verdict["reason"],
                            expected_country=expected_country,
                            egress=target["egress"])

    # 2 — connect to the node (worker gateway reachable?)
    # 3 — verify node (upstream / exit reachable — /exit-ip answers this)
    # 4+5 — verify route + actual egress in one measurement
    ev_cls = await verify_egress(f"loc:{location}")
    ev = ev_cls.get("egress") or {}
    connected = bool(ev.get("ok"))
    steps.append({"step": 2, "name": "connect_node", "ok": connected,
                  "detail": ("worker gateway reachable" if connected else
                             (ev.get("error") or "gateway unreachable"))})
    steps.append({"step": 3, "name": "verify_node",
                  "ok": connected,
                  "detail": ("upstream answered /exit-ip" if connected else
                             "upstream did not answer")})
    steps.append({"step": 4, "name": "verify_route", "ok": connected,
                  "detail": (f"route via {target.get('upstream') or 'worker'}"
                             if connected else "route not measurable")})
    steps.append({"step": 5, "name": "verify_egress", "ok": bool(ev.get("ok")),
                  "detail": (f"observed {ev.get('public_ip')} "
                             f"({ev.get('country_code') or ev.get('country') or '?'})"
                             if ev.get("ok") else "egress not measurable")})

    # 6 — compare expected vs observed
    cmp_result = compare_route_expectations(expected_country, ev,
                                             expected_asn, expected_ip)
    steps.append({"step": 6, "name": "compare_expectations",
                  "ok": cmp_result["route_health"] == "HEALTHY",
                  "detail": cmp_result.get("reason") or "; ".join(
                      cmp_result.get("reasons", [])) or "no expectations set"})

    # 7 — measure latency, always labeled
    latencies = [labeled_latency(
        "route_rtt", ev.get("latency_ms"),
        "worker→upstream→ip-check round trip")]
    cp_rtt = await measure_control_plane_rtt()
    latencies.append(cp_rtt)
    steps.append({"step": 7, "name": "measure_latency", "ok": True,
                  "detail": "; ".join(
                      f"{l['measure']}={l['ms']}ms" if l["ms"] is not None else
                      f"{l['measure']}=n/a" for l in latencies)})

    # 8 — evidence already stored by verify_egress; record route verdict
    # 9 — health state
    health = cmp_result["route_health"] if connected else "UNREACHABLE"
    return _verdict(location, health, steps, latencies,
                    egress=ev_cls, expected_country=expected_country,
                    comparison=cmp_result)


def _verdict(location: str, health: str, steps: list, latencies: list,
             egress: Optional[dict] = None, expected_country: Optional[str] = None,
             error: Optional[str] = None, comparison: Optional[dict] = None) -> dict:
    out = {"ok": health == "HEALTHY", "location": location,
           "route_health": health, "steps": steps, "latencies": latencies,
           "expected_country": expected_country}
    if egress is not None:
        out["egress"] = egress
    if error:
        out["error"] = error
    if comparison:
        out["comparison"] = comparison
    entry = {"ts": time.time(), "location": location, "route_health": health,
             "expected_country": expected_country}
    _route_history.append(entry)
    del _route_history[:-ROUTE_HISTORY_BOUND]
    if health == "ROUTE_MISMATCH":
        try:
            import structured_events as events
            events.log_event("ROUTE_MISMATCH", severity="WARNING",
                             location=location, expected_country=expected_country,
                             note="expected ≠ observed — never masked as healthy")
        except Exception:
            pass
    return out


def route_history() -> List[dict]:
    return list(_route_history)


def egress_health_layers() -> dict:
    """EGRESS_HEALTH is about the VPN egress — NOT the application API.
    APPLICATION/NODE/ROUTE layers are sourced from their owning engines."""
    layers = {layer: "UNKNOWN" for layer in HEALTH_LAYERS}
    # APPLICATION_HEALTH — panel process is answering (we are running this code)
    layers["APPLICATION_HEALTH"] = "HEALTHY"
    try:
        import node_manager
        s = node_manager.summary()
        by = s.get("by_state", {})
        if by.get("OFFLINE"):
            layers["NODE_HEALTH"] = "DEGRADED"
        elif by.get("REGISTER"):
            layers["NODE_HEALTH"] = "UNKNOWN"
        elif s.get("nodes"):
            layers["NODE_HEALTH"] = "HEALTHY"
        else:
            layers["NODE_HEALTH"] = "UNKNOWN"   # no nodes registered — honest
    except Exception:
        pass
    recent = _route_history[-1] if _route_history else None
    if recent:
        rh = recent.get("route_health")
        layers["ROUTE_HEALTH"] = rh if rh in ROUTE_HEALTH_STATES else "UNKNOWN"
        if rh == "HEALTHY":
            layers["EGRESS_HEALTH"] = "HEALTHY"
        elif rh in ("ROUTE_MISMATCH",):
            layers["EGRESS_HEALTH"] = "ROUTE_MISMATCH"
        elif rh == "NO_EXIT_NODE_AVAILABLE":
            layers["EGRESS_HEALTH"] = "NO_EXIT_NODE_AVAILABLE"
        elif rh == "UNREACHABLE":
            layers["EGRESS_HEALTH"] = "UNREACHABLE"
    panel_ev = _evidence.get("panel")
    if panel_ev and panel_ev.ok and time.time() - panel_ev.timestamp <= EGRESS_EVIDENCE_TTL:
        if layers["EGRESS_HEALTH"] == "UNKNOWN":
            layers["EGRESS_HEALTH"] = "HEALTHY"   # panel egress measured & fresh
    # PROTOCOL_HEALTH — are protocol engines actually registered & serving?
    # (a healthy API says nothing about VPN traffic; this layer reports the
    #  protocol serving layer itself, from registry evidence — not vibes.)
    try:
        import protocol_engine
        import compat as _compat
        enabled = protocol_engine.get_enabled_protocols()
        names = set()
        for item in enabled:
            names.add(getattr(item, "name", item) if not isinstance(item, str)
                      else item)
        prod = {p for p, r in _compat.READINESS.items() if r == "PRODUCTION"}
        if names & prod:
            layers["PROTOCOL_HEALTH"] = "HEALTHY"
        elif names:
            layers["PROTOCOL_HEALTH"] = "DEGRADED"     # only BETA serving
        else:
            layers["PROTOCOL_HEALTH"] = "UNKNOWN"
    except Exception:
        pass
    return layers


# ── API surface (registered from main) ──────────────────────────────────────

def register_routes(app) -> None:
    from main import require_auth

    @app.get("/api/egress/summary")
    async def api_egress_summary(_=Depends(require_auth)):
        cp = control_plane_info()
        topo = await worker_topology()
        panel = classify_egress("panel")
        wte = classify_egress("worker-wte")
        exit_nodes = [l for l in topo.get("locations", [])
                      if l.get("role") == "EXIT_NODE"]
        return JSONResponse({
            "ok": True, "engine": f"egress_engine/{EGRESS_ENGINE_VERSION}",
            "concepts": {
                "endpoint": ("where the client connects (address/SNI/hostname) — "
                             "does NOT change the physical egress"),
                "route": "entry → relay → exit path traffic traverses",
                "egress": "the public IP/ASN/country the Internet sees",
            },
            "control_plane": {**cp, "egress": panel},
            "worker_wte": {"role": "EDGE_NODE", "egress": wte},
            "exit_nodes": exit_nodes,
            "exit_nodes_count": len(exit_nodes),
            "worker_reachable": bool(topo.get("ok")),
            "egress_health": egress_health_layers(),
        })

    @app.get("/api/egress/verify")
    async def api_egress_verify(target: str = "panel", _=Depends(require_auth)):
        res = await verify_egress(target)
        return JSONResponse(res)

    @app.get("/api/egress/routes")
    async def api_egress_routes(_=Depends(require_auth)):
        return JSONResponse(await route_inventory())

    @app.post("/api/egress/validate-route")
    async def api_validate_route(request: Request, _=Depends(require_auth)):
        try:
            body = await request.json()
        except Exception:
            body = {}
        res = await validate_route(
            location=(body.get("location") or "auto"),
            expected_country=body.get("expected_country"),
            expected_asn=body.get("expected_asn"),
            expected_ip=body.get("expected_ip"))
        return JSONResponse(res)

    @app.get("/api/egress/health")
    async def api_egress_health(_=Depends(require_auth)):
        return JSONResponse({
            "ok": True, "layers": egress_health_layers(),
            "formula": ("EGRESS_HEALTH is derived ONLY from measured egress "
                        "evidence and route verdicts — never from application "
                        "API health."),
            "route_history": route_history()[-10:],
        })
