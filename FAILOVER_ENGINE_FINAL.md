# FAILOVER_ENGINE_FINAL.md — failover_engine.py v1.0.0 (Phase 38 / P1)

---

## v11.4.0-builder update — capability hard gates (spec §15)
`select_replacement` now enforces HARD capability gates BEFORE scoring:
- **protocol requirement** — node must serve the protocol, else skipped (`UNSUPPORTED_NODE_PROTOCOL`);
- **transport requirement** — the node's compat-decomposed capabilities must carry the transport, else skipped (`UNSUPPORTED_NODE_TRANSPORT`);
- **role: EXIT_NODE** — only nodes with valid egress evidence are eligible (`NO_VERIFIED_EGRESS`).

A health/latency score can never override capability reality. `score_node`
additionally reports `UNSUPPORTED_NODE_TRANSPORT` in the ranking reasons.
Every failover run emits the `FAILOVER_TRIGGERED` structured event (node,
reason, protocol, transport). The 7-step pipeline, verdicts, and no-blind-failback
semantics are unchanged. Verified by new unit tests (incompatible nodes are
never selected; compatible nodes are).

# EMIX-PRO v11.3.0-network

> A failover is successful ONLY when the replacement route is actually usable.
> Never fail over blindly. Never report FAILOVER_SUCCESS without a verified path.

## 1. Pipeline (7 steps, event-sourced)

```
1. stop assigning NEW configs/connections   → node DRAINING
2. drain state (existing traffic continues)
3. select replacement     → EXPLAINABLE scoring (ranking_reason[])
4. verify replacement     → node_manager ONLINE (runtime-gated, re-evaluated)
5. verify route           → egress_engine 9-step validation
6. verify egress          → classification must not be UNKNOWN
7. re-point routes + resume → FAILOVER_SUCCESS
```

Verdicts: **FAILOVER_SUCCESS | FAILOVER_FAILED | FAILOVER_NO_REPLACEMENT**.

- A failed failover **keeps the old node drained** — never fails back blindly
  to a bad node.
- The replacement is NOT activated unless the route is usable.

## 2. Node states (node_manager.py, Phase 38 extension)

```
ONLINE · DEGRADED · DRAINING · MAINTENANCE · OFFLINE · QUARANTINED · (REGISTER⊂UNKNOWN)
```

- **DRAINING** — existing traffic continues; `online_nodes()` excludes it (no
  new assignments). Set via `set_draining()`; driven by failover step 1.
- **QUARANTINED** — operator override while egress/behavior is investigated
  (e.g. ROUTE_MISMATCH evidence); survives fresh heartbeats.
- Runtime gate: a draining node whose runtime reports DOWN is OFFLINE (the
  runtime gate beats drain — you cannot drain a corpse).

## 3. Explainable node scoring (pure, unit-tested)

Factors and weights (sum 100): health 25, latency 15, jitter 5, packet loss 10,
load 10, egress quality 15, country match 8, ASN match 4, protocol
compatibility 5, historical stability 3.

Rules:
- Every factor produces a human-readable reason: `+ 42ms latency`,
  `+ VERIFIED egress evidence`, `? latency UNKNOWN`, `- DRAINING (no new
  assignments)`.
- UNKNOWN factors score 0 with an explicit `?` reason — never guessed.
- Country match requires VERIFIED evidence — a label without proof does not
  count (test: `score_country_match_needs_verification`).

Example output (E2E test flow 4):
```
nl-02 selected (score …):
  + ONLINE (runtime-verified)
  ? latency UNKNOWN
  ? packet loss UNKNOWN
  + load 30%
  ? egress UNKNOWN
  ? historical stability UNKNOWN
```

## 4. Wiring (main.py)

- `set_route_repoint_fn` — re-points `route_engine` registry routes from the
  failed node to the replacement (audited in route notes).
- `POST /api/failover/{node_id}?reason=` — operator-triggered failover.
- `GET /api/failover/history|summary` — bounded history (50 records).

## 5. Evidence (tests/unit/test_failover_engine.py, 24 tests + E2E flow 4)

- DRAINING blocks new assignments; undrain restores ONLINE.
- QUARANTINED survives fresh heartbeat; unquarantine restores ONLINE.
- Drained + runtime DOWN ⇒ OFFLINE.
- Scoring: drained/quarantined nodes penalized; latency quality curve; UNKNOWN
  explicit; verified-egress beats unknown; country needs proof; protocol
  compatibility; weights sum to 100.
- Pipeline: unknown node ⇒ FAILOVER_FAILED; no replacement ⇒
  FAILOVER_NO_REPLACEMENT (node stays drained); full success path ⇒
  FAILOVER_SUCCESS with re-pointed routes; unhealthy replacement ⇒ FAILED
  (drain retained); history bounded.

## 6. Known limits (honest)

- Replacement selection currently considers nodes registered in
  `node_manager` (panel/worker/vps/exit kinds). Weighted routing across an
  arbitrary external node fleet requires those nodes to be registered first
  (Node API, Phase 37.9).
- Latency/jitter/loss metrics for scoring are provider-injected; production
  wiring currently supplies control-plane RTT only — other factors report
  UNKNOWN rather than inventing numbers.
