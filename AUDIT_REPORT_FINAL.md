# AUDIT_REPORT_FINAL.md — EMIX-PRO v11 Full Repository Audit

> **UPDATE 2026-09-02 (post-audit, v11.2.0-egress): CRITICAL PRODUCTION DEFECT — FALSE EGRESS / CUSTOM IP SEMANTICS — FOUND & FIXED.**
> Production evidence: selected node Railway–Amsterdam, "Custom IP" 185.164.73.192, **actual detected egress 208.77.244.84 (Railway, Amsterdam)**. The UI's "IP سفارشی" field only set the **client dial address (entry)** and never controlled routing — while the label "لوکیشن خروج" implied country egress. Root cause: endpoint-layer values (address/SNI/hostname) were presented as egress claims, and exit detection was a heuristic string-check (`upstream.includes('railway.app')`) in the frontend.
> Fix (single source of truth — `egress_engine.py` + 45 regression tests, suite **687/687 green**):
> - **Node roles** derived from physical reality: CONTROL_PLANE / EXIT_NODE / RELAY_NODE / EDGE_NODE / HYBRID (a Railway upstream is always a relay into the control plane — it can never masquerade as an arbitrary-country exit).
> - **Egress Verification Engine**: measured evidence only (public IP, ASN, ISP, country, city, IPv4/IPv6, timestamp, measurement source), classified **VERIFIED_EGRESS / CONFIGURED_ONLY / UNKNOWN** with TTL expiry — a configured IP is NEVER reported as the actual egress.
> - **Route model** entry→relay→exit→egress with per-route health and labeled latency (control_plane_rtt / node_rtt / route_rtt / protocol_handshake_rtt).
> - **9-step route validation pipeline** (`POST /api/egress/validate-route`): resolve → connect → verify node → verify route → verify egress → compare expected vs observed → latency → evidence → verdict. Expected≠observed ⇒ **ROUTE_MISMATCH** (never HEALTHY); country without a real exit node ⇒ **NO_EXIT_NODE_AVAILABLE** (never a faked label).
> - **Health layers split**: APPLICATION_HEALTH / NODE_HEALTH / ROUTE_HEALTH / EGRESS_HEALTH — a healthy Railway API says nothing about VPN egress health.
> - **UI honesty**: "IP سفارشی" renamed to "آدرس اندپوینت (ورودی — نه IP خروج)"; exit-location options marked "بدون نود خروج — خروج: Railway (کنترل‌پلین)"; new Route & Egress truth card (CONTROL PLANE / EXIT NODE / REAL EGRESS / STATUS DIRECT·RELAY·VERIFIED·UNKNOWN); gaming remarks state the true exit per link; `gamingCheckExitIP` now renders the engine verdict with evidence, mismatch alerts, and labeled latencies.
> - New APIs: `/api/egress/summary`, `/api/egress/verify`, `/api/egress/routes`, `/api/egress/validate-route`, `/api/egress/health`. Worker v2.2.0-egress returns ASN + ip_family + classification. Tests: tests/unit/test_egress_engine.py (28) + tests/integration/test_egress_semantics.py (17).


> **UPDATE 2026-09-02 (same audit cycle):** every P0 fix and the P1 persistence/frontend items from §5 have now been APPLIED and regression-tested (19 new tests in tests/integration/test_audit_fixes.py; suite: **642/642 green**). Statuses below describe the FOUND state; the fix plan in §5 is executed — see MIGRATION_GUIDE_FINAL.md §3 for the change log. Two additional latent production bugs were found and fixed during fix-verification: the em-dash HTTP-header crash on /sub-all-v2, and the shipped JS syntax error that killed the Diagnostics Center UI since v11.0.0-arch.

> Phase A (Recon + Audit) deliverable of the master evolution plan.
> Evidence-based: every classification below was verified against code (file:line), runtime wiring, and the 623-test suite.
> Baseline audited: working tree on top of commit `bccf0d7` (v11.0.0-arch) — includes Phase 37.9/37.10/37.11 modules (node_manager, runtime_supervisor, config_lifecycle) with 72 new tests.
> Audit date: 2026-09-02. Auditor: GLM-5.3 (principal architect).
> Honesty contract: no feature is called IMPLEMENTED unless the full path (UI → API → engine → runtime → persistence) works.

---

## 1. Method

- 3 parallel recon agents mapped: (a) backend core (main.py 4,833 lines, 11 engine modules, persistence, jobs), (b) protocol/transport layer (all 18 adapters, relay runtimes, link emitters, compat matrix), (c) frontend (pages.py 10,614 lines, every page loader, all 164 fetch call-sites cross-checked against 239 backend routes).
- Every P0 finding below was then personally re-verified in-source by the lead engineer before being accepted.
- Test suite executed 5×: 623 passed, 622 passed + 1 flaky (order/timing-dependent cold-start flake in `test_health_endpoints`, root cause: health-tracker registration depends on a probe side effect — see §5.3).
- Status vocabulary: IMPLEMENTED / PARTIAL / BROKEN / FAKE-UI / NOT_IMPLEMENTED / NOT_TESTABLE / DUPLICATED / DEPRECATED.

---

## 2. System snapshot

| Property | Value |
|---|---|
| Entry point | `main.py` (FastAPI, uvicorn workers=1) — 4,834 lines |
| Frontend | `pages.py` — 10,614 lines single-file admin UI (vanilla JS) |
| Persistence | **No database.** Single JSON state file `/data/rvg_state.json` (atomic tmp+rename, debounced 2 s) + feature sidecar JSONs |
| Endpoints | 258 HTTP routes (132 direct + 126 via 19 registered modules) |
| Tests | 623 passing (mixed: unit, mocked-integration, DB-file integration, runtime integration; real-network where marked) |
| Engines (Phase 36/37) | compat, config_compiler, endpoint_profiles, network_health, ip_quality, job_system, diagnostics, smart_route, node_manager, runtime_supervisor, config_lifecycle — all exist, all wired, all tested |
| Real runtimes in-process | 8 relay routes (vless-ws, vless-xhttp ×2 modes, trojan-ws, trojan-xhttp ×2, ss-ws + shared XHTTP session engine), SOCKS5, HTTP-proxy outbound |
| Real runtimes subprocess | MTProto official binary (compiled from source, per-uuid supervised, real stats polling) |
| External deps at runtime | Cloudflare Worker (optional WTE/gaming), ipapi.co / ipinfo.io / ip-api.com (IP intelligence), api.qrserver.com (QR!), central worker (announcements/support) |

---

## 3. Feature classification (the core table)

Legend: **IMPLEMENTED** = full path works end-to-end, evidence cited. Others follow the vocabulary above.

### 3.1 Core platform

| Feature | Status | Evidence / Limitation |
|---|---|---|
| Auth (password login, session cookie) | **PARTIAL** | Login/logout/me/change-password work (main.py:1785–1796). BUT: default password "123456" if `ADMIN_PASSWORD` unset (main.py:358); sessions in-memory → all sessions lost on restart; login rate-limit only behind experimental flags (default OFF → brute-forceable); SHA256(secret-salted) but unsalted-per-user and fast. |
| Session persistence | **NOT_IMPLEMENTED** | `SESSIONS` dict in-memory; Railway redeploy logs everyone out. |
| Config CRUD (`/api/links`) | **PARTIAL** | Full CRUD + idempotency map (TTL 600 s, cap 500). Create path still silently coerces `fingerprint→"chrome"` (main.py:2418) and `ss_cipher→default` (2532) despite "strict, no coercion" policy — documented deviation. |
| Config Compiler (canonical) | **PARTIAL** | Pipeline real: normalize → compat validate → credentials → endpoint semantics → emit → self-check → parse-back → checksum (config_compiler.py:400). Byte-identical wire-compat proven by tests. **Gap:** `_generate_share_link_legacy` (main.py:1062–1196) is a full duplicate kept as emergency fallback; MTProto bypasses the compiler entirely (main.py:1033); 3 independent vless-URI builders coexist (compiler / legacy fallback / multiloc `_forge_vless_link`). |
| Compatibility matrix (SSoT) | **IMPLEMENTED** | compat.py: 34 combos (8 VALID / 7 EXPERIMENTAL / 5 NOT_IMPLEMENTED / 14 INVALID) + SERVER_RUNTIME table + READINESS. Served at `/api/config-matrix`, consumed by frontend gating (cmLoadMatrix) and diagnostics. **Gap:** frontend degrades silently to allow-all if the matrix fetch fails (pages.py:7332). |
| Endpoint Profiles | **PARTIAL** | Full CRUD + validate + resolve + legacy spoof_sni migration (endpoint_profiles.py). Persisted via save/load_state. **Gap:** deleting a profile leaves dangling `endpoint_profile_id` on links → silent fallback to standard, no cleanup, no warning. |
| Network Health Engine | **PARTIAL** | Real state machine (8-sample window), deterministic score (0.30 availability + 0.25 latency + 0.15 handshake + 0.15 jitter + 0.15 stability), 10-layer decomposition, 15-min TTL expiry, UNKNOWN-after-expiry. **Bug:** background health-sweep probes throwaway copies of links → sweep results never persist to LINKS (main.py:436–438 + network_health.py:469–472) — health only persists from initial-create probe and manual probe route. Restart wipes all records to UNKNOWN (by design, but stale persisted `link["health"]` serves as read-only fallback main.py:4530). |
| Health expiration | **IMPLEMENTED** | `health_checked_at` / TTL 15 min / effective UNKNOWN after expiry (network_health.py). |
| IP Quality Engine | **PARTIAL** | Real TCP×3 + real TLS handshake + DNS consistency + 2–3 HTTP providers in parallel; honest UNKNOWNs; provider ABC + cache TTL 6 h + prune job. **Gap:** ip-api.com queried over **plain HTTP** (ip_quality.py:195) — queried IPs leak to on-path observers; cache lost on restart. |
| Job system | **IMPLEMENTED** | Per-job asyncio.Lock, per-run timeout, bounded retries with backoff, name dedup, counters (job_system.py). 7 jobs registered (health-sweep 600 s, expiry-sweep 300 s, ip-quality-prune 3600 s, node-heartbeat 120 s, runtime-supervision 60 s, mtproto-stats 120 s, lifecycle-reconcile 300 s). **Gap:** single-worker assumption (fine — uvicorn workers=1); a job stuck longer than its interval silently skips runs. |
| Diagnostics Center | **IMPLEMENTED** | Structured error deque(100), middleware (request IDs, slow-request >2 s, unhandled-exception → 500 JSON), overview aggregating 10 subsystems. In-memory only (lost on restart — acceptable for an error feed, documented). **Gap:** iterates LINKS without lock via reverse `from main import LINKS` (diagnostics.py:246). |
| Smart Route v3 | **PARTIAL** | `rank_rows` pure + explainable `ranking_reason` per candidate (health/latency/loss/load/reliability weighted), endpoint `/api/exp/route/configs/ranked`. **Gaps:** v1 upstream registry is experimental-gated and unpersisted; v1 does blocking socket.connect in request path; consumes health data that the sweep fails to persist (see above) → rankings refresh correctly only via manual probe-all. |
| Node Manager (37.9) | **BROKEN (route)** | Engine implemented + tested + persisted (managed_nodes in state file), heartbeats, maintenance, runtime-health evaluators. **BUT its primary API `GET /api/nodes` (main.py:4697) is SHADOWED by the outbound-panels route at main.py:3217 — FastAPI serves the first match → flagship endpoint unreachable in production.** |
| Runtime Supervisor (37.10) | **PARTIAL** | Crash detection → diagnostics record → node heartbeat DOWN → exponential backoff restart (5 s→300 s, 5 restarts/900 s, give-up FAILED). **Gap:** only runtimes registered at startup are supervised — MTProto instances created after startup are never attached to the supervisor (main.py:587 registers only at boot); restart counters lost on panel restart. |
| Config Lifecycle (37.11) | **IMPLEMENTED** | Pure `derive_lifecycle` (CREATED/VALIDATING/HEALTHY/DEGRADED/FAILED/EXPIRED/REVOKED) + reconcile job persists state+reason onto links. |
| Subscription engine | **PARTIAL** | v2 profiles (ALL/HEALTHY/FASTEST/REGION/PROTOCOL/CUSTOM) + v1 legacy output preserved; expiry/quota/disabled filtering; group subs with passwords. **Gap:** HEALTHY/FASTEST profiles depend on Network Health records that the background sweep fails to persist (same root bug) — after a restart, filtering quality degrades to UNKNOWN-based behavior until manual re-probe. |
| Backup export/import | **IMPLEMENTED** | validate → stage → rollback → verify → commit (backup_validator.py), tested. |
| Traffic accounting | **PARTIAL** | Real EWMA-adaptive batch accounting (64 KB…4 MB / ≤5 s) via `_QuotaGate` both directions, quota enforced at open + per-batch, persisted via debounced save. **Gaps:** overshoot up to one batch (~4 MB) before cutoff; `stats`/`hourly_traffic` totals are in-memory → traffic history resets on restart; vless/xhttp relays call raw `save_state()` on connection close while trojan uses the debounced path (inconsistent write amplification). |
| Accounts engine | **NOT_IMPLEMENTED** | No account entity. Each link IS the credential (single-user-per-link model). SUBS are link groups, not accounts. No per-user auth, no user management. (Design decision to document, not a bug.) |
| Device engine | **NOT_IMPLEMENTED** | `/api/connections` groups live connections by IP (ephemeral). No device fingerprint, no device limits, no revoke/disconnect per device. |
| Multi-node failover / drain | **NOT_IMPLEMENTED** | Node Manager tracks nodes; no automatic failover, no drain mode, no recovery policy engine yet. |
| Automation engine | **PARTIAL** | The 7 jobs ARE declarative automations (expiry→disable, health→recheck, crash→restart). No general trigger/condition/action/cooldown abstraction, no audit log of automated actions. |

### 3.2 Protocol layer

| Feature | Status | Evidence / Limitation |
|---|---|---|
| vless-ws relay (real server) | **IMPLEMENTED** | Real in-process VLESS server: auth gate, 0-RTT early-data (ed=2048), header parse, real TCP egress IPv4-first, 1 MB buffers, `X-EMIX-Ping` fast path (protocol/vless/websocket.py:50–152). Real health probe exists (adapter → link_health._probe_ws_tunnel). |
| trojan-ws relay | **IMPLEMENTED** | Real SHA224 auth cache, relay both directions (protocol/trojan/websocket.py). |
| shadowsocks-ws relay (AEAD) | **IMPLEMENTED** | Real crypto: HKDF-SHA1 subkey, EVP_BytesToKey, ChaCha20Poly1305/AES-GCM (protocol/shadowsocks/shadowsocks.py:26–78). |
| XHTTP (packet-up + stream-up) | **IMPLEMENTED** | Shared session engine: reaper, AIMD adaptive flow 256 KB–32 MB, EWMA QuotaGate. stream-on removed as uplink mode (honest). gRPC = envelope mimicry only (content-type), correctly classified NOT_TESTABLE. |
| MTProto (subprocess) | **IMPLEMENTED** | Official MTProxy binary compiled from source, per-uuid subprocess with FakeTLS, real secret from core.telegram.org, process watcher, graceful kill, real stats polling, psutil connection listing. Honest "no byte counters" doc. |
| SOCKS5 (Zeus) / HTTP proxy | **IMPLEMENTED** | Real asyncio SOCKS5 server; HTTP-proxy adapter does a real outbound HTTPS probe. |
| VMess / VLESS-Reality / SS-2022 adapters | **BETA (config-gen only)** | Emit valid links; health_check honestly returns NOT_TESTABLE (no inbound runtime). |
| WireGuard / OpenVPN adapters (vpn_pro) | **BETA + page unreachable** | Real X25519 keygen + .ovpn emission with embedded certs, but: no runtime (Railway can't host them — control-plane only), **nav item commented out → entire ~700-line page unreachable**, and generated WG keys are in-memory → **lost on restart**. |
| TUIC / Hysteria2 / NaiveProxy | **NOT_IMPLEMENTED (honest)** | DEFERRED returns, validate always False. |
| SSH adapter | **NOT_TESTABLE** | asyncssh not installed; emits ssh:// links only. |
| httpupgrade transport | **NOT_IMPLEMENTED (honest)** | Refuses to generate; correctly classified. |
| Adapter contract | **PARTIAL** | Base contract covers metadata/capabilities/validate/configure/generate_link/health_check/start/stop/status. Extended contract (restart/latency_test/traffic_stats/online_clients/export/cleanup/diagnostics) implemented by ZERO adapters. MTProto process orchestration lives in main.py (~160 lines, §5.6) — protocol logic scattered in the entrypoint. |

### 3.3 Frontend (pages.py)

| Feature | Status | Evidence |
|---|---|---|
| All 18 nav pages data-backed | **IMPLEMENTED** | Every reachable page loader fetches real APIs. Fakes are specific widgets (below). |
| Create-config compat gating | **IMPLEMENTED (gated)** | Consumes `/api/config-matrix`, blocks EXPERIMENTAL/NOT_IMPLEMENTED/INVALID with reason toast (cmGateCombo). Degrades to allow-all if matrix fetch fails. |
| uTLS fingerprint button | **BROKEN** | Calls `/api/exp/link/utls`; backend route is case-sensitive `/api/exp/link/uTLS` (exp_api.py:153) → always 404. |
| Zeus TLS-Mask save | **BROKEN** | Duplicate `id="zeus-tls-sni"` (div:3542 before input:3592) → JS reads the div → TypeError every time → misleading "connection error" toast. |
| VPN Pro page | **DEPRECATED (unreachable)** | Nav commented out (pages.py:3049–3051); ~700 lines orphaned. |
| Domain-gen / domain-scan / suggest-domain modals | **DEAD CODE** | Never openable (no caller). MTProto auto-domain widget: invalid inline style (comma → declarations dropped) + referenced elements don't exist. |
| Overview service-status card | **FAKE-UI** | Six hardcoded green "فعال" statuses, no API (pages.py:3156–3168). |
| Overview distribution chart | **FAKE-UI** | Doughnut with hardcoded `data:[55,35,10]` (pages.py:8231–8238). |
| Links info-strip (sent/recv, period usage) | **FAKE-UI** | `#info-sent-recv` / `#info-usage` never updated by any JS → permanently "0 B". |
| Login "GATEWAY ONLINE" badge | **FAKE-UI** | Static, no health check. |
| QR codes | **BROKEN (privacy)** | All 3 call-sites use third-party `api.qrserver.com`, sending full vless:// links (UUID credentials) AND WireGuard client configs **including private keys** to an external service. |
| Version strings | **STALE** | 6 hardcoded "v9.5/v9.7" strings vs actual v11. |
| Error handling | **PARTIAL** | 45 catch blocks: 35 completely empty. Good surfaces exist (create-modal 400 detail, bridge staged failures, diag center); loaders fail silently. |
| Diagnostics page auth | **PARTIAL** | Uses raw fetch → expired session renders zeros instead of redirecting to login. |
| Light theme | **BROKEN (CSS)** | Invalid selector `:[data-theme="light"]{` at lines 22 and 415 (public page correct). |

### 3.4 Security posture (pre-hardening)

| Area | Status | Evidence |
|---|---|---|
| SSRF guard on `/proxy/{target}` | **IMPLEMENTED** | Private nets + metadata IP + redirect-hop revalidation + header allowlist; tested (tests/integration/test_proxy_ssrf.py). |
| **Credential phone-home** | **BROKEN (security)** | central.py:19 sends `AUTH["password_hash"]` + domain to a third-party CF worker every 300 s, silently (all exceptions swallowed). Not documented anywhere. |
| **Hardcoded worker admin token in UI** | **BROKEN (security)** | pages.py:6246 embeds `X-EMIX-Token: emix-gw-7f3a…` + worker URL — visible to any logged-in user, grants location admin on the shared worker. |
| Login brute-force protection | **NOT_IMPLEMENTED (default)** | RateLimitMiddleware exists but only for `/api/login` and only when `EMIX_EXPERIMENTAL=1` + `EMIX_ENABLE_RATE_LIMIT=1`. Default off. |
| Self-update channel | **RISK (default-off)** | Downloads from unsigned manifest (sha1 optional, manifest-supplied), overwrites code. `DISABLE_UPDATES=1` default. One env var from active. |
| Password hashing | **PARTIAL** | SHA256(pw + panel-secret): salted per-panel but fast → brute-forceable if leaked (which the phone-home does). No argon2/bcrypt. |
| Secrets at rest | **PARTIAL** | `.rvg_secret` + `.bot_tcp_proxy_token` chmod 600; state file contains link UUIDs (credentials) unencrypted — standard for this class of panel, documented. |
| QR credential exfiltration | **BROKEN (privacy)** | See §3.3 QR row. |
| ip-api.com plaintext | **BROKEN (privacy)** | ip_quality.py:195. |
| Public sub password | **RISK (documented)** | Sent as `?pw=` query — visible in logs/history/Referer. Client-compat constraint; documented in SECURITY_AUDIT_FINAL.md. |

### 3.5 Cross-cutting code health

| Finding | Severity | Evidence |
|---|---|---|
| Route shadowing kills flagship API | P0 | main.py:3217 vs :4697. |
| Health-sweep results never persist | P0 | main.py:436–438 (copies) + network_health.py:469–472. |
| `'connections' in dir()` always False | P1 | main.py:536 — `dir()` in function scope lists locals, never globals → panel node `clients` always null. |
| 116 broad-except lines in main.py (17 `except→pass`) | P1 | Silent error swallowing census. |
| Reverse `from main import …` in 10+ modules | P1 | ip_quality.py:57, diagnostics.py:246, smart_route.py:374, central.py:12, relays — the "main-free, dependency-injected engines" claim holds for engines, not feature modules. |
| Dead env vars documented in 5 docs | P2 | `EMIX_SESSION_TTL` / `EMIX_SAVE_DEBOUNCE` defined in config_layer.py:48/56, never read (main.py hardcodes 7 d / 2 s). |
| SNI profiles docstring claims persistence — false | P1 | sni_management.py:15 vs save_state (never includes them). |
| Dead code | P2 | telemt.py (zero importers), ~500 lines dead JS (modals + quick-create + WS tester), `pingAllViaWorker` no caller. |
| Session/traffic/job-counter loss on restart | P1 | See §4. |

---

## 4. Persistence reality matrix (restart survival)

| State | Survives restart? | Mechanism |
|---|---|---|
| LINKS / SUBS / NODES / NODE_KEYS / password_hash | ✅ | rvg_state.json (atomic write, debounced) |
| endpoint_profiles | ✅ | persist/restore_snapshot wired into save/load_state |
| managed_nodes | ✅ | same bridge |
| link["last_ping"] | ✅ | written by every real probe |
| link["health"] (engine record) | ⚠️ partial | persisted only from create-probe + manual probe; **background sweep writes to throwaway copies** (P0 bug) |
| stats / hourly_traffic / connections / activity / errors | ❌ | in-memory; traffic history resets to 0 |
| SESSIONS | ❌ | in-memory; all logins dropped |
| network_health records/history, ip_quality cache | ❌ | by-design fresh-evidence policy; stale persisted health is read-only fallback |
| job counters, runtime supervisor restart counters | ❌ | in-memory |
| SNI profiles | ❌ | **docstring claims persisted — false** |
| vpn_pro WireGuard server/client keys | ❌ | in-memory store — generated keys LOST |
| gaming/zeus/bridge/multiloc/clean-ip configs | ✅ | own sidecar JSONs |

---

## 5. P0/P1 fix plan (drives Phases B–T)

1. **P0-security:** strip `panel_password_hash` from central registration + kill switch; remove hardcoded worker token from UI; local QR generation (backend `qrcode` lib); default-on login rate limiting; drop ip-api.com plaintext provider.
2. **P0-correctness:** un-shadow node-manager API (`/api/managed-nodes`); fix `dir()` bug; persist health-sweep results (write-back + debounced save); fix uTLS 404 (alias route); fix zeus-tls-sni duplicate ID; register MTProto runtimes with supervisor at creation time.
3. **P1:** wire dead env vars; persist SNI profiles + vpn_pro keys + sessions + traffic totals; debounced saves in vless/xhttp relays; supervisor persistence of counters; frontend real-data widgets (status card, distribution chart, info-strip, versions); replace empty catches with surfaced errors; fix light-theme CSS; re-enable VPN Pro page with honest "control-plane only" labeling.
4. **P2:** dead-code removal (telemt, orphaned modals, legacy quick-create); unify vless emitters long-term (compiler absorbs multiloc path); extract MTProto orchestration out of main.py.

---

## 6. What is genuinely production-grade today

- The 8-combo relay core (vless/trojan/ss × ws/xhttp) with real in-process servers, real quota accounting, real health probes, and byte-compatible link emission.
- MTProto subprocess lifecycle with real binary, real stats, honest limitations.
- The engine layer (compat/compiler/endpoint-profiles/health/ip-quality/jobs/diagnostics/lifecycle) — pure, tested, honest.
- SSRF-guarded proxy; backup with rollback; atomic persistence of the core state.

## 7. What is honestly not there yet

- Accounts/devices engines; multi-node failover & drain; automation abstraction; adapter extended contract; runtime supervision of post-boot instances; persistent sessions/traffic history; rate-limited login by default; local QR; half the observability story survives a restart.

— End of audit. Every claim above is re-verifiable from the cited file:line references.
