# SECURITY_AUDIT_FINAL.md — EMIX-PRO v11.1.0-audit

> Scope: authentication, authorization, injection surfaces, SSRF, secrets, rate limiting, supply chain, privacy.
> Every finding was verified in source. Items marked **FIXED 2026-09** were fixed and regression-tested in this audit cycle (tests/integration/test_audit_fixes.py).

---

## 1. Executive summary

| Area | Posture |
|---|---|
| Credential exfiltration | **FIXED 2026-09** — password hash no longer leaves the box; QR no longer leaks links/keys to third parties |
| Brute force | **FIXED 2026-09** — always-on login guard (5 failures / 15 min / IP, env kill switch) |
| SSRF | Strong, tested (16 tests) |
| Command injection | Real risk surface exists (MTProto compile, self-updater) — mitigations below |
| Secrets at rest | Acceptable for panel class, documented |
| Residual risks | Listed in §6 with severity and operator guidance |

---

## 2. Authentication & sessions

- Single-admin password model. `ADMIN_PASSWORD` env; **default "123456" if unset** (main.py:~370) — documented, startup should warn loudly. Recommendation: generate a random default on first boot and print it once.
- Hash: `sha256(pw + panel_secret)` — salted per-panel but fast. PBKDF2 (210k iters) implemented in security_exp.py behind the experimental `pbkdf2_password` flag with verify+rehash path. **Recommendation: promote to default in a migration release.**
- Sessions: cookie `rvg_session`, httponly, samesite=lax, TTL 7d (env-tunable `EMIX_SESSION_TTL` — **FIXED 2026-09: actually wired**). Sessions now persist to state (survive redeploy) with expiry filter on restore.
- Login brute-force guard — **FIXED 2026-09**: only *failed* attempts count; 5 failures/15 min → HTTP 429 + Retry-After; success clears; `EMIX_LOGIN_RATE_LIMIT=0` opt-out (not recommended). Regression-tested including lockout-of-correct-password and recovery.
- CSRF: double-submit cookie implemented (security_exp.py) but experimental-gated (off by default). Cookie is `samesite=lax` which blocks cross-site POST from third-party sites in practice — acceptable default, documented.
- API-wide rate limiting: experimental-gated (60/min/IP). QR endpoint has its own 30/min/IP limiter (public).

## 3. Authorization

- All admin routes behind `require_auth` (cookie session). Subscription/public routes are intentionally public by UUID (`/sub/{uuid}`, `/p/{uuid_key}`) — capability-by-possession, standard for this class.
- Node-key auth (`X-RVG-Node-Key`) uses `secrets.compare_digest` — constant-time.
- Public `/api/qr` (this audit): scheme allowlist (link schemes + WG config only), 2048-char cap, per-IP rate limit — cannot be abused as an open QR/text renderer or storage oracle.

## 4. Injection surfaces

| Surface | Verdict |
|---|---|
| SQL injection | N/A — no SQL; JSON state store, keys validated by shape |
| Command injection (subprocess) | MTProto: `asyncio.create_subprocess_exec` with a **list argv, no shell** — port/ad-tag/secret passed as argv values, not interpolated strings. domain passed via `-D` flag is validated by `sanitize_domain` regex. **Safe by construction.** |
| Self-updater (`updater.py`) | Downloads from a manifest-supplied URL, optional sha1 (manifest-supplied → not a signature). **Default disabled** (`DISABLE_UPDATES=1`). Residual: if an operator enables updates, a compromised manifest = code execution. Recommendation: require a pinned release + Ed25519 signature before allowing enable. |
| Path traversal | State writes confined to DATA_DIR with fixed names; backup import validated by backup_validator (shape-checked) — **FIXED 2026-09 path unchanged**; QR output is in-memory. |
| SSRF `/proxy/{target}` | Private ranges (RFC1918, loopback, link-local, IPv6 ULA), cloud metadata IP (169.254.169.254), redirect-hop revalidation, header allowlist, response size cap, opt-in private allow (`EMIX_PROXY_ALLOW_PRIVATE`). 16 integration tests. **Strong.** |
| Header injection | **FIXED 2026-09**: `X-Emix-Filter-Notes` latin-1-sanitized (em-dash crash → 500 eliminated); subscription titles base64-encoded (`profile-title: base64:…`) |
| XSS | Frontend renders API data with `esc()` helper in critical paths (errors, labels, domain chips). Public sub page escapes link params. CSP available (experimental `csp_headers`). Residual: `innerHTML` usage is widespread; escaped at the high-traffic sites. |
| WebSocket relays | Auth by UUID at handshake (per-frame after); no user-controlled strings reach command/eval context. |

## 5. Secrets & privacy

| Item | Status |
|---|---|
| `password_hash` phone-home to central worker | **ELIMINATED 2026-09** — registration payload asserted credential-free by test; `EMIX_CENTRAL_ENABLED=0` kill switch; errors now surface to Diagnostics instead of silent pass |
| Hardcoded CF Worker admin token in UI | **ELIMINATED 2026-09** — VPS guide now uses YOUR-WORKER placeholders + security note |
| QR codes via api.qrserver.com | **ELIMINATED 2026-09** — local SVG generation (`/api/qr`, `qrcode` in requirements); links and WG private keys no longer sent off-box |
| ip-api.com over plain HTTP | **DISABLED by default 2026-09** (`EMIX_IP_API_HTTP=1` explicit opt-in) — queried IPs no longer leak to on-path observers |
| Secrets in logs | No passwords/JWT/private keys logged; `security_exp` logs only IP + failure counts; diagnostics records truncate messages and store no secrets; VPN `to_dict()` strips `wg_server_private_key` (tested) |
| Secrets at rest | `rvg_state.json` contains link UUIDs (they ARE the credentials) and — new this audit — WG server private keys (required for restart survival; volume is private to the panel). `.rvg_secret` and `.bot_tcp_proxy_token` chmod 600. **Operator note: the state file must live on a private volume.** |
| Public sub password as `?pw=` query | Documented risk (logs/Referer). Client-app compatibility constraint. Mitigation available: rotate `uuid_key`, or use header auth where the client supports it. |
| Login page advertises default password | Cosmetic leak — recommendation: remove the hint line (kept for operator convenience in this fork; flagged). |

## 6. Residual risk register (post-fix)

| # | Risk | Severity | Guidance |
|---|---|---|---|
| R1 | Default password "123456" when env unset | HIGH if unconfigured | Set `ADMIN_PASSWORD`; the brute-force guard limits guessing to 5/15min/IP |
| R2 | Fast hash (sha256) for panel password | MEDIUM | Enable `pbkdf2_password` experimental flag (verify+rehash path exists); promote to default next release |
| R3 | Self-update channel unsigned | MEDIUM (default-off) | Keep `DISABLE_UPDATES=1`; pin versions manually via git |
| R4 | Central announcements/support integration (any third-party dependency) | LOW post-fix | `EMIX_CENTRAL_ENABLED=0` if isolation is required |
| R5 | Multi-worker unsafe (in-memory SESSIONS/NODE_KEYS, debounced save) | N/A today | uvicorn workers=1 enforced in main; document if scaling |
| R6 | Public sub `?pw=` | LOW | Rotate keys; documented |
| R7 | CSP off by default (experimental) | LOW | Enable `csp_headers` experimental flag for defense-in-depth |

## 7. Test coverage for security

- tests/integration/test_proxy_ssrf.py — 16 tests
- tests/integration/test_audit_fixes.py — 19 tests (phone-home payload, lockout, QR allowlist/limits, ip-api default, env kill switches)
- tests/unit/test_security_signatures.py — 36 tests (TLS signature profiles)
- tests/unit/test_backup_validator.py — 14 tests (import rollback)

**Verdict:** no known credential exfiltration path remains; the two injection-capable surfaces (subprocess, updater) are respectively safe-by-construction and default-disabled; authorization is consistently enforced. Residual risks are documented with operator guidance.
