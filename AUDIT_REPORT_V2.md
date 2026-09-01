# EMIX-PRO — Master Audit Report V2

**Date:** 2026-09-01
**Auditor methodology:** Full static inspection of 33k LOC (main.py 3,969 / pages.py 10,466 / protocol\* trees / 25 feature modules) + live test run (383 passed) + git history analysis (15 recent commits).
**Legend:** IMPLEMENTED / PARTIAL / BROKEN / FAKE-UI / MISSING / DUPLICATED / UNSAFE / NEEDS-REFACTOR

---

## 1. Architecture Map (actual, verified)

```
main.py (3,969 ln)  ── FastAPI app, routes, state, link-gen, sub-gen, auth, save/load
pages.py (10,466 ln) ── monolithic inline SPA (LOGIN_HTML + DASHBOARD_HTML + public page)
protocol/            ── REAL data-plane relays (vless/trojan/ss/xhttp×4 + mtg binary)
protocol_engine/     ── adapter ABC + registry/selector/fallback/metrics  (NOT in traffic path)
protocol_adapters/   ── ~20 adapter classes (thin facades + stubs)        (NOT in traffic path)
sni_management.py    ── SNIProfile TLS profiles (legit TLS mgmt, real health checks)
link_health.py       ── REAL end-to-end protocol probes (ws/xhttp/tcp)
smart_route.py       ── weighted upstream scoring (real TCP probes, exp-gated)
gaming_boost.py      ── Gaming Center (anti-DPI presets, WTE, WG/OVPN gen) — 1,897 ln
multiloc.py          ── WTE (worker-terminated egress) + real colo TLS scanning
cf_gateway_worker.js── real VLESS-server-in-Worker + reverse proxy (v2.1.0-wte)
vpn_pro.py           ── WG/OVPN config+crypto gen (provisioning DEFERRED)
```

**Verdict:** control-plane and data-plane are entangled in `main.py`; the two "engine" packages exist as parallel read-only layers rather than the serving path. NEEDS-REFACTOR (target: Phase-1 architecture).

## 2. Dependency map (import direction)

- `main.py` → protocol/*, mtproto, central, link_health, gaming_boost, multiloc, sni_management, vpn_pro, protocols_api, exp_api, … (god-module, 15+ feature imports)
- `protocol/*` → **back-imports main** (`from main import LINKS, LINKS_LOCK, stats`) — circular dependency, intentional but fragile
- `protocol_adapters/existing/*` → delegate to `main.generate_share_link` (facade loop)
- `link_health.py` → `from main import ...` (read-only, documented)

## 3–4. Protocol & Transport matrix (verified)

| Protocol | Transport | Data-plane | Link-gen | Health | Class |
|---|---|---|---|---|---|
| VLESS | WS | REAL relay | main+4 copies | REAL probe | IMPLEMENTED |
| VLESS | XHTTP (4 modes) | REAL relay | main+4 copies | REAL probe | IMPLEMENTED |
| Trojan | WS | REAL relay | main+4 copies | REAL probe | IMPLEMENTED |
| Trojan | XHTTP (4 modes) | REAL relay | main+4 copies | REAL probe | IMPLEMENTED |
| Shadowsocks | WS (AEAD) | REAL relay | main+copies | REAL probe | IMPLEMENTED |
| MTProto | TCP (mtg binary) | REAL subprocess | own | TCP probe | IMPLEMENTED |
| SOCKS5 (Zeus) | TCP | REAL RFC1928 | own | – | IMPLEMENTED |
| VLESS-Reality | TCP | MISSING (needs xray-core) | link_emit only | **FAKE ok=True** | BETA link-only |
| VMess | any | MISSING | link_emit only | **FAKE ok=True** | BETA link-only |
| SS-2022 | any | MISSING | link_emit only | **FAKE ok=True** | BETA link-only |
| WireGuard | UDP | MISSING (no TUN on Railway) | conf-gen, real X25519 | **FAKE ok=True** | BETA config-gen |
| OpenVPN | UDP/TCP | MISSING | .ovpn-gen | **FAKE ok=True** | BETA config-gen |
| Hysteria2 / TUIC / NaiveProxy | – | MISSING | – | NotImplementedError | STUB |
| SSH | TCP | MISSING | – | **FAKE ok=True** | STUB |
| gRPC / HTTPUpgrade | – | MISSING (XHTTP mimic via Content-Type) | – | – | FAKE-UI (docs-only) |

## 5–6. Feature matrix (selected)

| Feature | Class | Evidence |
|---|---|---|
| Per-link SNI Spoofing | PARTIAL | vless/trojan only; SS/MTProto skip; Mode-B sets allowInsecure=1 |
| SNI Profiles (TLS mgmt) | IMPLEMENTED | sni_management.py, real TLS health |
| WTE / multi-location | IMPLEMENTED | real colo TLS scan, real egress test |
| Gaming Center | IMPLEMENTED | real client-side scan; est. pings labeled |
| Health / ping | PARTIAL | real probes but per-link, on-demand only; no periodic sweep, no per-config health state object |
| Smart route | PARTIAL | real scoring but upstream registry is manual, exp-gated, not connected to configs/nodes |
| Node manager | PARTIAL | NODES + circuit breaker + snapshot push; no capability/health ranking integration |
| IP "clean" | PARTIAL | clean_ip_boost: ArvanCloud list + TLS reachability; **no reputation providers, no classification** |
| Subscriptions | PARTIAL | base64 + headers, healthy filtering MISSING, profiles MISSING |
| Traffic accounting | IMPLEMENTED | per-relay `check_and_use` under lock, hourly aggregation, quota gate |
| Background jobs | PARTIAL | 3 ad-hoc loops (session cleanup, central heartbeat, mtproto restart); no retry/backoff/dedup framework |
| Observability | PARTIAL | error_logs deque(50), /api/health; no request IDs, no error codes, no slow-request tracking |
| Backup/restore | IMPLEMENTED | validate→stage→apply→verify→rollback + 14 tests |
| Telegram bot | IMPLEMENTED | bot + TCP-proxy attach |
| Railway deploy | IMPLEMENTED | healthcheck, volume checks, restart-on-fail |
| Cloudflare Worker deploy | **MISSING** | no CF API client; manual paste via /api/multiloc/worker-code |
| VPN Pro (WG/OVPN lifecycle) | **FAKE-UI in UI**, honest DEFERRED in backend | vpn_pro returns status:"DEFERRED"; nav removed in commit bfa1266 |
| Devices | **MISSING** | no device/session tracking per account |
| Failover | PARTIAL | hysteresis logic exists in smart_route but is not wired to real subscription updates |

## 7. Duplicate-code matrix

| Logic | Copies |
|---|---|
| Share-link generation | 4 layers: `main.generate_share_link` (L683), `link_emit.py`, `protocol_adapters/*`, `exp_api.py` + second WG generator in `vpn_pro.py` |
| Health probing | link_health.py vs protocol_engine/health.py (bookkeeping) vs gaming_health.py (3 engines) |
| TCP-probe-with-RTT | smart_route / multiloc / gaming_health / node_health (4 implementations) |
| SNI validation | `_validate_sni` (main) vs `validate_server_name` (sni_management) |

## 8. Security risks

| # | Risk | Severity | Status |
|---|---|---|---|
| S1 | Default admin password "123456" | HIGH (if env unset) | pre-existing, documented |
| S2 | Mode-B SNI spoof → `allowInsecure=1` (no MITM protection) | MEDIUM | opt-in per link |
| S3 | central.py posts password hash off-box every 5 min | MEDIUM | documented in AUDIT_REPORT.md §H.4 |
| S4 | Sessions in memory only → all users logged out on redeploy | LOW | UX issue |
| S5 | No rate limit on /api/login by default | MEDIUM | security_exp exists, OFF |
| S6 | CORS wildcard default | LOW | spec-compliant (no credentials) |
| S7 | SSRF in /proxy | FIXED | 16 tests |
| S8 | Fake `ok=True` health in 6 adapters | HIGH (trust) | **this pass fixes** |

## 9. Performance bottlenecks

- pages.py is one ~10.5k-line inline SPA — no minification/splitting (acceptable for single-panel deploy)
- SS O(N) link scan per connection (N small, documented DEFERRED)
- Health checks on-demand only → selector/registry metrics always zero → ranking decisions starved
- No caching layer for repeated snapshot fetches beyond 8s `_NODE_CACHE`

## 10. Concurrency / database problems

- JSON store (atomic + debounced) — OK for scale ≤1k links; no FK/transactions; single-worker enforced
- Trojan cache invalidation fixed (content-based); xHTTP reaper race fixed; quota gate atomic under LINKS_LOCK
- No orphan-cleanup for node-mirrored links after node removal (minor)

## 11. Configuration-generation problems (root cause of "panel→link" model)

1. `protocol` is a single fused string (`"trojan-xhttp-packet-up"`) — no protocol/transport/security separation
2. Unknown protocol **silently coerced** to DEFAULT_PROTOCOL (main.py:1992) instead of 400
3. No compatibility validation layer (any UI combo accepted)
4. No config versioning; no deterministic rebuild from a spec
5. 4 competing emitters produce divergent output for the same logical config

## 12. Health-check problems

- No per-config health state object (HEALTHY/DEGRADED/UNREACHABLE/INVALID/UNKNOWN missing)
- No health score; `/api/links/best` ranks by raw latency only
- No periodic sweep; results only exist after manual ping
- 6 adapters fake `ok=True` (pollutes engine rolling health)

## 13. Frontend/backend inconsistencies

- VPN Pro nav removed (backend honest-DEFERRED) — consistent now
- gRPC/HTTPUpgrade advertised in README but are XHTTP mimics — documentation drift
- Unified-configs tab generates links on the fly (b208791) — consistent
- Gaming "estimated ping" labels honest; presets carry static text estimates

## 14. Recommended migration order (this pass)

1. **compat.py** — single compatibility truth (protocol×transport×security)
2. **endpoint_profiles.py** — Endpoint & Transport Profile Engine (SNI-Spoofing refactor, migration-safe)
3. **config_compiler.py** — one emitter; old functions become facades (wire-compat preserved)
4. **network_health.py** — per-config health states + scores + sweep
5. **ip_quality.py** — provider abstraction + evidence-based classification
6. **job_system.py** + **diagnostics.py** — ops backbone
7. Honest adapter statuses (kill fake-healthy)
8. Subscription profiles; smart-route v2 consuming health
9. Tests + COMPETITIVE_MATRIX.md + FINAL_AUDIT_REPORT.md

**Non-goals preserved:** no wire-level changes to relays; JSON store kept (documented roadmap); no destructive migration; all legacy API fields keep working.
