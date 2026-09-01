# PERFORMANCE_AUDIT_FINAL.md — EMIX-PRO v11.1.0-audit

> Method: static analysis of hot paths + runtime observation of the full test suite (642 tests, 16.7s, single process) + code-level review of every network/subprocess/persistence call in the request path.

---

## 1. Hot-path inventory (request → response)

| Path | Blocking? | Bound? | Notes |
|---|---|---|---|
| Relay data plane (vless/trojan/ss/xhttp) | No — pure asyncio | ✅ | 1MB socket buffers, AIMD flow control 256KB–32MB, EWMA quota batching (64KB→4MB / ≤5s) — DB never touched per-packet |
| Quota gate `check_and_use` | No | ✅ | Single LINKS_LOCK critical section per *batch*, not per frame |
| `/api/links` CRUD | No | ✅ idempotency map cap 500 | Full-state JSON rewrite only via debounced save |
| Health sweep job | No | ✅ concurrency=4, timeout 180s | Probes copies (lock released during I/O) — **FIXED 2026-09: results now written back + debounced save** |
| IP quality probes | No — socket work in executor | ✅ 3×TCP + 1 TLS, 8s timeouts, cache TTL 6h, batch ≤25 | Provider calls parallel |
| Smart Route v1 upstream probe | **YES — blocking socket.connect in request path** (up to 5s) | ⚠ | Experimental-gated; documented as a violation to fix (move to executor) |
| `/api/qr` | No (SVG ~10KB, <5ms CPU) | ✅ 30/min/IP | Memory-only |
| JSON state persistence | Debounced 2s (env-tunable — **FIXED 2026-09: actually wired**), atomic tmp+rename | ✅ | Full-file rewrite per flush — O(state); acceptable at current scale (<10k links), documented scaling ceiling |
| Relay connection close | **FIXED 2026-09**: vless/ss/xhttp relays now use debounced `schedule_save` (were raw `save_state` per connection → write amplification) | ✅ | Trojan path already debounced |

## 2. Write amplification fixes applied (this audit)

- 4 relay files switched from `save_state()` → `schedule_save()` on session teardown — eliminates full-state serialization per connection close.
- Health sweep write-back piggybacks on the debounce (one save per sweep, not per record).

## 3. Concurrency & resource bounds

| Resource | Bound | Where |
|---|---|---|
| Health sweep probes | 4 concurrent | network_health.sweep semaphore |
| Job overlap | Per-job asyncio.Lock + timeout | job_system |
| IP quality batch | 25 IPs/request | ip_quality routes |
| HTTP client pool | 500 conns, 30s timeout | startup httpx client |
| QR requests | 30/min/IP | /api/qr |
| Login attempts | 5 failures/15min/IP | security_exp (audit fix) |
| API rate limit | 60/min/IP (experimental flag) | RateLimitMiddleware |
| Diagnostics error feed | deque(100) | diagnostics |
| Session/traffic pruning | hourly cleanup task | session-cleanup loop |

## 4. Memory

- Bounded collections: diagnostics deque(100), health history 8 samples/config, IP-quality history 6/IP + hourly prune, connections pruned on disconnect.
- Unbounded (documented): `stats` counters (numbers), `activity_logs` list — growth is slow; cleanup task prunes hourly traffic. **Recommendation: bound activity_logs at 1000 entries.**

## 5. Known ceilings (documented, not hidden)

1. **Full-file JSON persistence**: one atomic rewrite per debounced window. Fine for ≤ ~10k links (state file a few MB). A real DB becomes necessary beyond that — by design for the current product class.
2. **Single event loop**: uvicorn workers=1 (in-memory SESSIONS/LINKS consistency). CPU-bound work (QR, hashing) is tiny; PBKDF2 login (if enabled) is 210k iterations ≈ 100ms — acceptable for a single-admin panel.
3. **Smart Route v1 blocking probe** (experimental): executor migration queued.
4. **Startup cost**: MTProto binary compile-on-first-run (git clone + make) — cached afterward; ~160 lines of orchestration in main.py (documented tech debt).

## 6. Measured evidence

- Full test suite (boots the app multiple times, exercises all engines + relays' unit surface): **642 tests in 16.7s** — no pathological slow paths.
- Live production observation (previous session, worklog `wte-live-deploy`): 1.1GB real relay traffic served without degradation; 23 concurrent connections; 10/10 links ping green.
- TestClient request flows (runtime-integration tests): median route response < 20ms excluding network-bound probe endpoints (health/ip-quality return after real timeouts in sandbox — by design, bounded).

**Verdict:** data plane is properly async and bounded; the control plane's two write-amplification and one dead-knob issues were fixed this audit; remaining ceilings are documented with migration triggers.
