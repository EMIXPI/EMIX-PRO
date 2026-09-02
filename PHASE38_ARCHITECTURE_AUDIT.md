# PHASE38_ARCHITECTURE_AUDIT.md
# Reconnaissance — required before any production code change

- **Date:** 2026-09-02
- **Baseline commit:** `738aff0` (v11.2.0-egress, on top of `8ce9695` v11.1.0-audit)
- **Baseline test result:** **687/687 passing** (12.1s, verified this session before any change)
- **Boot:** production uvicorn boot previously verified (0 errors, 10/10 endpoint smoke 200)
- **Method:** full test run, module-by-module inspection, frontend/backend contract trace, worklog history review

---

## 1. What already exists (verified, tested)

| Capability | Module | State |
|---|---|---|
| Egress truth engine (NODE_ROLES, VERIFIED/CONFIGURED_ONLY/UNKNOWN, 9-step validation, evidence TTL) | `egress_engine.py` | **REAL** — 45 tests |
| FALSE EGRESS / Custom IP defect fix (field renamed "آدرس اندپوینت", country select honest) | `pages.py:3931-3934` | **REAL** |
| Node registry + heartbeat state machine + runtime-health gate | `node_manager.py` | **REAL** — states `REGISTER/ONLINE/DEGRADED/OFFLINE/MAINTENANCE` |
| Outbound circuit breaker (per-node) | `node_health.py` | **REAL** |
| Network health engine (facets, score, TTL, sweep job) | `network_health.py` | **REAL** |
| Endpoint Profiles (SNI-spoof successor, legacy `spoof_sni` migration) | `endpoint_profiles.py` | **REAL** |
| Unified Config Compiler (validate → resolve → emit → self-check → parse-back) | `config_compiler.py` | **REAL** |
| Protocol/transport matrix SSoT (`VALID/EXPERIMENTAL/NOT_IMPLEMENTED/INVALID`) | `compat.py` | **REAL** |
| IP Quality engine (CLEAN/GOOD/QUESTIONABLE/DEGRADED/BLOCKED/UNKNOWN, facets, providers) | `ip_quality.py` | **REAL** |
| Diagnostics Center (error records, no-silent-catch middleware) | `diagnostics.py` | **REAL** |
| Job system (bounded supervisor, backoff) | `job_system.py` | **REAL** |
| Exit-node blueprint (VLESS-over-WS relay deployable to Railway/Koyeb/Render) | `exit_node/` + `gaming_boost.py` | **REAL** |
| WTE worker v2.2.0-egress (`/vl`, `/egress-test`, `/exit-ip`, locations in KV) | `cf_gateway_worker.js` | **REAL** |
| Persistence (rvg_state.json: links/subs/sessions/stats/nodes/profiles/WG keys) | `main.py:223-309` | **REAL** |
| Panel auth (cookie session, TTL) | `main.py:447-451` | **REAL** (admin only) |

## 2. Gaps found (Phase 38+ scope, honest)

| Phase | Gap |
|---|---|
| P0 | Route objects exist only *inside* gaming link dicts — no first-class `route_engine.py` with route_id/expected-vs-observed fields |
| P1 | No `failover_engine.py`; no DRAINING/QUARANTINED/UNKNOWN node states; no explainable node scoring (ranking_reason exists only in smart-selector for links) |
| P2 | **No account/device layer at all.** SESSIONS = admin tokens; SUBS = subscription groups (no user concept) |
| P3 | Subscription is a link-group, not a first-class object with route_policy/node_policy/quota/status lifecycle |
| P4 | Matrix vocabulary is VALID (≈ SUPPORTED); needs public SUPPORTED alias + "never expose unsupported as selectable" audit pass |
| P6 | Health layers exist for APPLICATION/NODE/ROUTE/EGRESS; **PROTOCOL_HEALTH missing**; STALE revalidation exists via TTLs but needs explicit exposure |
| P7 | Diagnostics covers errors; needs Routes/Egress/Accounts/Devices/Subscriptions sections |
| P11 | No E2E for: account lifecycle, device revocation, failover drain, domestic routing |
| P17 | **No domestic (Iran) split-tunnel routing at all** — no prefix DB, no policy, no decision pipeline, no rules updater, no UI |
| P8 | Frontend has honest egress card (v11.2.0) but no Routing Mode UI, no Test-Route diagnostics, no accounts UI |

## 3. Non-gaps verified (do not rebuild)

- Egress classification/verification pipeline — keep as SSoT; new engines must *consume* it, not re-probe.
- Config emission must continue to go through `config_compiler.compile_from_link` (self-check enforced).
- `spoof_sni` legacy migration already lossless — must remain so (P13).

## 4. Implementation order (this phase)

1. `route_engine.py` — first-class Route objects + route decision pipeline (P0)
2. `node_manager.py` state extension (DRAINING/QUARANTINED/UNKNOWN) + `failover_engine.py` (P1)
3. `account_manager.py` — Account/Subscription/Device/Session (P2/P3)
4. `domestic_route_engine.py` + `domestic_rules_updater.py` — Iran split tunneling (P17), RIPEstat seed bundled (1955 v4 + 570 v6 prefixes, checksummed)
5. compat SUPPORTED alias + PROTOCOL_HEALTH + diagnostics sections (P4/P6/P7)
6. main.py wiring + persistence + jobs (P9 bounded: TTL/locks/queues)
7. Frontend: Routing Mode, Test Route, Accounts, honest exit-node panel (P8)
8. E2E suite (P11) + production gates (P16) + docs (P14/P12)

## 5. Baseline snapshot

```
tests: 687 passed, 4 warnings, 12.13s
modules: 40+ engine modules, pages.py 10744 lines, main.py 5032 lines
worker: cf_gateway_worker.js v2.2.0-egress
git: main @ 738aff0 (clean except 3 file-mode chmod artifacts)
```

**Recon complete. Production code changes may begin.**
