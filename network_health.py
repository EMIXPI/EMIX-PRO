# network_health.py — Network Health Engine v2 (Phases 6/7 + 37.5/37.6/37.11)
#
# Unifies per-config health into one engine with an explicit state machine:
#
#     UNKNOWN ──probe──► HEALTHY   (ok  and score ≥ 70)
#                    └─► DEGRADED  (ok  and score < 70, or flaky history)
#                    └─► UNREACHABLE (probe failed: TCP/TLS/handshake/egress)
#     not allowed ────► INVALID    (disabled / expired / quota exhausted)
#
# A configuration is NEVER healthy because it was generated — only a real
# protocol-level probe (link_health._run_link_ping, injected by main.py to
# avoid circular imports) can set HEALTHY.
#
# ── Layered health model (Phase 37.5) ────────────────────────────────────
#
# A single ok/fail boolean cannot distinguish "config is valid" from "server
# reachable" from "protocol answered" from "application round-trip worked".
# Every probe result is now decomposed into explicit LAYERS, each PASS / FAIL
# / NOT_TESTABLE — a layer without evidence is NOT_TESTABLE, never PASS:
#
#     CONFIG → DNS → TCP → TLS → TRANSPORT → PROTOCOL → APPLICATION
#           → LATENCY → LOSS → QUALITY
#
# Layer semantics:
#   config       — the stored link record parses + validates (compat engine)
#   dns          — hostname resolved (implicit in a successful TCP connect)
#   tcp          — TCP connection established to the endpoint
#   tls          — TLS handshake completed (ws_ms measured implies this)
#   transport    — WebSocket / XHTTP channel established & framed
#   protocol     — protocol auth accepted (VLESS/Trojan/SS header verified)
#   application  — end-to-end HTTP round-trip THROUGH the tunnel (e2e_ms)
#   latency      — numeric latency evidence available
#   loss         — loss ratio computable from history
#   quality      — composite score computable
#
# ── Health score v2 (Phase 37.6 — audited, deterministic) ────────────────
#
#     score = 100 × ( 0.30·availability + 0.25·latency + 0.15·handshake
#                   + 0.15·jitter + 0.15·stability )
#             × runtime_factor × node_load_factor
#
#   availability — fraction of recent probes that succeeded (this IS the
#                  packet-loss view: 1 − loss_ratio — one term, cannot drift)
#   latency      — normalized mean e2e_ms  (250ms → 1.0, 2000ms → 0.0)
#   handshake    — normalized mean ws_ms   (100ms → 1.0,  800ms → 0.0)
#   jitter       — normalized stdev e2e_ms (25ms → 1.0,  300ms → 0.0)
#   stability    — consecutive-success streak / window length
#   runtime_factor — OFFLINE runtime → 0.0, DEGRADED runtime → 0.7, else 1.0
#   node_load_factor — load ≥ 85 → 0.85, load ≥ 70 → 0.95, else 1.0
#
# Determinism: every input is a fixed window of at most HISTORY_LEN samples;
# means/stdev are pure functions of that window; rounding is fixed (round()).
# No wall-clock, no randomness. The formula is stable across restarts.
#
# ── Health expiry (Phase 37.11) ──────────────────────────────────────────
#
# Health evidence decays: a record older than HEALTH_TTL_SECONDS is reported
# as expired — effective state UNKNOWN until revalidated by a new probe.
# Callers (subscriptions, smart route, node manager) must use
# effective_state()/effective_dict() rather than the raw stored state.

from __future__ import annotations
import asyncio
import time
import statistics
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Awaitable, Dict, List

# ── Tunables ────────────────────────────────────────────────────────────────

HISTORY_LEN = 8              # probes kept per config
E2E_BASELINE_MS = 250.0      # "perfect" end-to-end latency
E2E_MAX_MS = 2000.0          # latency at which score component = 0
WS_BASELINE_MS = 100.0
WS_MAX_MS = 800.0
JITTER_BASELINE_MS = 25.0    # v2: stdev of e2e where jitter component = 1.0
JITTER_MAX_MS = 300.0        # stdev at which jitter component = 0
HEALTHY_SCORE = 70
DEGRADED_FLAKY = 0.34        # >1/3 recent failures while currently ok → DEGRADED
HEALTH_TTL_SECONDS = 900.0   # v2 (37.11): health evidence expires after 15 min
E2E_DEGRADED_MS = 1500.0     # v2 (37.6): hard latency gate — never HEALTHY above
WS_DEGRADED_MS = 500.0       # v2 (37.6): hard handshake gate

STATES = ("HEALTHY", "DEGRADED", "UNREACHABLE", "INVALID", "UNKNOWN")
LAYER_STATES = ("PASS", "FAIL", "NOT_TESTABLE")
LAYERS = ("config", "dns", "tcp", "tls", "transport", "protocol",
          "application", "latency", "loss", "quality")

# Layer derivation hints — exception/detail classifiers (Phase 37.5)
_DNS_ERRORS = ("gaierror", "getaddrinfo", "name or service not known",
               "temporary failure in name resolution", "nodename nor servname")
_TCP_ERRORS = ("connectionrefusederror", "connectionreseterror", "timeout",
               "timed out", "network is unreachable", "errno 101",
               "connectionabortederror", "brokenpipe")
_TLS_ERRORS = ("ssl", "certificate", "handshake_failure", "certificateverify",
               "alert", "sslerror", "cert", "tls fail", "tls:", "tls error",
               "tls handshake")


def _classify_failure_layer(detail: str) -> str:
    """Best-effort: which layer did the failure happen in?

    Pure string classification of the probe detail (exception class + message
    produced by link_health). When nothing matches, the failure is reported
    at the PROTOCOL layer (the deepest layer a tunnel probe reaches before
    returning a non-protocol error).
    """
    d = (detail or "").lower()
    if any(k in d for k in _DNS_ERRORS):
        return "dns"
    if any(k in d for k in _TLS_ERRORS):
        return "tls"
    if any(k in d for k in _TCP_ERRORS):
        return "tcp"
    return "protocol"


# ── Record model ────────────────────────────────────────────────────────────

@dataclass
class ProbeSample:
    ts: float
    ok: bool
    ws_ms: Optional[float] = None
    e2e_ms: Optional[float] = None


@dataclass
class HealthRecord:
    uid: str
    protocol: str = ""
    state: str = "UNKNOWN"
    score: Optional[int] = None
    checked_at: Optional[str] = None
    checked_ts: Optional[float] = None
    health_expires_at: Optional[str] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None
    handshake_ms: Optional[float] = None
    jitter_ms: Optional[float] = None
    loss_pct: Optional[float] = None
    consecutive_ok: int = 0
    consecutive_fail: int = 0
    samples: int = 0
    layers: dict = field(default_factory=dict)
    last_probe: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        expired = self.is_expired()
        return {
            "uid": self.uid,
            "protocol": self.protocol,
            "state": self.state,
            "effective_state": self.effective_state(),
            "expired": expired,
            "score": self.score,
            "checked_at": self.checked_at,
            "checked_ts": self.checked_ts,
            "health_expires_at": self.health_expires_at,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "handshake_ms": self.handshake_ms,
            "jitter_ms": self.jitter_ms,
            "loss_pct": self.loss_pct,
            "consecutive_ok": self.consecutive_ok,
            "consecutive_fail": self.consecutive_fail,
            "samples": self.samples,
            "layers": dict(self.layers or {}),
        }

    def is_expired(self, ttl: float = HEALTH_TTL_SECONDS) -> bool:
        """True when the stored evidence is older than the TTL (37.11)."""
        if self.state in ("UNKNOWN", "INVALID") or self.checked_ts is None:
            return False  # nothing to expire
        return (time.time() - self.checked_ts) > ttl

    def effective_state(self, ttl: float = HEALTH_TTL_SECONDS) -> str:
        """State the rest of the system should trust RIGHT NOW.

        HEALTHY/DEGRADED/UNREACHABLE evidence expires to UNKNOWN after the
        TTL; INVALID (policy: disabled/expired/quota) never expires because
        it is derived from the link record, not from the network.
        """
        if self.state in ("UNKNOWN", "INVALID"):
            return self.state
        if self.is_expired(ttl):
            return "UNKNOWN"
        return self.state


# ── Engine state ────────────────────────────────────────────────────────────

_records: Dict[str, HealthRecord] = {}
_history: Dict[str, deque] = {}
_lock = asyncio.Lock()

# injected by main.py at bootstrap (avoids circular imports)
_probe_fn: Optional[Callable[..., Awaitable[dict]]] = None
_allowed_fn: Optional[Callable[[dict], bool]] = None


def set_probe_fn(fn) -> None:
    global _probe_fn
    _probe_fn = fn


def set_allowed_fn(fn) -> None:
    global _allowed_fn
    _allowed_fn = fn


# ── Scoring v2 (deterministic — see module header formula) ─────────────────

def _norm(value: Optional[float], baseline: float, worst: float) -> float:
    if value is None:
        return 0.0
    if value <= baseline:
        return 1.0
    if value >= worst:
        return 0.0
    return 1.0 - (value - baseline) / (worst - baseline)


def compute_score(samples: List[ProbeSample],
                  runtime_state: Optional[str] = None,
                  node_load: Optional[float] = None) -> Optional[int]:
    """Weighted score from real probe samples. None when never probed.

    runtime_state / node_load are external context factors (Phase 37.6):
      runtime_state OFFLINE → 0, DEGRADED → ×0.7, else no penalty
      node_load  (0-100)    ≥85 → ×0.85, ≥70 → ×0.95, else no penalty
    """
    if not samples:
        return None
    successes = [s for s in samples if s.ok]
    if not successes:
        return 0
    n = len(samples)
    e2e = [s.e2e_ms for s in successes if s.e2e_ms is not None]
    ws = [s.ws_ms for s in successes if s.ws_ms is not None]
    availability = len(successes) / n
    lat = _norm(statistics.mean(e2e), E2E_BASELINE_MS, E2E_MAX_MS) if e2e else 0.0
    hand = _norm(statistics.mean(ws), WS_BASELINE_MS, WS_MAX_MS) if ws else 0.0
    jit = (_norm(statistics.stdev(e2e), JITTER_BASELINE_MS, JITTER_MAX_MS)
           if len(e2e) >= 2 else 0.0)
    # loss is captured by availability (1 − loss_ratio) — one term, no double count
    streak = 0
    for s in reversed(samples):
        if s.ok:
            streak += 1
        else:
            break
    stability = streak / n
    raw = 100.0 * (0.30 * availability + 0.25 * lat + 0.15 * hand +
                   0.15 * jit + 0.15 * stability)
    # external context factors
    if runtime_state == "OFFLINE":
        return 0
    if runtime_state == "DEGRADED":
        raw *= 0.7
    if node_load is not None:
        if node_load >= 85:
            raw *= 0.85
        elif node_load >= 70:
            raw *= 0.95
    return max(0, min(100, round(raw)))


def score_formula() -> str:
    """Machine-readable formula description (37.6: document the formula)."""
    return ("score = 100 × (0.30·availability + 0.25·latency + 0.15·handshake "
            "+ 0.15·jitter + 0.15·stability) × runtime_factor × "
            "node_load_factor; latency 250→2000ms, handshake 100→800ms, "
            "jitter 25→300ms; hard gates: e2e>1500ms or ws>500ms → DEGRADED; "
            "window ≤ 8 samples, deterministic")


def classify(link_allowed: bool, samples: List[ProbeSample],
             runtime_state: Optional[str] = None,
             node_load: Optional[float] = None) -> tuple[str, Optional[int], Optional[str]]:
    """Classify into (state, score, error). Pure function — unit-testable."""
    if not link_allowed:
        return "INVALID", None, "config not allowed (disabled / expired / quota exhausted)"
    if not samples:
        return "UNKNOWN", None, None
    last = samples[-1]
    score = compute_score(samples, runtime_state=runtime_state, node_load=node_load)
    if not last.ok:
        return "UNREACHABLE", score, "last probe failed (connect / TLS / handshake / egress)"
    loss = sum(1 for s in samples if not s.ok) / len(samples)
    # hard latency gates: a slow tunnel is never HEALTHY (37.6)
    e2e_ok = [s.e2e_ms for s in samples if s.ok and s.e2e_ms is not None]
    ws_ok = [s.ws_ms for s in samples if s.ok and s.ws_ms is not None]
    slow = ((e2e_ok and statistics.mean(e2e_ok) > E2E_DEGRADED_MS) or
            (ws_ok and statistics.mean(ws_ok) > WS_DEGRADED_MS))
    if loss > DEGRADED_FLAKY or slow or (score is not None and score < HEALTHY_SCORE):
        reason = "latency above degraded gate (e2e>1500ms or ws>500ms)" if slow else None
        return "DEGRADED", score, reason
    return "HEALTHY", score, None


# ── Layered diagnostics (Phase 37.5) ────────────────────────────────────────

def _empty_layers() -> dict:
    return {layer: "NOT_TESTABLE" for layer in LAYERS}


def derive_layers(link_allowed: bool, probe_result: dict,
                  link: Optional[dict] = None) -> dict:
    """Decompose one probe result into per-layer states. PURE function.

    Honesty rules:
      * a layer with no evidence is NOT_TESTABLE — never PASS
      * TCP-only probes (mtproto) cannot certify TLS/transport/protocol/
        application layers — they stay NOT_TESTABLE
      * a not-allowed config fails at the CONFIG layer; deeper layers are
        NOT_TESTABLE (nothing was probed)
    """
    layers = _empty_layers()
    if not link_allowed:
        layers["config"] = "FAIL"
        return layers
    # config layer: stored record parses + decomposes to a known protocol
    layers["config"] = "PASS"
    try:
        import compat
        fused = (link or {}).get("protocol", "vless-ws")
        c = compat.validate_fused(fused)
        layers["config"] = "PASS" if c.ok else "FAIL"
    except Exception:
        layers["config"] = "NOT_TESTABLE"

    ok = bool(probe_result.get("ok"))
    ws_ms = probe_result.get("ws_ms")
    e2e_ms = probe_result.get("e2e_ms")
    detail = str(probe_result.get("detail", "") or "")
    test_kind = probe_result.get("test", "")

    if test_kind in ("",) and not ok and not ws_ms and not e2e_ms and not detail:
        # no probe content at all — nothing was tested
        for layer in ("dns", "tcp", "tls", "transport", "protocol", "application"):
            layers[layer] = "NOT_TESTABLE"
        return layers

    if ok:
        # successful probe — certifies every layer the test kind reaches
        layers["dns"] = "PASS"    # resolution was implicit in the connect
        layers["tcp"] = "PASS"
        if test_kind == "tcp-connect":
            # MTProto probe: raw TCP only — deeper layers unproven
            layers["latency"] = "PASS" if ws_ms is not None else "NOT_TESTABLE"
            return layers
        layers["tls"] = "PASS"
        layers["transport"] = "PASS"
        layers["protocol"] = "PASS"
        if e2e_ms is not None:
            layers["application"] = "PASS"
        layers["latency"] = "PASS" if e2e_ms is not None or ws_ms is not None else "NOT_TESTABLE"
        return layers

    # failed probe — locate the failing layer, deeper layers are NOT_TESTABLE
    fail_layer = _classify_failure_layer(detail)
    if fail_layer == "dns":
        layers["dns"] = "FAIL"
    elif fail_layer == "tcp":
        layers["dns"] = "PASS"      # DNS worked (we got far enough to fail on TCP)
        layers["tcp"] = "FAIL"
    elif fail_layer == "tls":
        layers["dns"] = "PASS"
        layers["tcp"] = "PASS"
        layers["tls"] = "FAIL"
    else:  # protocol or transport-stage failure
        layers["dns"] = "PASS"
        layers["tcp"] = "PASS"
        if ws_ms is not None:
            # handshake timing exists → TLS + transport channel came up,
            # failure happened while speaking the protocol or the app path
            layers["tls"] = "PASS"
            layers["transport"] = "PASS"
            layers["protocol"] = "FAIL"
        else:
            layers["tls"] = "NOT_TESTABLE"
            layers["transport"] = "FAIL"
            layers["protocol"] = "NOT_TESTABLE"
        if test_kind == "tcp-connect":
            # TCP probe that failed: only DNS/TCP known
            layers["tls"] = "NOT_TESTABLE"
            layers["transport"] = "NOT_TESTABLE"
            layers["protocol"] = "NOT_TESTABLE"
    layers["latency"] = "FAIL"
    return layers


def finalize_layers(layers: dict, samples: List[ProbeSample],
                    score: Optional[int]) -> dict:
    """Fill LATENCY / LOSS / QUALITY layers from history + score. PURE.

      latency — PASS when the newest successful probe carried timing numbers,
                FAIL when the newest probe failed, NOT_TESTABLE with no samples
      loss    — PASS when loss ratio is 0, FAIL when > 0, NOT_TESTABLE w/o samples
      quality — PASS when score ≥ 70, FAIL when score < 70, NOT_TESTABLE w/o score
    """
    out = dict(layers or _empty_layers())
    if not samples:
        return out
    last = samples[-1]
    last_ok_with_timing = last.ok and (last.ws_ms is not None or last.e2e_ms is not None)
    out["latency"] = "PASS" if last_ok_with_timing else "FAIL"
    loss_ratio = sum(1 for s in samples if not s.ok) / len(samples)
    out["loss"] = "PASS" if loss_ratio == 0 else "FAIL"
    if score is None:
        out["quality"] = "NOT_TESTABLE"
    else:
        out["quality"] = "PASS" if score >= HEALTHY_SCORE else "FAIL"
    return out


# ── Recording ───────────────────────────────────────────────────────────────

async def record_probe(uid: str, link: dict, probe_result: dict,
                       runtime_state: Optional[str] = None,
                       node_load: Optional[float] = None) -> HealthRecord:
    """Record one real probe result (shape: link_health._run_link_ping output)."""
    allowed = _allowed_fn(link) if _allowed_fn else bool(link.get("active", True))
    sample = ProbeSample(
        ts=time.time(),
        ok=bool(probe_result.get("ok")),
        ws_ms=probe_result.get("ws_ms"),
        e2e_ms=probe_result.get("e2e_ms"),
    )
    async with _lock:
        hist = _history.setdefault(uid, deque(maxlen=HISTORY_LEN))
        hist.append(sample)
        samples = list(hist)
        state, score, error = classify(allowed, samples,
                                       runtime_state=runtime_state,
                                       node_load=node_load)
        e2e_vals = [s.e2e_ms for s in samples if s.ok and s.e2e_ms is not None]
        rec = _records.get(uid) or HealthRecord(uid=uid, protocol=link.get("protocol", ""))
        rec.protocol = link.get("protocol", rec.protocol)
        rec.state = state
        rec.score = score
        rec.error = error or (None if sample.ok else str(probe_result.get("detail", ""))[:200])
        rec.latency_ms = e2e_vals[-1] if e2e_vals else None
        rec.handshake_ms = sample.ws_ms
        rec.jitter_ms = round(statistics.stdev(e2e_vals), 1) if len(e2e_vals) >= 2 else None
        rec.loss_pct = round(100.0 * sum(1 for s in samples if not s.ok) / len(samples), 1)
        rec.consecutive_ok = 0
        rec.consecutive_fail = 0
        for s in reversed(samples):
            if s.ok and rec.consecutive_fail == 0:
                rec.consecutive_ok += 1
            elif not s.ok and rec.consecutive_ok == 0:
                rec.consecutive_fail += 1
            else:
                break
        rec.samples = len(samples)
        rec.checked_at = probe_result.get("checked_at") or datetime.now().isoformat()
        rec.checked_ts = probe_result.get("ts") or time.time()
        rec.health_expires_at = datetime.fromtimestamp(
            rec.checked_ts + HEALTH_TTL_SECONDS).isoformat()
        rec.layers = finalize_layers(
            derive_layers(allowed, probe_result, link), samples, score)
        rec.last_probe = dict(probe_result)
        _records[uid] = rec
        # attach to the link record so it persists with the next save
        try:
            link["health"] = rec.to_dict()
        except Exception:
            pass
    return rec


def mark_invalid(uid: str, link: dict, reason: str) -> HealthRecord:
    """Mark a config INVALID without probing (not allowed / bad state)."""
    rec = _records.get(uid) or HealthRecord(uid=uid, protocol=link.get("protocol", ""))
    rec.state = "INVALID"
    rec.score = None
    rec.error = reason[:200]
    rec.checked_at = datetime.now().isoformat()
    rec.checked_ts = time.time()
    rec.layers = {layer: "NOT_TESTABLE" for layer in LAYERS}
    rec.layers["config"] = "FAIL"
    _records[uid] = rec
    try:
        link["health"] = rec.to_dict()
    except Exception:
        pass
    return rec


# ── Probing ─────────────────────────────────────────────────────────────────

async def probe_config(uid: str, link: dict, via: str = "direct") -> HealthRecord:
    """Run a real probe through the injected probe function, then record."""
    if _probe_fn is None:
        return mark_invalid(uid, link, "health engine not wired to a probe executor")
    try:
        result = await _probe_fn(uid, link, via=via)
    except Exception as exc:
        result = {"ok": False, "detail": f"probe executor error: {type(exc).__name__}: {exc}"}
    return await record_probe(uid, link, result)


async def sweep(via: str = "direct", concurrency: int = 4,
                links_provider: Optional[Callable[[], Awaitable[list]]] = None) -> dict:
    """Probe every known config (bounded concurrency). Called by the job system."""
    if links_provider is None or _probe_fn is None:
        return {"ok": False, "reason": "engine not wired"}
    targets = await links_provider()
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _one(uid: str, link: dict):
        async with sem:
            try:
                return await probe_config(uid, link, via=via)
            except Exception as exc:
                return mark_invalid(uid, link, f"sweep error: {exc}")

    recs = await asyncio.gather(*[_one(u, d) for u, d in targets]) if targets else []
    by_state = {s: 0 for s in STATES}
    expired = 0
    for r in recs:
        by_state[r.effective_state()] = by_state.get(r.effective_state(), 0) + 1
        if r.is_expired():
            expired += 1
    return {
        "ok": True, "via": via, "total": len(recs),
        "by_state": by_state, "expired": expired,
        "checked_at": datetime.now().isoformat(),
    }


# ── Introspection ───────────────────────────────────────────────────────────

def get_health(uid: str) -> Optional[HealthRecord]:
    return _records.get(uid)


def get_health_dict(uid: str) -> Optional[dict]:
    r = _records.get(uid)
    return r.to_dict() if r else None


def all_health() -> Dict[str, dict]:
    return {uid: r.to_dict() for uid, r in _records.items()}


def healthy_uids(min_score: int = HEALTHY_SCORE) -> List[str]:
    """UIDs currently HEALTHY (unexpired evidence) with score ≥ min.

    Phase 37.13: subscriptions must never blindly include stale-healthy
    configs — expired evidence is UNKNOWN here and therefore excluded.
    """
    out = []
    for uid, r in _records.items():
        if r.effective_state() == "HEALTHY" and (r.score or 0) >= min_score:
            out.append(uid)
    return out


def summary() -> dict:
    by_state = {s: 0 for s in STATES}
    expired = 0
    for r in _records.values():
        by_state[r.effective_state()] = by_state.get(r.effective_state(), 0) + 1
        if r.is_expired():
            expired += 1
    return {
        "tracked": len(_records),
        "by_state": by_state,
        "expired": expired,
        "health_ttl_s": HEALTH_TTL_SECONDS,
        "engine": "network_health/2.0",
        "formula": score_formula(),
    }


def reset_for_tests() -> None:
    """Test helper: wipe engine state (used by the integration suite)."""
    _records.clear()
    _history.clear()
