# MASTER NETWORK ARCHITECTURE AUDIT — EMIX-PRO

**Phase:** 38+ / PHASE 0 (Deep Reconnaissance) · **Baseline:** v11.3.0-network (commit e189f43) · **Date:** 2026-09-02
**Rule:** this audit was written BEFORE any architectural change in this phase. The repository and runtime are the source of truth — every claim below carries a `file:line` reference verified in-source.

---

## 0. Executive summary

EMIX-PRO already has a **canonical Config Compiler** (`config_compiler.py`), a **single compatibility matrix** (`compat.py`), a **canonical Endpoint Profile resolver** (`endpoint_profiles.py`), and first-class engines for routes, egress, failover, accounts/devices and Iran domestic routing (Phase 38, 808/808 tests). What it does **NOT** yet have, and this phase must add without faking:

| # | Gap | Evidence |
|---|-----|----------|
| 1 | No **capability-driven Config Builder** — there is no `GET /api/config-builder/capabilities`, no canonical `ConfigRequest`, no unified "ساخت کانفیگ" page. The existing create-link modal (`pages.py:2021-2310`) creates LINKS records; it is not a 9-step capability-driven builder with preview/history. | repo-wide grep: zero matches |
| 2 | No **deployment capability model** — nothing distinguishes `RAILWAY_EDGE` / `RAILWAY_DEPLOYMENT` / `RAILWAY_OUTBOUND` / `ACTUAL_EGRESS`. Protocol support is keyed to the *panel*, never to the *deployment*. | `protocol_engine/capabilities.py` exists but is wired to nothing (see §3) |
| 3 | No **Iran Gateway / IRAN_PROXY** — `ROUTE_POLICIES = ("ALL_VPN","IRAN_DIRECT","CUSTOM")` (`route_engine.py:41`); `IRAN_PROXY` appears nowhere in the repo. IRAN_DIRECT = USER_ISP only (correct), but there is no "real Iranian gateway/exit" architecture. | repo-wide case-insensitive grep: zero matches |
| 4 | No **generated-config history** ("کانفیگ‌های ساخته‌شده") — no store of built configs with copy/regenerate/view/delete. | zero matches |
| 5 | No **structured event log** — no `CONFIG_GENERATED`, `ROUTE_SELECTED`, `EGRESS_VERIFIED`, … events; only `log_activity` (Persian activity feed) and per-engine bounded histories. | grep `log_event|CONFIG_GENERATED`: no matches |
| 6 | **Reachable duplicate emitters remain** (see §2) — the compiler is canonical for stored links, but 4 independent URI constructors are still production-reachable and one xray-JSON builder bypasses the compiler. | §2 below |
| 7 | **Auth gaps in existing routers** (pre-existing, not introduced by this phase): `exp_api.py`, `smart_route.py`, `gaming_health.py`, `isp_detect.py` have no `require_auth` — flag-gated only. `/api/qr` is public by design (rate-limited, scheme-allowlisted). | §8 |
| 8 | `EMIX_IRAN_PREFIX_SOURCE` documented in `domestic_rules_updater.py:18` but never read by code (doc/code drift). | §5 |

---

## 1. All protocol implementations (what actually runs)

### 1a. Data-plane runtimes (REAL, in-process or subprocess)

| Runtime | Where | Reality |
|---|---|---|
| VLESS over WS relay | `protocol/vless/websocket.py:50-152` | Full WS endpoint: auth gate, 0-RTT early-data, VLESS header parse, real TCP egress via `open_connection_v4first`, 1MB buffers. Always-on FastAPI routes `main.py:3463-3486`. |
| VLESS over XHTTP | `protocol/vless/` + `xhttp_core.py` | Shared XHTTP session engine (reaper, AIMD flow control, EWMA QuotaGate); 2 validated modes: `xhttp-packet-up`, `xhttp-stream-up`. |
| Trojan over WS/XHTTP | `protocol/trojan/` | SHA224 hash-cache auth, real relays. |
| Shadowsocks AEAD over WS | `protocol/shadowsocks/shadowsocks.py` | Real crypto (HKDF-SHA1 subkey, EVP_BytesToKey, ChaCha20Poly1305/AESGCM). |
| MTProto (official mtg) | `protocol/mtproto/mtproto_native.py` | REAL subprocess: compiles Telegram MTProxy from source, per-uuid `asyncio.create_subprocess_exec`, port range 8500-8600, real stats poll. `telemt.py` is dead code (zero importers). |
| WTE (Worker-Terminated Egress) | `cf_gateway_worker.js` | VLESS server inside a Cloudflare Worker via `cloudflare:sockets connect()` — **TCP only; UDP is DNS-over-HTTPS only** (`:231-248,274-277`). `/egress-test` chains 4 IP providers → VERIFIED_EGRESS evidence. |
| Exit node package | `exit_node/server.js` | Node 20 VLESS-over-WS TCP-only server (cmd!==0x01 closes — TCP only). |
| SOCKS5 | `zeussocks5.py:221-230` | Real `asyncio.start_server`. |

### 1b. Link/config emitters (BETA — no server runtime in the panel)

`vmess`, `vless-reality`, `ss-2022` (via `link_emit.py`), `wireguard` + `openvpn` (via `vpn_pro.py` — real X25519 keygen / real .conf text, but the panel cannot host them on Railway), `hysteria2`/`tuic`/`naiveproxy`/`ssh` (DEFERRED stubs — honest `NOT_IMPLEMENTED`).

### 1c. The compatibility SSoT — `compat.py`

`PROTOCOLS={vless,trojan,shadowsocks,mtproto}` (`:20`), `TRANSPORTS={ws,xhttp-packet-up,xhttp-stream-up}` (`:21`), `SERVER_RUNTIME` 8 combos (`:26-35`), `TRANSPORT_MATRIX` 34 combos with states VALID/EXPERIMENTAL/NOT_IMPLEMENTED/INVALID (`:69-108`), `READINESS` per protocol (`:156-172`), `matrix_view()` (`:322`), `selectable_combinations()` (`:128`), public status SUPPORTED vocabulary (`:115-120`). Served at `GET /api/config-matrix` (`main.py:4721`) — **authed**, consumed by the create-link modal (`pages.py:7884-7909`) with fail-visible behavior.

**Verdict:** protocol reality is honestly modeled at the panel level. What is missing is the *node-level* and *deployment-level* capability projection (§3).

---

## 2. All config generators / duplicate builders (the convergence map)

**Canonical:** `config_compiler.compile_config` (`config_compiler.py:400-483`) — pipeline normalize → compat.validate → credentials → endpoint resolve → SNI applicability → emit → self-check + parse-back → checksum. `main.generate_share_link` (`main.py:1247-1288`) is a facade over it (byte-identical, tests prove). `POST /api/configs/compile` (`main.py:4726-4745`) is the existing preview entrypoint. `account_manager.compile_subscription_configs` (`account_manager.py:561-587`) injects `compile_from_link` — subscriptions already use the canonical compiler for local links.

**Still-reachable independent emitters (production paths):**

| Emitter | Location | Reachable via | Risk |
|---|---|---|---|
| `_emit_mtproto_link` | `main.py:1230-1244` | every mtproto link (deliberate: public TCP-proxy semantics) | documented, contained |
| `multiloc._forge_vless_link` | `multiloc.py:444-453` | `POST /api/multiloc/links` worker mode (vless) | 3rd vless-URI builder — must converge |
| `gaming_boost._build_gaming_xray_json` | `gaming_boost.py:1204-1296` | `POST /api/gaming/xray-json` | xray JSON bypasses compiler emitter |
| WG/OVPN file generators | `vpn_pro.py:303/423`, `gaming_boost.py:303/357` | VPN Pro + gaming pages | config-file emitters (documented BETA) |
| `_generate_share_link_legacy` | `main.py:1291-1425` | emergency fallback only (`main.py:1288`, diagnostic recorded) | contained by design |
| `link_emit.*` family | `link_emit.py` | `exp_api.py` (experimental flag) | intended experimental surface |

**Rewriters (consume compiler output — legitimate layer):** gaming `_gaming_link`, turbo `_turbo_link`, bridge `_rewrite_link`, clean-IP chain, zeus `_apply_sni_override`, multiloc `_tunnel_link`. Note: `_replace_query_param` regex helper is duplicated 4× (multiloc:440, gaming:916, bridge:105, zeus:239).

**Subscription assemblers:** 5 inline base64 joins (`main.py:1758,1776,2009,3975,4992`) + unused `config_compiler.subscription_document` (`:488`) + experimental `link_emit.gen_subscription_*`. All local-link URIs come from the compiler; node links enter as opaque pre-built strings from remote panels; `foreign_links` are stored verbatim (admin-pasted).

**Frontend duplicate (source-level):** `pages.py:10344-10346` builds raw `vless://` base links in JS before posting to `/api/exp/link/finalmask|utls` — experimental page only.

---

## 3. Protocol capability engines — three disconnected systems

1. `compat.py` — panel-level protocol/transport/security matrix (used by compiler + UI + failover indirectly).
2. `protocol_engine/capabilities.py:36-99` — rich `Capabilities` frozen dataclass (`supports_udp`, `supports_tcp`, `supports_tls`, `supports_ipv6`, inbound/outbound…) per registered adapter. **Wired to NOTHING**: not consumed by node_manager, failover, config compiler, or any frontend.
3. `node_manager.NodeRecord.capabilities` — `List[str]` of *fused protocol strings* ("vless-ws") — a different vocabulary again. Failover checks protocol compatibility by substring membership only (`failover_engine.py:180-187`).

**No deployment-level capability exists.** Nothing keys protocol support to Railway vs worker vs VPS; nothing distinguishes `RAILWAY_EDGE` (Cloudflare/CDN ingress in front) / `RAILWAY_DEPLOYMENT` (the app runtime) / `RAILWAY_OUTBOUND` (egress via Railway's network) / `ACTUAL_EGRESS` (measured exit). Railway detection is env-var/host-hint based (`main.py:128`, `railway_infra.py:59-65`, `egress_engine.py:80`).

**UDP reality:** panel data plane is TCP (WS/XHTTP over TLS through HTTP ingress); worker is TCP + DNS-only UDP; exit node is TCP-only. WireGuard/OpenVPN/Hysteria/TUIC UDP flags in adapters are *advertised-not-hosted* — must never be presented as Railway-native.

---

## 4. SNI / Endpoint Profile implementations

**Canonical resolver (ONE):** `endpoint_profiles.py` — `EndpointProfile` dataclass (`:71-116`), `resolve()` precedence: profile-id → inline endpoint → legacy spoof Mode A/B → standard (`:302-392`). Used by the compiler and link creation. Migration + legacy stats included.

**Separate, non-competing systems (do not consolidate blindly):**
- `sni_management.py` — TLS/reverse-proxy SNI registry with real TLS health checks + ArvanCloud probes. Does NOT feed link generation. Serves `/api/security/sni/profiles*`.
- Legacy per-link `spoof_sni` fields in LINKS (back-compat, `main.py:157-162`).
- Boost-layer SNI rewrites (gaming/zeus) — operate on the *emitted URI*, documented.

**Verdict:** there is exactly ONE canonical endpoint/TLS semantics engine for link generation. The new Config Builder must consume `endpoint_profiles` (presets + resolve) — a second SNI engine is explicitly forbidden. SNI is never routing/egress (enforced by `egress_engine.NON_ROUTING_KEYS:83-85` and P17 tests).

---

## 5. Routing / egress / failover / accounts / domestic (Phase 38 state)

- `egress_engine.py` (821 ln): roles CONTROL_PLANE/EXIT_NODE/RELAY_NODE/EDGE_NODE/HYBRID; `EgressEvidence` TTL store; `classify_egress` (VERIFIED_EGRESS/CONFIGURED_ONLY/UNKNOWN — configured values never reported as egress); `validate_route` 9-step pipeline; `select_exit_country` (NO_EXIT_NODE_AVAILABLE); 5 health layers incl PROTOCOL_HEALTH; 5 authed API endpoints.
- `route_engine.py` (300 ln): `Route` dataclass, registry (bound 500), `assess_route`, `sync_inventory`, policies `("ALL_VPN","IRAN_DIRECT","CUSTOM")`. **No IRAN_PROXY.**
- `failover_engine.py` (344 ln): 7-step never-blind pipeline; 10-factor explainable scoring; protocol check is substring-based only (no transport/route compatibility yet).
- `account_manager.py` (816 ln): Account→Subscription→Device→Session; PBKDF2; one-time device tokens (SHA-256 stored); backend-enforced limits; `can_connect` gate; compile via injected compiler.
- `domestic_route_engine.py` (648 ln) + `domestic_rules_updater.py`: longest-prefix-match DB (2,528 real RIPEstat prefixes bundled as checksummed seed); IRAN_DOMESTIC/NON_IRAN/UNKNOWN on actual resolved IP; USER_ISP attribution for DIRECT; CF/Railway never-Iranian guards; split-tunnel compile (xray GEOIP:IR+CIDR; WG/OVPN/URI honest NOT_SUPPORTED); atomic updater with rollback. **Policy presets: ALL_VPN, IRAN_DIRECT only.** `EMIX_IRAN_PREFIX_SOURCE` documented but not read (drift).
- `node_manager.py` (318 ln): 8 states, 5 kinds, `derive_state`, runtime-health evaluators per kind, persistence under `managed_nodes`.

---

## 6. Subscription / QR / frontend forms / legacy APIs

- **Subscriptions:** 5 endpoints, all compiler-driven for local links (§2). Headers via `build_sub_headers`. UA-sniffing on the public sub endpoint. Backward compatible.
- **QR:** ONE local endpoint `GET /api/qr` (`main.py:5089-5133`) — local SVG via `qrcode` lib, scheme allowlist, 2048-char cap, 30 req/min/IP. All 9+ frontend call-sites use it. **No third-party QR remains.** New builder must reuse only this.
- **Frontend config forms:** create-link modal (cm*) — LINKS-creation, matrix-gated; gaming (anti-DPI + WG/OVPN); multiloc (bridge-config builder); VPN Pro (WG/OVPN forms); experimental (link tools); routing (policy cards + test-route); accounts. 24 page sections, 23 nav items, `navTo` loader map `pages.py:5187`. Design system: glass (no clay classes), Vazirmatn, RTL, `.card/.btn/.badge/.modal-v2/.cm-*`. Two script blocks; a past syntax error killed a whole block (documented `pages.py:4627-4630`) — new JS must be `node --check`-verified.
- **Legacy APIs:** `spoof_sni` fields (back-compat), `/api/config-matrix`, `/api/configs/compile`, all `/sub*`, `/api/links*`, boost endpoints — must remain working.

---

## 7. Persistence / jobs / wiring patterns (for the new engines)

- `rvg_state.json` atomic save (`main.py:241-281`) with additive engine snapshots (`_persist_phase38_engines:284-297`), debounced `schedule_save` (`:330-345`), defensive restore per engine (`load_state:144-239`). New engines follow the same pattern.
- Jobs: `job_system.register(name, fn, interval=, timeout=, retries=)` (`main.py:877-881` pattern). Candidates: iran-gateway-check.
- Router registration: fault-isolated try/except blocks at import time (`main.py:4212-4347`).
- `_wire_phase38_engines()` (`main.py:798-851`) — DI seams (compile fn, repoint fn, resolver, seed load).

---

## 8. Security posture (facts)

- `require_auth` session-cookie dependency (`main.py:483-487`); login brute-force guard; PBKDF2; device tokens SHA-256; QR local; no hardcoded secrets after v11.1.0-audit.
- **Pre-existing auth gaps (out of strict scope of this phase's new code, but must not be extended):** `exp_api.py` / `smart_route.py` / `gaming_health.py` / `isp_detect.py` routers are flag-gated only. All NEW endpoints in this phase MUST use `require_auth`.
- Diagnostics middleware + `diagnostics.record_error` (secret-free). `EMIX_DISABLE_LOGGING` global switch.

---

## 9. What this phase will build (mapped to spec, honest labels)

| Spec item | Implementation plan | Honesty constraint |
|---|---|---|
| Protocol Capability Engine (`GET /api/config-builder/capabilities`) | new `capability_engine.py` merging compat.py + protocol_engine capabilities + node/deployment model | frontend renders from API only; never hardcode support in JS |
| Canonical `ConfigRequest` + unified builder | new `config_builder.py` on top of `compile_config` (compiler untouched) | one compiler, no second emitter |
| Unified Config Builder UI "ساخت کانفیگ" + history | new page in `pages.py` using existing design system | preview from canonical compiler only |
| IRAN_PROXY / Iran Gateway "🇮🇷 پروکسی ایران" | new `iran_gateway.py` + policy preset + UI section | only network evidence (measured egress in IR) yields VERIFIED_IRAN_EGRESS; configured IP is CONFIGURED, never VERIFIED |
| Railway compatibility model | `RAILWAY_EDGE/RAILWAY_DEPLOYMENT/RAILWAY_OUTBOUND/ACTUAL_EGRESS` distinction in capability_engine | UDP never claimed Railway-native |
| Failover route/transport compatibility | extend `score_node` requirements check | explicit UNSUPPORTED_* reasons |
| Structured events | new lightweight `structured_events.py` + wiring | never log credentials/tokens/private keys |
| Diagnostics extension | config_builder/iran_gateway/events sections | real data only |
| Railway validation matrix | honest CONFIG_VALID / RUNTIME_STARTED / LISTENER_REACHABLE stages + NOT_TESTABLE labels for real-traffic stages | no REAL_TRAFFIC_CONFIRMED without a real client |

**Nothing in this audit was assumed; everything was verified in source. Deep recon is complete — architecture work may begin.**
