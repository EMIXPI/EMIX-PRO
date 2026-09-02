# EGRESS_ENGINE_FINAL.md — egress_engine.py v1.0.0 (Phase 38 / P0+P6)
# EMIX-PRO v11.3.0-network

> The single source of truth for every egress/route/role claim in EMIX.
> Born from the CRITICAL PRODUCTION DEFECT fix (v11.2.0-egress) and extended
> in Phase 38 with PROTOCOL_HEALTH (P6).

## 1. The defect it fixed (production evidence, 2026)

```
Selected node      : Railway — Amsterdam
Configured custom IP: 185.164.73.192
Actual egress       : 208.77.244.84  (Railway, Amsterdam)
```

Therefore, enforced in code and tests:
- `CUSTOM_IP != REAL_EGRESS_IP`
- `SNI != ROUTING` · `HOSTNAME != ROUTING` · `TLS_SERVER_NAME != ROUTING`

## 2. Taxonomies (public contract — UI + tests consume these)

| Set | Values |
|---|---|
| NODE_ROLES | CONTROL_PLANE / EXIT_NODE / RELAY_NODE / EDGE_NODE / HYBRID |
| EGRESS_CLASSIFICATIONS | VERIFIED_EGRESS / CONFIGURED_ONLY / UNKNOWN |
| ROUTE_STATUSES | DIRECT / RELAY / VERIFIED / UNKNOWN |
| ROUTE_HEALTH_STATES | HEALTHY / ROUTE_MISMATCH / NO_EXIT_NODE_AVAILABLE / DEGRADED / UNREACHABLE / UNKNOWN |
| HEALTH_LAYERS (P6, Phase 38) | APPLICATION / NODE / ROUTE / **PROTOCOL** / EGRESS |
| LATENCY_MEASURES | control_plane_rtt / node_rtt / route_rtt / protocol_handshake_rtt |

Phase 38 addition: **PROTOCOL_HEALTH** — derived from the live protocol
registry × compat.READINESS: production protocols serving ⇒ HEALTHY; only
BETA serving ⇒ DEGRADED; none ⇒ UNKNOWN. A healthy API still says nothing
about VPN egress health — the layers stay separate.

## 3. Role derivation (physical reality, not labels)

```
kind=panel                          → CONTROL_PLANE
upstream is a Railway host         → RELAY_NODE  (terminates at control plane)
worker terminates tunnel (WTE)     → EDGE_NODE   (CF colo egress)
upstream is a real non-Railway srv → EXIT_NODE   (verify to prove)
```
Railway is **CONTROL_PLANE** — it can never masquerade as an arbitrary-country
exit (test: `Railway-masquerade prevention`).

## 4. Evidence lifecycle

- Every verification stores `EgressEvidence`: public_ip, ASN, ISP, country,
  region, city, ip_family, timestamp, measurement_source, error.
- TTL 300s: expired evidence degrades to UNKNOWN — a configured IP never
  silently "becomes" the verified egress again.
- `classify_egress()` returns VERIFIED_EGRESS only for fresh ok evidence;
  a configured upstream is returned as `configured_address` with an explicit
  note — **never** as `public_ip`.

## 5. The 9-step route validation (`validate_route`)

1 resolve endpoint → 2 connect to node → 3 verify node → 4 verify route →
5 verify actual egress → 6 compare expected vs observed → 7 measure labeled
latency → 8 store evidence → 9 assign health state.

- Expected country without a real exit node ⇒ **NO_EXIT_NODE_AVAILABLE**.
- Expected ≠ observed ⇒ **ROUTE_MISMATCH** (never HEALTHY).
- No measurement ⇒ **UNKNOWN** (never marked healthy).

## 6. Phase 38 deltas

- `HEALTH_LAYERS` + `egress_health_layers()` now include PROTOCOL_HEALTH.
- Consumed by the new `route_engine.py` (P0) and `failover_engine.py` (P1) —
  both treat this module as the single source of truth and never re-probe.
- `diagnostics_overview()` (P7) now includes the health layers + route history
  tail under `checks.egress`.

## 7. API (admin-auth)

| Endpoint | Purpose |
|---|---|
| `GET /api/egress/summary` | roles + classifications + control plane + exit nodes |
| `GET /api/egress/verify?target=` | measure + classify (panel/worker/loc) |
| `GET /api/egress/routes` | route inventory |
| `POST /api/egress/validate-route` | 9-step pipeline |
| `GET /api/egress/health` | health layers + formula + route history |

## 8. Evidence

- 28 unit tests (tests/unit/test_egress_engine.py) + 17 integration semantics
  tests (tests/integration/test_egress_semantics.py) — includes E2E
  CLIENT→CONTROL_PLANE→EXIT_NODE→INTERNET→EGRESS VERIFICATION with injected
  providers.
- Production gate: real boot, `/api/egress/summary|routes|health` 200
  (38/38 smoke PASS); worker topology from the real deployed worker.
- Cloudflare Anycast / Railway host classification guards shared with the
  domestic engine (never Iranian egress).
