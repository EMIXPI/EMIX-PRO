# ROUTE_ENGINE_FINAL.md — route_engine.py v1.0.0 (Phase 38 / P0)
# EMIX-PRO v11.3.0-network

> Routes are first-class objects. Every route answers: entry? relays? exit?
> expected vs observed? healthy? verified? — with measured evidence only.

## 1. What it is

`route_engine.py` gives the routing model an explicit, inspectable shape:

```
Client → Entry node → [Relay node, …] → Exit node → Internet → Egress
```

Before Phase 38, route data lived only inside per-link dicts in
`gaming_boost._gaming_links`. Now routes are registry objects with identity,
policy, metrics, and an honest health verdict.

## 2. Route object contract

| Field | Type | Honesty rule |
|---|---|---|
| `route_id` | str | stable identity |
| `entry_node` | str | where the client connects |
| `relay_nodes[]` | list | hops between entry and exit |
| `exit_node` | str\|None | **None ⇒ NO_EXIT_NODE_AVAILABLE** (never faked) |
| `expected_country` / `expected_asn` | str\|None | operator/user expectation (Route-level) |
| `observed_country` / `observed_asn` | str\|None | **MEASURED only** — from egress evidence, never configured values |
| `health` | ROUTE_HEALTH_STATES | expected≠observed ⇒ ROUTE_MISMATCH, never masked |
| `latency{}` | labeled measures | control_plane_rtt / node_rtt / route_rtt / protocol_handshake_rtt |
| `packet_loss` / `jitter` | float\|None | None ⇒ UNKNOWN (never invented) |
| `last_verified` | ts\|None | age > 900s ⇒ `stale: true` |
| `verification_state` | VERIFIED_EGRESS / CONFIGURED_ONLY / UNKNOWN | reuses egress_engine taxonomy — one source of truth |
| `route_policy` | ALL_VPN / IRAN_DIRECT / CUSTOM | domestic split-tunnel semantics (P17) |

`to_dict()` additionally exposes `latency_labeled` (each number names what it
measured) and `stale` (health expires — old results are STALE, not green).

## 3. Behavior rules (all unit-tested — tests/unit/test_route_engine.py, 15 tests)

1. **No exit node** → health = `NO_EXIT_NODE_AVAILABLE`, verification = UNKNOWN.
2. **Verified evidence + matching expectation** → HEALTHY + VERIFIED_EGRESS.
3. **Expected Turkey / observed Netherlands** → ROUTE_MISMATCH (spec §P0).
4. **No evidence** → UNKNOWN; `observed_country` stays None — a configured
   address is never reported as an observation.
5. **Expired evidence (TTL 300s)** → degrades to UNKNOWN/CONFIGURED_ONLY.
6. **Metrics providers are injectable**; missing provider ⇒ field stays None
   (labeled UNKNOWN), provider failure ⇒ None (never a fake number).
7. **Registry is bounded** (500 routes; oldest evicted) — no unbounded memory.
8. `sync_inventory()` builds a read-only route view from `egress_engine.worker_topology()` —
   the egress engine remains the single source of truth; route_engine never
   re-probes.

## 4. API (admin-auth, registered from main)

| Endpoint | Purpose |
|---|---|
| `GET /api/routes` | registry routes (or live inventory when empty) + summary |
| `GET /api/routes/summary` | counts by health / verification |
| `GET /api/routes/{route_id}` | one route (404 when unknown) |

## 5. Wiring (main.py)

- `register_routes(app, require_auth)` — bottom bootstrap block, fault-isolated.
- `set_metrics_provider("control_plane_rtt", egress_engine.measure_control_plane_rtt)` —
  wired in `_wire_phase38_engines()` at startup.
- Failover re-pointing: `failover_engine.set_route_repoint_fn` re-points
  registered routes from a failed node to its replacement (audited in route notes).

## 6. What this engine does NOT do

- It does not probe anything itself (evidence comes from egress_engine).
- It does not enforce routing on the data plane — enforcement lives in client
  configs (Config Compiler + split-tunnel rules) and the worker/exit nodes.
- It does not claim DIRECT domestic egress — that attribution
  (`USER_ISP`) belongs to `domestic_route_engine.py`.

## 7. Evidence

- 15 unit tests (`tests/unit/test_route_engine.py`) — classification, mismatch,
  staleness, bounded registry, labeled latency, provider failure semantics.
- Integration: `tests/integration/test_phase38_e2e.py` flows 5–7 (mismatch not
  masked, configured-IP never reported, SNI-invariance).
- Production boot: `GET /api/routes` 200 with live worker-derived inventory
  (38/38 smoke PASS, real uvicorn boot).
