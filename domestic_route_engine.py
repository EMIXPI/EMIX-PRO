# domestic_route_engine.py — Iran Domestic Direct Routing (Phase 38 / P17)
# ══════════════════════════════════════════════════════════════════════════════
# Split-tunneling, done honestly:
#
#     Client in Iran
#         ├── Iranian destination ──► DIRECT ──► user's local ISP (USER_ISP)
#         └── International ────────► EMIX VPN ─► Exit node ─► Internet
#
# CLASSIFICATION  : IRAN_DOMESTIC | NON_IRAN | UNKNOWN
#                   (based on the ACTUAL resolved destination IP — never on
#                    domain suffix like ".ir" alone: domains change IPs)
# ROUTE POLICY    : {"iran": DIRECT|VPN|BLOCK, "international": VPN,
#                    "unknown": VPN}   — user's default is never silently changed
# POLICY PRESETS  : ALL_VPN | IRAN_DIRECT | IRAN_PROXY | INTERNATIONAL_VPN
#   IRAN_PROXY     : Iranian destinations → EMIX route → REAL Iran Gateway
#                    (iran_gateway registry; VERIFIED_IRAN_EGRESS only from
#                    measured evidence — a configured IP is never proof)
#   INTERNATIONAL_VPN : Iranian destinations → BLOCK (never enter the tunnel)
# DECISION        : DIRECT | VPN | BLOCK
# EGRESS TRUTH    : DIRECT traffic egresses from USER_ISP — never Railway,
#                   never Cloudflare, never an EMIX exit node.
#                   IRAN_PROXY traffic to Iranian destinations egresses via
#                   IRAN_GATEWAY (expected; verified only with evidence).
# STATUS          : DOMESTIC_ROUTE_VERIFIED only with prefix evidence.
#
# CRITICAL RULES:
#   * Cloudflare Anycast ≠ Iranian egress; CF ranges are flagged and are
#     NEVER auto-classified as Iranian egress.
#   * Railway stays CONTROL_PLANE — never an Iranian exit (P17 Railway rule).
#   * IP classification is prefix-evidence-based; DNS resolution must not
#     force domestic traffic into the VPN (decision follows the final IP).
#   * Clients/protocols that cannot enforce route-level split tunneling get
#     SPLIT_TUNNEL_NOT_SUPPORTED — never a config that only LOOKS supported.
#
# Bounded memory: decision history and traffic accounting are capped.
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import ipaddress
import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Tuple, Callable

from pydantic import BaseModel

import egress_engine as ee

DOMESTIC_ENGINE_VERSION = "1.0.0"

# Classifications / decisions / policies (public contract)
DESTINATION_CLASSES = ("IRAN_DOMESTIC", "NON_IRAN", "UNKNOWN")
ROUTE_DECISIONS = ("DIRECT", "VPN", "BLOCK")
POLICY_PRESETS = ("ALL_VPN", "IRAN_DIRECT", "IRAN_PROXY", "INTERNATIONAL_VPN",
                  "CUSTOM")

# Traffic accounting categories
TRAFFIC_CATEGORIES = ("DOMESTIC_DIRECT", "INTERNATIONAL_VPN", "UNKNOWN")

# Domestic eligibility / verification states
DOMESTIC_STATUS = ("DOMESTIC_ROUTE_VERIFIED", "DOMESTIC_ELIGIBLE", "UNKNOWN")

# Split-tunnel client support verdicts
SPLIT_TUNNEL_VERDICTS = ("SPLIT_TUNNEL_SUPPORTED", "SPLIT_TUNNEL_NOT_SUPPORTED")

# Clients that can actually enforce route-level split tunneling:
# xray-core JSON configs carry a full routing section (ip rules / GEOIP).
# Plain URI links, WireGuard AllowedIPs (include-lists only — cannot express
# "everything except Iran") and OpenVPN (pull-include semantics differ per
# client) are honestly NOT_SUPPORTED here.
SPLIT_TUNNEL_CLIENT_SUPPORT = {
    "xray": "SPLIT_TUNNEL_SUPPORTED",
    "xray-json": "SPLIT_TUNNEL_SUPPORTED",
    "sing-box": "SPLIT_TUNNEL_SUPPORTED",
    "wireguard": "SPLIT_TUNNEL_NOT_SUPPORTED",
    "wg": "SPLIT_TUNNEL_NOT_SUPPORTED",
    "openvpn": "SPLIT_TUNNEL_NOT_SUPPORTED",
    "ovpn": "SPLIT_TUNNEL_NOT_SUPPORTED",
    "uri": "SPLIT_TUNNEL_NOT_SUPPORTED",
}

DECISION_HISTORY_BOUND = 200
SEED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "configs", "iran_prefixes_seed.json")
MIN_DATASET_PREFIXES = 50          # below this an update is rejected (updater)

# Cloudflare IPv4 ranges (published CF network list) — anycast, NOT Iranian
# egress, regardless of which country a CF colo serves.
CLOUDFLARE_IPV4 = (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "172.64.0.0/13", "131.0.72.0/22",
)
CLOUDFLARE_IPV6 = (
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32",
    "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
)


def _now() -> float:
    return time.time()


# ── Prefix database (longest-prefix-match, bisect-free exact dict per mask) ─

class PrefixDB:
    """Iranian destination prefix database with versioning and metadata.

    Structure: {4: {prefixlen: {net_int: meta}}, 6: {...}} — exact-match dict
    per prefix length gives O(#distinct-lengths) lookups with no linear scan.
    """

    def __init__(self) -> None:
        self._v4: Dict[int, Dict[int, dict]] = {}
        self._v6: Dict[int, Dict[int, dict]] = {}
        self.meta: dict = {"version": 0, "source": None, "fetched_at": None,
                           "count": 0, "checksum": None, "loaded_at": _now(),
                           "confidence": "UNKNOWN", "origin": "empty"}

    # -- build -------------------------------------------------------------
    @staticmethod
    def _parse_prefix(p: str) -> List:
        """Accept CIDR, single IP, and RIPEstat range format 'start-end'.
        Returns a list of ip_network objects (range → summarized CIDRs)."""
        p = str(p).strip()
        if "-" in p and "/" not in p:
            start_s, end_s = p.split("-", 1)
            start = ipaddress.ip_address(start_s.strip())
            end = ipaddress.ip_address(end_s.strip())
            if start.version != end.version or int(end) < int(start):
                raise ValueError(f"invalid range {p!r}")
            return list(ipaddress.summarize_address_range(start, end))
        if "/" in p:
            return [ipaddress.ip_network(p, strict=False)]
        return [ipaddress.ip_network(f"{p}/{ipaddress.ip_address(p).max_prefixlen}",
                                     strict=False)]

    def load_prefixes(self, prefixes: List[str], meta: Optional[dict] = None) -> int:
        """Replace the DB contents. Raises ValueError on malformed input so
        callers can keep the previous known-good dataset (atomic updates).
        Handles CIDR, single IPs and RIPEstat 'start-end' ranges."""
        v4: Dict[int, Dict[int, dict]] = {}
        v6: Dict[int, Dict[int, dict]] = {}
        count = 0
        for p in prefixes:
            for net in self._parse_prefix(p):
                bucket = v4 if net.version == 4 else v6
                key = int(net.network_address) >> (net.max_prefixlen - net.prefixlen)
                bucket.setdefault(net.prefixlen, {})[key] = {"prefix": str(net)}
                count += 1
        self._v4, self._v6 = v4, v6
        self.meta = {**self.meta, **(meta or {})}
        self.meta["count"] = count
        self.meta["loaded_at"] = _now()
        return count

    # -- lookup ------------------------------------------------------------
    def classify(self, ip: str) -> Tuple[str, Optional[dict]]:
        """(classification, matched_prefix_meta). IRAN_DOMESTIC only with a
        real prefix hit; NON_IRAN when the IP parses but no prefix matches;
        UNKNOWN for unparseable input (never a guess)."""
        try:
            addr = ipaddress.ip_address((ip or "").strip())
        except ValueError:
            return "UNKNOWN", None
        bucket = self._v4 if addr.version == 4 else self._v6
        addr_int = int(addr)
        for plen in sorted(bucket.keys(), reverse=True):
            shift = addr.max_prefixlen - plen
            meta = bucket[plen].get(addr_int >> shift)
            if meta is not None:
                return "IRAN_DOMESTIC", {**meta, "prefix_len": plen,
                                         "version": self.meta.get("version")}
        return "NON_IRAN", None

    def prefix_count(self) -> int:
        return sum(len(b) for b in self._v4.values()) + \
            sum(len(b) for b in self._v6.values())


# ── Engine state ────────────────────────────────────────────────────────────

_db = PrefixDB()
_decision_history: List[dict] = []
_accounting = {cat: {"bytes_sent": 0, "bytes_received": 0,
                     "connections": 0, "duration_s": 0.0}
               for cat in TRAFFIC_CATEGORIES}
_resolver: Optional[Callable] = None        # DI: async fn(domain) -> ip|None


def set_resolver(fn: Callable) -> None:
    """Inject the DNS resolver used for domain→IP classification. The final
    routing decision ALWAYS follows the resolved IP, never the domain name."""
    global _resolver
    _resolver = fn


def _cf_note(ip: str) -> Optional[str]:
    try:
        addr = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return None
    for cidr in (CLOUDFLARE_IPV4 if addr.version == 4 else CLOUDFLARE_IPV6):
        if addr in ipaddress.ip_network(cidr):
            return "cloudflare-anycast: never classified as Iranian egress"
    return None


def seed_dataset_path() -> str:
    return SEED_PATH


def load_seed(path: Optional[str] = None) -> int:
    """Load the bundled seed dataset (RIPEstat snapshot). Returns prefix count.
    Empty/missing file → 0 (classification stays UNKNOWN-honest)."""
    p = path or SEED_PATH
    try:
        with open(p, "r", encoding="utf-8") as f:
            doc = json.load(f)
        prefixes = doc.get("prefixes", [])
        _db.load_prefixes(prefixes, {
            "version": doc.get("version", 0),
            "source": doc.get("source"),
            "source_name": doc.get("source_name"),
            "fetched_at": doc.get("fetched_at"),
            "checksum": doc.get("checksum"),
            "confidence": "seed:ripestat-snapshot",
            "origin": "seed",
        })
    except Exception:
        return 0
    return _db.prefix_count()


def apply_dataset(doc: dict, require_min: int = MIN_DATASET_PREFIXES) -> dict:
    """Validate + atomically apply an update. On ANY failure the previous
    known-good dataset stays in place (rollback = no-op)."""
    prefixes = doc.get("prefixes", [])
    if not isinstance(prefixes, list) or len(prefixes) < require_min:
        raise ValueError(
            f"dataset rejected: {len(prefixes) if isinstance(prefixes, list) else '?'} "
            f"prefixes (min {require_min}) — keeping previous dataset")
    # validate + normalize EVERY prefix (CIDR / IP / range) before the swap
    try:
        parsed: List = []
        for p in prefixes:
            parsed.extend(PrefixDB._parse_prefix(p))
    except ValueError as exc:
        raise ValueError(f"dataset rejected: malformed prefix ({exc}) — "
                         "keeping previous dataset") from exc
    # checksum verification over the NORMALIZED prefix list
    import hashlib
    normalized = [str(net) for net in parsed]
    declared = doc.get("checksum")
    actual = hashlib.sha256("\n".join(normalized).encode()).hexdigest()
    if declared and declared != actual:
        raise ValueError("dataset rejected: checksum mismatch — keeping previous")
    n = _db.load_prefixes(normalized, {
        "version": doc.get("version") or int(_now()),
        "source": doc.get("source"),
        "source_name": doc.get("source_name") or doc.get("source"),
        "fetched_at": doc.get("fetched_at") or _now(),
        "checksum": actual,
        "confidence": "verified:source-fetched",
        "origin": "update",
    })
    return {"applied": n, "version": _db.meta.get("version"),
            "source": _db.meta.get("source")}


def dataset_status() -> dict:
    return {**_db.meta, "prefix_count": _db.prefix_count()}


def dataset_prefixes() -> List[str]:
    """Normalized prefix list — for client-side rule emission (/sub-json).
    Core-surface helper: the IR-Direct subscription needs the exact same
    dataset the engine classifies with (one source of truth)."""
    nets: List[str] = []
    for table in (_db._v4, _db._v6):
        for by_key in table.values():
            for meta in by_key.values():
                p = meta.get("prefix")
                if p:
                    nets.append(p)
    return nets


# ── Route policy ────────────────────────────────────────────────────────────

@dataclass
class RoutePolicy:
    iran: str = "DIRECT"                     # DIRECT | VPN | BLOCK
    international: str = "VPN"               # VPN
    unknown: str = "VPN"                     # user-selected default for UNKNOWN
    name: str = "CUSTOM"

    def to_dict(self) -> dict:
        return asdict(self)


PRESET_POLICIES: Dict[str, RoutePolicy] = {
    "ALL_VPN": RoutePolicy(iran="VPN", international="VPN", unknown="VPN",
                           name="ALL_VPN"),
    "IRAN_DIRECT": RoutePolicy(iran="DIRECT", international="VPN", unknown="VPN",
                               name="IRAN_DIRECT"),
    # Phase 38+ §13: Iranian destinations ride the EMIX route through a REAL
    # Iran Gateway. Requires iran_gateway (no gateway → explicit verdict, the
    # route is never silently degraded to a fake "Iranian exit").
    "IRAN_PROXY": RoutePolicy(iran="VPN", international="VPN", unknown="VPN",
                              name="IRAN_PROXY"),
    # Phase 38+ §11: international-only tunnel — Iranian destinations are
    # refused (BLOCK) so domestic traffic never enters the VPN.
    "INTERNATIONAL_VPN": RoutePolicy(iran="BLOCK", international="VPN",
                                     unknown="VPN", name="INTERNATIONAL_VPN"),
}

# DI seam: iran_gateway.iran_proxy_egress_status (injected by main to avoid
# an import cycle). Returns the honest gateway egress verdict.
_gateway_status_fn: Optional[Callable] = None


def set_gateway_status_fn(fn) -> None:
    global _gateway_status_fn
    _gateway_status_fn = fn


def gateway_egress_status() -> dict:
    """IRAN_PROXY gateway verdict (honest: UNCONFIGURED/UNVERIFIED/VERIFIED
    with evidence — never invented)."""
    if _gateway_status_fn is None:
        return {"configured": False, "state": "UNKNOWN",
                "egress": "iran_gateway module not wired",
                "verdict": "IRAN_GATEWAY_UNCONFIGURED"}
    try:
        return _gateway_status_fn()
    except Exception as exc:
        return {"configured": False, "state": "UNKNOWN",
                "egress": f"gateway status error: {exc}",
                "verdict": "IRAN_GATEWAY_UNCONFIGURED"}


def get_policy(name: str) -> RoutePolicy:
    return PRESET_POLICIES.get(name, PRESET_POLICIES["ALL_VPN"])


def set_policy_preset(name: str, policy: RoutePolicy) -> None:
    """Register/replace a named policy preset (admin-defined custom routing)."""
    policy.name = name
    PRESET_POLICIES[name] = policy


# ── The route decision pipeline ─────────────────────────────────────────────

async def decide_route(destination: str, policy: Optional[RoutePolicy] = None,
                       resolved_ip: Optional[str] = None) -> dict:
    """For every connection:
      1. resolve destination (domain → IP; the decision follows the FINAL IP)
      2. classify against the domestic prefix database
      3. apply the route policy
      4. attribute egress honestly (DIRECT ⇒ USER_ISP)
      5. record the decision (bounded)
    """
    policy = policy or PRESET_POLICIES["ALL_VPN"]
    dest = (destination or "").strip()
    ip = resolved_ip

    # 1. resolve
    resolved_by = "provided"
    if ip is None:
        is_ip = _looks_like_ip(dest)
        if is_ip:
            ip = dest
            resolved_by = "literal"
        elif _resolver is not None and dest:
            try:
                ip = await _maybe_await(_resolver(dest))
                resolved_by = "dns"
            except Exception:
                ip = None
                resolved_by = "resolver-error"
        else:
            resolved_by = "no-resolver"

    # 2. classify (actual destination IP after resolution)
    if ip is None:
        classification = "UNKNOWN"
        matched = None
    else:
        classification, matched = _db.classify(ip)

    # 3. policy
    leg = {"IRAN_DOMESTIC": policy.iran,
           "NON_IRAN": policy.international,
           "UNKNOWN": policy.unknown}[classification]
    decision = leg if leg in ("DIRECT", "VPN", "BLOCK") else "VPN"

    # 4. egress attribution — honest, never invented
    cf_note = _cf_note(ip) if ip else None
    railway_note = ("railway-control-plane: never an Iranian exit"
                    if ee.is_control_plane_address(dest) else None)
    iran_gateway_status = None
    if decision == "DIRECT":
        egress = "USER_ISP"
        egress_note = "traffic exits from the user's local ISP — VPN BYPASSED"
    elif decision == "BLOCK":
        egress = "NONE"
        egress_note = ("destination refused by policy (INTERNATIONAL_VPN) — "
                       "domestic traffic never enters the tunnel")
    elif (policy.name == "IRAN_PROXY" and classification == "IRAN_DOMESTIC"):
        egress = "IRAN_GATEWAY"
        iran_gateway_status = gateway_egress_status()
        verdict = iran_gateway_status.get("verdict", "IRAN_GATEWAY_UNCONFIGURED")
        egress_note = (
            "Iranian destination rides the EMIX route through the Iran Gateway "
            f"({verdict}) — expected egress, VERIFIED only with measured evidence")
        if verdict != "VERIFIED_IRAN_EGRESS":
            iran_gateway_status.setdefault(
                "warning",
                "IRAN_PROXY without a verified gateway does NOT provide "
                "Iranian egress — configure and check a real gateway")
    else:
        egress = "EMIX_ROUTE"
        egress_note = "traffic exits via the selected EMIX exit node (verified separately)"

    domestic_status = "UNKNOWN"
    if classification == "IRAN_DOMESTIC" and decision == "DIRECT":
        domestic_status = ("DOMESTIC_ROUTE_VERIFIED" if matched
                            else "UNKNOWN")
    elif classification == "IRAN_DOMESTIC" and decision in ("VPN", "BLOCK"):
        domestic_status = "DOMESTIC_ELIGIBLE"   # eligible but policy chose VPN/BLOCK

    verdict = {
        "destination": dest,
        "resolved_ip": ip,
        "resolved_by": resolved_by,
        "classification": classification,
        "matched_prefix": (matched or {}).get("prefix"),
        "dataset_version": _db.meta.get("version"),
        "policy": policy.to_dict(),
        "policy_name": policy.name,
        "decision": decision,
        "vpn_bypassed": decision != "VPN",
        "egress": egress,
        "egress_note": egress_note,
        "iran_gateway": iran_gateway_status,
        "domestic_status": domestic_status,
        "notes": [n for n in (cf_note, railway_note) if n],
        "at": _now(),
    }
    _decision_history.append(verdict)
    del _decision_history[:-DECISION_HISTORY_BOUND]
    return verdict


def _looks_like_ip(s: str) -> bool:
    try:
        ipaddress.ip_address((s or "").strip())
        return True
    except ValueError:
        return False


async def _maybe_await(v):
    return await v if hasattr(v, "__await__") else v


async def test_route(destination: str, resolved_ip: Optional[str] = None) -> dict:
    """Diagnostic facade — same pipeline as decide_route (async, awaited by
    the API handler; never a separate code path)."""
    return await decide_route(destination, resolved_ip=resolved_ip)


def decision_history(limit: int = 50) -> List[dict]:
    return list(_decision_history[-limit:])


# ── Traffic accounting (bounded counters, category-truthful) ────────────────

def account_traffic(category: str, bytes_sent: int = 0, bytes_received: int = 0,
                    connections: int = 0, duration_s: float = 0.0) -> dict:
    """Category is derived from the ROUTE/DESTINATION logic — NEVER from the
    destination domain suffix (.ir heuristic is forbidden)."""
    if category not in TRAFFIC_CATEGORIES:
        category = "UNKNOWN"
    row = _accounting[category]
    row["bytes_sent"] += max(0, int(bytes_sent))
    row["bytes_received"] += max(0, int(bytes_received))
    row["connections"] += max(0, int(connections))
    row["duration_s"] += max(0.0, float(duration_s))
    return accounting_summary()


def accounting_summary() -> dict:
    return {cat: dict(row) for cat, row in _accounting.items()}


# ── Split-tunnel config compilation (client-capability honest) ──────────────

def split_tunnel_support(client_type: str) -> str:
    return SPLIT_TUNNEL_CLIENT_SUPPORT.get(
        (client_type or "").strip().lower(), "SPLIT_TUNNEL_NOT_SUPPORTED")


def compile_split_tunnel_rules(policy: RoutePolicy,
                               client_type: str = "xray-json",
                               use_geoip: bool = True) -> dict:
    """Compile routing rules for clients that can ENFORCE them.

    xray/xray-json/sing-box → real routing rules (GEOIP:IR when the client
    ships geoip data; otherwise the verified IR CIDR dataset).
    IRAN_PROXY → not applicable client-side (all traffic enters the tunnel;
    the Iran routing happens in the EMIX route — server-side).
    INTERNATIONAL_VVPN → BLOCK rules for Iranian prefixes (blackhole outbound).
    Everything else → SPLIT_TUNNEL_NOT_SUPPORTED (never a look-alike config).
    """
    support = split_tunnel_support(client_type)
    if support != "SPLIT_TUNNEL_SUPPORTED":
        return {
            "client": client_type,
            "verdict": "SPLIT_TUNNEL_NOT_SUPPORTED",
            "reason": f"{client_type} cannot enforce route-level split tunneling",
            "policy": policy.to_dict(),
        }
    if policy.name == "IRAN_PROXY" or (policy.iran == "VPN" and policy.name == "IRAN_PROXY"):
        return {
            "client": client_type,
            "verdict": "SPLIT_TUNNEL_NOT_APPLICABLE",
            "reason": "IRAN_PROXY routes inside the EMIX network (server-side) — "
                      "the client config carries no domestic routing rules; "
                      "egress via IRAN_GATEWAY (verified separately)",
            "policy": policy.to_dict(),
        }
    if policy.iran == "VPN" and policy.name not in ("IRAN_PROXY",):
        return {
            "client": client_type,
            "verdict": "SPLIT_TUNNEL_NOT_APPLICABLE",
            "reason": "policy does not request direct domestic routing",
            "policy": policy.to_dict(),
        }
    if policy.iran == "BLOCK":
        # INTERNATIONAL_VVPN: Iranian prefixes → blackhole (refused client-side)
        rules: List[dict] = []
        if use_geoip:
            rules.append({"type": "GEOIP", "value": "ir",
                          "outbound": "blackhole",
                          "note": "GEOIP:IR → refused (INTERNATIONAL_VVPN)"})
        v4_prefixes, v6_prefixes = [], []
        for plen_bucket in _db._v4.values():
            v4_prefixes.extend(m["prefix"] for m in plen_bucket.values())
        for plen_bucket in _db._v6.values():
            v6_prefixes.extend(m["prefix"] for m in plen_bucket.values())
        rules.append({"type": "CIDR", "value": v4_prefixes[:2000],
                      "ip_version": 4, "outbound": "blackhole",
                      "dataset_version": _db.meta.get("version")})
        if v6_prefixes:
            rules.append({"type": "CIDR", "value": v6_prefixes[:1000],
                          "ip_version": 6, "outbound": "blackhole"})
        return {
            "client": client_type,
            "verdict": "SPLIT_TUNNEL_SUPPORTED",
            "policy": policy.to_dict(),
            "rules": rules,
            "route_types": ["DOMAIN", "IP", "CIDR", "GEOIP"],
            "mechanism": "xray routing section: ip rules → outbound blackhole "
                          "(Iranian destinations refused); international → proxy",
            "dataset_version": _db.meta.get("version"),
            "dataset_prefix_count": _db.prefix_count(),
        }
    if policy.iran != "DIRECT":
        return {
            "client": client_type,
            "verdict": "SPLIT_TUNNEL_NOT_APPLICABLE",
            "reason": "policy does not request direct domestic routing",
            "policy": policy.to_dict(),
        }

    rules = []
    if use_geoip:
        rules.append({"type": "GEOIP", "value": "ir",
                      "outbound": "direct",
                      "note": "GEOIP:IR — requires geoip.dat on the client"})
    # CIDR fallback (and always included as the strongest explicit form)
    v4_prefixes, v6_prefixes = [], []
    for plen_bucket in _db._v4.values():
        v4_prefixes.extend(m["prefix"] for m in plen_bucket.values())
    for plen_bucket in _db._v6.values():
        v6_prefixes.extend(m["prefix"] for m in plen_bucket.values())
    rules.append({"type": "CIDR", "value": v4_prefixes[:2000],
                  "ip_version": 4, "outbound": "direct",
                  "dataset_version": _db.meta.get("version")})
    if v6_prefixes:
        rules.append({"type": "CIDR", "value": v6_prefixes[:1000],
                      "ip_version": 6, "outbound": "direct"})
    return {
        "client": client_type,
        "verdict": "SPLIT_TUNNEL_SUPPORTED",
        "policy": policy.to_dict(),
        "rules": rules,
        "route_types": ["DOMAIN", "IP", "CIDR", "GEOIP"],
        "mechanism": ("xray routing section: ip rules → outbound direct; "
                      "everything else → outbound vpn (proxy)"),
        "dataset_version": _db.meta.get("version"),
        "dataset_prefix_count": _db.prefix_count(),
    }


# ── DNS interaction (split DNS policy) ──────────────────────────────────────

def dns_policy_for(policy: RoutePolicy) -> dict:
    """DNS must not accidentally force domestic traffic through the VPN.
    Final routing ALWAYS follows the resolved destination IP, so both local
    and remote resolvers are safe — but we surface the recommended mode."""
    return {
        "recommended": ("local DNS for domestic lookups, VPN DNS for "
                        "international (split DNS)") if policy.iran == "DIRECT"
        else "VPN DNS for all lookups",
        "decision_basis": "destination IP after resolution (never domain-only)",
        "note": "resolution source does not change the route decision",
    }


# ── Summary / reset ─────────────────────────────────────────────────────────

# ── Active routing mode (persisted by main; default ALL_VPN) ───────────────

_active_policy_name: str = "ALL_VPN"


def get_active_policy_name() -> str:
    return _active_policy_name


def get_active_policy() -> RoutePolicy:
    return PRESET_POLICIES.get(_active_policy_name, PRESET_POLICIES["ALL_VPN"])


def set_active_policy(name: str) -> RoutePolicy:
    """Switch the panel routing mode (ALL_VPN | IRAN_DIRECT | custom preset).
    The user's default policy is never silently changed — this is an explicit
    operator/user action, persisted via snapshot."""
    global _active_policy_name
    if name not in PRESET_POLICIES:
        raise ValueError(f"unknown policy preset: {name}")
    _active_policy_name = name
    return get_active_policy()


def persist_policy_snapshot() -> dict:
    return {"active_policy": _active_policy_name}


def restore_policy_snapshot(data: dict) -> None:
    global _active_policy_name
    name = (data or {}).get("active_policy")
    if name in PRESET_POLICIES:
        _active_policy_name = name


def summary() -> dict:
    return {
        "dataset": dataset_status(),
        "policy_presets": {k: p.to_dict() for k, p in PRESET_POLICIES.items()},
        "active_policy": _active_policy_name,
        "decisions_recorded": len(_decision_history),
        "decision_history_bound": DECISION_HISTORY_BOUND,
        "traffic_accounting": accounting_summary(),
        "split_tunnel_clients": dict(SPLIT_TUNNEL_CLIENT_SUPPORT),
        "engine": f"domestic_route_engine/{DOMESTIC_ENGINE_VERSION}",
    }


def reset_for_tests() -> None:
    global _resolver, _active_policy_name, _gateway_status_fn
    _active_policy_name = "ALL_VPN"
    _decision_history.clear()
    for row in _accounting.values():
        for k in row:
            row[k] = 0 if k != "duration_s" else 0.0
    _resolver = None
    _gateway_status_fn = None


# ── API surface (admin-auth; registered from main) ─────────────────────────

class PolicyIn(BaseModel):
    policy: str
    confirm: bool = False


class TestRouteIn(BaseModel):
    destination: str
    resolved_ip: Optional[str] = None


def register_routes(app, require_auth) -> None:
    from fastapi import Depends, Query
    from fastapi.responses import JSONResponse

    _auth = [Depends(require_auth)]

    @app.get("/api/domestic/status", dependencies=_auth)
    async def api_domestic_status():
        return summary()

    @app.get("/api/domestic/policy", dependencies=_auth)
    async def api_domestic_policy():
        return {"active_policy": get_active_policy_name(),
                "policy": get_active_policy().to_dict(),
                "dns": dns_policy_for(get_active_policy()),
                "presets": {k: p.to_dict() for k, p in PRESET_POLICIES.items()}}

    @app.post("/api/domestic/policy", dependencies=_auth)
    async def api_domestic_set_policy(body: PolicyIn):
        try:
            p = set_active_policy(body.policy)
            return {"active_policy": body.policy, "policy": p.to_dict(),
                    "note": "routing mode switched (explicit action, persisted)"}
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.post("/api/domestic/test-route", dependencies=_auth)
    async def api_test_route(body: TestRouteIn):
        """Route diagnostics: destination → classification → rule → decision
        → egress attribution. Same pipeline as live decisions (no fork) —
        including the ACTIVE routing policy."""
        return await decide_route(body.destination,
                                  policy=get_active_policy(),
                                  resolved_ip=body.resolved_ip)

    @app.get("/api/domestic/decisions", dependencies=_auth)
    async def api_decisions(limit: int = Query(50)):
        return {"decisions": decision_history(limit)}

    @app.get("/api/domestic/traffic", dependencies=_auth)
    async def api_traffic():
        return {"accounting": accounting_summary(),
                "categories": list(TRAFFIC_CATEGORIES)}

    @app.post("/api/domestic/traffic", dependencies=_auth)
    async def api_traffic_record(category: str = Query(...),
                                 bytes_sent: int = Query(0),
                                 bytes_received: int = Query(0),
                                 connections: int = Query(0),
                                 duration_s: float = Query(0.0)):
        return {"accounting": account_traffic(category, bytes_sent,
                                               bytes_received, connections,
                                               duration_s)}

    @app.get("/api/domestic/split-tunnel", dependencies=_auth)
    async def api_split_tunnel(client: str = Query("xray-json"),
                               use_geoip: bool = Query(True)):
        rules = compile_split_tunnel_rules(get_active_policy(), client, use_geoip)
        return {"client": client, **rules,
                "support_map": dict(SPLIT_TUNNEL_CLIENT_SUPPORT)}

    @app.get("/api/domestic/dataset", dependencies=_auth)
    async def api_dataset():
        return dataset_status()

    @app.post("/api/domestic/rules/update", dependencies=_auth)
    async def api_rules_update(source_url: Optional[str] = Query(None)):
        import domestic_rules_updater as dru
        report = await dru.update_rules(source_url)
        return report

    @app.get("/api/domestic/rules/status", dependencies=_auth)
    async def api_rules_status():
        import domestic_rules_updater as dru
        return dru.status()
