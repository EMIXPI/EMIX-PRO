# job_system.py — background job framework (Phase 20)
#
# Moves expensive/periodic work out of HTTP requests with:
#   retry       — bounded attempts per run
#   timeout     — per-run wall clock kill
#   cancellation— clean stop() on shutdown
#   backoff     — exponential delay between attempts (base * 2^attempt)
#   locking     — per-job asyncio.Lock prevents overlapping runs
#   dedup       — registering the same name replaces the old job (no dupes)
#   observability— run_count/fail_count/last_error/last_duration_ms/status()
#
# One supervisor task drives everything; a crashed job never kills the loop.

from __future__ import annotations
import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Optional, Dict, List

logger = logging.getLogger("EMIX.jobs")

DEFAULT_INTERVAL = 300.0
DEFAULT_TIMEOUT = 120.0
DEFAULT_RETRIES = 2
DEFAULT_BACKOFF = 2.0


@dataclass
class Job:
    name: str
    fn: Callable[..., Awaitable]
    interval: float = DEFAULT_INTERVAL
    timeout: float = DEFAULT_TIMEOUT
    retries: int = DEFAULT_RETRIES
    backoff: float = DEFAULT_BACKOFF
    # runtime state
    run_count: int = 0
    fail_count: int = 0
    last_run: Optional[float] = None
    last_duration_ms: Optional[float] = None
    last_error: Optional[str] = None
    last_status: str = "PENDING"     # PENDING / OK / FAILED / RUNNING / CANCELLED
    enabled: bool = True
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


class JobSystem:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._task: Optional[asyncio.Task] = None
        self._stopping = False
        self._started_at: Optional[float] = None

    # ── registration (dedup by name) ─────────────────────────────────────
    def register(self, name: str, fn: Callable[..., Awaitable], **kwargs) -> Job:
        self._jobs.pop(name, None)  # dedup: same name replaces old job
        job = Job(name=name, fn=fn, **kwargs)
        self._jobs[name] = job
        logger.info("[jobs] registered %s (interval=%ss timeout=%ss retries=%s)",
                    name, job.interval, job.timeout, job.retries)
        return job

    def unregister(self, name: str) -> bool:
        return self._jobs.pop(name, None) is not None

    # ── lifecycle ─────────────────────────────────────────────────────────
    async def start(self) -> None:
        if self._task is not None:
            return
        self._stopping = False
        self._started_at = time.time()
        self._task = asyncio.create_task(self._supervise(), name="emix-job-supervisor")
        logger.info("[jobs] supervisor started (%d jobs)", len(self._jobs))

    async def stop(self) -> None:
        self._stopping = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("[jobs] supervisor stopped")

    # ── execution ─────────────────────────────────────────────────────────
    async def run_now(self, name: str) -> dict:
        job = self._jobs.get(name)
        if job is None:
            return {"ok": False, "error": f"unknown job: {name}"}
        ok, err, ms = await self._execute(job)
        return {"ok": ok, "job": name, "error": err, "duration_ms": ms}

    async def _execute(self, job: Job) -> tuple[bool, Optional[str], float]:
        if job._lock.locked():
            return False, "already running (lock held)", 0.0
        async with job._lock:
            job.last_status = "RUNNING"
            t0 = time.monotonic()
            err: Optional[str] = None
            attempt = 0
            while attempt <= job.retries:
                try:
                    await asyncio.wait_for(job.fn(), timeout=job.timeout)
                    err = None
                    break
                except asyncio.TimeoutError:
                    err = f"timeout after {job.timeout}s"
                except asyncio.CancelledError:
                    job.last_status = "CANCELLED"
                    raise
                except Exception as exc:
                    err = f"{type(exc).__name__}: {str(exc)[:200]}"
                attempt += 1
                if attempt <= job.retries:
                    delay = job.backoff * (2 ** (attempt - 1))
                    logger.warning("[jobs] %s failed (%s) — retry %d/%d in %.1fs",
                                   job.name, err, attempt, job.retries, delay)
                    await asyncio.sleep(delay)
            job.last_run = time.time()
            job.last_duration_ms = round((time.monotonic() - t0) * 1000, 1)
            job.run_count += 1
            if err is None:
                job.last_status = "OK"
                job.fail_count = 0
            else:
                job.last_status = "FAILED"
                job.fail_count += 1
                job.last_error = err
                logger.error("[jobs] %s FAILED permanently: %s", job.name, err)
            return err is None, err, job.last_duration_ms

    async def _supervise(self) -> None:
        while not self._stopping:
            now = time.time()
            next_wake = 5.0
            for job in list(self._jobs.values()):
                if not job.enabled:
                    continue
                due = (job.last_run is None) or (now - job.last_run >= job.interval)
                if due:
                    # fire and forget; the per-job lock prevents overlap
                    asyncio.create_task(self._execute(job))
                else:
                    remaining = job.interval - (now - job.last_run)
                    next_wake = min(next_wake, max(0.5, remaining))
            await asyncio.sleep(min(next_wake, 5.0))

    # ── introspection ─────────────────────────────────────────────────────
    def status(self) -> dict:
        jobs: List[dict] = []
        for job in self._jobs.values():
            jobs.append({
                "name": job.name,
                "enabled": job.enabled,
                "interval_s": job.interval,
                "timeout_s": job.timeout,
                "retries": job.retries,
                "run_count": job.run_count,
                "fail_count": job.fail_count,
                "last_status": job.last_status,
                "last_run": job.last_run,
                "last_duration_ms": job.last_duration_ms,
                "last_error": job.last_error,
                "next_due_in_s": (None if job.last_run is None
                                  else round(max(0.0, job.interval - (time.time() - job.last_run)), 1)),
            })
        return {
            "supervisor": "RUNNING" if self._task is not None and not self._task.done() else "STOPPED",
            "uptime_s": round(time.time() - self._started_at, 1) if self._started_at else None,
            "jobs": jobs,
        }


# module-level singleton (single-worker app — matches the persistence model)
jobs = JobSystem()
