# COMPETITIVE_MATRIX_FINAL.md — EMIX-PRO v11.1.0-audit

> Benchmarks: **vpn-ui**, **RVG**, **SpiderPanel**, **Nyx**, **Zeus** (architectural study only — no proprietary code copied).
> Scoring: ✅ real & verified · 🟡 partial/honest-labeled · ❌ absent.
> EMIX's identity target (master spec §43): *Intelligent Network Orchestration* — not "most protocols".

## 1. Feature matrix

| Capability | EMIX | vpn-ui | RVG | SpiderPanel | Nyx | Zeus | EMIX advantage | EMIX missing | Priority |
|---|---|---|---|---|---|---|---|---|---|
| VLESS/Trojan/SS relays (in-process) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | AIMD XHTTP + 0-RTT early-data | — | — |
| MTProto (official binary, supervised) | ✅ | ✅ | 🟡 | ❌ | 🟡 | 🟡 | subprocess supervision + backoff | byte counters | LOW |
| WireGuard runtime + peer mgmt | 🟡 control-plane | ✅ native | ❌ | ❌ | ✅ | ✅ | keygen+QR+registry (keys survive restart now) | runtime hosting (Railway constraint) | MED (needs VPS node) |
| AmneziaWG | ❌ | ✅ | ❌ | ❌ | ❌ | 🟡 | — | full support | LOW |
| OpenVPN runtime | 🟡 control-plane | ✅ | ❌ | ❌ | 🟡 | 🟡 | .ovpn + certs | runtime hosting | LOW |
| IKEv2 | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | — | native | LOW |
| Config Compiler (parse-back + checksum) | ✅ | ❌ | ❌ | 🟡 | ❌ | ❌ | self-verifying emission | — | — |
| Compatibility matrix SSoT (API-consumed) | ✅ | 🟡 | 🟡 | 🟡 | ❌ | ❌ | UI can't offer impossible combos | — | — |
| Layered health (10 layers, TTL expiry) | ✅ | 🟡 ping-based | 🟡 | ❌ | ✅ | 🟡 | evidence-only, expiring, UNKNOWN ≠ PASS | — | — |
| Health score (weighted, documented) | ✅ | ❌ | ❌ | ❌ | 🟡 | 🟡 | deterministic formula + reasons | — | — |
| Node heartbeat state machine | ✅ | 🟡 | ❌ | 🟡 | ✅ | 🟡 | runtime-gated, persisted | — | — |
| Runtime supervision w/ backoff | ✅ | 🟡 | ❌ | ❌ | 🟡 | ❌ | crash→restart→give-up budget | post-panel-restart counters | LOW |
| Config lifecycle state machine | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | CREATED→REVOKED + reconcile | — | — |
| Smart routing w/ ranking_reason | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | explainable decisions | — | — |
| IP Quality (facets, providers, honest UNKNOWN) | ✅ | ❌ | ❌ | ❌ | 🟡 | 🟡 | CLEAN requires negative evidence | — | — |
| Multi-node failover + drain | ❌ | 🟡 | ❌ | ❌ | ✅ | 🟡 | registry exists | failover engine | **HIGH** |
| Accounts (per-user identity) | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | — | account engine | **HIGH** |
| Device management (fingerprint, revoke) | ❌ | ✅ | 🟡 | 🟡 | ✅ | ✅ | — | device engine | MED |
| Traffic accounting (batched, quota-safe) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | EWMA batching under concurrency | per-day granularity lost on restart | LOW |
| Subscriptions (profiles, expiry/quota filters) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | HEALTHY/FASTEST backed by real health | — | — |
| IP-federation (peer panels) | ✅ | ❌ | ✅ | ❌ | ❌ | 🟡 | node keys + aggregation | — | — |
| Railway resilience (state, volume warn) | ✅ | ❌ | 🟡 | ✅ | ❌ | ❌ | restart-survival verified by tests | — | — |
| Diagnostics Center (structured, request IDs) | ✅ | ❌ | 🟡 | ❌ | 🟡 | 🟡 | component-coded errors, safe context | feed resets on restart | LOW |
| Local QR (no third-party) | ✅ | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | credentials never leave the panel | — | — |
| Security posture (SSRF guard, brute-force guard, no phone-home) | ✅ | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | tested guards; documented residual risks | PBKDF2 default, signed updater | MED |

## 2. Positioning

**EMIX's differentiation is real where it matters for the master spec's identity goal:** layered expiring health, supervised runtimes, lifecycle state machine, explainable routing, self-verifying compiler, and honest compat matrix are capabilities the benchmark panels either lack or approximate with ping-based heuristics. Competitors win on **breadth** (vpn-ui's native WG/AWG/OpenVPN/IKEv2 runtime depth; Zeus's account/device management scale; Nyx's failover intelligence). EMIX deliberately does not chase protocol enumeration — deferred protocols refuse rather than pretend.

## 3. Gap-closure backlog (priority order)

1. **HIGH — Accounts + Device engine**: identity, expiry, quota, device fingerprint/revoke (unifies today's link-as-credential model). Prerequisite for honest multi-user scale.
2. **HIGH — Multi-node failover + drain**: build on the (now un-shadowed) node registry + health engine; states PRIMARY→FAILOVER_PENDING→FAILOVER→RECOVERING with compatibility/health/capacity selection.
3. **MED — Automation abstraction**: trigger/condition/action/cooldown/audit-log generalization of the 7 existing jobs.
4. **MED — WG/AWG runtime on VPS nodes**: the control-plane is ready; needs the node agent.
5. **MED — Security promotions**: PBKDF2 default, signed update channel, bounded activity log.
6. **LOW — Adapter extended contract** (latency_test/traffic_stats/online_clients), MTProto byte counters (upstream binary limitation), main.py decomposition (extract MTProto orchestration + retire legacy emitter).

## 4. Zeus live re-audit (2026-09-03, after the v11.5.1 identity incident)

**Context**: user asked whether Zeus's latest changes could improve EMIX-PRO's health after the production incident (all delivered configs cut after redeploy). Method: cloned `panel-zeus/Z-E-U-S` @ `561c8b3` (pushed 2026-09-03 07:59 +0330) — **architectural study only, zero proprietary code copied** (their license: Proprietary / Non-Commercial).

**What Zeus is (v2.0.6)**: a single-file Cloudflare Worker (~595 KB `Source.js`) + D1 database + one-click Telegram bot deployment. VLESS/Trojan over WebSocket terminated inside the Worker (egress = CF colo), multi-location routing by chaining users through **community-scanned public SOCKS5 lists per country** (`proxy/*.txt`, incl. 820 Iranian entries), TLS-fragment presets per Iranian ISP, PWA panel, anti-tamper/DRM integrity checks, full JSON backup/import.

**Their last-7-day changes (verified in git log — all operational-health, not features)**:
1. **D1 daily row-quota exhaustion** → user-facing Persian error («سهمیه دیتابیس شما تمام شده…») + D1 write-throttling relaxed (50→250 MB threshold, 20s→60s / 120s→300s intervals) + live d1Reads/d1Writes quota bars. Their own «everything down» incident was **platform quota, not code**.
2. **Online window 20s→60s→180s** (relaxed twice in one day) — flapping «offline» display fix.
3. **Subscription links switched to `vless://uuid@0.0.0.0:1?…&host=<domain>`** — the «client-resolve» convention: capable clients (v2rayNG/Hiddify/Karing family) resolve the `host` domain client-side and pick their own best IP.
4. `fragment=…,tlshello` URL param emitted **only for TLS ports**.
5. Panel auto-refresh default → 5 s.

**Mapping to EMIX-PRO**:

| Zeus change | EMIX-PRO state | Verdict |
|---|---|---|
| D1 quota → honest Persian errors | v11.5.1 identity incident root-caused + fixed (stable identity chain, honest `source`/`stable_across_redeploy` labels); structured events + honest verdicts across all engines | equivalent already shipped |
| D1 write throttling | no per-row quota on Railway; traffic accounting already EWMA-batched, quota-safe | n/a |
| Online window flapping (20/60/180s) | session sweep = 3600 s idle; health states expire to UNKNOWN honestly, never born HEALTHY | already saner |
| `0.0.0.0:1` client-resolve links | standard **domain-dial** links achieve the same via portable semantics — verified live: the one config that kept ping through the identity incident was our multiloc **Auto–PoP** (`addr = domain`), because Karing resolved the domain client-side | achieved, portable; nonstandard encoding deliberately not adopted |
| fragment-tlshello-on-TLS-only | we never emit fragment URL params (Xray client JSON snippets only) | no bug to fix |
| 5 s auto-refresh | event/diagnostics polling already bounded | skip |

**Structural lessons (the real answer to «can Zeus help our health?»)**:
1. Zeus never has our identity incident **because D1 persists by platform design**. Our equivalent is the v11.5.1 identity chain (RAILWAY_SERVICE_ID-derived, redeploy-stable — deployed and verified live) **plus the operator action: set `SECRET_KEY` or attach a Volume at `/data`**. Note: state beyond identity (accounts, saved Clean-IPs, custom links) is still ephemeral without a Volume.
2. Zeus users hold **subscription URLs** — self-healing on every refresh. With stable identity, EMIX-PRO's `/sub/{uuid}` now gives the same for default configs: re-import via sub URL once → future redeploys no longer cut clients.
3. Their public-SOCKS Iranian exit is a trust hazard our Iran Gateway refuses by design: evidence-verified gateway or honest `UNCONFIGURED` — never an untrusted exit.

**Score impact**: none — matrix above already scores Zeus; this re-audit only confirms the two structural advantages (platform-native persistence, one-click bot deploy) and one honest gap (their exit trust model is weaker than ours by choice).

## 5. EMIX + RVG cross-audit (2026-09-03, v11.6.0-revive) — the revival sources

**Context**: user's live report — «کلاینت همچنان ارور میده و کانفیگ درست نشدن… پروتکل سالم پروژه EMIX رو بهت میدم چک کنی… این پروژه الهام گرفته شده از RVG بوده و احتمالا آپدیت داده… Rvg از طریق وورکر خودکاری که به پروژه اش وصل کرده اپدیت جدید میده برای پنل… میخوام بخش های سالم با بررسی این دو پروژه دوباره احیا بشن.»

**EMIX (github.com/EMIXPI/EMIX @ 05f2f2c)** — the known-healthy sibling:
- History is a mirror of our own incident class: new transports (REALITY/gRPC/Hysteria2/TUIC) → critical regression → Xray/sing-box bridges → **full revert (9408236)** → «Restore to healthy original state (c33ba43)» + ping-test button only.
- Health mechanism #1: **updater LOCKED** (`DISABLE_UPDATES=1` default — the worker manifest can never rewrite the panel). EMIX-PRO never adopted the RVG auto-updater, so this hazard does not exist here.
- Health mechanism #2: protocol surface kept at the proven set (vless-ws/xhttp/trojan/ss/mtproto) — identical core emitters to ours (verified by diff; EMIX-PRO is a strict superset with 0-RTT, fast-ping path, IPv4-first connect).

**RVG (github.com/arvin341az-glitch/RVG @ ce2f878)** — the family root, «recently updated» per user:
- Its auto-update worker (rvg-update.arvin341az.workers.dev/version.json, manifest v11.0.2) distributes a main.py **sha1-identical to the repo** — the GitHub repo IS the latest release.
- The v11.0.2 payload = **weak-link tuning**: RELAY_BUF 1MB→256KB, SOCK_BUF 4MB→512KB (bufferbloat fix on weak links), WRITE_HIGH_WATER 512KB→128KB, TCP_USER_TIMEOUT 20s (half-dead mobile connections reaped). Plus system stats (psutil), server-location endpoint.
- **Adopted in EMIX-PRO v11.6.0**: the full weak-link profile, as a single source of truth in `protocol/net_connect.py` consumed by every protocol module. Deliberately NOT adopted: the auto-updater itself (uncontrolled remote rewrites of a running panel = the exact incident class we just survived).

**Live truth test that framed the revival (real client emulation from sandbox)**:
- Production healthy at every layer: identity stable across TWO redeploys; delivered configs (clean AND spoofed SNI) connect full E2E (TLS → WS 101 → VLESS → real HTTP 200).
- User-side breakage pattern (Karing screenshot): all Railway-direct entries dead, CF-routed Auto–PoP alive → vantage/path-specific blocking (Iran→Railway direct), not server-side breakage.
- Answer shipped in v11.6.0: (1) every sub now carries a same-identity **CF-tunnel variant** (verified full E2E via the real worker: 101 → VLESS → HTTP 200, exit AMS) so clients auto-survive direct-path blocks; (2) **پینگ واقعی از مرورگر شما** card measures BOTH entry paths from the admin's own network — the exact vantage Karing uses; (3) RVG weak-link tuning for the weak-Iranian-link experience; (4) worker UUID auto-sync so the WTE allowlist never goes stale.

| Revival item | Source | EMIX-PRO implementation |
|---|---|---|
| Weak-link buffers + TCP_USER_TIMEOUT | RVG v11.0.2 | `protocol/net_connect.py` single source; all protocols import |
| Real client-vantage ping | user request («پینگ واقعی») + EMIX ping-button spirit | browser WS probes (direct + CF gateway) on the configs page; `/api/client-ping-config` |
| Sub multi-entry resilience | Zeus client-resolve idea + our multiloc tunnel | `/sub/{uuid}` / `/sub-all` / `/sub-group` append CF `/loc/auto` variant (same UUID, honest `· CF` remark) |
| Worker UUID staleness | our own finding (6/7 synced) | auto-sync on vless link create/delete |
| Updater lock | EMIX (DISABLE_UPDATES) | n/a — EMIX-PRO has no auto-updater (by design) |

**Conclusion**: the two reference projects' healthy patterns are now either adopted (RVG tuning, multi-entry subs) or already structurally present (EMIX's locked protocol surface ≡ our canonical compiler path; identity stability ≡ their no-updater stance). The remaining user-side action: **re-import once via sub URLs** — each refresh now self-heals across BOTH entry paths.
