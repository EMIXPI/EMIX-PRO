# EMIX Reverse Proxy Subsystem

**Module:** `reverseproxy/`
**Status:** STABLE (opt-in, default off)
**Phases implemented:** 31 (engine), 32 (routing), 33 (load balancing), 34 (health), 36 (cache safety), 37 (header management), 38 (SSRF hardening), 39 (origin auth)

---

## 1. Overview

The reverseproxy subsystem is an **opt-in** reverse-proxy layer that sits in front of the existing EMIX FastAPI routes. When `EMIX_REVERSE_PROXY_ENABLED=0` (default), the subsystem is a no-op and EMIX behaves exactly as before.

When enabled, it provides:
1. Host+path routing to upstream URLs
2. Load balancing across multiple upstreams (5 strategies)
3. Circuit-breaker per upstream (closed → open → half_open → closed)
4. HMAC-SHA256 origin authentication (edge → EMIX)
5. Cache-safety headers on tunnel/auth paths
6. Trusted-edge X-Forwarded-For handling
7. Background upstream health checks

---

## 2. Configuration (env vars)

| Env var | Default | Purpose |
|---|---|---|
| `EMIX_REVERSE_PROXY_ENABLED` | `0` | Enable the subsystem |
| `EMIX_REVERSE_PROXY_ROUTES_JSON` | unset | JSON array of routes |
| `EMIX_TRUSTED_EDGES` | unset | Comma-separated trusted CDN/edge hostnames (globs allowed) |
| `EMIX_ORIGIN_AUTH_SECRET` | unset | HMAC secret shared with edge (origin auth disabled if empty) |
| `EMIX_CACHE_SAFETY` | `1` | Apply no-store headers on tunnel paths |
| `EMIX_MIN_TLS_VERSION` | `1.2` | Minimum TLS version |

### Example routes JSON

```json
[
  {
    "host": "emix.example.com",
    "path": "/",
    "transport": "http",
    "upstreams": [
      {"url": "http://127.0.0.1:8000", "weight": 2, "priority": 1, "verify_tls": true}
    ],
    "lb_strategy": "round_robin",
    "connect_timeout": 10.0,
    "read_timeout": 30.0,
    "ws_idle_timeout": 300.0,
    "health_check_path": "/api/ping",
    "health_check_interval": 30.0,
    "health_check_timeout": 5.0
  },
  {
    "host": "tunnel.emix.example.com",
    "transport": "websocket",
    "upstreams": [
      {"url": "http://127.0.0.1:8000"}
    ],
    "ws_idle_timeout": 600.0
  }
]
```

---

## 3. Load Balancing Strategies

| Strategy | Behavior |
|---|---|
| `round_robin` | Cycle through healthy upstreams |
| `weighted` | Weighted random based on `Upstream.weight` |
| `least_connections` | Pick the upstream with fewest active connections |
| `latency_aware` | Pick the upstream with lowest avg RTT in last 5 min |
| `priority` | Filter to highest `Upstream.priority`, then round-robin |

All strategies skip upstreams whose circuit is OPEN (cooldown not elapsed).

---

## 4. Circuit Breaker

Per (route, upstream) pair:
- 3 consecutive failures → OPEN (cooldown 30s)
- Cooldown elapsed → HALF_OPEN (one probe allowed)
- Probe succeeds → CLOSED
- Probe fails → OPEN again (cooldown restarted)

This pattern is identical to the node_health circuit breaker (Phase 4.10).

---

## 5. Cache Safety (Phase 36 — non-negotiable)

Every response on a tunnel/auth/subscription/admin path automatically gets:
```
Cache-Control: no-store, no-cache, must-revalidate, max-age=0
Pragma: no-cache
Expires: 0
Surrogate-Control: no-store
CDN-Cache-Control: no-store  (ArvanCloud convention)
```

This is applied globally via a middleware in `main.py` (not just on `/proxy`).

**Tunnel paths include:**
- `/ws/*` (VLESS WebSocket)
- `/trojan-ws`, `/ss-ws` (Trojan/Shadowsocks WebSocket)
- `/xhttp-siz10/*`, `/txhttp-siz10/*` (XHTTP all modes)
- `/sub/*`, `/sub-all`, `/p/*` (subscription URLs — contain UUID/credentials)
- `/api/login`, `/api/logout`, `/api/change-password`
- `/api/backup/*`
- `/api/links*`, `/api/subs*`, `/api/nodes*`
- `/api/me`, `/api/exp/*`, `/api/protocols/*` (except GET list)
- `/api/settings/*`, `/api/announcements/view`, `/api/support/*`
- `/api/mtproto/*`, `/api/zeus-proxy/*`, `/api/bot-tcp-proxy/*`, `/api/domain-gen/*`
- `/api/connections`, `/api/activity`
- `/stats`, `/proxy/*`

---

## 6. Header Management (Phase 37)

### Forwarded to upstream (allowlist)
- `User-Agent`, `Accept`, `Accept-Encoding`, `Accept-Language`
- `Content-Type`, `Content-Disposition`, `Range`
- `If-Modified-Since`, `If-None-Match`
- `Cache-Control`, `Pragma`, `Expires`

### NEVER forwarded
- Hop-by-hop (RFC 7230 §6.1): `Connection`, `Keep-Alive`, `Proxy-Authenticate`, `Proxy-Authorization`, `TE`, `Trailers`, `Transfer-Encoding`, `Upgrade`, `Content-Encoding`, `Content-Length`
- Sensitive: `Cookie`, `Authorization`, `Proxy-Authorization`, `X-Forwarded-*`, `Forwarded`

### CRLF injection check
Any header value containing `\r` or `\n` is rejected with HTTP 400.

---

## 7. HMAC Origin Authentication (Phase 39)

### Flow
1. Edge (Cloudflare Worker or ArvanCloud transform rule) computes:
   - `signature = HMAC-SHA256(secret, METHOD + "|" + PATH + "|" + timestamp + "|" + body)`
   - `timestamp = int(time.time())`
2. Edge sends headers:
   - `X-EMIX-Origin-Signature: <hex signature>`
   - `X-EMIX-Origin-Timestamp: <epoch seconds>`
3. EMIX recomputes HMAC and compares with `hmac.compare_digest` (constant time — no timing attacks)
4. EMIX checks `abs(now - timestamp) <= 60` (replay window)
5. On failure: HTTP 401 + log warning (no information leakage in error message)

### Configuration
- Set `EMIX_ORIGIN_AUTH_SECRET=<32-byte-secret>` on Railway
- Configure edge-side signature generation (admin's responsibility — ArvanCloud doesn't natively support HMAC signatures)
- Use `POST /api/edge/origin/test` to generate test signatures for validation

### Disabled by default
If `EMIX_ORIGIN_AUTH_SECRET` is empty/unset, origin auth is OFF and all requests pass.

---

## 8. Trusted-Edge Client IP Handling (Phase 37)

`get_real_client_ip(headers, remote_addr)`:
1. If no trusted-edge header (`cf-connecting-ip`, `cf-ipcountry`, `x-arvan-edge`, `x-real-ip`, `x-forwarded-for`) is present → return `remote_addr` (actual TCP peer)
2. If trusted-edge header present → extract first `X-Forwarded-For` entry
3. Fallback to `X-Real-IP`

This prevents IP spoofing from arbitrary clients sending fake XFF headers.

To add a trusted edge, set `EMIX_TRUSTED_EDGES`:
```
EMIX_TRUSTED_EDGES=cloudflare.com,*.workers.dev,arvancloud.com,*.arvancloud.com
```

Glob patterns supported: `*.workers.dev` matches `emix-gateway.personalemixone.workers.dev`.

---

## 9. API Endpoints

All endpoints require session-cookie auth (registered in `main.py` with `Depends(require_auth)`).

| Method | Path | Description |
|---|---|---|
| GET | `/api/edge/config` | Current reverse-proxy config (no secrets) |
| GET | `/api/edge/routes` | List configured routes |
| GET | `/api/edge/upstreams/health` | All upstream health snapshot |
| POST | `/api/edge/reload` | Force-reload config from env vars |
| POST | `/api/edge/origin/test` | Generate test HMAC signature (for edge-side validation) |

---

## 10. Background Health Checks (Phase 34)

When `EMIX_REVERSE_PROXY_ENABLED=1` AND routes are configured, a background task probes each upstream every `health_check_interval` seconds (default 30s).

- One probe per interval per upstream (bounded traffic)
- Probes `GET <upstream_url><route.health_check_path>` (default `/api/ping`)
- 2xx + 3xx = success, 4xx + 5xx = failure
- Records in `UpstreamHealth` (5-min rolling window)
- Circuit-breaker state updated

The task is cancelled cleanly on `shutdown`.

---

## 11. Limitations

1. **Single worker only.** The reverse proxy shares EMIX's single-uvicorn-worker model. Multi-worker would create inconsistent circuit-breaker state.
2. **No gRPC streaming proxy.** The reverse proxy handles HTTP requests. For gRPC, use the existing XHTTP transport which already mimics the gRPC envelope.
3. **No HTTP/3 upstream.** httpx supports HTTP/2 only. HTTP/3 upstream would require `aioquic` (deferred).
4. **Per-request httpx client.** The current implementation creates a new `httpx.AsyncClient` per request. For high-throughput deployments, a per-upstream connection pool would be more efficient — but adds complexity and resource management concerns. Deferred.
5. **Origin auth is OFF by default.** Admins must explicitly set `EMIX_ORIGIN_AUTH_SECRET` to enable.

---

## 12. Tests

20 tests in `tests/unit/test_reverse_proxy.py`:
- Config loaded from env vars
- Trusted-edge glob matching (cloudflare.com, *.workers.dev, arvancloud.com)
- Route matching by host+path
- Tunnel path detection
- Cache safety header injection
- CRLF injection detection
- Real client IP extraction (direct vs trusted-edge)
- HMAC signature round-trip (build + verify)
- Replay rejection
- Signature mismatch rejection
- Disabled-when-no-secret behavior
- Upstream health recording
- Circuit breaker state transitions
- Load balancer strategies (round_robin, priority, skip-open-circuits, all-unhealthy)

All pass.
