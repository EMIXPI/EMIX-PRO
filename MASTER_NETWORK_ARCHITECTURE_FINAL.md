# MASTER NETWORK ARCHITECTURE — FINAL

**Version:** v11.4.0-builder · **Phase:** 38+ (Unified Routing, Egress, Iran Network, Multi-Node, Protocol Engine & Config Builder) · **Date:** 2026-09-02
**Predecessor docs:** `MASTER_NETWORK_ARCHITECTURE_AUDIT.md` (Phase A recon — written BEFORE any change), `PHASE38_ARCHITECTURE_FINAL.md` (v11.3.0-network).

---

## 0. Status vocabulary (used throughout this document)

`IMPLEMENTED` code exists and is wired · `VERIFIED` proven by tests/evidence in this repo · `PARTIALLY_VERIFIED` some stages proven, others not · `NOT_TESTABLE` cannot be proven in CI (needs real client/network) · `UNSUPPORTED` deliberately not possible on this deployment · `DEFERRED` future work.

---

## 1. The control plane (target architecture — as built)

```
                    EMIX CONTROL PLANE (Railway)
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   Config Engine      Routing Engine      Node Engine
   (config_builder)  (route_engine +     (node_manager +
        │             domestic_route)    capability_engine)
   Protocol Engine     Egress Engine      Health Engine
   (compat + adapters) (egress_engine)   (network_health)
        │                  │                  │
   Endpoint Profile   Failover Engine    IP Quality
   (endpoint_profiles)(failover_engine)  (ip_quality)
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                CANONICAL COMPILER (config_compiler)
                           │
                      DATA PLANE
                           │
                 ┌─────────┼─────────┐
                 │         │         │
              Railway    Worker     Exit/VPS
             in-panel    (WTE)       nodes
               relays   (CF colo)  (TCP)
                           │
                        Internet
```

**Status: IMPLEMENTED + VERIFIED** — every box is a real module; wiring is fault-isolated (a failed engine never blocks boot); 904/904 tests pass ×3 consecutive.

## 2. Object relationship chain (spec §2 — as enforced)

```
Account (account_manager)
  → Subscription (route_policy, protocol, quota, expiry)
    → Device (one-time token, revocation)
      → Config (config_builder.ConfigRequest → history entry)
        → Protocol + Transport + Security (compat matrix — SSoT)
          → Endpoint Profile (endpoint_profiles — the ONE TLS/endpoint engine)
            → Routing Policy (domestic_route_engine presets + iran_gateway)
              → Node (capability_engine.node_catalogue — records + evidence)
                → Egress (egress_engine — VERIFIED only with measured evidence)
                  → Verification (structured events + diagnostics)
```

**Status: IMPLEMENTED + VERIFIED** — the Config Builder validates every link of this chain BEFORE generation (spec §19) and refuses with an explicit reason at the failing stage (`capability` / `node` / `endpoint` / `routing` / `compiler`).

## 3. Engine inventory (new in v11.4.0-builder)

| Engine | File | Role | Status |
|---|---|---|---|
| **Capability Engine** | `capability_engine.py` | protocol × transport × security × node × deployment × client capability document; Railway compatibility model (RAILWAY_EDGE / RAILWAY_DEPLOYMENT / RAILWAY_OUTBOUND / ACTUAL_EGRESS); Railway validation matrix (§25) | IMPLEMENTED + VERIFIED (unit + integration + gates) |
| **Config Builder** | `config_builder.py` | canonical `ConfigRequest` → validation pipeline → canonical compiler → outputs (uri / xray-json / subscription / split rules) + bounded history | IMPLEMENTED + VERIFIED (real-client traffic stages NOT_TESTABLE) |
| **Iran Gateway** | `iran_gateway.py` | IRAN_PROXY gateways; real TCP reachability + egress probes (HTTP proxy / SOCKS5 / emix-worker); VERIFIED_IRAN_EGRESS only from measured IR evidence | IMPLEMENTED + PARTIALLY_VERIFIED (probe code paths unit-tested with fakes; real-gateway e2e needs a real Iranian server — NOT_TESTABLE here) |
| **Structured Events** | `structured_events.py` | CONFIG_GENERATED / ROUTE_SELECTED / EGRESS_VERIFIED / ROUTE_MISMATCH / NODE_QUARANTINED / FAILOVER_TRIGGERED / IRAN_GATEWAY_CHECK / PROTOCOL_VALIDATION_FAILED / SPLIT_TUNNEL_COMPILED; secret-scrubbing at the sink | IMPLEMENTED + VERIFIED (scrub tests incl. UUID redaction) |
| **Domestic routing (extended)** | `domestic_route_engine.py` | + IRAN_PROXY (Iranian destinations via real gateway) + INTERNATIONAL_VVPN (BLOCK leg, blackhole rules) | IMPLEMENTED + VERIFIED |

Existing engines (routes, egress, failover, accounts, node manager, compiler, endpoint profiles) are UNCHANGED in contract — additive extensions only:
- `route_engine.ROUTE_POLICIES` now includes `IRAN_PROXY` / `INTERNATIONAL_VVPN`.
- `failover_engine.select_replacement` gained hard capability gates (UNSUPPORTED_NODE_PROTOCOL / UNSUPPORTED_NODE_TRANSPORT / NO_VERIFIED_EGRESS for EXIT_NODE role) — an incompatible node can never be selected regardless of health score.
- `egress_engine` / `node_manager` / `failover_engine` emit structured events at the truth points (mismatch announced, never masked).
- `network_health.ensure_record()` — fresh configs get a born-UNKNOWN record synchronously (race fix; never born HEALTHY).

## 4. API surface (all new endpoints require auth — 401 verified)

| Endpoint | Purpose |
|---|---|
| `GET /api/config-builder/capabilities` | THE capability document the frontend renders from — protocols, transports, deployments (4 layers each), node catalogue with per-combo statuses + egress evidence, client formats, routing policies, IRAN_PROXY gateway state, compat matrix |
| `GET /api/railway/validation-matrix` | §25 honest per-combo stages: CONFIG_VALID (real compile at request time) / RUNTIME_STARTED / LISTENER_REACHABLE (live app routes) / CLIENT_CONNECTED+ → `NOT_TESTABLE_WITHOUT_REAL_CLIENT` |
| `POST /api/config-builder/preview` | validation + preview from the canonical compiler (no history write, placeholder credential labeled) |
| `POST /api/config-builder/generate` | full generation + history entry + CONFIG_GENERATED event |
| `GET /api/config-builder/history[?account_id=]` | "کانفیگ‌های ساخته‌شده" (masked) |
| `GET /api/config-builder/history/{id}?reveal=` | view (masked) / reveal (authed admin — URI + credential) |
| `POST /api/config-builder/history/{id}/regenerate` | re-compile from the stored spec — deterministic (same credential → same URI → same checksum) |
| `DELETE /api/config-builder/history/{id}` | delete |
| `GET/POST /api/iran-gateway`, `POST /api/iran-gateway/{id}/check`, `GET /api/iran-gateway/status`, `DELETE /api/iran-gateway/{id}` | Iran Gateway registry + verification |
| `GET /api/events[?event=&severity=&limit=]`, `GET /api/events/stats` | structured event log (scrubbed) |

## 5. Frontend (spec §6, §21, §23)

- **ساخت کانفیگ** (`pg-builder`) — the ONE canonical builder page: 9-step flow (protocol → node → transport → security → Endpoint Profile → routing → client/output → validation preview → generate), desktop two-column (builder + preview), mobile single-column. Every option renders from `/api/config-builder/capabilities` — **no protocol-support assumptions are hardcoded in JavaScript** (source-level test enforces the API dependency).
- **کانفیگ‌های ساخته‌شده** — history cards with مشاهده/کپی، بازسازی، حذف.
- **🇮🇷 پروکسی ایران** (`pg-iranproxy`) — dedicated section: IRAN_DIRECT vs IRAN_PROXY explanation, gateway add form, gateway cards with state badges + evidence + "بررسی و اثبات خروج" button.
- Isolated `<script>` block (a syntax error in one block can never kill the dashboard — see the v11.0.0 lesson documented in `pages.py`). All blocks `node --check` verified.
- Design system unchanged: glass, RTL, Vazirmatn, existing `.card/.btn/.badge/.cm-*` classes.

**Status: IMPLEMENTED + VERIFIED** (markers asserted in served HTML; JS syntax checked).

## 6. What the system can now answer (spec §37)

| Question | Answer mechanism | Status |
|---|---|---|
| "What protocol can this node actually run?" | `node_catalogue()` per-node protocols with per-deployment statuses | VERIFIED |
| "What transport can this deployment actually carry?" | deployment models: carries + tcp/udp truth (panel: HTTP-layer + TCP proxy; worker: TCP via cloudflare:sockets, UDP DNS-only) | VERIFIED |
| "Where will this traffic actually go?" | routing policy legs + egress attribution per leg (USER_ISP / EMIX exit / IRAN_GATEWAY / NONE) | VERIFIED (attribution logic; real traffic NOT_TESTABLE) |
| "Is Iranian routing DIRECT or through a real Iran Gateway?" | IRAN_DIRECT vs IRAN_PROXY are distinct policies; IRAN_PROXY requires a gateway with VERIFIED_IRAN_EGRESS | VERIFIED |
| "What is the actual egress IP?" | egress_engine evidence (TTL 300s) — never a configured value | VERIFIED |
| "Was the egress verified?" | classification VERIFIED_EGRESS / CONFIGURED_ONLY / UNKNOWN + measurement source + timestamp | VERIFIED |
| "Can the selected client implement this routing?" | CLIENT_FORMATS split-tunnel map → SPLIT_TUNNEL_NOT_SUPPORTED refusal | VERIFIED |
| "Can this configuration actually work on the selected deployment?" | validate_request_combination + compiler pipeline with stage-labeled rejections | VERIFIED |
| "What happened during this operation?" | /api/events (CONFIG_GENERATED, ROUTE_MISMATCH, …) | VERIFIED |

## 7. Known limitations (honest)

- Real-client stages (CLIENT_CONNECTED / REAL_TRAFFIC_CONFIRMED / RECONNECT_CONFIRMED) are `NOT_TESTABLE_WITHOUT_REAL_CLIENT` — labeled, never faked.
- IRAN_PROXY data-plane enforcement depends on the EMIX route actually relaying through the configured gateway; the gateway itself is external (deployment of the relay hop is operator work). Egress attribution is honest (expected vs VERIFIED).
- Config history stores credentials server-side (same trust domain as LINKS uuid storage); masked in list responses; revealed only in the authed view action. QR stays LOCAL (`/api/qr`).
- Pre-existing (documented, out of scope of this phase): `exp_api/smart_route/gaming_health/isp_detect` routers remain flag-gated without `require_auth`; duplicate boost-layer rewriters operate on compiler output (legitimate layer); `multiloc._forge_vless_link` remains a production-reachable third vless builder on the WTE path (documented in the audit — convergence deferred to avoid rewriting working WTE code without reason).
