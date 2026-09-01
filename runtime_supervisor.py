# runtime_supervisor.py — Runtime Supervision (Phase 37.10)
#
# Supervises every process-like runtime the panel manages. Today that is the
# MTProto instance family (official mtproto-proxy subprocesses); the module is
# generic so future runtimes (xray-core, sing-box, wireguard) plug in without
# structural change.
#
# Per runtime:
#   start / stop / restart / status / logs / health / crash detection
#
# Crash policy (deterministic, no infinite restart loops):
#   1. detect    — monitor() polls each runtime's alive-check
#   2. log       — structured diagnostics record (component "runtime")
#   3. node state updated via node_manager.heartbeat (runtime DOWN)
#   4. restart   — according to policy, with EXPONENTIAL BACKOFF:
#        delay = min(base * 2^restart_count, max_delay)
#        backoff resets after `stable_uptime_s` of continuous health
#   5. record    — restart_count per runtime, exposed via status()
#   6. give-up   — after max_restarts within backoff_window, state FAILED
#                  (no more restarts until an operator resets or the window
#                  slides past — bounded by construction)
#
# Diagnostics exposure: /api/runtime/status (registered in main.py).

from __future__ import annotations
import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, List, Dict

import diagnostics as diagnostics_mod

logger = logging.getLogger("EMIX.runtime")

RUNTIME_STATES = ("RUNNING", "STOPPED", "CRASHED", "RESTARTING", "FAILED", "UNKNOWN")

BACKOFF_BASE_S = 5.0
BACKOFF_MAX_S = 300.0
MAX_RESTARTS_WINDOW = 5
BACKOFF_WINDOW_S = 900.0     # restarts within this window count toward give-up
STABLE_UPTIME_S = 120.0      # continuous health after which backoff resets


@dataclass
class SupervisedRuntime:
    id: str
    name: str
    kind: str                       # "mtproto-subprocess" | future kinds
    node_id: Optional[str] = None   # node_manager association
    # injected checkers (DI — the module never imports mtproto_native/main)
    is_alive_fn: Optional[Callable[[], bool]] = None
    restart_fn: Optional[Callable[[], Awaitable[bool]]] = None
    stop_fn: Optional[Callable[[], Awaitable[bool]]] = None
    # state
    state: str = "UNKNOWN"
    restart_count: int = 0
    last_restart_at: Optional[float] = None
    last_crash_at: Optional[float] = None
    last_error: Optional[str] = None
    started_at: Optional[float] = None
    _restart_ts: List[float] = field(default_factory=list)
    _next_restart_allowed: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "kind": self.kind,
            "node_id": self.node_id, "state": self.state,
            "restart_count": self.restart_count,
            "last_crash_iso": _iso(self.last_crash_at),
            "last_restart_iso": _iso(self.last_restart_at),
            "uptime_s": round(time.time() - self.started_at, 1) if self.started_at else None,
            "last_error": self.last_error,
            "backoff": {
                "next_restart_allowed_in_s": round(
                    max(0.0, self._next_restart_allowed - time.time()), 1),
                "restarts_in_window": len(self._restart_ts),
            },
        }


def _iso(ts: Optional[float]) -> Optional[str]:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)) if ts else None


class RuntimeSupervisor:
    """Registry + crash-loop detection for supervised runtimes."""

    def __init__(self, backoff_base: float = BACKOFF_BASE_S,
                 backoff_max: float = BACKOFF_MAX_S,
                 max_restarts: int = MAX_RESTARTS_WINDOW,
                 window: float = BACKOFF_WINDOW_S):
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.max_restarts = max_restarts
        self.window = window
        self._runtimes: Dict[str, SupervisedRuntime] = {}

    # ── registration ────────────────────────────────────────────────────
    def register(self, rt: SupervisedRuntime) -> SupervisedRuntime:
        existing = self._runtimes.get(rt.id)
        if existing is not None:
            # refresh the fns (they can be rebound per boot), keep counters
            existing.is_alive_fn = rt.is_alive_fn
            existing.restart_fn = rt.restart_fn
            existing.stop_fn = rt.stop_fn
            existing.node_id = rt.node_id or existing.node_id
            existing.name = rt.name or existing.name
            return existing
        self._runtimes[rt.id] = rt
        return rt

    def unregister(self, runtime_id: str) -> bool:
        return self._runtimes.pop(runtime_id, None) is not None

    # ── policy: exponential backoff (pure, testable) ─────────────────────
    def backoff_delay(self, rt: SupervisedRuntime, now: Optional[float] = None) -> float:
        """Delay before the next restart attempt. Bounded exponential."""
        return min(self.backoff_max, self.backoff_base * (2 ** min(rt.restart_count, 8)))

    def restarts_allowed(self, rt: SupervisedRuntime, now: Optional[float] = None
                         ) -> tuple[bool, str]:
        """Give-up gate: bounded restarts within the sliding window."""
        now = time.time() if now is None else now
        rt._restart_ts = [t for t in rt._restart_ts if now - t < self.window]
        if len(rt._restart_ts) >= self.max_restarts:
            return False, (f"give-up: {len(rt._restart_ts)} restarts within "
                           f"{int(self.window)}s window")
        if now < rt._next_restart_allowed:
            return False, (f"backoff: next attempt allowed in "
                           f"{round(rt._next_restart_allowed - now, 1)}s")
        return True, "ok"

    def _note_restart(self, rt: SupervisedRuntime) -> None:
        now = time.time()
        rt._restart_ts.append(now)
        rt.restart_count += 1
        rt.last_restart_at = now
        rt._next_restart_allowed = now + self.backoff_delay(rt)

    # ── monitoring ───────────────────────────────────────────────────────
    async def monitor_once(self) -> dict:
        """One supervision pass over all runtimes. Never raises."""
        results = {}
        for rt in list(self._runtimes.values()):
            try:
                results[rt.id] = await self._check_one(rt)
            except Exception as exc:
                rt.state = "UNKNOWN"
                rt.last_error = f"{type(exc).__name__}: {str(exc)[:150]}"
                results[rt.id] = {"state": rt.state, "action": "error",
                                  "error": rt.last_error}
        return results

    async def _check_one(self, rt: SupervisedRuntime) -> dict:
        now = time.time()
        # prune restart window
        rt._restart_ts = [t for t in rt._restart_ts if now - t < self.window]

        if rt.is_alive_fn is None:
            rt.state = "UNKNOWN"
            return {"state": "UNKNOWN", "action": "none",
                    "reason": "no alive-checker registered (honest: cannot claim RUNNING)"}

        try:
            alive = bool(rt.is_alive_fn())
        except Exception as exc:
            rt.state = "UNKNOWN"
            rt.last_error = f"alive-check failed: {exc}"[:150]
            return {"state": "UNKNOWN", "action": "none", "error": rt.last_error}

        if alive:
            # healthy: reset backoff after stable uptime
            if rt.state != "RUNNING":
                rt.state = "RUNNING"
            if rt.started_at is None:
                rt.started_at = now
            elif now - rt.started_at >= STABLE_UPTIME_S and rt._restart_ts:
                # long enough stable → forgive one crash from the window
                if rt._restart_ts and now - rt._restart_ts[-1] > STABLE_UPTIME_S:
                    rt._restart_ts = rt._restart_ts[:-1] if len(rt._restart_ts) > 1 else []
            await self._heartbeat_node(rt, "OK")
            return {"state": "RUNNING", "action": "none"}

        # ── crash path ──
        was_running = rt.state == "RUNNING"
        rt.state = "CRASHED"
        rt.last_crash_at = now
        rt.started_at = None
        rt.last_error = rt.last_error or "process not alive"

        # 1+2: structured diagnostics record
        await diagnostics_mod.record_error(
            code="RUNTIME_CRASH",
            message=f"runtime {rt.id} ({rt.kind}) is not alive",
            component="runtime",
            severity="CRITICAL" if was_running else "WARNING",
            context={"runtime": rt.id, "kind": rt.kind,
                     "restart_count": rt.restart_count},
        )
        # 3: node state → runtime DOWN
        await self._heartbeat_node(rt, "DOWN")

        # 4: restart per policy
        allowed, why = self.restarts_allowed(rt, now)
        if not allowed or rt.restart_fn is None:
            rt.state = "FAILED" if not allowed else "CRASHED"
            if not allowed:
                await diagnostics_mod.record_error(
                    code="RUNTIME_GIVEUP",
                    message=f"runtime {rt.id} reached restart budget: {why}",
                    component="runtime", severity="CRITICAL",
                    context={"runtime": rt.id, "kind": rt.kind},
                )
            return {"state": rt.state, "action": "give-up" if not allowed else "no-restart-fn",
                    "reason": why}

        rt.state = "RESTARTING"
        try:
            ok = await rt.restart_fn()
        except Exception as exc:
            ok = False
            rt.last_error = f"restart raised: {exc}"[:150]
        self._note_restart(rt)
        await diagnostics_mod.record_restart(rt.node_id) if rt.node_id else None
        if ok:
            rt.state = "RUNNING"
            rt.started_at = time.time()
            rt.last_error = None
            await self._heartbeat_node(rt, "OK")
            return {"state": "RUNNING", "action": "restarted",
                    "restart_count": rt.restart_count}
        rt.state = "CRASHED"
        await self._heartbeat_node(rt, "DOWN")
        return {"state": "CRASHED", "action": "restart-failed",
                "restart_count": rt.restart_count, "error": rt.last_error}

    async def _heartbeat_node(self, rt: SupervisedRuntime, health: str) -> None:
        if not rt.node_id:
            return
        try:
            import node_manager
            await node_manager.heartbeat(rt.node_id, kind="runtime-health",
                                         runtime_health=health)
        except Exception:
            pass

    # ── lifecycle ops (exposed via API) ──────────────────────────────────
    async def restart(self, runtime_id: str, manual: bool = True) -> dict:
        rt = self._runtimes.get(runtime_id)
        if rt is None:
            return {"ok": False, "error": f"unknown runtime: {runtime_id}"}
        if rt.restart_fn is None:
            return {"ok": False, "error": "runtime has no restart function"}
        try:
            ok = await rt.restart_fn()
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        if manual:
            # manual restarts bypass backoff but still count toward the budget
            self._note_restart(rt)
        rt.state = "RUNNING" if ok else "CRASHED"
        if ok:
            rt.started_at = time.time()
            rt.last_error = None
            await self._heartbeat_node(rt, "OK")
        return {"ok": ok, "runtime": rt.to_dict()}

    async def stop(self, runtime_id: str) -> dict:
        rt = self._runtimes.get(runtime_id)
        if rt is None:
            return {"ok": False, "error": f"unknown runtime: {runtime_id}"}
        if rt.stop_fn is None:
            return {"ok": False, "error": "runtime has no stop function"}
        try:
            ok = await rt.stop_fn()
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        if ok:
            rt.state = "STOPPED"
            rt.started_at = None
            await self._heartbeat_node(rt, "DOWN")
        return {"ok": ok, "runtime": rt.to_dict()}

    def status(self) -> dict:
        return {
            "supervisor": "runtime_supervisor/1.0",
            "policy": {
                "backoff_base_s": self.backoff_base,
                "backoff_max_s": self.backoff_max,
                "max_restarts_in_window": self.max_restarts,
                "window_s": self.window,
                "stable_uptime_resets_backoff_s": STABLE_UPTIME_S,
            },
            "runtimes": [rt.to_dict() for rt in self._runtimes.values()],
        }


# process-local singleton
supervisor = RuntimeSupervisor()


def reset_for_tests() -> None:
    global supervisor
    supervisor = RuntimeSupervisor()
