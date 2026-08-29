# EMIX-PRO Troubleshooting

**Version:** 9.11.0-reverse-proxy-edge

---

## 1. Login Issues

### "Wrong password" after redeploy
**Cause:** State directory `/data` is not persistent — password_hash resets to default `sha256("123456" + secret)` after every redeploy.
**Fix:**
1. Attach a Railway volume at `/data`.
2. OR set `ADMIN_PASSWORD` env var explicitly.

### Login returns 200 with empty body
**Cause (historical):** Auto-enabled `csrf_protection` middleware consumed login response body. FIXED in commit `61aa7ef` — CSRF is now opt-in.
**Fix:** Make sure `EMIX_ENABLE_CSRF_PROTECTION` is NOT set to `1` (default = off).

### Login works but immediately logs out
**Cause:** Session TTL expired or session cleanup task aggressive.
**Fix:** Set `EMIX_SESSION_TTL=604800` (7 days, default) and `EMIX_SESSION_CLEANUP_INTERVAL=3600` (1 hour, default).

---

## 2. Protocol Issues

### VLESS-WS / Trojan-WS not pinging
**Cause:** Cloudflare/edge WebSocket upgrade headers not forwarded.
**Fix:**
1. Verify edge CDN allows WebSocket passthrough.
2. Verify `Upgrade` + `Connection` headers reach EMIX.
3. Check `/api/protocols/vless-ws/test` returns `ok=true`.

### Shadowsocks ping fails with "AEAD decrypt"
**Cause (historical):** Default SS config had empty password. FIXED in commit `ae575e2`.
**Fix:** Recreate the SS link (delete + create new one) — the new default has a generated password.

### MTProto instance not running
**Cause:** Railway TCP proxy not attached (no saved Railway token).
**Fix:**
1. Open Dashboard → Bot TCP Proxy section.
2. Enter Railway API token.
3. EMIX will auto-create TCP proxies for each MTProto instance.

### XHTTP packet-up fails with "seq_buf overflow"
**Cause:** A client is sending packets out of order with high seq numbers, exceeding the 4MB buffer cap (Phase 2.7).
**Fix:** This is by design — the connection is torn down to prevent memory exhaustion. Update the client to a newer version that sends packets in order.

---

## 3. CDN / Edge Issues

### Cache poisoning (subscription URL cached)
**Cause:** CDN cached `/sub/{uuid}` (contains UUID + traffic info — credentials!).
**Fix:**
1. EMIX auto-sends `Cache-Control: no-store` on `/sub/*` (Phase 36 middleware).
2. Verify your CDN respects `CDN-Cache-Control` and `Surrogate-Control` headers.
3. Add explicit cache-bypass rule on CDN for `/sub/*`, `/sub-all`, `/p/*`, `/api/login`, `/api/links/*`.

### WebSocket disconnects every 60s through CDN
**Cause:** CDN idle timeout too low.
**Fix:** Increase CDN WebSocket idle timeout to ≥300s.

### Wrong client IP in logs
**Cause:** X-Forwarded-For from non-trusted source (Phase 37 protection).
**Fix:** Add your CDN to `EMIX_TRUSTED_EDGES` env var.

### Origin auth fails (401 unauthorized origin)
**Cause:** HMAC signature mismatch or timestamp outside replay window.
**Fix:**
1. Verify `EMIX_ORIGIN_AUTH_SECRET` matches the edge-side secret.
2. Verify edge clocks are synced (±60s window).
3. Verify edge sends both `X-EMIX-Origin-Signature` and `X-EMIX-Origin-Timestamp` headers.
4. Use `POST /api/edge/origin/test` to generate a test signature for comparison.

---

## 4. Reverse Proxy Issues

### `/api/edge/*` returns 401
**Cause:** All `/api/edge/*` endpoints require admin session cookie.
**Fix:** Login first via `POST /api/login`, then use the returned cookie.

### All upstreams unhealthy (503)
**Cause:** Circuit breaker is OPEN for all upstreams in a route.
**Fix:**
1. Check `GET /api/edge/upstreams/health` for state.
2. Wait for cooldown (30s default).
3. Verify upstream URLs are reachable from EMIX.
4. Increase `EMIX_NODE_FAILURE_THRESHOLD` if too aggressive.

### Reverse proxy not routing
**Cause:** `EMIX_REVERSE_PROXY_ENABLED=0` or routes JSON malformed.
**Fix:**
1. Set `EMIX_REVERSE_PROXY_ENABLED=1`.
2. Verify `EMIX_REVERSE_PROXY_ROUTES_JSON` parses as valid JSON.
3. Check `GET /api/edge/config` returns the configured routes.
4. Force-reload via `POST /api/edge/reload`.

---

## 5. Persistence Issues

### Configs disappear after redeploy
**Cause:** No Railway volume attached at `/data`.
**Fix:**
1. Railway → Settings → Volumes → Add Volume → mount at `/data`.
2. Redeploy.

### State file corrupted
**Cause:** Crash mid-write (rare — atomic write + debounce protects against this).
**Fix:**
1. Restore from `rvg_state.pre-restore.json` (auto-backup before restore).
2. OR restore from a manual `GET /api/backup/export` snapshot.
3. If no backup: EMIX will recreate 3 default configs on next startup.

### JSON parse error on load
**Cause:** State file was written by a newer version with incompatible schema.
**Fix:** EMIX's `load_state()` has a backward-compat shim — only sha256-format password hashes are accepted. Other fields are preserved. If the file is truly corrupted, delete it and EMIX will recreate defaults.

---

## 6. Performance Issues

### High CPU usage
**Cause:** Likely the smart-selector is scoring too many protocols.
**Fix:**
1. Disable DEFERRED protocols via `POST /api/protocols/{name}/disable`.
2. Reduce `EMIX_SESSION_CLEANUP_INTERVAL` (less frequent cleanup).
3. Disable logging via `EMIX_DISABLE_LOGGING=1`.

### High memory usage
**Cause:** Likely `hourly_traffic` accumulating (Phase 1.3 — fixed) or `seq_buf` unbounded (Phase 2.7 — fixed).
**Fix:**
1. Verify `EMIX_HOURLY_RETENTION=72` (default — prunes after 72 hours).
2. Verify `EMIX_XHTTP_SEQ_BUF_MAX_MB=4` (default — tears down sessions exceeding 4MB).
3. Check `GET /api/health` for `state_counts` (links, sessions, active_connections).

### Slow dashboard load
**Cause:** `pages.py` is 9952 lines (~560KB HTML) — large initial payload.
**Fix:**
1. Use a CDN edge cache for `/dashboard` (read-only page, safe to cache).
2. Verify `Cache-Control` headers on `/dashboard` are not `no-store` (only tunnel paths are no-store).

---

## 7. Security Issues

### CORS preflight fails
**Cause:** `EMIX_CORS_ORIGINS` not set.
**Fix:** Set `EMIX_CORS_ORIGINS=https://your-domain.example.com,https://another.example.com`.

### SSRF attack attempts on /proxy
**Cause:** External attackers probing `/proxy/{target_url}` for internal services.
**Fix:** Already protected — Phase 7.14 rejects loopback, private, link-local, metadata endpoints. Verify with `GET /proxy/localhost` → should return 403.

### Suspicious activity in logs
**Cause:** Failed login attempts, rate-limit triggers.
**Fix:**
1. Set `EMIX_ENABLE_RATE_LIMIT=1` to enable rate-limiting.
2. Check `GET /api/activity` for activity log.
3. Rotate `ADMIN_PASSWORD` + `SECRET_KEY` if compromised.

---

## 8. Diagnostic Endpoints

| Endpoint | Auth | What it tells you |
|---|---|---|
| `GET /api/ping` | no | Service is up |
| `GET /api/deployment-version` | no | Version + features summary |
| `GET /api/health` | yes | Structured internal health |
| `GET /api/protocols` | yes | All 19 adapters + capabilities |
| `GET /api/protocols/{name}/health` | yes | Per-protocol rolling metrics |
| `GET /api/protocols/selector/rank?profile=stable` | yes | Smart-selector ranked list |
| `GET /api/nodes/health` | yes | Node circuit-breaker states |
| `GET /api/edge/upstreams/health` | yes | Reverse-proxy upstream health |
| `GET /stats` | yes | Aggregate stats + recent errors |
| `GET /api/connections` | yes | Live connections |

---

## 9. Getting Help

1. Check this document first.
2. Check `docs/ARCHITECTURE.md` for system design.
3. Check `docs/PROTOCOL_MATRIX.md` for protocol support.
4. Check `AUDIT_REPORT.md` for known issues + fixes.
5. Run the test suite: `pytest tests/ -v` — should be 218 passing.
6. Check Railway deployment logs for startup errors.
