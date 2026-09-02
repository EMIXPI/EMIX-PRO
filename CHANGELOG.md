# CHANGELOG — EMIX-PRO

## v11.4.0-builder (2026-09-02) — Phase 38+: Unified Config Builder, Capability Engine, IRAN_PROXY & Iran Gateway

**Master Network Platform Upgrade: Unified Routing, Egress, Iran Network,
Multi-Node, Protocol Engine & Config Builder.**

Baseline: v11.3.0-network (808 tests) → **904/904 tests, 3× consecutive clean
runs, real uvicorn boot 0 errors, 17/17 API smoke + 5 auth-401 gates,
7/7 UI markers, secret scan clean.** This phase adds **96 tests.**

### NEW ENGINES
- **capability_engine.py (§3-§5, §25)** — the protocol × transport × security
  × node × deployment × client capability engine. Railway compatibility model
  with FOUR distinct layers (RAILWAY_EDGE / RAILWAY_DEPLOYMENT /
  RAILWAY_OUTBOUND / ACTUAL_EGRESS — never conflated). Railway priority order
  (VLESS+XHTTP+TLS first; MTProto TCP via Railway TCP proxy). UDP-dependent
  protocols (WireGuard/Hysteria/TUIC/…) are NEVER exposed as Railway-native.
  Honest Railway validation matrix: CONFIG_VALID (real compile at request
  time) / RUNTIME_STARTED / LISTENER_REACHABLE (live app routes) —
  CLIENT_CONNECTED+ honestly NOT_TESTABLE_WITHOUT_REAL_CLIENT.
  API: GET /api/config-builder/capabilities, GET /api/railway/validation-matrix.
- **config_builder.py (§6-§7, §18-§21)** — the ONE canonical ConfigRequest →
  validation-before-generation (stage-labeled rejections: capability / node /
  endpoint / routing / compiler) → CANONICAL COMPILER (zero new emitters) →
  outputs (URI / Xray JSON / subscription / split-tunnel rules) → bounded
  history (کانفیگ‌های ساخته‌شده: view-masked / reveal-authed / deterministic
  regenerate / delete). IRAN_DIRECT with a non-split client is refused with
  SPLIT_TUNNEL_NOT_SUPPORTED; IRAN_PROXY without a gateway is refused.
  API: POST /api/config-builder/preview|generate, GET history, POST
  history/{id}/regenerate, DELETE history/{id}.
- **iran_gateway.py (§13)** — 🇮🇷 پروکسی ایران: real Iranian gateway registry
  with evidence-based state machine (UNCONFIGURED → CONFIGURED → REACHABLE →
  HEALTHY / VERIFIED_IRAN_EGRESS / ROUTE_MISMATCH / DEGRADED / UNREACHABLE /
  UNSUPPORTED). Real probes: TCP reachability + egress measurement through
  HTTP-proxy / SOCKS5 (minimal in-house CONNECT client) / emix-worker
  endpoints. A manually entered Iranian IP is CONFIGURED, never VERIFIED.
  API: /api/iran-gateway* (all admin-auth).
- **structured_events.py (§29)** — CONFIG_GENERATED / ROUTE_SELECTED /
  EGRESS_VERIFIED / ROUTE_MISMATCH / NODE_QUARANTINED / FAILOVER_TRIGGERED /
  IRAN_GATEWAY_CHECK / PROTOCOL_VALIDATION_FAILED / SPLIT_TUNNEL_COMPILED —
  bounded ring buffer with central secret-scrubbing (passwords/tokens/keys
  field blocklist + UUID redaction). API: GET /api/events.

### ROUTING POLICIES (§11-§13)
- domestic_route_engine: + IRAN_PROXY (Iranian destinations via a REAL
  gateway; honest IRAN_GATEWAY egress attribution with the live verdict
  embedded — warning when unverified, never a fake Iranian exit) and
  INTERNATIONAL_VVPN (BLOCK leg: domestic traffic never enters the tunnel;
  blackhole split rules for capable clients). POLICY_PRESETS now five.
- route_engine.ROUTE_POLICIES extended accordingly.

### FAILOVER CAPABILITY GATES (§15)
- select_replacement: HARD gates — protocol requirement, transport
  requirement (compat-decomposed capabilities) and EXIT_NODE role
  (valid-egress-evidence only). An incompatible node can NEVER be selected,
  regardless of health/latency score. FAILOVER_TRIGGERED structured event.

### UI (§6, §21, §23-§24)
- ✨ ساخت کانفیگ (pg-builder): 9-step capability-driven builder (protocol →
  node → transport → security → Endpoint Profile → routing → client/output →
  validation preview → generate); desktop two-column, mobile single-column;
  EVERY option renders from /api/config-builder/capabilities — zero
  protocol-support hardcoding in JS (source-level test enforced). Smart field
  visibility per protocol. Preview from the canonical compiler only.
- کانفیگ‌های ساخته‌شده: history cards (مشاهده/کپی، بازسازی، حذف) with
  masked credentials in list view.
- 🇮🇷 پروکسی ایران (pg-iranproxy): IRAN_DIRECT vs IRAN_PROXY explainer,
  gateway add form, gateway cards with state badges + evidence +
  بررسی-و-اثبات-خروج button.
- Isolated <script> block + scoped bld-/igw- CSS; all blocks node --check OK.

### FIXES
- network_health.ensure_record(): fresh configs get a born-UNKNOWN record
  SYNCHRONOUSLY (race fix — /api/health/links/{uid} could 404 in the window
  before the background initial probe landed; found via a rare full-suite
  flake after this phase's changes shifted timing; root-caused and fixed,
  6/6 clean runs after).

### WIRING / PERSISTENCE / JOBS
- main: fault-isolated registration of the four new engines; _wire_phase38
  extended (host/worker-domain/CDN providers; gateway status fn → domestic
  engine; live listener-path evidence for the validation matrix). Additive
  persistence keys iran_gateway + config_builder (defensive restores).
  New job: iran-gateway-check (6h). Diagnostics: +config_builder /
  iran_gateway / events / iran_routing sections. EMIX_VERSION=11.4.0-builder.

### DOCS (§32)
- MASTER_NETWORK_ARCHITECTURE_AUDIT.md (Phase A — pre-change recon),
  MASTER_NETWORK_ARCHITECTURE_FINAL.md, RAILWAY_PROTOCOL_COMPATIBILITY.md,
  ROUTE_EGRESS_ARCHITECTURE_FINAL.md, IRAN_NETWORK_ARCHITECTURE.md,
  UNIFIED_CONFIG_BUILDER_FINAL.md + updates (failover/accounts/readiness/
  competitive/README).

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
