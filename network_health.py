# network_health.py — Network Health Engine (Phases 6 & 7)
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
# Health score (0-100), weighted like the gaming engine but from full
# end-to-end probes:
#     40%  latency       (e2e_ms, baseline 250..2000ms)
#     20%  handshake     (ws_ms,  baseline 100..800ms)
#     20%  reachability  (1 - loss over recent history)
#     20%  stability     (consecutive successes)
#
# The engine keeps a small bounded history per config so jitter/trend data
# survives across requests without database writes (records are attached to
# the LINKS record as `health` on every save — persistence via main.save_state).

from __future__ import annotations
import asyncio
import time
import statistics
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Awaitable, Dict, List

# ── Tunables (env-overridable via main config layer conventions) ────────────

HISTORY_LEN = 8              # probes kept per config
E2E_BASELINE_MS = 250.0      # "perfect" end-to-end latency
E2E_MAX_MS = 2000.0          # latency at which score component = 0
WS_BASELINE_MS = 100.0
WS_MAX_MS = 800.0
HEALTHY_SCORE = 70
DEGRADED_FLAKY = 0.34        # >1/3 recent failures while currently ok → DEGRADED

STATES = ("HEALTHY", "DEGRADED", "UNREACHABLE", "INVALID", "UNKNOWN")


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
    error: Optional[str] = None
    latency_ms: Optional[float] = None
    handshake_ms: Optional[float] = None
    jitter_ms: Optional[float] = None
    loss_pct: Optional[float] = None
    consecutive_ok: int = 0
    consecutive_fail: int = 0
    samples: int = 0
    last_probe: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "protocol": self.protocol,
            "state": self.state,
            "score": self.score,
            "checked_at": self.checked_at,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "handshake_ms": self.handshake_ms,
            "jitter_ms": self.jitter_ms,
            "loss_pct": self.loss_pct,
            "consecutive_ok": self.consecutive_ok,
            "consecutive_fail": self.consecutive_fail,
            "samples": self.samples,
        }


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


# ── Scoring ─────────────────────────────────────────────────────────────────

def _norm(value: Optional[float], baseline: float, worst: float) -> float:
    if value is None:
        return 0.0
    if value <= baseline:
        return 1.0
    if value >= worst:
        return 0.0
    return 1.0 - (value - baseline) / (worst - baseline)


def compute_score(samples: List[ProbeSample]) -> Optional[int]:
    """Weighted score from real probe samples. None when no successful probe."""
    if not samples:
        return None
    successes = [s for s in samples if s.ok]
    if not successes:
        return 0
    e2e = [s.e2e_ms for s in successes if s.e2e_ms is not None]
    ws = [s.ws_ms for s in successes if s.ws_ms is not None]
    lat = _norm(statistics.mean(e2e), E2E_BASELINE_MS, E2E_MAX_MS) if e2e else 0.0
    hand = _norm(statistics.mean(ws), WS_BASELINE_MS, WS_MAX_MS) if ws else 0.0
    loss = len(samples) - len(successes)
    reach = 1.0 - (loss / len(samples))
    streak = 0
    for s in reversed(samples):
        if s.ok:
            streak += 1
        else:
            break
    stability = streak / len(samples) if samples else 0.0
    score = 100.0 * (0.40 * lat + 0.20 * hand + 0.20 * reach + 0.20 * stability)
    return max(0, min(100, round(score)))


def classify(link_allowed: bool, samples: List[ProbeSample]) -> tuple[str, Optional[int], Optional[str]]:
    """Classify into (state, score, error). Pure function — unit-testable."""
    if not link_allowed:
        return "INVALID", None, "config not allowed (disabled / expired / quota exhausted)"
    if not samples:
        return "UNKNOWN", None, None
    last = samples[-1]
    score = compute_score(samples)
    if not last.ok:
        return "UNREACHABLE", score, "last probe failed (connect / TLS / handshake / egress)"
    loss = sum(1 for s in samples if not s.ok) / len(samples)
    if loss > DEGRADED_FLAKY or (score is not None and score < HEALTHY_SCORE):
        return "DEGRADED", score, None
    return "HEALTHY", score, None


# ── Recording ───────────────────────────────────────────────────────────────

async def record_probe(uid: str, link: dict, probe_result: dict) -> HealthRecord:
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
        state, score, error = classify(allowed, samples)
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
    for r in recs:
        by_state[r.state] = by_state.get(r.state, 0) + 1
    return {
        "ok": True, "via": via, "total": len(recs),
        "by_state": by_state,
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
    """UIDs currently HEALTHY (or DEGRADED with a decent score). For subscriptions."""
    out = []
    for uid, r in _records.items():
        if r.state == "HEALTHY" and (r.score or 0) >= min_score:
            out.append(uid)
    return out


def summary() -> dict:
    by_state = {s: 0 for s in STATES}
    for r in _records.values():
        by_state[r.state] = by_state.get(r.state, 0) + 1
    return {
        "tracked": len(_records),
        "by_state": by_state,
        "engine": "network_health/1.0",
    }
