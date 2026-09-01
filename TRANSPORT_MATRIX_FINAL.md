# TRANSPORT_MATRIX_FINAL.md — EMIX-PRO v11.1.0-audit

> **Single source of truth:** `compat.py` (`TRANSPORT_MATRIX`, `SERVER_RUNTIME`, `READINESS`, `SNI_APPLICABLE`).
> This document is a *rendering* of that source, not an independent copy — the machine-readable API is `GET /api/config-matrix` (authed), which the frontend create-modal consumes for gating (cmLoadMatrix/cmGateCombo) and the Config Compiler enforces server-side. If this file and compat.py disagree, compat.py wins.

## 1. Legend

- **VALID** — full path works: compiler emits, relay/runtime serves, health probes exist.
- **EXPERIMENTAL** — link emission works (client can connect to a compatible external server) but EMIX hosts no runtime for it, or semantics are partial.
- **NOT_IMPLEMENTED** — refused at generation; honest error.
- **INVALID** — semantically impossible; refused with reason.

## 2. Protocol × Transport × Security matrix (34 combinations)

| Protocol | Transport | TLS | State | Server runtime in EMIX | Notes |
|---|---|---|---|---|---|
| vless | ws | tls | **VALID** | relay (in-process) | flagship; 0-RTT early-data ed=2048 |
| vless | xhttp-packet-up | tls | **VALID** | relay (session engine) | AIMD adaptive flow |
| vless | xhttp-stream-up | tls | **VALID** | relay (session engine) | stream-on removed as uplink (honest) |
| vless | tcp | tls | EXPERIMENTAL | none | link-only; external xray server required |
| vless | tcp | reality | EXPERIMENTAL | none | vless-reality adapter (BETA) |
| vless | grpc | tls | EXPERIMENTAL | none | gRPC *envelope mimicry* only (content-type); health: NOT_TESTABLE, never claimed as real gRPC |
| vless | httpupgrade | tls | NOT_IMPLEMENTED | none | refused |
| vless | ws | none | INVALID | — | WS relay requires TLS in this deployment |
| vless | ws | reality | INVALID | — | Reality is TCP-only semantics |
| vless | xhttp ×2 | none/reality | INVALID | — | same as above (6 combos) |
| trojan | ws | tls | **VALID** | relay | SHA224 auth cache |
| trojan | xhttp-packet-up | tls | **VALID** | relay | — |
| trojan | xhttp-stream-up | tls | **VALID** | relay | — |
| trojan | tcp | tls | EXPERIMENTAL | none | link-only |
| trojan | tcp | reality | EXPERIMENTAL | none | trojan-reality emitter (experimental section) |
| trojan | grpc | tls | NOT_IMPLEMENTED | none | refused |
| trojan | httpupgrade | tls | NOT_IMPLEMENTED | none | refused |
| trojan | ws/xhttp ×2 | none/reality | INVALID | — | 6 combos |
| shadowsocks | ws | tls | **VALID** | relay | real AEAD crypto (HKDF/EVP/ChaCha20/AESGCM) |
| shadowsocks | ws | none | EXPERIMENTAL | none | link-only |
| shadowsocks | tcp | none | EXPERIMENTAL | none | ss2022 emitter (BETA) |
| shadowsocks | grpc | tls | NOT_IMPLEMENTED | none | refused |
| shadowsocks | httpupgrade | tls | NOT_IMPLEMENTED | none | refused |
| mtproto | tcp | none | **VALID** | subprocess (official MTProxy) | FakeTLS at the protocol level, not panel TLS |

Totals: **8 VALID / 7 EXPERIMENTAL / 5 NOT_IMPLEMENTED / 14 INVALID** — matches `compat.TRANSPORT_MATRIX` and `/api/config-matrix` exactly (asserted by 43 unit tests).

## 3. Server runtime registry (`SERVER_RUNTIME`)

| Fused combo | Runtime kind |
|---|---|
| vless-ws, vless-xhttp-packet-up, vless-xhttp-stream-up | in-process relay |
| trojan-ws, trojan-xhttp-packet-up, trojan-xhttp-stream-up | in-process relay |
| shadowsocks-ws | in-process relay |
| mtproto-tcp | supervised subprocess (official binary) |

## 4. Protocol readiness (`READINESS`)

| Tier | Protocols |
|---|---|
| PRODUCTION | vless, trojan, shadowsocks, mtproto |
| BETA | vmess (link emission), vless-reality (config-gen), ss-2022 (config-gen), wireguard (control-plane + keygen), openvpn (control-plane + .ovpn) |
| EXPERIMENTAL | hysteria2, tuic, naiveproxy, ssh (all honest DEFERRED/NOT_TESTABLE) |

## 5. SNI applicability (`SNI_APPLICABLE`)

vless/trojan: `true` (all transports). shadowsocks/ws: `false` (partial support documented — URI keeps params but relay ignores). mtproto: `false` (FakeTLS domain is protocol-internal).

## 6. Enforcement points (one source, many consumers)

| Consumer | How it consumes compat.py |
|---|---|
| Config Compiler | `validate()` in the pipeline — rejects INVALID, refuses NOT_IMPLEMENTED, warns EXPERIMENTAL |
| `/api/config-matrix` | `matrix_view()` JSON — machine-readable |
| Frontend create modal | fetches the matrix; blocks EXPERIMENTAL/NOT_IMPLEMENTED/INVALID with a reason toast; **audit fix: gating degradation is now user-visible** (netErr) — server remains the authority |
| Diagnostics Center | transports summary (valid/experimental/ni/invalid counts) |
| Smart Route / Node Manager | capability filters use the fused combo keys |
| Tests | 43 unit tests pin the matrix — a change to compat.py without updating reality fails CI |

## 7. Known limitations (honest)

- WireGuard/OpenVPN are BETA *control-plane* only — Railway cannot host their runtimes; the UI labels this explicitly (VPN Pro page re-enabled with "کنترل-پلن" badge, audit fix).
- gRPC transport is envelope mimicry (XHTTP sets the content-type) — health_check honestly returns NOT_TESTABLE; never advertised as real gRPC.
- httpupgrade refused rather than half-implemented — per zero-fake-features.
