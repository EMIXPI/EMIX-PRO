# ACCOUNT_DEVICE_FINAL.md — account_manager.py v1.0.0 (Phase 38 / P2+P3)

---

## v11.4.0-builder update — config ownership linkage
The Unified Config Builder completes the chain with config ownership:
`ConfigRequest.account_id / subscription_id` are stored on every history
entry (کانفیگ‌های ساخته‌شده) and the history list supports `?account_id=`
filtering. All engine semantics (PBKDF2, one-time device tokens, limits,
can_connect gate, subscription lifecycle, canonical-compiler emission) are
unchanged from v11.3. The full object chain is now:
Account → Subscription → Device → Config (history) → Protocol → Transport →
Endpoint Profile → Routing Policy → Node → Egress → Verification.

# EMIX-PRO v11.3.0-network

> Account → Subscription → Config → Route → Node → Verified Egress.
> Device → Session. All limits enforced BACKEND-side — never only in UI.

## 1. Entities

| Entity | Fields (essentials) |
|---|---|
| Account | id, username, password_hash (PBKDF2-SHA256), status (ACTIVE/DISABLED), expires_at, traffic_quota_bytes, used_bytes, max_devices, max_concurrent_sessions, max_subscriptions |
| Subscription | subscription_id, account_id, profile, protocol, transport, route_policy (ALL_VPN/IRAN_DIRECT/CUSTOM), node_policy (auto/pinned), quota_bytes, expires_at, status (ACTIVE/EXPIRED/REVOKED/SUSPENDED/DRAINING), link_ids |
| Device | device_id, account_id, name, platform, client_metadata (capped 256), token_hash (SHA-256), last_seen, connection_state, revoked |
| ClientSession | session_id, account_id, device_id, node_id, started_at, last_seen, bytes_in/out, active |

Subscription statuses match the spec exactly:
`ACTIVE / EXPIRED / REVOKED / SUSPENDED / DRAINING` (DRAINING = quota
exhausted: existing connections continue, new ones blocked).

## 2. Security rules (all tested)

- **Passwords**: PBKDF2-SHA256, per-account random salt, 120,000 iterations,
  constant-time verification. Hashes are never serialized to API responses.
- **Device tokens**: `secrets.token_urlsafe(24)`, returned EXACTLY ONCE at
  registration, stored only as SHA-256 hash, never logged (test:
  `test_audit_never_contains_token_or_password`).
- **Disable cascade**: disabling an account kills its live sessions
  immediately (backend-enforced).
- **Revocation cascade**: revoking a device kills its sessions and invalidates
  its token.
- Minimal PII: email optional; no unnecessary sensitive data stored.
- All endpoints admin-auth gated (`Depends(require_auth)`); smoke gate
  verified unauthenticated access ⇒ 401.

## 3. Backend-enforced limits

| Limit | Default | Enforcement point |
|---|---|---|
| MAX_DEVICES | 5 (per-account overridable) | `register_device()` — `DEVICE_LIMIT_REACHED` (revoked devices free their slots) |
| MAX_CONCURRENT_SESSIONS | 3 | `open_session()` — `SESSION_LIMIT_REACHED` |
| MAX_SUBSCRIPTIONS | 10 | `create_subscription()` — `SUBSCRIPTION_LIMIT_REACHED` |
| Traffic quota (account + subscription) | configurable | `track_usage()` + connection gate |
| Expiry (account + subscription) | configurable | sweep job + connection gate |

## 4. The connection gate (single source of truth)

`can_connect(account_id, device_id?, subscription_id?)` → verdict + honest reason:

```
ALLOWED | ACCOUNT_UNKNOWN | ACCOUNT_DISABLED | ACCOUNT_EXPIRED |
QUOTA_EXCEEDED | DEVICE_UNKNOWN | DEVICE_REVOKED | SESSION_LIMIT_REACHED |
SUBSCRIPTION_UNKNOWN | SUBSCRIPTION_EXPIRED | SUBSCRIPTION_REVOKED |
SUBSCRIPTION_SUSPENDED
```

Exposed at `GET /api/connect/authorize` (used by E2E tests; exit nodes /
workers can consume the same verdict).

## 5. Subscription → config emission (no duplicate logic)

`compile_subscription_configs()` routes every link through the injected
compile function — wired in `main._wire_phase38_engines()` to
`config_compiler.compile_from_link`. If the compiler is not wired, the
response says `CONFIG_COMPILER_NOT_WIRED` instead of inventing URIs
(test: `test_subscription_compilation_requires_unified_compiler`).

## 6. Background jobs (bounded)

- `account-sweep` (300s): `reconcile_subscription_statuses()` (expiry →
  EXPIRED; quota → DRAINING) + `sweep_stale_sessions()` (1h idle → closed).
- Audit events bounded (200); history preserved across restarts via
  `persist_snapshot()`/`restore_snapshot()` in rvg_state.json
  (`account_manager` key — additive; old state files load unchanged).

## 7. API (admin-auth)

```
GET/POST /api/accounts
GET  /api/accounts/summary
GET  /api/accounts/{id}                      (+ devices + subscriptions + sessions)
POST /api/accounts/{id}/status?status=
POST /api/accounts/{id}/devices              → {device, access_token(once)}
POST /api/accounts/{id}/subscriptions
GET  /api/accounts/{id}/subscriptions
POST /api/devices/{id}/revoke | /rename
POST /api/subscriptions/{id}/status?status=
GET  /api/connect/authorize?account_id=&device_id=&subscription_id=
```

## 8. Frontend (pages.py — pg-accounts)

Honest cards: quota usage %, expiry + EXPIRED chips, device list with
connection state + revoke, subscription rows with status/policy chips,
one-time token display with "never logged" warning. All data from the real
API; nothing hardcoded.

## 9. Evidence

- 32 unit tests (tests/unit/test_account_manager.py): hashing, gates, limits,
  cascades, reconciliation, persistence round-trip, audit hygiene.
- E2E flows 1/9/10 (account→device→subscription→route→verified egress;
  expired subscription rejected; revoked device rejected).
- Smoke: create/get/disable account 200; unauthorized 401; persistence
  round-trip via rvg_state.json.
