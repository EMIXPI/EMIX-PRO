# PHASE38_ARCHITECTURE_FINAL.md — EMIX-PRO v11.3.0-network
# Verified architecture as delivered (Phase 38)

> **Philosophy unchanged: claims backed by evidence.** Every network claim in
> this document is backed by a test, a boot log, or a 38/38 smoke run.

## 1. Release identity

- Version: **v11.3.0-network** (`EMIX_VERSION`)
- Base: v11.2.0-egress (commit 738aff0, 687 tests) → Phase 38
- Result: **808/808 tests, 3× consecutive clean runs, real uvicorn boot with
  38/38 endpoint smoke PASS, all JS blocks node --check OK**
- Phase 38 new tests: **121** (15 route + 24 failover + 32 account + 35
  domestic + 15 E2E)

## 2. Layer map (post-Phase-38)

```
┌─ FRONTEND (pages.py, single-page, glassmorphism)
│    pg-routing (Network Routing Mode + Test Route + dataset + accounting)
│    pg-accounts (accounts/devices/subscriptions, backend limits surfaced)
│    honest egress card (v11.2.0) — CONTROL PLANE / EXIT NODE / REAL EGRESS / STATUS
├─ API (FastAPI, admin-auth; register_routes(app, require_auth) pattern)
│    /api/routes /api/failover /api/accounts /api/domestic/* /api/egress/*
├─ ENGINES (pure, DI, unit-tested)
│    egress_engine   — egress truth SSoT (roles/classification/9-step/health layers)
│    route_engine    — first-class Route objects (P0)
│    failover_engine — drain→explainable select→verify→repoint (P1)
│    account_manager — accounts/devices/subscriptions/sessions (P2/P3)
│    domestic_route_engine + domestic_rules_updater — IR split tunneling (P17)
│    node_manager (extended: DRAINING/QUARANTINED) · network_health · ip_quality
│    config_compiler (unified emitter) · endpoint_profiles · diagnostics · job_system
├─ DATA (rvg_state.json — additive keys: account_manager, domestic_routing)
│    configs/iran_prefixes_seed.json — real RIPEstat snapshot (2528 prefixes, checksummed)
└─ EDGE (cf_gateway_worker.js v2.2.0-egress; exit_node/ relay blueprint)
```

## 3. Phase 38 delivery matrix (spec § → implementation)

| Spec | Delivered | Evidence |
|---|---|---|
| P0 Route & Egress abstraction | route_engine.py: route_id/entry/relay/exit/expected-vs-observed/health/labeled latency/packet_loss/jitter/last_verified/verification_state | 15 unit + E2E 5-7 |
| P0 Egress verification (CONFIGURED/OBSERVED/VERIFIED) | egress_engine (v11.2.0) + PROTOCOL_HEALTH layer | 28+17 tests |
| P0 Custom IP semantics | field renamed "آدرس اندپوینت" (v11.2.0); configured never reported as egress | E2E flow 6 |
| P0 Endpoint Profile | endpoint_profiles.py (Phase 25, spoof_sni-compatible) — controls only TLS name/hostname/transport/ALPN | 29 tests |
| P1 Multi-node engine | node_manager + DRAINING/QUARANTINED/UNKNOWN; failover_engine | 24 tests |
| P1 Failover never blind | 7-step pipeline, verdicts, drain retention on failure | E2E flow 4 |
| P1 Explainable selection | score_node() 10 factors, ranking_reason[] | unit scoring tests |
| P2 Accounts | account_manager.py, PBKDF2, backend limits | 32 tests |
| P2 Devices | registration/list/last-seen/platform/revoke/rename/limits; MAX_DEVICES/MAX_CONCURRENT_SESSIONS backend-side | unit + E2E 10 |
| P3 Subscription first-class | statuses ACTIVE/EXPIRED/REVOKED/SUSPENDED/DRAINING; unified compiler emission | unit + E2E 9 |
| P4 Protocol/transport matrix | compat SSoT + public SUPPORTED vocabulary + selectable_combinations(); unsupported never selectable | compat tests |
| P5 IP Quality | CLEAN/GOOD/QUESTIONABLE/DEGRADED/BLOCKED/UNKNOWN with facets+evidence+timestamps (Phase 37; unchanged, verified) | 16 tests |
| P6 Health V3 | 5 layers (APPLICATION/NODE/ROUTE/PROTOCOL/EGRESS), TTL expiry → STALE/UNKNOWN | egress tests |
| P7 Observability | diagnostics sections: routes/egress/accounts/domestic_routing/failover; no silent catches (middleware) | E2E diagnostics test |
| P8 Frontend honest | pg-routing + pg-accounts + Test Route; JS verified; unauth 401 | smoke + render checks |
| P9 Performance | bounded registries (500 routes / 50 failover / 200 audit / 20 updater history), TTLs, locks, debounced saves, timeouts (resolver 5s, updater 20s) | bounds tests |
| P10 Security | auth gates on all new endpoints; PBKDF2; one-time tokens; no tokens/passwords in audit; secret scan clean; deps current | security tests + scans |
| P11 E2E | 15 flows incl. the 10 mandatory ones | test_phase38_e2e.py |
| P12 Competitive | COMPETITIVE_MATRIX_V2.md (EMIX vs RVG/Nyx/Spider/vpn-ui/Zeus) | doc |
| P13 Migration | additive keys; old state loads unchanged; spoof_sni compat preserved | migration tests |
| P14 Documentation | this file + 7 engine docs + readiness V2 + competitive V2 + changelog | docs |
| P15 Test quality | 808 tests classified by level; mocks never described as real network | readiness V2 §test classification |
| P16 Production gate | 15 gates executed | readiness V2 |
| P17 Iran domestic routing | full engine + updater + UI + diagnostics + 35 tests | below |

## 4. P17 — Iran Domestic Direct Routing (as delivered)

- **Dataset**: real RIPEstat `country-resource-list` snapshot bundled as seed
  (**2528 prefixes**: 1958 IPv4 + 570 IPv6, SHA-256 checksummed, source
  metadata). NOT a hardcoded tiny list — the daily job refreshes atomically
  from the live source (verified at boot: `[domestic-rules] dataset updated:
  2528 prefixes`).
- **Classification**: `IRAN_DOMESTIC / NON_IRAN / UNKNOWN` by longest-prefix
  match on the ACTUAL resolved destination IP (never domain suffix; decision
  follows DNS changes — tested).
- **Policy**: presets ALL_VPN / IRAN_DIRECT
  `{iran: DIRECT, international: VPN, unknown: VPN}`; user default never
  silently changed (explicit POST /api/domestic/policy, persisted).
- **Egress attribution**: DIRECT ⇒ `USER_ISP` (with "VPN BYPASSED" note) —
  never Railway, never Cloudflare, never an EMIX exit node.
- **Cloudflare rule**: all published CF v4+v6 ranges flagged
  `cloudflare-anycast: never classified as Iranian egress` (tested v4+v6).
- **Railway rule**: control-plane hosts flagged
  `railway-control-plane: never an Iranian exit` (tested).
- **Split-tunnel compilation**: xray/xray-json/sing-box ⇒ real routing rules
  (GEOIP:ir + verified CIDR dataset, route types DOMAIN/IP/CIDR/GEOIP);
  WireGuard/OpenVPN/plain-URI ⇒ honest `SPLIT_TUNNEL_NOT_SUPPORTED`
  (WG AllowedIPs cannot express "everything except Iran"; tested).
- **Rules updater**: atomic apply, validation (min-threshold, parseable,
  checksum), versioning, rollback-by-retention (empty/malformed/small
  datasets NEVER replace a working one — 4 tests), TTL staleness flag,
  failure fallback, status/history endpoints, manual trigger button in UI.
- **DNS interaction**: route decision follows the post-resolution IP; split-DNS
  recommendation surfaced; resolution source cannot flip the decision basis.
- **Traffic accounting**: DOMESTIC_DIRECT / INTERNATIONAL_VPN / UNKNOWN with
  bytes/connections/duration — category derived from route/destination logic,
  never from .ir suffix.
- **UI (pg-routing)**: Network Routing Mode cards (ALL_VPN / 🇮🇷 IRAN_DIRECT),
  Test Route diagnostic (destination → resolved IP → classification → rule →
  decision → egress attribution), dataset card (source/version/checksum),
  accounting card, client support table.
- **API**: /api/domestic/status|policy|test-route|decisions|traffic|
  split-tunnel|dataset|rules/update|rules/status (all admin-auth).

## 5. Cross-cutting guarantees (unchanged, re-verified)

- Railway = CONTROL_PLANE; country selection requires a verified exit node
  (NO_EXIT_NODE_AVAILABLE otherwise).
- Config emission only through the unified Config Compiler (self-check +
  parse-back). Subscriptions use it too (injected; never duplicated).
- `spoof_sni` legacy fields remain readable (P13; existing migration tests).
- No artificial document endings, no fake statuses, no unbounded state.

## 6. What is still NOT claimed (honest GRAY list)

1. **Data-plane enforcement of IRAN_DIRECT on arbitrary clients** — the panel
   compiles the rules and demonstrates decisions; the client must apply them
   (xray-family clients do; WG/OVPN honestly NOT_SUPPORTED).
2. **Failover scoring input richness** — latency/jitter/loss per candidate
   node require per-node probes not yet scheduled; they report UNKNOWN
   (explicit `?` reasons) rather than invented values.
3. **Device token handshake on the edge** — worker/exit-node integration for
   account-gated connections is engine + API ready, but the deployed worker
   still authorizes by UUID allow-list (no breaking change).
4. **Multi-panel account sync** — accounts are per-panel (rvg_state.json);
   node sync (Phase 37.9) covers links/subs, not accounts yet.
5. **`main.py` size** — still 5,100+ lines; decomposition continues to be a
   background priority, not a regression.
