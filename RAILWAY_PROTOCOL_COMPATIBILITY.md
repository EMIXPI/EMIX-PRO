# RAILWAY PROTOCOL COMPATIBILITY

**Version:** v11.4.0-builder · **Module:** `capability_engine.py` · **Live endpoints:** `GET /api/config-builder/capabilities`, `GET /api/railway/validation-matrix`

---

## 1. The four Railway layers (never conflated)

| Layer | Meaning | What it carries |
|---|---|---|
| `RAILWAY_EDGE` | the public HTTP(S) edge in front of the app | WebSocket + XHTTP upgrade requests over TLS |
| `RAILWAY_DEPLOYMENT` | the app runtime itself (this FastAPI process) | in-process vless/trojan/ss relays + mtproto subprocesses |
| `RAILWAY_OUTBOUND` | egress via Railway's network | what external IP providers observe (measured, TTL 300s) |
| `ACTUAL_EGRESS` | the measured exit | **VERIFIED only via egress_engine evidence — never inferred from a Railway region label** |

**Rule (spec §4):** Railway is a deployment environment, not a protocol layer. Protocol support derives from the actual network path and runtime — nothing else.

## 2. Priority order (what the panel actually serves, in order)

| # | Protocol | Transport | Security | Runtime | Status |
|---|---|---|---|---|---|
| 1 | VLESS | xhttp-packet-up | tls | in-panel relay | VALID (PRODUCTION) |
| 2 | VLESS | xhttp-stream-up | tls | in-panel relay | VALID (PRODUCTION) |
| 3 | Trojan | xhttp-packet-up | tls | in-panel relay | VALID (PRODUCTION) |
| 4 | Trojan | xhttp-stream-up | tls | in-panel relay | VALID (PRODUCTION) |
| 5 | VLESS | ws | tls | in-panel relay | VALID (PRODUCTION) |
| 6 | Trojan | ws | tls | in-panel relay | VALID (PRODUCTION) |
| 7 | Shadowsocks | ws | tls | in-panel relay (AEAD, v2ray-plugin) | VALID (PRODUCTION) |
| 8 | MTProto | tcp | none (FakeTLS in-secret) | real mtg subprocess via **Railway TCP Proxy** | VALID (PRODUCTION) |

Compatibility transports where actually supported: `ws`/`xhttp` over TLS — yes (HTTP-layer, VERIFIED). `grpc` — **EXPERIMENTAL: XHTTP mimics the gRPC envelope only (content-type application/grpc) — no real gRPC transport**. `httpupgrade` — NOT_IMPLEMENTED (no inbound). Raw TCP (vless/trojan/tcp, ss/tcp) — EXPERIMENTAL link emission only; no raw-TCP inbound on the HTTP deployment (MTProto is the exception via the TCP-proxy path).

## 3. UDP policy (absolute)

- **The Railway deployment provides NO usable public UDP.** `DEPLOYMENT_MODEL["panel"]["udp"] == "NOT_PROVIDED"`.
- The Cloudflare Worker (WTE) provides TCP via `cloudflare:sockets connect()`; UDP is **DNS-only** (DoH, port 53) — `udp == "DNS_ONLY"`.
- Therefore: **WireGuard / OpenVPN-UDP / Hysteria / Hysteria2 / TUIC / AmneziaWG are NEVER exposed as Railway-native.** `validate_request_combination` returns `UNSUPPORTED` with the reason `UDP-dependent protocol — deployment provides no usable public UDP`. They may exist only on a real UDP-capable node with verified support (none exists today — the UI hides them accordingly, driven by the capabilities API).
- The exit-node package (`exit_node/server.js`) is TCP-only by construction (`cmd!==0x01 closes`).

## 4. Validation matrix (spec §25 — honest stages)

`GET /api/railway/validation-matrix` evaluates, per combo, at request time:

| Stage | Evidence source | Honesty |
|---|---|---|
| `CONFIG_VALID` | a REAL `config_compiler.compile_config()` executed for a representative spec | real evidence |
| `RUNTIME_STARTED` | relays: always-on route registry (wired live from main); mtproto: live subprocess instance count | real |
| `LISTENER_REACHABLE` | the tunnel route paths exist in the running app | real |
| `CLIENT_CONNECTED` | — | `NOT_TESTABLE_WITHOUT_REAL_CLIENT` (never PASS) |
| `REAL_TRAFFIC_CONFIRMED` | — | `NOT_TESTABLE_WITHOUT_REAL_CLIENT` |
| `RECONNECT_CONFIRMED` | — | `NOT_TESTABLE_WITHOUT_REAL_CLIENT` |

**Final status vocabulary:** `IMPLEMENTED_RUNTIME_VERIFIED_IN_PROCESS` (config+runtime+listener real in-process; real-client stages not tested) · `CONFIG_VALID_RUNTIME_CONDITIONAL` (mtproto — per-link instances) · `CONFIG_VALID_ONLY` · `FAILED` · `UNSUPPORTED`.

> A unit-test-only result is NOT real protocol verification. No combo is labeled `VERIFIED` without measured client+traffic evidence.

## 5. Worker (WTE) compatibility

- VLESS over WS terminates INSIDE the Cloudflare Worker (`/vl` path) — egress = the executing colo, measured by `/egress-test` (4 chained IP providers) → `VERIFIED_EGRESS` evidence with TTL.
- Tunnel mode (`/loc/{name}/…`) proxies the upstream panel through the worker — the panel's protocol surface rides through HTTP-layer passthrough.
- **Anycast ≠ geography.** The executing colo is the egress — never inferred from hostname or worker domain.

## 6. Backward compatibility

All v11.3 endpoints/behaviors unchanged; the matrix is additive. The create-link modal continues to gate on `/api/config-matrix` (compat SSoT); the new builder gates on `/api/config-builder/capabilities` (superset: adds node/deployment/client/routing dimensions on top of the same compat SSoT).
