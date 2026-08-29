# EMIX-PRO Architecture

**Version:** 9.11.0-reverse-proxy-edge
**Date:** 2026-08-29

This document describes the ACTUAL architecture of EMIX-PRO as it exists in the codebase today. No architectural aspirations are described here — only what's implemented.

---

## 1. Service Overview

EMIX-PRO is a single-process FastAPI application that:
1. Hosts production proxy protocols (VLESS/Trojan/Shadowsocks/MTProto/XHTTP) as WebSocket + HTTP routes
2. Provides an admin dashboard at `/dashboard`
3. Manages link configurations, subscriptions, nodes, sessions
4. Persists state to a JSON file at `/data/rvg_state.json`
5. Optionally (Phase 31+) acts as a reverse-proxy with HMAC origin authentication

**Process model:** single uvicorn worker (correct — all state is in-process).

---

## 2. Layered Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Railway Edge (HTTPS)                         │
│                       TLS termination + routing                      │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│                  Optional: Cloudflare Worker (v1.5.0)                │
│       Multi-location gateway, KV namespace, admin token auth        │
└──────────────────────────────────────────────────────────────────────┘
                                ↓ (or direct)
┌──────────────────────────────────────────────────────────────────────┐
│              Optional: ArvanCloud / other CDN edge                   │
│         Client IP forwarding, cache bypass, WAF, HMAC edge          │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│                    Optional: EMIX reverse proxy                     │
│  (reverseproxy/ subsystem — opt-in via EMIX_REVERSE_PROXY_ENABLED)  │
│   Routes by host+path → upstream URL, load-balancing, HMAC auth      │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│                        FastAPI app (main.py)                        │
│   1. Cache-safety middleware (Phase 36) — no-store on tunnel paths  │
│   2. Public-host learning middleware                                  │
│   3. CORS (configurable, never wildcard+credentials)                │
│   4. RateLimitMiddleware + SecurityHeadersMiddleware (opt-in)       │
│   5. 83 routes: auth, links, subs, nodes, stats, backup, protocols,  │
│      exp_api, gaming, smart_route, isp_detect, edge                  │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│                          Protocol layer                              │
│  protocol/vless/{vless,websocket,xhttp_*}.py                         │
│  protocol/trojan/{trojan,websocket,xhttp_*}.py                       │
│  protocol/shadowsocks/{shadowsocks,websocket}.py                    │
│  protocol/mtproto/{mtproto_native,telemt}.py (per-instance binary)  │
│  zeussocks5.py (SOCKS5 server, RFC1929 user/pass auth)                │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│                    Protocol engine + adapters                        │
│  protocol_engine/ (base, registry, capabilities, health, metrics,   │
│    selector, fallback)                                               │
│  protocol_adapters/existing/ (8 STABLE — wrap production code)       │
│  protocol_adapters/ (11 more — 3 EXPERIMENTAL link-emission,         │
│    5 DEFERRED, 3 EXPERIMENTAL capability-detection)                  │
└──────────────────────────────────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────────┐
│                      Persistence + state                             │
│  In-memory: LINKS, SUBS, NODES, SESSIONS, NODE_KEYS                 │
│  (guarded by asyncio.Lock)                                            │
│  JSON file at /data/rvg_state.json (atomic write + debounce)         │
│  Session cleanup background task (Phase 1.2)                          │
│  Hourly-traffic bounded retention (Phase 1.3)                         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Module Inventory

### 3.1 Core (main.py, 3483 lines)
- FastAPI app + 83 routes
- Auth: SESSIONS dict, sha256(password + secret) hash, session TTL 7 days
- Persistence: `load_state()` / `save_state()` with atomic temp+rename + debounce
- Background tasks: session cleanup (Phase 1.2), central heartbeat
- HTTP forward proxy `/proxy/{target_url}` with SSRF protection (Phase 7.14)
- Cache-safety middleware (Phase 36)
- Version endpoint + deployment-version endpoint

### 3.2 Protocol implementations (protocol/, ~3000 lines)
- `protocol/vless/` — vless.py + websocket.py + xhttp_core.py + 4 xHTTP mode handlers
- `protocol/trojan/` — same structure
- `protocol/shadowsocks/` — AEAD (chacha20-ietf-poly1305 / aes-256-gcm)
- `protocol/mtproto/` — per-instance official Telegram binary

### 3.3 Protocol engine (protocol_engine/, 7 modules, ~600 lines)
- `base.py` — ProtocolAdapter abstract class
- `capabilities.py` — 24 capability flags + Transport/ProtocolStatus enums
- `registry.py` — register/unregister/get/list + safe_register
- `health.py` — RollingHealth (5-min window success rate + p95 RTT)
- `metrics.py` — per-protocol counters (connections, bytes, fallbacks)
- `selector.py` — smart scoring with 5 network profiles
- `fallback.py` — bounded retries + exponential backoff

### 3.4 Protocol adapters (protocol_adapters/, 19 adapters)
- `existing/` (8 STABLE) — wrap production code, no wire changes
- 3 EXPERIMENTAL link-emission (VMess, VLESS-Reality, SS-2022)
- 5 DEFERRED (Hysteria2, TUIC, WireGuard, NaiveProxy, OpenVPN) — refuse to start
- 3 EXPERIMENTAL capability-detection (SSH, gRPC, HTTPUpgrade)

### 3.5 Reverse proxy subsystem (reverseproxy/, 7 modules, ~750 lines)
- `config.py` — Route + Upstream + ReverseProxyConfig (env-var loaded)
- `headers.py` — header filtering, cache safety, CRLF injection check, trusted-edge IP
- `auth.py` — HMAC-SHA256 origin authentication (Phase 39)
- `health.py` — per-upstream RollingHealth + circuit breaker (closed/open/half_open)
- `loadbalancer.py` — 5 strategies (round_robin, weighted, least_connections, latency_aware, priority)
- `proxy.py` — main reverse_proxy_handler + background upstream health checks
- `api.py` — /api/edge/* endpoints (re-registered in main.py with require_auth)

### 3.6 Auxiliary modules
- `central.py` — heartbeat to external worker (sends password_hash — Phase 8.4 documented risk)
- `bottokentcpproxy.py` + `botgeneratedomin.py` — Railway TCP proxy automation via Telegram bot
- `zeussocks5.py` — SOCKS5 server
- `link_emit.py` — VMess/VLESS-Reality/SS-2022 link emission
- `link_health.py` — fast ping path + WS/XHTTP probe
- `security_exp.py` — opt-in PBKDF2 + rate limit + CSRF + CSP
- `experimental.py` — toggle-based experimental features
- `exp_api.py` — experimental endpoints (link emit + subscription formats)
- `protocols_api.py` — /api/protocols/* endpoints
- `node_health.py` — node circuit breaker (Phase 4.10)
- `backup_validator.py` — strict backup schema validation (Phase 3.9)
- `config_layer.py` — typed EmixConfig with env-var overrides

### 3.7 Dashboard (pages.py, 9952 lines)
- 19 page sections (`pg-overview`, `pg-links`, `pg-bridge`, `pg-zeus`, `pg-gaming`,
  `pg-vpn`, `pg-subgroups`, `pg-subscriptions`, `pg-traffic`, `pg-connections`,
  `pg-nodes`, `pg-logs`, `pg-errors`, `pg-updates`, `pg-support`, `pg-backup`,
  `pg-settings`, `pg-experimental`, `pg-unified-configs`)
- 27 `@media` queries for mobile responsiveness (down to 260px)
- NixHD design system (deep black + violet + yellow + glassmorphism)
- Vazirmatn + Tabler icons + JetBrains fonts

### 3.8 Tests (tests/, 218 tests, all passing)
- 10 unit test files
- 4 integration test files
- 4 regression test files
- conftest.py with project root + env vars

### 3.9 Documentation (docs/)
- `PROTOCOLS.md` — protocol support matrix (Phase 2)
- `POST_MULTIPROTOCOL_STATE.md` — Phase 30 reconnaissance
- `ARVANCLOUD.md` — ArvanCloud edge/CDN readiness (UNVERIFIED)
- `ARCHITECTURE.md` — this document
- `PROTOCOL_MATRIX.md` — protocol × transport × CDN matrix
- `REVERSE_PROXY.md` — reverse-proxy subsystem documentation
- `DEPLOYMENT.md` — Railway deployment guide
- `TROUBLESHOOTING.md` — common issues
- `FINAL_HEALTH_REPORT.md` — final health scorecard

---

## 4. State Management

### 4.1 In-memory state (single-worker, process-local)
- `LINKS: dict[uuid, dict]` + `LINKS_LOCK = asyncio.Lock()`
- `SUBS: dict[sub_id, dict]` + `SUBS_LOCK`
- `NODES: dict[node_id, dict]` + `NODES_LOCK`
- `NODE_KEYS: dict[key_id, dict]` + `NODE_KEYS_LOCK`
- `SESSIONS: dict[token, expiry_timestamp]` + `SESSIONS_LOCK`
- `connections: dict[conn_id, dict]` — active connection metadata
- `hourly_traffic: dict[iso_key, bytes]` — bounded 72-hour retention (Phase 1.3)
- `error_logs: deque(maxlen=50)` + `activity_logs: deque(maxlen=200)`
- `_NODE_CACHE: dict[node_id, {at, data}]` — 8s TTL

### 4.2 Persistence
- JSON file at `DATA_DIR/rvg_state.json` (default `/data`)
- Atomic write: `.tmp` → `os.replace()`
- Debounced: `schedule_save()` coalesces bursts every `SAVE_DEBOUNCE_SECONDS=2.0`
- Backup before restore: `.pre-restore.json` (Phase 3.9)
- Loaded at startup, saved on shutdown, saved debounced on mutations

### 4.3 Background tasks
- `central.heartbeat_loop()` — every 5 min, posts to external worker
- `_session_cleanup_loop()` — every hour, prunes expired sessions (Phase 1.2)
- `reverseproxy.background_upstream_health_checks()` — per-route health probes (Phase 34, opt-in)
- All tasks cancelled cleanly on `shutdown`

---

## 5. Authentication & Sessions

- `AUTH["password_hash"]` = `sha256(password + CONFIG['secret'])`
- `load_state()` has backward-compat shim: only accepts sha256-format (64 hex) hashes, rejects PBKDF2 from never-released audit branch
- Sessions: `secrets.token_urlsafe(32)`, stored with expiry timestamp, TTL 7 days
- Session validation: `is_valid_session(token)` checks `exp < time.time()` + lazy pop
- Session cleanup: background task prunes expired entries hourly
- No CSRF token by default (csrf_protection is opt-in via `EMIX_ENABLE_CSRF_PROTECTION=1`)

---

## 6. External Integrations

### 6.1 Cloudflare Worker (`cf_gateway_worker.js` v1.5.0)
- Multi-location gateway
- KV namespace `EMIX_LOCATIONS`
- Admin token `EMIX_TOKEN`
- WebSocket passthrough
- `/loc/{name}/...` route forwarding
- `/admin/locations` (token-authed)
- `/gateway-status` (5-min cache)

### 6.2 Central service (`central.py`)
- Heartbeat every 5 min to `https://panel-rvg.arvin341az.workers.dev/api/register`
- Sends: `domain`, `version`, `panel_password_hash`, `description`
- **Phase 8.4 — documented risk:** hash is `sha256(password + secret)` — brute-forceable if password is weak. Admin should set strong `ADMIN_PASSWORD` + `SECRET_KEY`.

### 6.3 Railway TCP proxy automation (`bottokentcpproxy.py`)
- Per-port TCP proxy creation via Railway GraphQL API
- Token stored in `DATA_DIR/.railway_token`
- Used for MTProto public proxy endpoints (each MTProto instance has its own port)

### 6.4 Telegram bot
- Built into `bottokentcpproxy.py` + `botgeneratedomin.py`
- Manages proxy creation, domain generation
- All network calls have bounded timeouts

---

## 7. Configuration System

`config_layer.py` exposes typed `EmixConfig` dataclass with env-var overrides:

| Env var | Default | Purpose |
|---|---|---|
| `EMIX_SESSION_TTL` | 604800 (7 days) | Session expiry |
| `EMIX_SESSION_CLEANUP_INTERVAL` | 3600 (1 hour) | Cleanup loop interval |
| `EMIX_SAVE_DEBOUNCE` | 2.0 | State save debounce (seconds) |
| `EMIX_HOURLY_RETENTION` | 72 | Hourly-traffic retention (hours) |
| `EMIX_XHTTP_SEQ_BUF_MAX_MB` | 4 | xHTTP packet-up buffer cap |
| `EMIX_NODE_TIMEOUT` | 10.0 | Node request timeout |
| `EMIX_NODE_MAX_RETRIES` | 2 | Node circuit breaker retries |
| `EMIX_NODE_BACKOFF_BASE_MS` | 250 | Exponential backoff base |
| `EMIX_NODE_FAILURE_THRESHOLD` | 3 | Circuit breaker threshold |
| `EMIX_NODE_COOLDOWN` | 30 | Circuit breaker cooldown |
| `EMIX_PROXY_ALLOW_PRIVATE` | false | Allow private IPs in /proxy |
| `EMIX_PROXY_MAX_BYTES` | 50MB | Max proxy response size |
| `EMIX_CORS_ORIGINS` | unset (= `*` without credentials) | Allowed CORS origins |
| `EMIX_REVERSE_PROXY_ENABLED` | false | Enable reverse proxy |
| `EMIX_REVERSE_PROXY_ROUTES_JSON` | unset | Route configuration |
| `EMIX_TRUSTED_EDGES` | unset | Trusted CDN/edge hostnames |
| `EMIX_ORIGIN_AUTH_SECRET` | unset | HMAC origin auth secret |
| `EMIX_CACHE_SAFETY` | true | Apply no-store headers |
| `EMIX_MIN_TLS_VERSION` | 1.2 | Min TLS version |

All defaults match prior hardcoded values — no env var required to deploy.

---

## 8. Test Coverage

**218 tests, all passing:**

| File | Tests | Coverage |
|---|---|---|
| test_parse_size.py | 10 | Phase 2.8 — input validation |
| test_backup_validator.py | 14 | Phase 3.9 — backup schema |
| test_node_circuit_breaker.py | 9 | Phase 4.10 — circuit breaker |
| test_trojan_cache.py | 5 | Phase 6.12 — generation counter |
| test_protocol_registry.py | 9 | Phase 2 — registry behavior |
| test_protocol_capabilities.py | 4 | Phase 2 — capability enum |
| test_smart_selector.py | 10 | Phase 2 — selector scoring |
| test_fallback.py | 5 | Phase 2 — fallback chain |
| test_reverse_proxy.py | 20 | Phase 31-39 — reverse proxy + cache + HMAC |
| test_reaper_race.py | 3 | Phase 1.6 — single reaper |
| test_seq_buf_bound.py | 5 | Phase 2.7 — buffer limit |
| test_hourly_traffic_bound.py | 7 | Phase 1.3 — bounded retention |
| test_session_cleanup.py | 5 | Phase 1.2 — session cleanup |
| test_proxy_ssrf.py | 16 | Phase 7.14 — SSRF protection |
| test_protocol_adapters.py | 95 (19 × 5) | Phase 2 — every adapter |
| **Total** | **218** | — |

Run: `pytest tests/ -q`

---

## 9. Deployment Model

### Railway (current production)
- Single uvicorn worker (`python main.py`)
- PORT env var (Railway auto-sets)
- Binds `0.0.0.0`
- Healthcheck: `GET /api/ping`
- Restart on failure (max 5 retries, 180s timeout)
- Optional persistent volume at `/data` for state

### Limitations on Railway
- No privileged kernel access (no BBR, no sysctl)
- No system WireGuard (would need userspace wireguard-go)
- No Docker-in-Docker (can't run external binaries)
- UDP supported but architecture is TCP/WS-only
- Single region (Amsterdam by default)

### Why not SQLite/PostgreSQL?
JSON persistence is sufficient for the typical deployment size (≤1000 links). Atomic write + debounce handles the I/O pattern. Adding a DB would require:
- Railway persistent volume (costs more)
- Schema migrations + transactions
- More failure modes

The StorageBackend abstraction (Phase 15) is DEFERRED — JSON backend remains default.
