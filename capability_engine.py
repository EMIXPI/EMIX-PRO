# capability_engine.py — Protocol / Transport / Deployment Capability Engine
#
# Phase 38+ (spec §3-§5, §25): ONE capability source that answers, honestly:
#
#   "What protocol can this node actually run?"
#   "What transport can this deployment actually carry?"
#   "Can the selected client implement this routing?"
#   "Can this configuration actually work on the selected deployment?"
#
# It MERGES three previously-disconnected systems (see
# MASTER_NETWORK_ARCHITECTURE_AUDIT.md §3):
#   1. compat.py            — panel-level protocol × transport × security matrix (SSoT)
#   2. protocol_engine      — per-adapter capability flags (supports_udp, …)
#   3. node_manager         — per-node fused-protocol capability strings
# and adds the missing 4th dimension: the DEPLOYMENT (Railway vs worker vs VPS).
#
# Railway compatibility model (spec §4) — four distinct layers, never conflated:
#   RAILWAY_EDGE        — the HTTP(S) public edge that fronts the app (CDN/ingress)
#   RAILWAY_DEPLOYMENT  — the app runtime itself (FastAPI, in-process relays)
#   RAILWAY_OUTBOUND    — egress via Railway's network (what ipapi sees)
#   ACTUAL_EGRESS       — the measured exit (evidence-based, egress_engine)
#
# Honesty rules:
#   * UDP is NEVER claimed on a deployment that does not provide usable public UDP.
#   * Node capabilities come from records/evidence, never from node NAMES.
#   * gRPC = XHTTP envelope mimicry only (compat.py) — labeled EXPERIMENTAL, not real gRPC.
#   * Everything unmeasured is UNKNOWN, never healthy/verified.

from __future__ import annotations
import time
from typing import Optional, Callable

import compat

ENGINE_VERSION = "1.0.0"

# ── Deployment layers (spec §4 — never confuse these) ───────────────────────

DEPLOYMENT_LAYERS = (
    "RAILWAY_EDGE",         # public HTTP(S) edge in front of the app
    "RAILWAY_DEPLOYMENT",   # the app runtime (this process)
    "RAILWAY_OUTBOUND",     # network egress as seen by external IP providers
    "ACTUAL_EGRESS",        # measured exit — evidence only (egress_engine)
)

DEPLOYMENT_IDS = ("panel", "worker", "vps", "exit-node", "iran-gateway")

# ── UDP-dependent protocols (spec §4 — NEVER Railway-native) ─────────────────

UDP_DEPENDENT_PROTOCOLS = ("wireguard", "openvpn-udp", "hysteria", "hysteria2",
                           "tuic", "amneziawg")

# Railway priority order (spec §4) — what the panel actually serves, in order.
RAILWAY_PRIORITY = (
    ("vless", "xhttp-packet-up", "tls"),
    ("vless", "xhttp-stream-up", "tls"),
    ("trojan", "xhttp-packet-up", "tls"),
    ("trojan", "xhttp-stream-up", "tls"),
    ("vless", "ws", "tls"),
    ("trojan", "ws", "tls"),
    ("shadowsocks", "ws", "tls"),
    ("mtproto", "tcp", "none"),   # TCP via Railway TCP-proxy path (real subprocess)
)

# Transport reality on each deployment (what the network path ACTUALLY carries).
# "carries" = transports the ingress/data-plane can transport today.
DEPLOYMENT_MODEL = {
    "panel": {
        "label": "EMIX Control Plane (Railway deployment)",
        "node_kind": "panel",
        "layers": {
            "RAILWAY_EDGE": "HTTP(S) public edge — carries ws/xhttp over TLS",
            "RAILWAY_DEPLOYMENT": "FastAPI in-process relays (vless/trojan/ss) + mtproto subprocess",
            "RAILWAY_OUTBOUND": "egress via Railway network — measured by egress_engine",
            "ACTUAL_EGRESS": "VERIFIED only via egress_engine evidence (TTL 300s)",
        },
        "carries": ["ws", "xhttp-packet-up", "xhttp-stream-up", "tcp"],
        "tcp": "http-layer (ws/xhttp) + Railway TCP proxy (mtproto)",
        "udp": "NOT_PROVIDED",   # Railway public ingress provides no usable public UDP
        "tls": True,
        "ipv4": True,
        "ipv6": "UNKNOWN",       # depends on Railway deployment config — not asserted
        "raw_tcp_protocols": ["mtproto"],   # via Railway TCP proxy only
        "priority": [list(c) for c in RAILWAY_PRIORITY],
        "role": "CONTROL_PLANE",
        "note": "Railway is a deployment environment, not a protocol layer — "
                "protocol support derives from the actual network path and runtime",
    },
    "worker": {
        "label": "Cloudflare Worker (WTE — Worker-Terminated Egress)",
        "node_kind": "worker",
        "layers": {
            "RAILWAY_EDGE": "not applicable (Cloudflare edge fronts this node)",
            "RAILWAY_DEPLOYMENT": "not applicable (Cloudflare Worker runtime)",
            "RAILWAY_OUTBOUND": "egress via the executing Cloudflare colo",
            "ACTUAL_EGRESS": "VERIFIED only via worker /egress-test evidence",
        },
        "carries": ["ws"],
        "tcp": "via cloudflare:sockets connect() — TCP only",
        "udp": "DNS_ONLY",       # DoH for port 53 only (cf_gateway_worker.js:231-248)
        "tls": True,
        "ipv4": True,
        "ipv6": "UNKNOWN",
        "priority": [["vless", "ws", "tls"]],
        "role": "EDGE_NODE",
        "note": "Anycast colo ≠ geography. WTE egress = the executing colo — "
                "verified by /egress-test, never inferred from hostname",
    },
    "vps": {
        "label": "External VPS / bridge node",
        "node_kind": "vps",
        "layers": {
            "RAILWAY_EDGE": "not applicable",
            "RAILWAY_DEPLOYMENT": "not applicable",
            "RAILWAY_OUTBOUND": "not applicable",
            "ACTUAL_EGRESS": "VERIFIED only via measured evidence",
        },
        "carries": ["ws", "xhttp-packet-up", "xhttp-stream-up", "tcp"],
        "tcp": "real sockets",
        "udp": "UNKNOWN",        # possible in principle — UNVERIFIED until measured
        "tls": True,
        "ipv4": True,
        "ipv6": "UNKNOWN",
        "priority": [],          # per-node: from node record capabilities
        "role": "RELAY_NODE",
        "note": "capabilities derive from the node record + evidence, not the name",
    },
    "exit-node": {
        "label": "Dedicated exit node",
        "node_kind": "exit",
        "layers": {
            "RAILWAY_EDGE": "not applicable",
            "RAILWAY_DEPLOYMENT": "Node.js VLESS-over-WS server (TCP only)",
            "RAILWAY_OUTBOUND": "egress via the node's own network",
            "ACTUAL_EGRESS": "VERIFIED only via measured evidence",
        },
        "carries": ["ws", "tcp"],
        "tcp": "real sockets (exit_node/server.js: cmd!==0x01 closes — TCP only)",
        "udp": "UNKNOWN",        # not provided by the current exit-node image
        "tls": True,
        "ipv4": True,
        "ipv6": "UNKNOWN",
        "priority": [["vless", "ws", "tls"]],
        "role": "EXIT_NODE",
        "note": "country selection requires a VERIFIED exit node "
                "(egress_engine.select_exit_country — NO_EXIT_NODE_AVAILABLE otherwise)",
    },
    "iran-gateway": {
        "label": "Iran Gateway (IRAN_PROXY — real Iranian exit)",
        "node_kind": "external",
        "layers": {
            "RAILWAY_EDGE": "not applicable",
            "RAILWAY_DEPLOYMENT": "external gateway process (managed elsewhere)",
            "RAILWAY_OUTBOUND": "not applicable",
            "ACTUAL_EGRESS": "VERIFIED_IRAN_EGRESS only via measured evidence in IR",
        },
        "carries": ["tcp"],
        "tcp": "depends on gateway protocol (external)",
        "udp": "UNKNOWN",
        "tls": "UNKNOWN",
        "ipv4": True,
        "ipv6": "UNKNOWN",
        "priority": [],
        "role": "EXIT_NODE",
        "note": "a manually entered Iranian IP is CONFIGURED, never VERIFIED — "
                "only network evidence establishes Iranian egress",
    },
}

# ── Client format capabilities (spec §26 — never generate unsupported fields) ─

CLIENT_FORMATS = {
    "uri": {
        "label": "Share URI (vless:// trojan:// ss:// tg://)",
        "split_tunnel": "SPLIT_TUNNEL_NOT_SUPPORTED",
        "fingerprint": True, "alpn": True, "sni": True,
        "routing_rules": "none — single outbound, client-side split tunneling "
                         "must be configured manually (not emitted)",
    },
    "xray-json": {
        "label": "Xray client JSON",
        "split_tunnel": "SPLIT_TUNNEL_SUPPORTED",
        "fingerprint": True, "alpn": True, "sni": True,
        "routing_rules": "routing.rules with GEOIP:ir / CIDR direct outbound "
                         "(compiled from the verified dataset)",
    },
    "sing-box": {
        "label": "sing-box JSON",
        "split_tunnel": "SPLIT_TUNNEL_SUPPORTED",
        "fingerprint": True, "alpn": True, "sni": True,
        "routing_rules": "route.rules with GEOIP equivalent / CIDR",
    },
    "subscription": {
        "label": "Base64 subscription body",
        "split_tunnel": "SPLIT_TUNNEL_NOT_SUPPORTED",
        "fingerprint": True, "alpn": True, "sni": True,
        "routing_rules": "per-link URIs only — no routing rules in the body",
    },
    "wireguard-conf": {
        "label": "WireGuard .conf",
        "split_tunnel": "SPLIT_TUNNEL_NOT_SUPPORTED",
        "fingerprint": False, "alpn": False, "sni": False,
        "routing_rules": "AllowedIPs controls tunnel scope (0.0.0.0/0 = all VPN); "
                         "AllowedIPs carve-out possible client-side",
    },
    "openvpn-conf": {
        "label": "OpenVPN .ovpn",
        "split_tunnel": "SPLIT_TUNNEL_NOT_SUPPORTED",
        "fingerprint": False, "alpn": False, "sni": False,
        "routing_rules": "redirect-gateway / route directives control scope",
    },
}

# ── Routing policy capabilities ──────────────────────────────────────────────

ROUTING_POLICIES = (
    "ALL_VPN",
    "IRAN_DIRECT",
    "IRAN_PROXY",
    "INTERNATIONAL_VPN",
    "CUSTOM",
)


def routing_policy_capabilities() -> list:
    """Explainable routing-policy catalogue (client + gateway requirements)."""
    return [
        {
            "policy": "ALL_VPN",
            "legs": {"iran": "VPN", "international": "VPN", "unknown": "VPN"},
            "egress": "EMIX exit node (verified where available)",
            "client_requirement": "none — works with every output format",
            "gateway_requirement": "none",
        },
        {
            "policy": "IRAN_DIRECT",
            "legs": {"iran": "DIRECT", "international": "VPN", "unknown": "VPN"},
            "egress": "USER_ISP for Iranian destinations (VPN BYPASSED) — "
                      "implemented client-side via split tunneling",
            "client_requirement": "split-tunnel-capable client "
                                  "(xray-json / sing-box) — otherwise SPLIT_TUNNEL_NOT_SUPPORTED",
            "gateway_requirement": "none — no Iranian server required",
        },
        {
            "policy": "IRAN_PROXY",
            "legs": {"iran": "VPN_VIA_IRAN_GATEWAY", "international": "VPN",
                     "unknown": "VPN"},
            "egress": "IRAN_GATEWAY for Iranian destinations (expected; "
                      "VERIFIED_IRAN_EGRESS only with measured evidence)",
            "client_requirement": "none — routing happens in the EMIX route",
            "gateway_requirement": "a real, reachable Iranian gateway "
                                   "(iran_gateway registry) — UNCONFIGURED otherwise",
        },
        {
            "policy": "INTERNATIONAL_VPN",
            "legs": {"iran": "BLOCK", "international": "VPN", "unknown": "VPN"},
            "egress": "EMIX exit node; Iranian destinations are refused "
                      "(privacy mode — domestic traffic never enters the tunnel)",
            "client_requirement": "split-tunnel-capable client for the BLOCK leg "
                                  "(xray-json / sing-box)",
            "gateway_requirement": "none",
        },
        {
            "policy": "CUSTOM",
            "legs": "admin-defined",
            "egress": "per leg",
            "client_requirement": "depends on legs",
            "gateway_requirement": "depends on legs",
        },
    ]


# ── Node capability projection (never from names — from records + evidence) ──

def _protocol_status_on_deployment(protocol: str, transport: str, security: str,
                                   deployment: str) -> dict:
    """Honest per-combo status on a deployment. Reads compat SSoT + deployment model."""
    state = compat.matrix_state(protocol, transport, security)
    dm = DEPLOYMENT_MODEL[deployment]
    carries = set(dm.get("carries", []))
    if state == "VALID" and transport in carries:
        return {"status": "SUPPORTED", "reason": ""}
    if protocol in UDP_DEPENDENT_PROTOCOLS and dm.get("udp") in ("NOT_PROVIDED", "DNS_ONLY"):
        return {
            "status": "UNSUPPORTED",
            "reason": f"UDP-dependent protocol — deployment provides no usable public UDP "
                      f"(udp={dm.get('udp')})",
        }
    if state == "INVALID":
        return {"status": "INVALID", "reason": compat._MATRIX_NOTES.get(
            (protocol, transport, security), "invalid combination per compat matrix")}
    if state == "EXPERIMENTAL":
        note = compat._MATRIX_NOTES.get((protocol, transport, security), "")
        if transport == "grpc":
            note = "XHTTP mimics the gRPC envelope only — no real gRPC transport"
        return {"status": "EXPERIMENTAL", "reason": note or "link emission only — no server runtime on this deployment"}
    if state == "NOT_IMPLEMENTED":
        return {"status": "NOT_IMPLEMENTED",
                "reason": compat._MATRIX_NOTES.get((protocol, transport, security),
                                                   "transport not implemented")}
    if transport not in carries:
        return {"status": "UNSUPPORTED",
                "reason": f"transport '{transport}' not carried by deployment "
                          f"'{deployment}' (carries: {sorted(carries)})"}
    return {"status": "UNSUPPORTED", "reason": "not supported on this deployment"}


def _egress_status_for(target_id: str) -> dict:
    """Egress evidence for a node/loc target (lazy — no import cycle)."""
    try:
        import egress_engine as ee
        ev = ee.evidence_for(target_id)
        if not ev or not ev.get("ok"):
            return {"classification": "UNKNOWN", "note": "no measured evidence"}
        cls = ee.classify_egress(target_id)
        return {
            "classification": cls.get("classification", "UNKNOWN"),
            "public_ip": (cls.get("egress") or {}).get("public_ip"),
            "country": (cls.get("egress") or {}).get("country"),
            "country_code": (cls.get("egress") or {}).get("country_code"),
            "asn": (cls.get("egress") or {}).get("asn"),
            "measured_at": (cls.get("egress") or {}).get("timestamp"),
        }
    except Exception:
        return {"classification": "UNKNOWN", "note": "egress engine unavailable"}


def _panel_node(host: str) -> dict:
    """The always-present control-plane node (id 'panel')."""
    dm = DEPLOYMENT_MODEL["panel"]
    protocols = []
    for (p, t, s) in RAILWAY_PRIORITY:
        st = _protocol_status_on_deployment(p, t, s, "panel")
        protocols.append({"protocol": p, "transport": t, "security": s,
                          "status": st["status"], "reason": st["reason"],
                          "runtime": compat.SERVER_RUNTIME.get((p, t), None)})
    return {
        "node_id": "panel",
        "name": "EMIX Control Plane",
        "deployment": "panel",
        "deployment_label": dm["label"],
        "role": dm["role"],
        "region": "Railway deployment",
        "address": host,
        "state": "ONLINE" if host else "UNKNOWN",
        "state_note": "control plane serving in-process relays",
        "tcp": dm["tcp"], "udp": dm["udp"], "tls": True,
        "ipv4": True, "ipv6": dm["ipv6"],
        "protocols": protocols,
        "priority": dm["priority"],
        "egress": _egress_status_for("panel"),
        "selectable": True,
    }


async def _worker_nodes() -> list:
    """Worker WTE + per-location nodes from live topology (lazy import).
    worker_topology() is async — awaited here."""
    out = []
    try:
        import egress_engine as ee
        topo = await ee.worker_topology()
    except Exception:
        return out
    dm = DEPLOYMENT_MODEL["worker"]
    for loc in topo.get("locations", []):
        name = loc.get("name", "")
        egress = _egress_status_for(f"loc:{name}")
        carries_wte = bool(loc.get("wte"))
        protocols = []
        if carries_wte:
            st = _protocol_status_on_deployment("vless", "ws", "tls", "worker")
            protocols.append({"protocol": "vless", "transport": "ws", "security": "tls",
                              "status": st["status"], "reason": st["reason"],
                              "runtime": "worker-wte"})
        upstream = loc.get("upstream") or ""
        # relayed upstreams inherit panel protocol surface honestly
        for (p, t, s) in RAILWAY_PRIORITY:
            if (p, t) in compat.SERVER_RUNTIME and t in ("ws", "xhttp-packet-up", "xhttp-stream-up"):
                st = _protocol_status_on_deployment(p, t, s, "worker")
                protocols.append({"protocol": p, "transport": t, "security": s,
                                  "status": st["status"] if t == "ws" else "EXPERIMENTAL",
                                  "reason": "via /loc tunnel to upstream (HTTP-layer passthrough)"
                                  if st["status"] == "SUPPORTED" else "tunnel passthrough only",
                                  "runtime": "worker-tunnel"})
        out.append({
            "node_id": f"loc:{name}",
            "name": loc.get("label") or name,
            "deployment": "worker",
            "deployment_label": dm["label"],
            "role": loc.get("role", "EDGE_NODE"),
            "region": loc.get("colo") or name,
            "address": upstream or loc.get("worker_domain", ""),
            "state": "ONLINE" if loc.get("ok") else "UNKNOWN",
            "state_note": "worker location from live topology",
            "tcp": dm["tcp"], "udp": dm["udp"], "tls": True,
            "ipv4": True, "ipv6": dm["ipv6"],
            "protocols": protocols,
            "egress": egress,
            "selectable": bool(name),
        })
    return out


def _managed_nodes() -> list:
    """node_manager records projected onto deployment models (lazy import)."""
    out = []
    try:
        import node_manager as nm
        nodes = nm.list_nodes()
    except Exception:
        return out
    for rec in nodes:
        if rec.get("kind") == "panel":
            continue  # panel is projected separately (with host)
        deployment = "vps" if rec.get("kind") in ("vps", "external") else \
            ("exit-node" if rec.get("kind") == "exit" else "worker")
        dm = DEPLOYMENT_MODEL[deployment]
        caps = rec.get("capabilities") or []
        protocols = []
        for fused in caps:
            p, t = compat.decompose(fused)
            s = "none" if p == "mtproto" else "tls"
            st = _protocol_status_on_deployment(p, t, s, deployment)
            protocols.append({"protocol": p, "transport": t, "security": s,
                              "status": st["status"], "reason": st["reason"],
                              "runtime": rec.get("runtime")})
        out.append({
            "node_id": rec.get("id"),
            "name": rec.get("name"),
            "deployment": deployment,
            "deployment_label": dm["label"],
            "role": dm["role"],
            "region": rec.get("region", ""),
            "address": rec.get("address", ""),
            "state": rec.get("effective_state", "UNKNOWN"),
            "state_note": "node_manager record — runtime-gated state",
            "tcp": dm["tcp"], "udp": dm["udp"], "tls": dm["tls"],
            "ipv4": True, "ipv6": dm["ipv6"],
            "protocols": protocols,
            "egress": _egress_status_for(f"node:{rec.get('id')}"),
            "selectable": rec.get("effective_state") in ("ONLINE", "DEGRADED", "REGISTER", "UNKNOWN"),
        })
    return out


async def node_catalogue(host: str = "") -> list:
    """Every selectable node with honest capabilities. The Config Builder
    renders THIS — it never invents nodes or protocol support."""
    out = [_panel_node(host)]
    out.extend(await _worker_nodes())
    out.extend(_managed_nodes())
    return out


# ── Railway real-world validation matrix (spec §25 — honest stages) ──────────

VALIDATION_STAGES = (
    "CONFIG_VALID",           # compiler accepts the combo (real compile at request time)
    "RUNTIME_STARTED",        # the runtime serving this combo is up in this process
    "LISTENER_REACHABLE",     # the route/path exists in the live app
    "CLIENT_CONNECTED",       # real client handshake — needs a REAL client
    "REAL_TRAFFIC_CONFIRMED", # real payload through the tunnel
    "RECONNECT_CONFIRMED",    # reconnect after drop
)

# Routes registered by the always-on relay layer (main.py:3463-3486) — the
# LISTENER evidence source. Filled at wire time by main via set_listener_paths().
_LISTENER_PATHS: dict = {}


def set_listener_paths(paths: dict) -> None:
    """DI: main registers the live relay route paths + mtproto instance probe."""
    _LISTENER_PATHS.clear()
    _LISTENER_PATHS.update(paths or {})


def _listener_probe() -> Callable:
    return _LISTENER_PATHS.get("__mtproto_probe__")


def railway_validation_matrix() -> dict:
    """Honest per-combo deployment validation. A unit-test-only result is NEVER
    real protocol verification (spec §25): CLIENT_CONNECTED / REAL_TRAFFIC /
    RECONNECT are NOT_TESTABLE_WITHOUT_REAL_CLIENT unless measured evidence
    exists. VERIFIED requires evidence; otherwise the label says what IS real."""
    combos = []
    for (p, t) in sorted(compat.SERVER_RUNTIME.keys()):
        sec = sorted(compat._ALLOWED_SECURITY.get((p, t), {"tls"}))[0]
        entry = {
            "protocol": p, "transport": t, "security": sec,
            "fused": compat.compose(p, t),
            "stages": {},
            "status": "UNSUPPORTED",
        }
        # 1. CONFIG_VALID — actually compile a representative spec right now
        try:
            import config_compiler as cc
            spec = cc.ConfigSpec(
                protocol=p, transport=t, security=sec,
                credential="00000000-0000-0000-0000-000000000000" if p in ("vless", "trojan")
                else ("0123456789abcdef0123456789abcdef" if p == "mtproto" else ""),
                ss_cipher="chacha20-ietf-poly1305" if p == "shadowsocks" else "",
                ss_password="test-password" if p == "shadowsocks" else "",
                host="validation.emix.invalid",
                mtproto_public_host="validation.emix.invalid" if p == "mtproto" else "",
                mtproto_public_port=443 if p == "mtproto" else 0,
            )
            compiled = cc.compile_config(spec)
            entry["stages"]["CONFIG_VALID"] = "PASS" if compiled.ok else f"FAIL: {'; '.join(compiled.errors)}"
        except Exception as exc:
            entry["stages"]["CONFIG_VALID"] = f"FAIL: {exc}"

        # 2/3. RUNTIME_STARTED + LISTENER_REACHABLE — from the live app routes
        runtime = compat.SERVER_RUNTIME.get((p, t))
        listener_key = f"{p}:{t}"
        if runtime == "relay":
            paths = _LISTENER_PATHS.get(listener_key)
            entry["stages"]["RUNTIME_STARTED"] = "PASS" if paths else \
                "UNKNOWN — relay routes not registered in this process"
            entry["stages"]["LISTENER_REACHABLE"] = "PASS" if paths else "UNKNOWN"
            if paths:
                entry["listener_paths"] = paths
        elif runtime == "subprocess":
            probe = _listener_probe()
            if probe is None:
                entry["stages"]["RUNTIME_STARTED"] = "UNKNOWN — no mtproto probe wired"
                entry["stages"]["LISTENER_REACHABLE"] = "UNKNOWN"
            else:
                try:
                    instances = probe()
                    entry["stages"]["RUNTIME_STARTED"] = "PASS" if instances else \
                        "NO_ACTIVE_INSTANCE — mtproto is per-link (subprocess spawns on link create)"
                    entry["stages"]["LISTENER_REACHABLE"] = "PASS" if instances else "NO_ACTIVE_INSTANCE"
                    entry["mtproto_instances"] = instances
                except Exception as exc:
                    entry["stages"]["RUNTIME_STARTED"] = f"UNKNOWN: {exc}"
                    entry["stages"]["LISTENER_REACHABLE"] = "UNKNOWN"
        else:
            entry["stages"]["RUNTIME_STARTED"] = "UNKNOWN — no server runtime for this combo"
            entry["stages"]["LISTENER_REACHABLE"] = "UNKNOWN"

        # 4-6. Real-client stages — honest labels, never faked
        ev = _egress_status_for("panel")
        if ev.get("classification") == "VERIFIED_EGRESS":
            entry["stages"]["CLIENT_CONNECTED"] = "NOT_TESTED_WITH_REAL_CLIENT"
            entry["stages"]["REAL_TRAFFIC_CONFIRMED"] = "NOT_TESTED_WITH_REAL_CLIENT"
            entry["stages"]["RECONNECT_CONFIRMED"] = "NOT_TESTED_WITH_REAL_CLIENT"
        else:
            entry["stages"]["CLIENT_CONNECTED"] = "NOT_TESTABLE_WITHOUT_REAL_CLIENT"
            entry["stages"]["REAL_TRAFFIC_CONFIRMED"] = "NOT_TESTABLE_WITHOUT_REAL_CLIENT"
            entry["stages"]["RECONNECT_CONFIRMED"] = "NOT_TESTABLE_WITHOUT_REAL_CLIENT"

        # Final status: honest aggregation
        cfg = entry["stages"].get("CONFIG_VALID", "")
        started = entry["stages"].get("RUNTIME_STARTED", "")
        listener = entry["stages"].get("LISTENER_REACHABLE", "")
        if cfg == "PASS" and started == "PASS" and listener == "PASS":
            entry["status"] = "IMPLEMENTED_RUNTIME_VERIFIED_IN_PROCESS"
            entry["status_note"] = "config compiles, runtime up, listener live in this " \
                                   "process — real-client traffic stages NOT tested here"
        elif cfg == "PASS" and ("INSTANCE" in started or started.startswith("UNKNOWN")):
            entry["status"] = "CONFIG_VALID_RUNTIME_CONDITIONAL"
            entry["status_note"] = "combo valid; runtime depends on per-link instances"
        elif cfg == "PASS":
            entry["status"] = "CONFIG_VALID_ONLY"
            entry["status_note"] = "compiler accepts, runtime not confirmed in this process"
        else:
            entry["status"] = "FAILED"
        combos.append(entry)

    return {
        "ok": True,
        "matrix": combos,
        "stages": list(VALIDATION_STAGES),
        "stage_semantics": {
            "CONFIG_VALID": "the canonical compiler accepts a representative spec for this combo (executed at request time — real evidence)",
            "RUNTIME_STARTED": "the runtime serving this combo is up in THIS process (relay routes / mtproto instances)",
            "LISTENER_REACHABLE": "the tunnel route/path exists in the live app",
            "CLIENT_CONNECTED": "requires a REAL client over a REAL network — labeled honestly, never faked",
            "REAL_TRAFFIC_CONFIRMED": "requires real payload through the tunnel",
            "RECONNECT_CONFIRMED": "requires a real reconnect after drop",
        },
        "final_status_vocabulary": (
            "VERIFIED — only with measured client+traffic evidence",
            "IMPLEMENTED_RUNTIME_VERIFIED_IN_PROCESS — config+runtime+listener real in-process; real-client stages not tested",
            "CONFIG_VALID_RUNTIME_CONDITIONAL — valid combo, per-link runtime",
            "CONFIG_VALID_ONLY — compiler-valid, runtime not confirmed",
            "FAILED — compiler rejects",
            "UNSUPPORTED — deployment cannot carry it",
        ),
        "note": "A unit-test-only result is NOT real protocol verification. "
                "Railway is a deployment environment — protocol support derives "
                "from the actual network path (HTTP-layer ws/xhttp + TCP proxy).",
    }


# ── The full builder capabilities document (spec §5) ─────────────────────────

async def builder_capabilities(host: str = "") -> dict:
    """GET /api/config-builder/capabilities response. The frontend renders
    ONLY from this — never hardcodes protocol support in JavaScript."""
    nodes = await node_catalogue(host)
    iran_gw_status = None
    try:
        import iran_gateway
        iran_gw_status = iran_gateway.summary()
    except Exception:
        iran_gw_status = {"state": "UNCONFIGURED", "note": "iran_gateway module unavailable"}
    return {
        "ok": True,
        "engine": f"capability_engine/{ENGINE_VERSION}",
        "protocols": [
            {"protocol": p, "readiness": compat.READINESS.get(p, "UNKNOWN"),
             "selectable": compat.READINESS.get(p) == "PRODUCTION",
             "note": "" if compat.READINESS.get(p) == "PRODUCTION" else
                     "BETA/EXPERIMENTAL — link/config emission only, no panel runtime"}
            for p in sorted(compat.PROTOCOLS)
        ],
        "protocol_readiness": dict(compat.READINESS),
        "transports": sorted(compat.TRANSPORTS | {"tcp", "grpc", "httpupgrade"}),
        "security": sorted(compat.SECURITY),
        "deployments": {
            did: {
                "label": dm["label"], "role": dm["role"], "layers": dm["layers"],
                "carries": dm["carries"], "tcp": dm["tcp"], "udp": dm["udp"],
                "tls": dm["tls"], "ipv4": dm["ipv4"], "ipv6": dm["ipv6"],
                "priority": dm["priority"], "note": dm["note"],
            } for did, dm in DEPLOYMENT_MODEL.items()
        },
        "deployment_layers": list(DEPLOYMENT_LAYERS),
        "udp_dependent_protocols": list(UDP_DEPENDENT_PROTOCOLS),
        "udp_rule": "UDP-dependent protocols are NEVER exposed as Railway-native. "
                    "They may exist only on a real UDP-capable node with verified support.",
        "nodes": nodes,
        "clients": CLIENT_FORMATS,
        "routing_policies": routing_policy_capabilities(),
        "routing_policy_ids": list(ROUTING_POLICIES),
        "outputs": ["uri", "xray-json", "subscription", "qr", "copy"],
        "iran_gateway": iran_gw_status,
        "matrix": compat.matrix_view(),
        "rules": [
            "SNI is endpoint/TLS semantics — never routing, never geographic egress",
            "unsupported combinations are hidden/rejected with an explicit reason",
            "WireGuard/OpenVPN appear only on real UDP-capable nodes (never Railway-native)",
            "node capabilities derive from records + evidence, never from names",
        ],
        "generated_at": time.time(),
    }


def validate_request_combination(protocol: str, transport: str, security: str,
                                 node_id: str = "panel",
                                 client_format: str = "uri") -> dict:
    """Spec §19 validation BEFORE generation — explicit reasons, no silent
    generation of invalid configs. Used by config_builder + the preview API."""
    problems = []
    c = compat.validate(protocol, transport, security)
    if not c.ok:
        problems.extend(c.reasons)
    deployment = "panel"
    if node_id and node_id != "panel" and not node_id.startswith("loc:"):
        try:
            import node_manager as nm
            rec = nm.get_node(node_id)
            if rec is None:
                problems.append(f"node '{node_id}' is not registered")
            else:
                deployment = "vps" if rec.kind in ("vps", "external") else \
                    ("exit-node" if rec.kind == "exit" else "worker")
        except Exception:
            pass
    elif node_id.startswith("loc:"):
        deployment = "worker"
    if not problems:
        st = _protocol_status_on_deployment(protocol, transport, security, deployment)
        if st["status"] not in ("SUPPORTED",):
            if st["status"] in ("INVALID", "NOT_IMPLEMENTED"):
                problems.append(f"combination {protocol}/{transport}/{security}: "
                                f"{st['status']} — {st['reason']}")
            else:
                problems.append(f"UNSUPPORTED on deployment '{deployment}': {st['reason']}")
    if client_format and client_format not in CLIENT_FORMATS:
        problems.append(f"unknown client format '{client_format}' — "
                        f"supported: {sorted(CLIENT_FORMATS)}")
    return {"ok": not problems, "problems": problems,
            "deployment": deployment}


def reset_for_tests() -> None:
    _LISTENER_PATHS.clear()


# ── API (all authed — spec §28) ──────────────────────────────────────────────

def register_routes(app, require_auth) -> None:
    from fastapi import Depends
    from fastapi.responses import JSONResponse

    @app.get("/api/config-builder/capabilities",
             dependencies=[Depends(require_auth)])
    async def api_builder_capabilities(request=None):
        host = ""
        try:
            import main
            host = main.get_host()
        except Exception:
            pass
        doc = await builder_capabilities(host)
        return JSONResponse(doc)

    @app.get("/api/railway/validation-matrix",
             dependencies=[Depends(require_auth)])
    async def api_railway_validation_matrix():
        return JSONResponse(railway_validation_matrix())
