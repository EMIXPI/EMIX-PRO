# ArvanCloud Edge/CDN Readiness

**Date:** 2026-08-29
**Status:** **UNVERIFIED** — ArvanCloud-specific behavior is documented here based on standard CDN/edge conventions. **No claim in this document has been verified against an actual ArvanCloud account.** Admins deploying on ArvanCloud MUST validate each item against their own ArvanCloud dashboard before relying on it.

---

## 1. Overview

EMIX-PRO supports an edge/CDN deployment model:

```
Client
   ↓
ArvanCloud Edge (CDN/WAF)
   ↓ (HTTPS, WebSocket, HTTP/2 where supported)
EMIX Reverse Proxy (optional — see reverseproxy/ subsystem)
   ↓
Railway Origin (EMIX FastAPI app)
```

The `reverseproxy/` subsystem (Phases 31-39) provides:
- Configurable routes (host + path → upstream URL)
- Load balancing across multiple EMIX instances
- HMAC origin authentication (edge → EMIX)
- Cache-safety headers on tunnel/auth paths (Phase 36 — non-negotiable)
- Trusted-edge X-Forwarded-For handling (Phase 37)

**The reverse proxy is OFF by default.** EMIX behaves exactly as before unless `EMIX_REVERSE_PROXY_ENABLED=1` + routes are configured.

---

## 2. DNS Setup

**Required:**
1. Configure your domain (e.g. `emix.example.com`) in ArvanCloud DNS.
2. Enable the CDN proxy (orange cloud equivalent) on the A/AAAA/CNAME record pointing to your Railway service.
3. Set the origin to your Railway public domain (`emix-pro-production.up.railway.app`).

**Origin protection:** Configure ArvanCloud to send `X-EMIX-Origin-Signature` + `X-EMIX-Origin-Timestamp` headers (Phase 39). Set `EMIX_ORIGIN_AUTH_SECRET` env var on Railway to the same secret.

---

## 3. CDN/Edge Configuration

| Setting | Value | Notes |
|---|---|---|
| Origin protocol | HTTPS | Railway terminates TLS automatically |
| WebSocket support | ENABLE | Required for VLESS-WS, Trojan-WS, Shadowsocks-WS, XHTTP |
| HTTP/2 | ENABLE | Improves connection multiplexing |
| HTTP/3/QUIC | OPTIONAL | ArvanCloud may or may not support — verify. UDP from edge to origin is not required (only client → edge needs UDP). |
| Cache level | "Bypass cache on /ws/*, /trojan-ws, /ss-ws, /xhttp-siz10/, /txhttp-siz10/, /sub/, /api/login, /api/links, etc." | See Phase 36 cache-safety list |
| WAF | ENABLE | Standard protection |

EMIX itself adds `Cache-Control: no-store` on all tunnel/auth paths via the Phase 36 middleware, so even if ArvanCloud doesn't bypass cache explicitly, the headers should be respected.

---

## 4. TLS Requirements

| Layer | Min version | Notes |
|---|---|---|
| Client ↔ ArvanCloud Edge | TLS 1.2+ (1.3 preferred) | Set by ArvanCloud dashboard |
| ArvanCloud Edge ↔ EMIX Origin | TLS 1.2+ | Railway terminates TLS automatically |
| Upstream (if reverse proxy enabled) | TLS 1.2+ (configurable via `EMIX_MIN_TLS_VERSION`) | Default 1.2 |

**Never disable TLS verification** in production. `Upstream.verify_tls=True` is the default.

---

## 5. WebSocket Requirements

EMIX uses WebSocket for VLESS, Trojan, Shadowsocks, and XHTTP transports. ArvanCloud MUST:
- Forward `Upgrade: websocket` and `Connection: Upgrade` headers
- Allow long-lived connections (no aggressive idle timeout < 5 min)
- Support permessage-deflate (optional — EMIX does not enable compression by default per Phase 14.5)

**EMIX-side:** WebSocket idle timeout is configurable per route (`ws_idle_timeout`, default 300s).

---

## 6. HTTP/2 Requirements

EMIX's FastAPI server speaks HTTP/2 via Cloudflare/Railway edge. ArvanCloud should:
- Enable HTTP/2 between client and edge
- Forward HTTP/2 to origin (Railway supports HTTP/2)

---

## 7. HTTP/3 / QUIC Limitations

**Status:** UNVERIFIED.

EMIX does NOT require HTTP/3 to the origin. The DEFERRED adapters for Hysteria2 + TUIC would require QUIC, but those are not implemented in the EMIX process (they require external Go binaries — see `protocol_adapters/hysteria2.py` + `protocol_adapters/tuic.py`).

If ArvanCloud supports HTTP/3 from client → edge, that's fine — EMIX accepts standard HTTP/2 (or HTTP/1.1 with WebSocket Upgrade) from edge → origin.

---

## 8. Timeout Considerations

| Phase | Default | Configurable |
|---|---|---|
| Client ↔ Edge | Set by ArvanCloud | — |
| Edge ↔ EMIX Origin | Set by ArvanCloud | — |
| EMIX route connect timeout | 10s | `EMIX_NODE_TIMEOUT` (per route) |
| EMIX route read timeout | 30s | per route `read_timeout` |
| EMIX WebSocket idle | 300s | per route `ws_idle_timeout` |
| EMIX session TTL | 7 days | `EMIX_SESSION_TTL` |

For tunnel traffic (WebSocket + XHTTP), increase the WebSocket idle timeout if clients have long-lived connections.

---

## 9. Caching Behavior

**Cache bypass rules (Phase 36 — non-negotiable):**

Tunnel paths MUST NEVER be cached:
- `/ws/*` — VLESS WebSocket
- `/trojan-ws` — Trojan WebSocket
- `/ss-ws` — Shadowsocks WebSocket
- `/xhttp-siz10/*` — VLESS XHTTP (all modes)
- `/txhttp-siz10/*` — Trojan XHTTP
- `/sub/*` — Subscription URLs (contain UUID + traffic info — credentials!)
- `/sub-all` — Aggregate subscription
- `/p/*` — Public sub page (per-user)
- `/api/login`, `/api/logout`, `/api/change-password` — auth endpoints
- `/api/backup/*` — state export/import
- `/api/links*`, `/api/subs*`, `/api/nodes*` — admin mutations
- `/api/me` — session check
- `/api/exp/*` — experimental endpoints (state-changing)
- `/api/protocols/*` (except `GET /api/protocols` itself)
- `/api/settings/*` — settings mutations
- `/api/announcements/view` — user-state mutation
- `/api/support/*` — private support messages
- `/api/mtproto/*`, `/api/zeus-proxy/*`, `/api/bot-tcp-proxy/*`, `/api/domain-gen/*`
- `/api/connections`, `/api/activity`
- `/stats`, `/proxy/*`

**EMIX adds `Cache-Control: no-store, no-cache, must-revalidate` + `CDN-Cache-Control: no-store` (ArvanCloud convention) + `Surrogate-Control: no-store` on all these paths via the Phase 36 middleware.** Even if ArvanCloud doesn't explicitly bypass cache, the headers should be respected.

---

## 10. Header Forwarding

**Headers EMIX trusts from a trusted edge (Phase 37):**
- `X-Forwarded-For` — first entry only (real client IP)
- `X-Real-IP` — fallback if XFF absent
- `CF-Connecting-IP` — Cloudflare convention
- `X-Arvan-Edge` — ArvanCloud convention (if ArvanCloud sets this)

**Headers EMIX NEVER trusts unless from trusted edge:**
- Any of the above from arbitrary clients → ignored, remote_addr used instead

**Headers EMIX strips from forwarded request (Phase 37):**
- `Cookie`, `Authorization`, `Proxy-Authorization`
- `X-Forwarded-For`, `X-Forwarded-Host`, `X-Forwarded-Proto`, `Forwarded`
- All hop-by-hop headers (RFC 7230 §6.1)

Only `User-Agent`, `Accept`, `Accept-Encoding`, `Accept-Language`, `Content-Type`, `Content-Disposition`, `Range`, `If-Modified-Since`, `If-None-Match`, `Cache-Control`, `Pragma`, `Expires` are forwarded.

---

## 11. Client IP Forwarding

EMIX's `get_real_client_ip()` (in `reverseproxy/headers.py`):
1. If request came through a trusted edge (verified by trusted-edge header presence), extract the first `X-Forwarded-For` entry.
2. If no trusted edge, return the actual TCP peer (`request.client.host`).

This prevents IP spoofing from arbitrary clients setting fake XFF headers.

---

## 12. Health Checks

EMIX exposes:
- `GET /api/ping` — lightweight, no auth, returns OK (Railway healthcheck)
- `GET /health` — same
- `GET /api/health` — authed, structured internal health (Phase 17)
- `GET /api/protocols/{name}/health` — authed, per-protocol rolling health
- `GET /api/edge/upstreams/health` — authed, per-upstream circuit-breaker state (Phase 34)

ArvanCloud should monitor `/api/ping` (no auth, public).

---

## 13. Origin Protection (Phase 39)

EMIX supports HMAC-SHA256 origin authentication between edge and origin:

1. Generate a 32-byte secret: `openssl rand -hex 32`
2. Set `EMIX_ORIGIN_AUTH_SECRET=<secret>` on Railway
3. Configure ArvanCloud (via a Cloudflare-Worker-style script or transform rule) to compute and send:
   - `X-EMIX-Origin-Signature: <hex(HMAC-SHA256(secret, METHOD|PATH|TIMESTAMP|BODY))>`
   - `X-EMIX-Origin-Timestamp: <epoch_seconds>`
4. EMIX verifies signature with `hmac.compare_digest` (constant time)
5. Replay window: ±60 seconds (configurable)

**Limitations:**
- The edge-side signature generation MUST be implemented by the admin (ArvanCloud doesn't natively support HMAC signatures — needs a custom Worker/transform rule).
- If `EMIX_ORIGIN_AUTH_SECRET` is empty/unset, origin auth is DISABLED (feature off → all requests pass).

---

## 14. Recommended DNS Configuration

```
emix.example.com.        CNAME  emix-pro-production.up.railway.app.  ; CDN proxied
api.emix.example.com.    CNAME  emix-pro-production.up.railway.app.  ; CDN proxied (if you want API on subdomain)
tunnel.emix.example.com. CNAME  emix-pro-production.up.railway.app.  ; CDN proxied (WebSocket)
```

Set `EMIX_CORS_ORIGINS=https://emix.example.com,https://api.emix.example.com` on Railway to enable credentials safely (Phase 7.13).

---

## 15. Railway Origin Configuration

On Railway:
1. Generate a public domain (`Settings → Networking → Generate Domain`).
2. Set environment variables:
   - `RAILWAY_PUBLIC_DOMAIN=<your-railway-domain>`
   - `ADMIN_PASSWORD=<strong-password>`
   - `SECRET_KEY=<strong-secret>`
   - `EMIX_CORS_ORIGINS=https://emix.example.com` (Phase 7.13)
   - `EMIX_TRUSTED_EDGES=arvancloud.com,*.arvancloud.com` (Phase 37)
   - `EMIX_ORIGIN_AUTH_SECRET=<32-byte-secret>` (Phase 39)
   - `EMIX_REVERSE_PROXY_ENABLED=0` (set to 1 only if using reverse-proxy routes)
3. (Optional) Attach a persistent volume at `/data` so state survives redeploys.

---

## 16. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| WebSocket disconnects every 60s | ArvanCloud idle timeout too low | Increase edge WebSocket timeout to ≥300s |
| Tunnel traffic cached | Cache bypass rules not configured | EMIX already sends `Cache-Control: no-store` — verify ArvanCloud respects it. Configure explicit bypass rules for `/ws/*`, `/trojan-ws`, `/ss-ws`, `/sub/*`, `/api/*` |
| Login fails through CDN | Origin auth signature mismatch | Verify `EMIX_ORIGIN_AUTH_SECRET` matches edge-side secret. Check replay window. |
| Wrong client IP in logs | XFF from non-trusted source | Add edge to `EMIX_TRUSTED_EDGES`. |
| CORS preflight fails | Origins not configured | Set `EMIX_CORS_ORIGINS`. |
| Subscription URL cached | CDN cached `/sub/*` | Configure bypass rule for `/sub/*` and `/sub-all`. |

---

## 17. Protocol Compatibility Matrix (UNVERIFIED)

| Protocol | ArvanCloud CDN-compatible? | Verified? |
|---|---|---|
| VLESS-WS | SHOULD work (WebSocket over HTTPS) | UNVERIFIED |
| VLESS-XHTTP | SHOULD work (HTTP POST/GET) | UNVERIFIED |
| Trojan-WS | SHOULD work (WebSocket) | UNVERIFIED |
| Trojan-XHTTP | SHOULD work (HTTP POST/GET) | UNVERIFIED |
| Shadowsocks (AEAD) | SHOULD work (WebSocket) | UNVERIFIED |
| MTProto (FakeTLS) | **NOT CDN-compatible** — needs direct TCP | N/A (must use direct TCP, not through CDN) |
| HTTP-Proxy | SHOULD work | UNVERIFIED |
| Zeus SOCKS5 | **NOT CDN-compatible** — raw TCP | N/A |
| VMess link emission | Link only — client connects directly | N/A |
| VLESS-Reality link emission | Link only — Reality is direct TLS, no CDN | N/A |
| SS-2022 link emission | Link only — direct TCP | N/A |

**Why UNVERIFIED:** I do not have access to an ArvanCloud account to test. Admins MUST verify by:
1. Setting up a test tunnel through ArvanCloud
2. Generating a config in EMIX
3. Importing into a client (v2rayNG / NekoBox)
4. Connecting + verifying traffic flows + checking the ArvanCloud dashboard logs

---

## 18. ArvanCloud vs Cloudflare

EMIX supports both. The existing Cloudflare Worker (`cf_gateway_worker.js` v1.5.0) is preserved unchanged. If you switch to ArvanCloud:
- The CF Worker is no longer needed (ArvanCloud's edge does the routing)
- Set `EMIX_TRUSTED_EDGES=arvancloud.com,*.arvancloud.com` instead of `cloudflare.com`
- Configure ArvanCloud DNS + CDN per sections above
- The CF Worker's multi-location feature (`/loc/{name}/...`) is replaced by ArvanCloud's own routing

**To switch back to Cloudflare:** just unset the env vars and the existing CF Worker takes over again.
