# CHANGELOG — EMIX-PRO

## v11.3.0-network (2026-09-02) — Phase 38: Real Network Architecture

**Production Network Architecture, Routing, Egress, Multi-Node Failover,
Accounts/Devices, Iran Domestic Direct Routing & Competitive Completion.**

Baseline: v11.2.0-egress (687 tests) → **808/808 tests, 3× consecutive clean
runs, real uvicorn boot 38/38 smoke PASS.** Phase 38 adds **121 tests**.

### NEW ENGINES
- **route_engine.py (P0)** — first-class Route objects:
  route_id / entry / relay[] / exit / expected-vs-observed country+ASN /
  health / labeled latency / packet_loss / jitter / last_verified /
  verification_state / route_policy. Bounded registry (500). Mismatch is
  never masked as HEALTHY. API: GET /api/routes, /api/routes/summary,
  /api/routes/{id} (admin-auth).
- **failover_engine.py (P1)** — never-blind failover: drain → explainable
  replacement selection (10-factor scoring with ranking_reason[]) → verify
  replacement health → verify route (egress 9-step) → verify egress →
  re-point routes → resume. Verdicts FAILOVER_SUCCESS / FAILED /
  NO_REPLACEMENT; failed failovers keep the old node drained.
  API: POST /api/failover/{node}, GET /api/failover/history|summary.
- **account_manager.py (P2+P3)** — Account/Subscription/Device/Session
  entities; PBKDF2-SHA256 password hashing; one-time device tokens (SHA-256
  stored, never logged); backend-enforced MAX_DEVICES /
  MAX_CONCURRENT_SESSIONS / quotas / expiry; connection gate
  (can_connect verdicts); subscription lifecycle
  ACTIVE/EXPIRED/REVOKED/SUSPENDED/DRAINING; config emission through the
  unified Config Compiler (injected — no duplicate URI logic).
  API: /api/accounts*, /api/devices/*, /api/subscriptions/*,
  /api/connect/authorize (admin-auth).
- **domestic_route_engine.py (P17)** — Iran domestic direct routing:
  prefix DB with longest-prefix match (CIDR/IP/RIPEstat range formats),
  classification IRAN_DOMESTIC / NON_IRAN / UNKNOWN (decision follows the
  ACTUAL resolved IP, never the domain suffix), policy presets ALL_VPN /
  IRAN_DIRECT, decision pipeline with honest egress attribution
  (DIRECT ⇒ USER_ISP — never Railway/Cloudflare/EMIX node), Cloudflare +
  Railway never-classified-as-Iranian guards, split-tunnel rule compilation
  (xray/xray-json/sing-box: GEOIP:IR + verified CIDRs; WireGuard/OpenVPN/
  URI: SPLIT_TUNNEL_NOT_SUPPORTED — honestly), traffic accounting
  (DOMESTIC_DIRECT / INTERNATIONAL_VPN / UNKNOWN), bounded decision history.
  API: /api/domestic/* (admin-auth).
- **domestic_rules_updater.py (P17)** — atomic dataset updates from a
  configurable trusted source (default: RIPEstat country-resource-list IR):
  validation (min threshold, parseable, checksum over normalized prefixes),
  versioning, rollback-by-retention (empty/malformed/small datasets NEVER
  replace a working one), TTL staleness flag, failure fallback, bounded
  history. Formats: RIPEstat JSON + plain CIDR text.
- **configs/iran_prefixes_seed.json** — REAL RIPEstat snapshot:
  2,528 prefixes (1,958 IPv4 + 570 IPv6), SHA-256 checksummed, with source
  metadata. Loaded at boot; refreshed daily by job (live update verified at
  boot: "dataset updated: 2528 prefixes").

### EXTENSIONS
- **node_manager.py** — node states extended with DRAINING (no new
  assignments, existing traffic continues), QUARANTINED (operator override,
  survives fresh heartbeats), UNKNOWN family; set_draining() /
  set_quarantine(); online_nodes() excludes drained/quarantined/maintenance;
  runtime gate still beats drain.
- **egress_engine.py** — HEALTH_LAYERS now includes PROTOCOL_HEALTH (P6)
  derived from the live protocol registry × compat.READINESS.
- **compat.py (P4)** — public status vocabulary (VALID→SUPPORTED,
  EXPERIMENTAL, INVALID, NOT_IMPLEMENTED); matrix_view() emits `status` +
  `public_states`; selectable_combinations() enforces "unsupported
  transports are never selectable".
- **diagnostics.py (P7)** — new sections: routes, egress (health layers +
  route history), accounts, domestic_routing, failover.
- **main.py** — Phase 38 bootstrap (fault-isolated registration),
  _wire_phase38_engines() (compiler injection, route repointing, real
  5s-bounded DNS resolver, seed loading), new jobs (domestic-rules-update
  daily, account-sweep 5 min), persistence keys (account_manager,
  domestic_routing — additive, defensive), EMIX_VERSION = 11.3.0-network.
- **pages.py (P8)** — new section **pg-routing** (مسیریابی هوشمند): Network
  Routing Mode cards (ALL_VPN / 🇮🇷 IRAN_DIRECT with honest descriptions),
  Test Route diagnostic tool (destination → resolved IP → classification →
  rule → decision → egress attribution), IR prefix dataset card
  (source/version/checksum + atomic update button), traffic accounting,
  client split-tunnel support table. New section **pg-accounts** (حساب‌ها):
  account creation, quota/expiry/limit surfaces, device list + one-time
  token display + revoke, subscription rows with status chips. Nav items +
  loaders registered; all data from real APIs; nothing hardcoded.

### TESTS (+121: 808 total)
- tests/unit/test_route_engine.py (15) — route semantics, mismatch,
  staleness, bounded registry, labeled latency, provider failure.
- tests/unit/test_failover_engine.py (24) — states, scoring factors,
  pipeline verdicts, drain retention.
- tests/unit/test_account_manager.py (32) — hashing, gates, limits,
  cascades, reconciliation, persistence, audit hygiene.
- tests/unit/test_domestic_routing.py (35) — the 13 mandatory P17 tests
  + updater robustness + seed dataset + DNS-follows-IP + CF/Railway guards.
- tests/integration/test_phase38_e2e.py (15) — the 10 mandatory flows
  (account→…→verified egress; control-plane→exit→egress verification;
  healthy node; failure→drain→failover→replacement; expected≠observed;
  configured≠actual; SNI invariance; NO_EXIT_NODE_AVAILABLE; expired
  subscription rejected; revoked device rejected) + domestic API +
  diagnostics coverage + persistence.

### PRODUCTION GATES (P16) — all PASS
Full suite 808×3 · compileall · old-state migration · real uvicorn boot
(0 errors) · 38/38 API smoke · JS node --check 3/3 · egress/route/failover/
account tests · security + secret scans clean · dependency versions current ·
git diff audited (no secrets, no generated artifacts).

### DOCS
PHASE38_ARCHITECTURE_AUDIT.md (recon) · PHASE38_ARCHITECTURE_FINAL.md ·
ROUTE_ENGINE_FINAL.md · EGRESS_ENGINE_FINAL.md · FAILOVER_ENGINE_FINAL.md ·
ACCOUNT_DEVICE_FINAL.md · PRODUCTION_READINESS_REPORT_V2.md (score 92/100,
test classification, honest GRAY list) · COMPETITIVE_MATRIX_V2.md ·
PROTOCOL_MATRIX_FINAL.md (P4 section) · MIGRATION_GUIDE_FINAL.md (v11.3
section) · this changelog.

---

## v11.2.0-egress (2026-09-01)
CRITICAL PRODUCTION DEFECT fix — FALSE EGRESS / Custom IP semantics.
Egress & Route Truth Engine (roles, VERIFIED/CONFIGURED_ONLY/UNKNOWN,
9-step validation, evidence TTL, labeled latencies, NO_EXIT_NODE_AVAILABLE,
ROUTE_MISMATCH). Custom IP field renamed to endpoint address; honest route
semantics in gaming links; worker v2.2.0-egress (/egress-test, /exit-ip with
ASN/IP-family). 45 new tests (687 total).

## v11.1.0-audit (2026-09-01)
Production audit: P0 security (phone-home removed, local QR, brute-force,
token, plaintext IP provider off) + P0 correctness (route shadow, sweep
persistence, dead Diagnostics UI, header crash) + persistence (sessions/
stats/SNI/WG keys) + real-data UI. 9 FINAL docs. 642 tests.

## v11.0.0-arch (2026-08-31)
Protocol Orchestrator + Config Compiler + Network Health Engine +
Endpoint Profiles (SNI-Spoof successor) + IP Quality + Jobs + Diagnostics.
