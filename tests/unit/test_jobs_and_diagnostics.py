"""Unit tests for job_system.py (Phase 20) and diagnostics.py (Phase 21)."""
import asyncio
import time

import pytest

import job_system as js
import diagnostics as diag


@pytest.fixture(autouse=True)
def _fresh_job_system():
    system = js.JobSystem()
    yield system
    # ensure no supervisor task leaks between tests
    if system._task:
        system._task.cancel()


# ── Job System ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_and_dedup():
    s = js.JobSystem()
    calls = []

    async def job():
        calls.append(1)

    s.register("j1", job, interval=60)
    s.register("j1", job, interval=60)  # same name replaces, no duplicate
    assert len(s._jobs) == 1

@pytest.mark.asyncio
async def test_run_now_success():
    s = js.JobSystem()
    ran = []

    async def job():
        ran.append(time.time())

    s.register("j", job)
    r = await s.run_now("j")
    assert r["ok"] and r["duration_ms"] >= 0
    assert len(ran) == 1
    status = {j["name"]: j for j in s.status()["jobs"]}
    assert status["j"]["last_status"] == "OK"
    assert status["j"]["run_count"] == 1

@pytest.mark.asyncio
async def test_run_now_unknown_job():
    s = js.JobSystem()
    r = await s.run_now("nope")
    assert not r["ok"]

@pytest.mark.asyncio
async def test_retry_then_fail():
    s = js.JobSystem()
    attempts = []

    async def failing():
        attempts.append(1)
        raise RuntimeError("boom")

    s.register("f", failing, retries=2, backoff=0.01)
    r = await s.run_now("f")
    assert not r["ok"]
    assert "boom" in r["error"]
    assert len(attempts) == 3  # 1 + 2 retries
    status = {j["name"]: j for j in s.status()["jobs"]}
    assert status["f"]["last_status"] == "FAILED"
    assert status["f"]["fail_count"] == 1

@pytest.mark.asyncio
async def test_timeout_kills_job():
    s = js.JobSystem()

    async def sleepy():
        await asyncio.sleep(30)

    s.register("slow", sleepy, timeout=0.05, retries=0)
    t0 = time.monotonic()
    r = await s.run_now("slow")
    assert not r["ok"] and "timeout" in r["error"]
    assert time.monotonic() - t0 < 2.0

@pytest.mark.asyncio
async def test_lock_prevents_overlap():
    s = js.JobSystem()
    running = []

    async def slow():
        running.append("in")
        await asyncio.sleep(0.1)
        running.append("out")

    s.register("locky", slow)
    first = asyncio.ensure_future(s.run_now("locky"))
    await asyncio.sleep(0.02)
    second = await s.run_now("locky")
    assert not second["ok"] and "already running" in second["error"]
    ok_first = await first
    assert ok_first["ok"]
    assert running == ["in", "out"]  # executed exactly once

@pytest.mark.asyncio
async def test_start_stop_supervisor():
    s = js.JobSystem()
    ticks = []

    async def fast_job():
        ticks.append(1)

    s.register("fast", fast_job, interval=0.05)
    await s.start()
    await asyncio.sleep(0.25)
    await s.stop()
    count_after_stop = len(ticks)
    await asyncio.sleep(0.2)
    assert len(ticks) >= 1
    assert len(ticks) == count_after_stop  # stopped → no more runs
    assert s.status()["supervisor"] == "STOPPED"

@pytest.mark.asyncio
async def test_disabled_job_not_run_by_supervisor():
    s = js.JobSystem()
    ticks = []

    async def job():
        ticks.append(1)

    j = s.register("off", job, interval=0.05)
    j.enabled = False
    await s.start()
    await asyncio.sleep(0.2)
    await s.stop()
    assert ticks == []


# ── Diagnostics ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clear_errors():
    diag._errors.clear()
    diag._error_counts.clear()
    yield
    diag._errors.clear()
    diag._error_counts.clear()


@pytest.mark.asyncio
async def test_record_error_structure():
    rec = await diag.record_error(code="TEST_CODE", message="something broke",
                                  component="unit-test", severity="WARNING",
                                  context={"uid": "abc"}, request_id="req-1")
    assert rec.code == "TEST_CODE"
    assert rec.severity == "WARNING"
    assert rec.component == "unit-test"
    d = rec.to_dict()
    assert d["timestamp_iso"] and d["request_id"] == "req-1"
    assert d["context"] == {"uid": "abc"}

@pytest.mark.asyncio
async def test_recent_errors_filtering():
    await diag.record_error("A", "a1", "c1", severity="INFO")
    await diag.record_error("B", "b1", "c2", severity="ERROR")
    await diag.record_error("A", "a2", "c1", severity="ERROR")
    all_rec = await diag.recent_errors(limit=10)
    assert len(all_rec) == 3
    only_c1 = await diag.recent_errors(component="c1")
    assert len(only_c1) == 2
    only_err = await diag.recent_errors(severity="ERROR")
    assert len(only_err) == 2

@pytest.mark.asyncio
async def test_error_stats_counts():
    for _ in range(3):
        await diag.record_error("REPEATED", "x", "c")
    stats = await diag.error_stats()
    assert stats["distinct_codes"] >= 1
    assert ("REPEATED", 3) in stats["top_codes"]

@pytest.mark.asyncio
async def test_message_and_context_truncated_no_crash():
    rec = await diag.record_error("BIG", "x" * 5000, "c", context={"k": "v" * 5000})
    assert len(rec.message) <= 300
    assert len(rec.context["k"]) <= 80

def test_record_error_sync():
    rec = diag.record_error_sync("SYNC", "msg", "comp")
    assert rec.code == "SYNC"

@pytest.mark.asyncio
async def test_overview_includes_known_checks():
    diag.set_persistence_probe(None)
    out = await diag.diagnostics_overview()
    assert out["ok"] is True
    assert "checks" in out
    for key in ("app", "persistence", "jobs", "network_health", "ip_quality", "protocols"):
        assert key in out["checks"]

@pytest.mark.asyncio
async def test_persistence_probe_injection():
    async def probe():
        return {"status": "OK", "links": 42}

    diag.set_persistence_probe(probe)
    out = await diag.diagnostics_overview()
    assert out["checks"]["persistence"] == {"status": "OK", "links": 42}
    diag.set_persistence_probe(None)
