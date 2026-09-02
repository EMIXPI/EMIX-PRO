# ROUTE & EGRESS ARCHITECTURE — FINAL

**Version:** v11.4.0-builder · **Modules:** `route_engine.py`, `egress_engine.py`, `domestic_route_engine.py`, `iran_gateway.py`, `failover_engine.py` · **v11.2.0-egress + v11.3.0-network remain the foundation — this document covers the v11.4.0 extensions.**

---

## 1. The truth chain (unchanged, restated)

```
CONFIGURED_EGRESS  —  what the operator typed (address, upstream, country label)
        ≠
OBSERVED_EGRESS    —  what a measurement saw (IP/ASN/ISP/geo, timestamped, TTL)
        ≠
VERIFIED_EGRESS    —  fresh measurement matching the expectation
```

- Configured values are surfaced ONLY as `configured_address` / `configured_note` — **never** as `public_ip`.
- `ROUTE_MISMATCH` (expected ≠ observed) is announced — structured event + history — never masked as healthy.
- `UNKNOWN` is `UNKNOWN`. Nothing unmeasured is healthy.

## 2. Routing policies (v11.4.0 — extended vocabulary)

`ROUTE_POLICIES = (ALL_VPN, IRAN_DIRECT, IRAN_PROXY, INTERNATIONAL_VVPN, CUSTOM)`

Every routing decision is **explainable** (spec §11): destination → resolved IP → classification → selected policy → selected node → VPN bypassed or used → egress expectation → observed egress (when measurable) → confidence → final verdict. The Config Builder preview exposes this per leg; `/api/domestic/test-route` exposes it per destination; `/api/egress/validate-route` runs the 9-step pipeline.

### IRAN_PROXY egress attribution (new)

For Iranian destinations under IRAN_PROXY: `egress = IRAN_GATEWAY` with the live gateway verdict embedded:
- `VERIFIED_IRAN_EGRESS` — gateway with fresh measured egress in IR.
- `NO_VERIFIED_IRAN_GATEWAY` + warning — gateway configured but unverified/unhealthy. The route is never silently degraded to a fake "Iranian exit".
- `ROUTE_MISMATCH` — measured gateway egress outside IR.
- `IRAN_GATEWAY_UNCONFIGURED` — no gateway at all (builder refuses to generate IRAN_PROXY configs in this state).

### INTERNATIONAL_VVPN BLOCK leg (new)

Iranian destinations are REFUSED (`decision = BLOCK`, `egress = NONE`) — domestic traffic never enters the tunnel. Split-tunnel compilation emits blackhole rules (GEOIP:ir + CIDR) for capable clients; incapable clients get `SPLIT_TUNNEL_NOT_SUPPORTED`.

## 3. Failover capability gates (new — spec §15)

`select_replacement` now enforces HARD gates before scoring:
- `protocol` requirement: node must serve it, else skipped (UNSUPPORTED_NODE_PROTOCOL).
- `transport` requirement: node's decomposed capabilities must carry it, else skipped (UNSUPPORTED_NODE_TRANSPORT).
- `role: EXIT_NODE` requirement: only nodes with valid egress evidence are eligible (NO_VERIFIED_EGRESS).

**A health/latency score can never override capability reality** — an incompatible node is never selected. The 7-step pipeline (drain → select → verify health → verify route → verify egress → re-point → resume) and 10-factor explainable scoring are unchanged from v11.3; failed failover still leaves the node drained (no blind failback). `FAILOVER_TRIGGERED` structured event emitted on every run.

## 4. Health layers (v11.3 + events)

`APPLICATION / NODE / ROUTE / PROTOCOL / EGRESS` layers unchanged. New: `EGRESS_VERIFIED` / `ROUTE_MISMATCH` / `NODE_QUARANTINED` structured events at the exact truth points. Health still expires (`STALE` → re-verification); fresh configs get a born-UNKNOWN record synchronously (race fix — never born HEALTHY, never 404 mid-probe).

## 5. Status

| Capability | Status |
|---|---|
| Egress evidence/classification/mismatch (v11.2) | VERIFIED (28 unit + 17 integration) |
| Route registry, explainability, inventory sync (v11.3) | VERIFIED |
| IRAN_PROXY attribution + gateway verdicts (v11.4) | VERIFIED |
| INTERNATIONAL_VVPN BLOCK leg + blackhole rules | VERIFIED |
| Failover capability gates (protocol/transport/egress) | VERIFIED |
| Structured truth events | VERIFIED |
| Real-network e2e through a real gateway/exit node | NOT_TESTABLE in CI (needs real servers) |
