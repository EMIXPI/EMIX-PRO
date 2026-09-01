# MIGRATION_GUIDE_FINAL.md — EMIX-PRO v11.1.0-audit

> This release is **additive and non-destructive**. No existing link, subscription, node key, or legacy field is removed. Every change below was verified by round-trip tests (tests/integration/test_audit_fixes.py).

## 1. Upgrade path (v11.0.0-arch → v11.1.0-audit)

Standard git pull + redeploy. On boot, `load_state()`:
1. Backfills `spoof_sni`/`spoof_sni_enabled` defaults if absent (pre-v10 backups).
2. Accepts only sha256-format `password_hash` (PBKDF2-format strings are ignored → fresh hash written; prevents downgrade lockout).
3. Restores — NEW this release, all defensive (corrupt records skipped, never crash boot):
   - `sni_profiles` → SNI Management store
   - `vpn_nodes` → VPN Pro node store **including WireGuard server private keys** (previously lost on every restart)
   - `sessions` → active admin sessions (no forced re-login after redeploy)
   - `stats_totals` → lifetime traffic totals (previously reset to 0)
4. Un-shadowed node-manager API: `GET /api/managed-nodes` (+ `/heartbeat`, `/maintenance`). The legacy `GET /api/nodes` (outbound panels) is untouched — its contract is unchanged.

**Rollback:** revert to the previous commit. The new state keys are simply ignored by the old loader (it reads only what it knows). No schema lock-in.

## 2. New state keys (rvg_state.json)

| Key | Content | Secret? |
|---|---|---|
| sni_profiles | SNI profile list | no (cert fingerprint only) |
| vpn_nodes | VPN nodes + WG server private key | **YES** — keep the volume private |
| sessions | token → expiry (filtered to non-expired on save) | bearer tokens — same class as link UUIDs |
| stats_totals | lifetime bytes/requests/errors | no |

## 3. Behavioral changes (intentional, documented)

| Change | Old behavior | New behavior | Why |
|---|---|---|---|
| Login failures | unlimited attempts | 5 failures/15min/IP → 429 | brute-force guard (opt-out `EMIX_LOGIN_RATE_LIMIT=0`) |
| Central registration | sent password_hash to worker | domain/version only + `EMIX_CENTRAL_ENABLED` kill switch | credential exfiltration removal |
| QR codes | third-party api.qrserver.com | local `/api/qr` SVG | links & WG private keys no longer leave the panel |
| ip-api.com provider | queried over plain HTTP | disabled; opt-in `EMIX_IP_API_HTTP=1` | queried-IP privacy |
| Health sweep | results discarded (copy-dict bug) | persisted to link records + debounced save | subscriptions/rankings keep fresh evidence |
| Background sweep save | — | one debounced save per sweep | write amplification |
| Relay connection close | raw full-state save per close (vless/ss/xhttp) | debounced schedule_save | write amplification |
| MTProto supervision | boot-time instances only | every created/restarted instance supervised | crash coverage |
| Diagnostics page | dead (JS syntax error shipped in v11.0.0-arch) | functional + session-aware | production bug fix |
| Overview widgets | 6 hardcoded "فعال" rows + fake doughnut + dead info-strip | live data from /api/diagnostics + /api/links + /stats | zero-fake-features |
| VPN Pro nav | hidden | visible, labeled "کنترل-پلن" (control-plane only) | honest reachability |
| Version strings | hardcoded v9.5/v9.7 | dynamic from /api/deployment-version | stale-claim removal |
| sub-all-v2 notes header | em-dash crash (HTTP 500) | latin-1-safe | production bug fix |
| uTLS button | 404 (case mismatch) | lowercase alias added | dead-button fix |
| Zeus TLS-Mask save | TypeError (duplicate id) | fixed ids | dead feature fix |

## 4. New environment variables

| Var | Default | Effect |
|---|---|---|
| EMIX_LOGIN_RATE_LIMIT | 1 (on) | 0 disables the login brute-force guard |
| EMIX_CENTRAL_ENABLED | 1 (on) | 0 disables all central-worker communication |
| EMIX_IP_API_HTTP | 0 (off) | 1 re-enables the plaintext-HTTP ip-api.com provider |
| EMIX_SESSION_TTL | 604800 | **now actually read** (was dead documentation) |
| EMIX_SAVE_DEBOUNCE | 2.0 | **now actually read** (was dead documentation) |
| (existing) EMIX_HEALTH_SWEEP_INTERVAL / EMIX_EXPIRY_SWEEP_INTERVAL | unchanged | unchanged |

## 5. Operator actions after upgrade (recommended)

1. Set `ADMIN_PASSWORD` if not already (guard limits guessing, but don't rely on it).
2. Attach a persistent volume at `/data` (warning banner otherwise).
3. `pip install -r requirements.txt` — adds `qrcode` (pure-Python, no Pillow needed; SVG output).
4. If you depended on the central announcements/support chat, verify reachability (errors now appear in Diagnostics Center instead of being swallowed).
5. If your tooling scraped `GET /api/nodes` expecting the node-manager registry (it never worked — shadowed route), point it at `/api/managed-nodes`.

## 6. Data safety guarantees

- Legacy `spoof_sni` fields: untouched; `/api/endpoint-profiles/migrate-legacy` remains opt-in, non-destructive, reversible.
- Existing URIs/subscriptions: byte-identical emission proven by the compiler wire-compat tests (26+ tests, incl. SNI-spoof Mode A/B).
- No destructive migrations exist; all restores skip corrupt records and log warnings.
