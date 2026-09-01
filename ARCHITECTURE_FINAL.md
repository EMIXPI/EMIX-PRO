# ARCHITECTURE_FINAL.md — EMIX-PRO v11.1.0-audit

## 1. System shape (as deployed)

```
                        EMIX UI  (pages.py — single-file admin, vanilla JS, 10.6k lines)
                            │  fetch/authF (cookie session)
                    API / CONTROL PLANE  (main.py FastAPI — 258 routes, uvicorn workers=1)
        ┌───────────────────┼────────────────────────────────┐
        │                   │                                │
  Protocol Engine      Config Compiler                    Platform services
  (registry+adapters)  (normalize→compat→credentials→      (auth, backup, idempotency,
   19 adapters           semantics→emit→parse-back→          subs, nodes federation,
   8 real runtimes       checksum; 1 emergency legacy         announcements/support)
                         fallback path kept)
        │                   │
        └───────────┬───────┘
                    │
          ┌─────────┴──────────┬─────────────────┬────────────────┐
          │                    │                 │                │
   Transport (ws/xhttp)   Security (TLS/       Endpoint        Network Health
   in-process relays      Reality/none,        Profile Engine   Engine (10 layers,
   + AIMD session engine  per compat matrix)   (SNI successor,  score, TTL expiry,
   + supervised MTProto                        spoof_sni migr.) UNKNOWN ≠ PASS)
   subprocesses                                                 │
                                                               Smart Route v3 (ranking_reason)
                                                               Node Manager (heartbeat, states)
                                                               Runtime Supervisor (backoff)
                                                               IP Quality (providers, facets)
                                                               Config Lifecycle (state machine)
                                                               Job System (7 jobs) + Diagnostics
                    │
             JSON state store (/data/rvg_state.json — atomic, debounced, defensive restore)
                    │
             Cloudflare Worker (OPTIONAL — WTE egress/multi-location/gaming)
             Central worker (OPTIONAL — announcements/support; kill switch)
```

## 2. Plane separation

| Plane | Where | Notes |
|---|---|---|
| CONTROL | main.py routes + engines | All admin + compile + health orchestration |
| DATA | protocol/* relays (always-on routes) + MTProto subprocesses | Auth per-frame, quota gate, accounting |
| PROTOCOL | protocol_adapters/ + protocol/{vless,trojan,shadowsocks,mtproto} | Protocol-specific code stays inside adapters/modules |
| TRANSPORT | websocket/xhttp_core engines, shared session engine | Transport-independent from protocol |
| SECURITY | compat security dimension + TLS in relays + security_exp | Only valid combos compiled |
| ENDPOINT | endpoint_profiles.py | address/hostname/SNI/port/transport/TLS/ALPN/Reality/IPv4-IPv6 prefs; legacy spoof migration |
| HEALTH | network_health.py (+ lifecycle/ip_quality) | Evidence-only, expiring |
| ROUTING | smart_route.py | v3 health-weighted + explainable |
| ACCOUNTING | _QuotaGate EWMA batching + stats + state persistence | Never per-packet writes |
| OBSERVABILITY | diagnostics.py + job_system.py | Request IDs, structured errors, job telemetry |

## 3. Where architecture debt remains (honest)

1. **main.py is still 4.9k lines** and contains: the MTProto process-orchestration subsystem (~160 lines), the emergency legacy link emitter (duplicate of compiler), and `_create_link_core` per-protocol field knowledge. The v11 engines are main-free; the *feature modules* (link_health, gaming_boost, ip_quality routes, smart_route, diagnostics, central) still lazy-import from main. This is contained (DI at engine boundaries, lazy imports elsewhere) but is the top refactoring priority for v12.
2. **Single-file frontend** (10.6k lines) — works, tested by node --check per block, but has no componentization. Display-level protocol knowledge persists in ~6 places (labels/icons) though *behavioral* rules come only from the compat matrix API.
3. **JSON state store** — atomic + debounced + defensive, but full-file rewrite per save; the documented migration trigger to SQLite is ~10k configs.

## 4. Design decisions worth preserving

- **Evidence-only health**: fresh configs are never born HEALTHY; probes that can't run return UNREACHABLE/UNKNOWN, never PASS; records expire (15 min TTL) — trust requires re-validation.
- **One source of truth**: compat.py is consumed by compiler, API, frontend, diagnostics, routing, and pinned by 43 tests.
- **Fail-visible UX**: audit-fix netErr reporter — loaders can no longer fail silently; matrix gating degradation is announced.
- **Idempotent supervision**: supervisor.register is update-or-insert (keeps counters); MTProto instances are re-attached at every creation/restart point (audit fix closed the post-boot gap).
- **Honest deferred protocols**: TUIC/Hysteria2/NaiveProxy enumerate but refuse — no fake support.

## 5. File map (engines)

| Module | LOC | Role |
|---|---:|---|
| compat.py | 341 | protocol×transport×security matrix (SSoT) |
| config_compiler.py | 518 | canonical compile pipeline + parse-back |
| endpoint_profiles.py | 458 | endpoint model + legacy migration |
| network_health.py | 584 | state machine, score, layers, TTL |
| ip_quality.py | 614 | facet-based IP quality + providers |
| node_manager.py | 264 | node registry, heartbeats, states |
| runtime_supervisor.py | 305 | crash detect, backoff, restart budget |
| config_lifecycle.py | 121 | CREATED→…→REVOKED derivation |
| job_system.py | 177 | bounded background jobs |
| diagnostics.py | 281 | structured errors + overview |
| smart_route.py | 436 | health-weighted ranking + reasons |

Runtime layer: protocol/vless|trojan|shadowsocks (relays, AEAD crypto, quota gates), protocol/mtproto/mtproto_native.py (subprocess family), protocol/net_connect.py (IPv4-first egress).
