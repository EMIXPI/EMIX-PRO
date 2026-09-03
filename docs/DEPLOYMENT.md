# EMIX-PRO Deployment Guide

**Version:** 11.5.1-hotfix-identity
**Platform:** Railway (primary), Cloudflare Worker (edge gateway, optional), ArvanCloud (edge, optional)

---

## 0. Panel Identity (READ FIRST — v11.5.1)

The panel derives the UUIDs of the **default configs** (and the admin password
hash) from a deployment **identity**. Identity resolution order:

| Priority | Source | Stable across redeploys? | Notes |
|---|---|---|---|
| 1 | `SECRET_KEY` env | ✅ yes | **Recommended** — operator-controlled, high entropy |
| 2 | `DATA_DIR/.rvg_secret` file | ✅ yes (needs Volume) | Existing volume deployments — unchanged behavior |
| 3 | `RAILWAY_SERVICE_ID` env | ✅ yes | Auto-fallback on Railway (stable per service; **not a strong secret**) |
| 4 | `EMIX_IDENTITY_SEED` env | ✅ yes | Generic fallback for other platforms (not a strong secret) |
| 5 | random | ❌ **NO** | Last resort — CRITICAL warning logged; every redeploy kills delivered default configs |

**Why this matters:** without a stable identity (no `SECRET_KEY`, no Volume),
every redeploy (i.e. every `git push`) regenerates the secret → default-config
UUIDs change → **every previously delivered config is rejected with
`1008 not authorized`** (this caused a real production outage — see CHANGELOG
v11.5.1). Check your deployment anytime:
`GET /api/deployment-version → identity.stable_across_redeploy`.

**Recommended setup:**
```
ADMIN_PASSWORD=<strong-password-16+chars>
SECRET_KEY=<strong-secret-32+chars>
```

---

## 1. Quick Start (Railway, no edge)

1. **Deploy on Railway:**
   - Click "Deploy on Railway" button in README, OR
   - Manual: `railway.app → New Project → Deploy from GitHub repo → select EMIXPI/EMIX-PRO`

2. **Generate a domain:**
   - Railway → Settings → Networking → Generate Domain
   - Sets `RAILWAY_PUBLIC_DOMAIN` automatically

3. **(Optional) Attach a persistent volume:**
   - Railway → Settings → Volumes → Add Volume → mount at `/data`
   - Without this, state is lost on every redeploy

4. **Set environment variables:**
   ```
   ADMIN_PASSWORD=<strong-password-16+chars>
   SECRET_KEY=<strong-secret-32+chars>
   ```

5. **Open dashboard:**
   - `https://<your-app>.up.railway.app/dashboard`
   - Login with `ADMIN_PASSWORD`

---

## 2. With Cloudflare Worker Edge (recommended for Iran users)

The existing `cf_gateway_worker.js` (v1.5.0) provides:
- Multi-location gateway (auto / de / nl / fr / tr / etc.)
- KV namespace `EMIX_LOCATIONS` for dynamic location management
- WebSocket passthrough (required for VLESS-WS / Trojan-WS)
- Admin token `EMIX_TOKEN`
- `/admin/locations` (token-authed)
- `/gateway-status`

### Setup
1. Deploy `cf_gateway_worker.js` to a Cloudflare Workers account.
2. Bind the KV namespace `EMIX_LOCATIONS`.
3. Set `EMIX_TOKEN` (worker secret).
4. (Optional) Add `EMIX_REVERSE_PROXY_ENABLED=0` on Railway (not needed — CF Worker handles routing).
5. (Recommended) Set `EMIX_TRUSTED_EDGES=cloudflare.com,*.workers.dev` on Railway.
6. (Optional) Set `EMIX_ORIGIN_AUTH_SECRET=<32-byte-secret>` on Railway AND configure the CF Worker to send `X-EMIX-Origin-Signature` + `X-EMIX-Origin-Timestamp`.

---

## 3. With ArvanCloud Edge (alternative)

See `docs/ARVANCLOUD.md` for full setup. Summary:

1. Configure DNS in ArvanCloud pointing to Railway origin.
2. Enable CDN proxy on the A/AAAA/CNAME record.
3. Set `EMIX_TRUSTED_EDGES=arvancloud.com,*.arvancloud.com` on Railway.
4. (Optional) Set `EMIX_ORIGIN_AUTH_SECRET` + configure ArvanCloud to send HMAC signature headers.
5. EMIX auto-applies `Cache-Control: no-store` on all tunnel/auth paths (Phase 36).

**UNVERIFIED:** ArvanCloud-specific behavior. Admins MUST validate against their own ArvanCloud dashboard.

---

## 4. Environment Variables Reference

### Required for production
| Env | Default | Purpose |
|---|---|---|
| `ADMIN_PASSWORD` | `123456` | Admin login password (CHANGE THIS) |
| `SECRET_KEY` | random | Internal secret (set explicitly for persistence across redeploys) |
| `RAILWAY_PUBLIC_DOMAIN` | auto-set by Railway | Public domain (auto-detected if unset) |

### Optional — security
| Env | Default | Purpose |
|---|---|---|
| `EMIX_CORS_ORIGINS` | unset (= `*` without credentials) | Comma-separated allowed origins |
| `EMIX_TRUSTED_EDGES` | unset | Trusted CDN/edge hostnames (globs allowed) |
| `EMIX_ORIGIN_AUTH_SECRET` | unset | HMAC secret for edge → EMIX authentication |
| `EMIX_PROXY_ALLOW_PRIVATE` | `0` | Allow private IPs in /proxy (SSRF protection bypass) |
| `EMIX_MIN_TLS_VERSION` | `1.2` | Minimum TLS version for upstream connections |

### Optional — reverse proxy (off by default)
| Env | Default | Purpose |
|---|---|---|
| `EMIX_REVERSE_PROXY_ENABLED` | `0` | Enable reverse-proxy subsystem |
| `EMIX_REVERSE_PROXY_ROUTES_JSON` | unset | JSON array of routes |
| `EMIX_CACHE_SAFETY` | `1` | Apply no-store headers on tunnel paths |

### Optional — performance tuning
| Env | Default | Purpose |
|---|---|---|
| `EMIX_SESSION_TTL` | `604800` (7 days) | Session expiry |
| `EMIX_SESSION_CLEANUP_INTERVAL` | `3600` (1 hour) | Cleanup loop interval |
| `EMIX_SAVE_DEBOUNCE` | `2.0` | State save debounce (seconds) |
| `EMIX_HOURLY_RETENTION` | `72` | Hourly-traffic retention (hours) |
| `EMIX_XHTTP_SEQ_BUF_MAX_MB` | `4` | xHTTP packet-up buffer cap |
| `EMIX_NODE_TIMEOUT` | `10.0` | Node request timeout |
| `EMIX_NODE_MAX_RETRIES` | `2` | Node circuit breaker retries |
| `EMIX_NODE_FAILURE_THRESHOLD` | `3` | Circuit breaker threshold |
| `EMIX_NODE_COOLDOWN` | `30` | Circuit breaker cooldown |
| `EMIX_PROXY_MAX_BYTES` | `50MB` | Max proxy response size |

### Optional — experimental (opt-in)
| Env | Default | Purpose |
|---|---|---|
| `EMIX_EXPERIMENTAL` | `1` (auto-enabled) | Enable experimental section |
| `EMIX_ENABLE_PBKDF2_PASSWORD` | `0` | Use PBKDF2 instead of sha256 for password hash |
| `EMIX_ENABLE_RATE_LIMIT` | `0` | Enable rate-limit middleware |
| `EMIX_ENABLE_CSRF_PROTECTION` | `0` | Enable CSRF protection (POST requires token) |
| `EMIX_ENABLE_CSP_HEADERS` | `0` | Enable Content-Security-Policy headers |
| `EMIX_ENABLE_HSTS` | `1` | Enable Strict-Transport-Security |

---

## 5. Railway Healthcheck

EMIX exposes `GET /api/ping` — returns 200 OK with no auth required. This is the Railway healthcheck endpoint (configured in `railway.toml`).

Other health endpoints:
- `GET /health` — same as /api/ping
- `GET /api/health` (authed) — structured internal health (Phase 17)
- `GET /api/protocols/{name}/health` (authed) — per-protocol rolling health
- `GET /api/edge/upstreams/health` (authed) — reverse-proxy upstream health

---

## 6. Graceful Shutdown

On `SIGTERM` / `SIGINT` (Railway sends SIGTERM on redeploy):
1. Cancel session cleanup task
2. Cancel reverse-proxy health-check task (if running)
3. Flush state to disk (`save_state()`)
4. Stop all MTProto processes (`mtproto.stop_all()`)
5. Close httpx client
6. Bounded shutdown timeout (no abrupt connection termination unless deadline reached)

---

## 7. Persistent Storage

**Without a Railway volume:**
- State is lost on every redeploy
- Default configs are recreated (3 default links: vless-ws, trojan-ws, shadowsocks)
- Custom links + subs + nodes are lost
- Password hash resets to default

**With a Railway volume at `/data`:**
- State persists across redeploys
- Password hash + custom links survive
- MTProto instances restart with same ports (if TCP proxy still exists)

**Recommended:** Attach a 1GB volume at `/data` for production.

---

## 8. Scaling Considerations

**Single worker is correct.** EMIX uses in-memory state for LINKS/SUBS/NODES/SESSIONS. Multi-worker would create inconsistent state.

If you need higher throughput:
1. Use the reverse-proxy subsystem to load-balance across multiple EMIX instances (each with its own Railway service)
2. Each instance has its own in-memory state — only the LINKS/SUBS in JSON are synced via shared volume (advanced pattern — not for typical deployments)
3. For typical deployments (≤1000 links, ≤100 concurrent users), single-instance is sufficient

---

## 9. Logging

EMIX uses Python `logging` at INFO level by default. Logs include:
- Startup/shutdown events
- Session cleanup prunes
- Hourly-traffic pruning
- Protocol registration
- Background task status
- (Optional) Activity logs via `log_activity()` — stored in deque(maxlen=200)

**Never logged:**
- Passwords (plaintext or hash)
- UUIDs of links (only first 8 chars in logs)
- Auth tokens / cookies
- Private keys

Set `EMIX_DISABLE_LOGGING=1` to suppress all logs (for high-throughput deployments).

---

## 10. Backup & Restore

- `GET /api/backup/export` (authed) — downloads `rvg-backup-YYYYMMDD-HHMMSS.json`
- `POST /api/backup/import` (authed) — strict schema validation (Phase 3.9):
  - VALIDATE → STAGE → BACKUP CURRENT → APPLY → VERIFY → COMMIT
  - Auto-rollback on apply or verify failure
  - Pre-restore snapshot at `rvg_state.pre-restore.json`

**Backup format** includes: links, subs, node_keys, nodes, password_hash (sha256 only — non-sha256 silently ignored), schema_version.

---

## 11. Monitoring

| Endpoint | Auth | Returns |
|---|---|---|
| `GET /api/ping` | no | OK (Railway healthcheck) |
| `GET /api/deployment-version` | no | Version + features summary |
| `GET /api/health` | yes | Structured internal health (Phase 17) |
| `GET /api/protocols` | yes | All 19 adapters + capabilities + metrics |
| `GET /api/protocols/selector/rank?profile=stable` | yes | Smart-selector ranked list |
| `GET /api/protocols/selector/best?profile=stable` | yes | Single best protocol |
| `GET /api/nodes/health` | yes | Node circuit-breaker states |
| `GET /api/edge/upstreams/health` | yes | Reverse-proxy upstream health |
| `GET /stats` | yes | Aggregate stats + hourly traffic + recent errors |

---

## 12. Troubleshooting

See `docs/TROUBLESHOOTING.md`.
