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
