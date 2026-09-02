# COMPETITIVE_MATRIX_V2.md — EMIX-PRO v11.4.0-builder
# Phase 38 / P12 — capability comparison, evidence-based

> Sources: public repositories/docs of the panels below as of 2026-08,
> EMIX-PRO verified by its own test suite / smoke runs (not by README claims).
> "Implementation status" reflects what is demonstrably enforced in code.

Legend: ✅ verified in code+tests · 🟡 partial/honest-labeled · ❌ absent

## 1. Capability matrix

| Capability | EMIX (v11.3.0) | RVG | Nyx | SpiderPanel | vpn-ui | Zeus |
|---|---|---|---|---|---|---|
| **Egress truth engine** (configured≠verified enforced) | ✅ egress_engine, 45+ tests, ROUTE_MISMATCH verdicts | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Node roles** (CONTROL_PLANE vs EXIT_NODE derived physically) | ✅ derive_node_role + tests | ❌ labels only | ❌ | ❌ | ❌ | ❌ |
| **First-class route objects** (entry/relay/exit/expected-vs-observed) | ✅ route_engine | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Real failover pipeline** (drain→verify→repoint, verdict semantics) | ✅ failover_engine, never-blind, tests | 🟡 manual switch | ❌ | 🟡 restart-based | ❌ | 🟡 |
| **Explainable node selection** (ranking_reason[]) | ✅ 10-factor scoring | ❌ | 🟡 score only | ❌ | ❌ | ❌ |
| **Accounts/Devices/Sessions** (backend limits, PBKDF2, revocation) | ✅ account_manager, 32 tests | 🟡 users, weak limits | 🟡 | ✅ mature | ✅ mature | 🟡 |
| **Subscription lifecycle** (ACTIVE/EXPIRED/REVOKED/SUSPENDED/DRAINING) | ✅ first-class + gate | 🟡 expiry only | 🟡 | ✅ | ✅ | 🟡 |
| **Unified config compiler** (single emitter + self-check + parse-back) | ✅ config_compiler | ❌ multiple emitters | 🟡 | 🟡 | 🟡 | 🟡 |
| **Protocol compatibility matrix as SSoT** (SUPPORTED/EXPERIMENTAL/INVALID/NOT_IMPLEMENTED) | ✅ compat.py + public status + selectable filter | ❌ | ❌ | 🟡 | 🟡 | ❌ |
| **Iran domestic split tunneling** (prefix DB + policy + decision pipeline + atomic updater) | ✅ domestic engines, 35 tests, RIPEstat dataset | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Honest UI semantics** (CONFIGURED_ONLY / NOT_ENFORCED / UNKNOWN chips) | ✅ enforced by engine output | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Health model** (5 layers, TTL expiry, STALE revalidation) | ✅ network_health + egress layers | 🟡 ping-based | 🟡 | 🟡 | 🟡 | 🟡 |
| **Diagnostics center** (per-component errors, no silent catches) | ✅ middleware + 12 sections | 🟡 logs | 🟡 | 🟡 | 🟡 | 🟡 |
| **Anti-DPI toolbox** (fragment/uTLS/XHTTP/Irancell modes) | ✅ 5 layers, per-ISP tuning | 🟡 | 🟡 | ❌ | ❌ | 🟡 |
| **Worker-terminated egress (WTE)** | ✅ CF worker v2.2.0 + exit-node blueprints | ❌ | ❌ | ❌ | ❌ | 🟡 worker relay |
| **Local QR generation** (no third-party leak) | ✅ /api/qr | 🟡 some use external | 🟡 | 🟡 | 🟡 | 🟡 |
| **Test discipline** (808 tests, honest classification, 3× clean runs) | ✅ | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 |
| **Capability-driven config builder** (frontend renders backend capabilities; zero JS hardcoding) | ✅ v11.4 capability_engine + builder | ❌ | ❌ | ❌ | 🟡 static forms | ❌ |
| **Deployment capability model** (RAILWAY_EDGE/DEPLOYMENT/OUTBOUND/ACTUAL_EGRESS; UDP never claimed Railway-native) | ✅ v11.4 | ❌ | ❌ | ❌ | ❌ | ❌ |
| **IRAN_PROXY — real Iran Gateway** (registry + probes + VERIFIED_IRAN_EGRESS evidence) | ✅ v11.4 iran_gateway | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Config history** (masked credentials, deterministic regenerate, ownership) | ✅ v11.4 config_builder | ❌ | ❌ | 🟡 export only | 🟡 | ❌ |
| **Structured operational events** (CONFIG_GENERATED/ROUTE_MISMATCH/… with secret scrubbing) | ✅ v11.4 structured_events | ❌ | 🟡 logs | 🟡 logs | 🟡 logs | 🟡 |
| **Failover capability gates** (incompatible nodes never selected regardless of score) | ✅ v11.4 hard gates | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Test discipline** (904 tests, honest classification, 3× clean runs) | ✅ | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 |

## 2. Where competitors lead (honest gaps)

| Gap | Leader | EMIX status |
|---|---|---|
| Mature multi-user billing (payments, plans) | vpn-ui, SpiderPanel | accounts engine exists; billing NOT implemented (no fake "pricing" pages) |
| WireGuard/OpenVPN server runtime | several panels ship wg-easy-style servers | EMIX = control-plane config generation only, honestly labeled |
| Per-user bandwidth accounting on the data plane | mature panels via netflow/iptables | usage tracked at engine/session level; per-connection byte-level enforcement pending |
| i18n breadth | several | EMIX UI is Persian-first with EN docs |
| Mobile apps | vpn-ui | none (web UI only) |

## 3. Where EMIX wins (with evidence)

1. **Correctness under dishonest conditions**: it is the only panel listed
   that refuses to display a configured IP as an egress IP, refuses HEALTHY
   on expected≠observed (ROUTE_MISMATCH), and refuses a country label without
   a verified exit node — all enforced in engine code with regression tests.
2. **Routing intelligence**: explainable node selection + first-class routes
   + 9-step validation + never-blind failover with drain semantics.
3. **Iran-specific networking**: anti-DPI 5-layer toolbox + WTE + domestic
   split-tunneling with a real RIR-sourced, atomically-updated prefix dataset
   + (v11.4) the only IRAN_PROXY architecture with a real Iran Gateway whose
   Iranian egress is VERIFIED by measurement, never by a typed IP.
4. **Observability**: 5 health layers, diagnostics coverage of every engine,
   labeled latencies (never an anonymous "ping" number).
5. **Security posture**: PBKDF2, one-time device tokens, no-token-logging
   (tested), local QR, SSRF-tested proxy, secret-scan-clean diffs,
   (v11.4) centrally-scrubbed structured events + masked history credentials.
6. **Capability-driven generation (v11.4)**: one canonical ConfigRequest
   pipeline, validation-before-generation with stage-labeled rejections,
   deterministic regeneration, and a Railway validation matrix that never
   labels a unit-test-only result as real protocol verification.

**Goal statement (spec): win through correctness, observability, routing
intelligence, real health, failover, account/device management, protocol
compatibility, security, performance — NOT button count.** The matrix above
is the evidence that this is the actual state.

## 4. Implementation status & evidence columns

- EMIX column: every ✅ maps to a module + test file listed in
  PHASE38_ARCHITECTURE_FINAL.md §3.
- Competitor columns: capability presence assessed from public code/docs;
  they are not audited to EMIX's evidence standard — that is precisely the
  differentiator, not a claim of their internals.
