# compat.py — Protocol × Transport × Security compatibility engine
#
# Single source of truth for "which combinations are legitimate".
# Replaces the lenient single-string PROTOCOLS check in _create_link_core
# (which silently coerced unknown protocols to the default).
#
# Design rules (Phase 3 / Phase 4 of the master architecture):
#   - A configuration is either VALID, INVALID (with reasons), or UNKNOWN.
#   - Never silently coerce: invalid input must produce an error.
#   - The matrix is declarative so the frontend can render only valid combos.
#   - Wire-compat: the existing fused protocol strings ("trojan-xhttp-packet-up")
#     remain the storage format; this module decomposes/validates them.

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

# ── Enumerations (mirror the REAL data-plane, nothing speculative) ──────────

PROTOCOLS = {"vless", "trojan", "shadowsocks", "mtproto"}
TRANSPORTS = {"ws", "xhttp-packet-up", "xhttp-stream-up"}
SECURITY = {"tls", "reality", "none"}

# Server-side data-plane capability (what actually runs in this panel).
# "link-only" = we can emit a client link but no server runtime exists here.
SERVER_RUNTIME = {
    ("vless", "ws"): "relay",
    ("vless", "xhttp-packet-up"): "relay",
    ("vless", "xhttp-stream-up"): "relay",
    ("trojan", "ws"): "relay",
    ("trojan", "xhttp-packet-up"): "relay",
    ("trojan", "xhttp-stream-up"): "relay",
    ("shadowsocks", "ws"): "relay",
    ("mtproto", "tcp"): "subprocess",  # mtg binary
}

# Security layer per (protocol, transport). These are the combinations the
# real link emitters actually produce today.
_ALLOWED_SECURITY = {
    ("vless", "ws"): {"tls"},
    ("vless", "xhttp-packet-up"): {"tls"},
    ("vless", "xhttp-stream-up"): {"tls"},
    ("trojan", "ws"): {"tls"},
    ("trojan", "xhttp-packet-up"): {"tls"},
    ("trojan", "xhttp-stream-up"): {"tls"},
    ("shadowsocks", "ws"): {"tls"},   # SS over TLS-wrapped WS (v2ray-plugin path)
    ("mtproto", "tcp"): {"none"},     # FakeTLS handled inside mtg secret
}

# Endpoint-profile feature applicability (Phase 25 refactor of SNI spoofing).
# sni_override applies only where the client link carries an sni/host param.
SNI_APPLICABLE = {
    ("vless", "ws"): True,
    ("vless", "xhttp-packet-up"): True,
    ("vless", "xhttp-stream-up"): True,
    ("trojan", "ws"): True,
    ("trojan", "xhttp-packet-up"): True,
    ("trojan", "xhttp-stream-up"): True,
    ("shadowsocks", "ws"): False,  # SS v2ray-plugin host param doubles as routing host — documented partial
    ("mtproto", "tcp"): False,     # FakeTLS domain lives in the secret
}

# ── Transport × Security matrix states (Phase 37.3) ─────────────────────────
# ONE source of truth for "which combination is legitimate". The UI renders
# from matrix_view(); the compiler enforces validate(); both read these tables.
# States: VALID (full server+client path real) | EXPERIMENTAL (link emission
# only / mimicry — no server runtime here) | NOT_IMPLEMENTED (advertised
# nowhere) | INVALID (protocol-theoretically or practically impossible).
TRANSPORT_MATRIX = {
    # VLESS transport/security combos
    ("vless", "ws", "tls"):        "VALID",
    ("vless", "ws", "none"):       "INVALID",        # plain WS is blocked on CDN/Railway ingress
    ("vless", "ws", "reality"):    "INVALID",        # Reality requires raw TCP/TLS inbound — impossible over WS relay
    ("vless", "xhttp-packet-up", "tls"): "VALID",
    ("vless", "xhttp-packet-up", "none"): "INVALID",
    ("vless", "xhttp-packet-up", "reality"): "INVALID",
    ("vless", "xhttp-stream-up", "tls"): "VALID",
    ("vless", "xhttp-stream-up", "none"): "INVALID",
    ("vless", "xhttp-stream-up", "reality"): "INVALID",
    ("vless", "tcp", "tls"):       "EXPERIMENTAL",   # link emission works; no TCP inbound in this panel
    ("vless", "tcp", "reality"):   "EXPERIMENTAL",   # vless-reality emitter exists; needs xray-core server
    ("vless", "grpc", "tls"):      "EXPERIMENTAL",   # gRPC transport: XHTTP mimics the envelope only
    ("vless", "httpupgrade", "tls"): "NOT_IMPLEMENTED",
    # Trojan
    ("trojan", "ws", "tls"):       "VALID",
    ("trojan", "ws", "none"):      "INVALID",
    ("trojan", "ws", "reality"):   "INVALID",
    ("trojan", "xhttp-packet-up", "tls"): "VALID",
    ("trojan", "xhttp-packet-up", "none"): "INVALID",
    ("trojan", "xhttp-packet-up", "reality"): "INVALID",
    ("trojan", "xhttp-stream-up", "tls"): "VALID",
    ("trojan", "xhttp-stream-up", "none"): "INVALID",
    ("trojan", "xhttp-stream-up", "reality"): "INVALID",
    ("trojan", "tcp", "tls"):      "EXPERIMENTAL",   # link emission works; no raw-TCP inbound here
    ("trojan", "tcp", "reality"):  "EXPERIMENTAL",   # trojan-reality emitter exists; needs xray-core
    ("trojan", "grpc", "tls"):     "NOT_IMPLEMENTED",
    ("trojan", "httpupgrade", "tls"): "NOT_IMPLEMENTED",
    # Shadowsocks (AEAD over WS with v2ray-plugin; plugin carries the TLS)
    ("shadowsocks", "ws", "tls"):  "VALID",
    ("shadowsocks", "ws", "none"): "EXPERIMENTAL",   # plugin without tls — plausible client-side, no server path here
    ("shadowsocks", "tcp", "none"): "EXPERIMENTAL",  # ss over raw TCP: client link possible, no inbound here
    ("shadowsocks", "grpc", "tls"): "NOT_IMPLEMENTED",
    ("shadowsocks", "httpupgrade", "tls"): "NOT_IMPLEMENTED",
    # MTProto (transport is fixed: TCP; security is inside the secret)
    ("mtproto", "tcp", "none"):    "VALID",
    ("mtproto", "tcp", "tls"):     "INVALID",        # FakeTLS is in-secret, not a TLS layer we control
    ("mtproto", "ws", "tls"):      "INVALID",        # MTProto does not ride WS in this panel
}

MATRIX_STATES = ("VALID", "EXPERIMENTAL", "NOT_IMPLEMENTED", "INVALID")

_MATRIX_NOTES = {
    ("vless", "grpc", "tls"): "XHTTP already mimics the gRPC envelope (content-type application/grpc) — no real gRPC transport",
    ("vless", "tcp", "reality"): "vless-reality link emitter exists (BETA) — requires an external xray-core server",
    ("trojan", "tcp", "reality"): "trojan-reality link emitter exists (BETA) — requires an external xray-core server",
    ("vless", "httpupgrade", "tls"): "transport not implemented in panel or emitters",
    ("trojan", "httpupgrade", "tls"): "transport not implemented in panel or emitters",
    ("vless", "ws", "reality"): "Reality cannot ride the WS relay path (needs raw TCP inbound)",
    ("mtproto", "tcp", "tls"): "MTProto FakeTLS is encoded inside the secret, not a TLS layer",
}

# Ready classification per the Zero-Fake-Features policy (Phase 32).
READINESS = {
    "vless": "PRODUCTION",
    "trojan": "PRODUCTION",
    "shadowsocks": "PRODUCTION",
    "mtproto": "PRODUCTION",
    # BETA (link/config generation only, no server runtime in this panel):
    "vmess": "BETA",
    "vless-reality": "BETA",
    "ss-2022": "BETA",
    "wireguard": "BETA",
    "openvpn": "BETA",
    # EXPERIMENTAL / NOT AVAILABLE:
    "hysteria2": "EXPERIMENTAL",
    "tuic": "EXPERIMENTAL",
    "naiveproxy": "EXPERIMENTAL",
    "ssh": "EXPERIMENTAL",
}

PRODUCTION_PROTOCOLS = tuple(sorted(k for k, v in READINESS.items() if v == "PRODUCTION"))


# ── Result object ───────────────────────────────────────────────────────────

@dataclass
class CompatResult:
    ok: bool
    protocol: str = ""
    transport: str = ""
    security: str = ""
    reasons: list = None

    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "protocol": self.protocol,
            "transport": self.transport,
            "security": self.security,
            "reasons": list(self.reasons),
        }


# ── Decompose the legacy fused protocol strings ─────────────────────────────

def decompose(fused: str) -> tuple[str, str]:
    """Split a stored protocol string into (protocol, transport).

    Legacy forms (wire-compat, these are what live in LINKS[] today):
      vless-ws                     → (vless, ws)
      xhttp-packet-up              → (vless, xhttp-packet-up)   # vless implied
      xhttp-stream-up              → (vless, xhttp-stream-up)
      trojan-ws                    → (trojan, ws)
      trojan-xhttp-packet-up       → (trojan, xhttp-packet-up)
      trojan-xhttp-stream-up       → (trojan, xhttp-stream-up)
      mtproto                      → (mtproto, tcp)
      shadowsocks                  → (shadowsocks, ws)
    """
    s = (fused or "").strip().lower()
    if s == "mtproto":
        return "mtproto", "tcp"
    if s == "shadowsocks":
        return "shadowsocks", "ws"
    if s in ("xhttp-packet-up", "xhttp-stream-up"):
        return "vless", s
    if s.startswith("trojan-xhttp-"):
        return "trojan", "xhttp-" + s[len("trojan-xhttp-"):]
    if s == "trojan-ws":
        return "trojan", "ws"
    if s == "vless-ws":
        return "vless", "ws"
    # Unknown shape: return raw so the validator can report precisely.
    return s, ""


def compose(protocol: str, transport: str) -> str:
    """Inverse of decompose() — produces the legacy storage string."""
    p, t = (protocol or "").lower(), (transport or "").lower()
    if p == "mtproto":
        return "mtproto"
    if p == "shadowsocks":
        return "shadowsocks"
    if t == "ws":
        return f"{p}-ws"
    if t.startswith("xhttp-"):
        # legacy storage: bare for vless, prefixed for trojan
        return t if p == "vless" else f"{p}-{t}"
    if t == "tcp":
        return p
    return f"{p}-{t}"


# ── The validator ───────────────────────────────────────────────────────────

def _s(v) -> str:
    """Safe string coerce (never raises on garbage input)."""
    try:
        return str(v or "").strip().lower()
    except Exception:
        return ""


def validate(protocol: str, transport: str, security: str = "tls") -> CompatResult:
    """Validate a (protocol, transport, security) triple strictly.

    Never raises. Never coerces. Invalid input → ok=False + human-readable
    reasons so the API can answer 400 with an actionable message.
    """
    res = CompatResult(
        ok=False,
        protocol=_s(protocol),
        transport=_s(transport),
        security=_s(security or "tls"),
    )
    p, t, sec = res.protocol, res.transport, res.security

    if p not in PROTOCOLS:
        res.reasons.append(
            f"protocol '{p or '(empty)'}' not supported here — supported: {sorted(PRODUCTION_PROTOCOLS)}"
        )
        return res
    if t not in TRANSPORTS and not (p == "mtproto" and t == "tcp"):
        res.reasons.append(
            f"transport '{t or '(empty)'}' not supported — supported: {sorted(TRANSPORTS | {'tcp'})}"
        )
        return res
    if sec not in SECURITY:
        res.reasons.append(f"security '{sec}' not supported — supported: {sorted(SECURITY)}")
        return res

    runtime = SERVER_RUNTIME.get((p, t))
    if runtime is None:
        res.reasons.append(f"protocol '{p}' has no server runtime for transport '{t}' in this panel")
        return res

    allowed_sec = _ALLOWED_SECURITY.get((p, t), set())
    if sec not in allowed_sec:
        res.reasons.append(
            f"security '{sec}' not applicable to {p}/{t} — applicable: {sorted(allowed_sec)}"
        )
        return res

    res.ok = True
    return res


def validate_fused(fused: str) -> CompatResult:
    """Validate a legacy fused protocol string (storage format)."""
    p, t = decompose(fused)
    if p not in PROTOCOLS:
        return CompatResult(
            ok=False, protocol=p, transport=t,
            reasons=[f"unknown protocol '{fused}' — no silent fallback to default"],
        )
    sec = "none" if p == "mtproto" else "tls"
    return validate(p, t, sec)


def sni_override_supported(fused: str) -> bool:
    """Whether an endpoint-profile SNI override legitimately applies."""
    p, t = decompose(fused)
    return SNI_APPLICABLE.get((p, t), False)


def matrix_view() -> dict:
    """Declarative matrix for the frontend: render ONLY valid combinations.

    Phase 37.3: includes EVERY transport × security combo with its state
    (VALID / EXPERIMENTAL / NOT_IMPLEMENTED / INVALID) — the same table the
    compiler enforces, so UI and backend share ONE source of truth.
    """
    combos = []
    # runtime-backed combos (the VALID core)
    for (p, t), runtime in sorted(SERVER_RUNTIME.items()):
        sec = sorted(_ALLOWED_SECURITY.get((p, t), set()))
        for s in sec:
            combos.append({
                "protocol": p, "transport": t, "security": s,
                "state": "VALID", "runtime": runtime,
                "fused": compose(p, t),
                "sni_override": SNI_APPLICABLE.get((p, t), False),
                "readiness": READINESS.get(p, "UNKNOWN"),
                "note": "",
            })
    # non-VALID combos from the transport matrix (complete coverage)
    for (p, t, s), state in sorted(TRANSPORT_MATRIX.items()):
        if (p, t) in SERVER_RUNTIME and s in _ALLOWED_SECURITY.get((p, t), set()):
            continue  # already emitted as VALID above
        combos.append({
            "protocol": p, "transport": t, "security": s,
            "state": state,
            "runtime": None,
            "fused": compose(p, t),
            "sni_override": SNI_APPLICABLE.get((p, t), False),
            "readiness": READINESS.get(p, "UNKNOWN"),
            "note": _MATRIX_NOTES.get((p, t, s), ""),
        })
    return {
        "protocols": sorted(PROTOCOLS),
        "transports": sorted(TRANSPORTS | {"tcp", "grpc", "httpupgrade"}),
        "security": sorted(SECURITY),
        "production": list(PRODUCTION_PROTOCOLS),
        "readiness": dict(READINESS),
        "states": list(MATRIX_STATES),
        "combinations": combos,
        "source": "compat.py/TRANSPORT_MATRIX (single source of truth)",
    }


def matrix_state(protocol: str, transport: str, security: str) -> str:
    """State of one combination from the single-source-of-truth matrix."""
    p, t, s = _s(protocol), _s(transport), _s(security)
    if TRANSPORT_MATRIX.get((p, t, s)) == "VALID":
        # VALID requires the runtime too — matrix and runtime tables agree
        # for every VALID entry by construction.
        return "VALID"
    return TRANSPORT_MATRIX.get((p, t, s), "NOT_IMPLEMENTED")
