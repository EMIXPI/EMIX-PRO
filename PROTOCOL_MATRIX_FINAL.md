# PROTOCOL_MATRIX_FINAL.md — EMIX-PRO v11.1.0-audit

> Per-protocol capability truth. Source of truth: adapters themselves (protocol_adapters/ + protocol/ runtimes) as introspected by /api/protocols and the protocol registry; statuses cross-checked against compat.READINESS.
> Client-compatibility notes included (a protocol is not production because the server starts — §34 of the master spec).

## 1. Matrix

| | VLESS | Trojan | Shadowsocks | MTProto | VMess | VLESS-Reality | SS-2022 | WireGuard | OpenVPN | SOCKS5 | HTTP-Proxy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Status** | PRODUCTION | PRODUCTION | PRODUCTION | PRODUCTION | BETA | BETA | BETA | BETA (control-plane) | BETA (control-plane) | PRODUCTION | PRODUCTION |
| **Runtime in EMIX** | in-process relay (ws/xhttp) | in-process relay (ws/xhttp) | in-process relay (ws) | subprocess (official MTProxy) | none | none | none | none | none | in-process server | outbound probe |
| **Server config** | n/a (relay is the server) | n/a | n/a | generated + supervised | URI emit | xray JSON emit | URI emit | WG conf + keygen (X25519) | .ovpn with embedded certs | n/a | n/a |
| **Client config / link** | ✅ compiler | ✅ compiler | ✅ compiler | ✅ tg:// link + secret | ✅ base64-JSON URI | ✅ URI (needs real pbk) | ✅ URI | ✅ client conf + QR (local, audit fix) | ✅ .ovpn + QR (local) | n/a | n/a |
| **start/stop/restart** | route-bound (always on) | route-bound | route-bound | ✅ supervised subprocess + backoff | ❌ | ❌ | ❌ | ❌ (control-plane) | ❌ | module-managed | n/a |
| **health_check** | ✅ REAL probe | ✅ REAL probe | ✅ REAL probe | ✅ real process state | NOT_TESTABLE (honest) | NOT_TESTABLE | NOT_TESTABLE | NOT_TESTABLE | NOT_TESTABLE | state introspection | ✅ REAL outbound probe |
| **latency measure** | ✅ ws_ms + e2e_ms per probe | ✅ | ✅ | connections/queries only | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **traffic accounting** | ✅ EWMA batch, both directions | ✅ | ✅ | connections/queries (no byte counters — honest) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **handshake verification** | ✅ VLESS header + response read | ✅ | ✅ | process watcher | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | TLS cert |
| **Subscription** | ✅ all profiles | ✅ | ✅ | ✅ | ✅ (via sub-all) | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **QR** | ✅ local /api/qr | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Device mgmt** | by-IP connections only (no device entity) | same | same | psutil listing | ❌ | ❌ | ❌ | client list (control-plane) | client list | ❌ | ❌ |
| **IPv4 / IPv6** | IPv4-first egress (Errno-101 fix), IPv6 dual-stack listen | same | same | IPv6→IPv4 fallback | n/a | n/a | n/a | n/a | n/a | ✅ | ✅ |
| **UDP** | ❌ (TCP egress only — DNS UDP handled by worker path, documented) | ❌ | ❌ | ❌ | n/a | n/a | n/a | ✅ (conf emitted; runtime on node) | ✅ (conf emitted) | ❌ | ❌ |
| **Client ecosystems** | v2rayN/NekoBox/Streisand/Shadowrocket/Hiddify | same family | Shadowsocks clients + v2rayN | Telegram native apps | v2rayN/Streisand | v2rayN/Streisand/Hiddify | sing-box family | official WG apps | OpenVPN Connect/Tunnelblick | any SOCKS client | browser/curl |
| **Tests** | relay unit + health 45 + adapters | cache 24 + health | crypto unit + health | subprocess runtime tests | emitter tests | emitter tests | emitter tests | 45 vpn_pro tests | 45 vpn_pro tests | runtime | runtime |

## 2. Deferred protocols (honest)

TUIC (v5/QUIC), Hysteria2 (QUIC), NaiveProxy (HTTP/2), SSH tunneling: adapters exist as honest `DEFERRED` — `validate()` returns False, `start()` returns False, health returns the literal string "no implementation available". They are *enumerated* in the registry for forward-planning and are **never advertised as supported** in UI or matrix.

## 3. Key honest statements

1. A link-only protocol (vmess/reality/ss2022) can be PRODUCTION *as an emitter* but is BETA *as a platform feature* because EMIX hosts no runtime for it — the panel cannot health-check what it does not serve.
2. WireGuard/OpenVPN on Railway are control-plane only (keygen, client config, QR, node registry). The panel never claims to run them; the VPN Pro page carries an explicit "کنترل-پلن" badge (audit fix).
3. MTProto traffic accounting is connections/queries only — the official binary exposes no byte counters; the panel says so in code, UI, and this matrix.
4. Client-side usability was factored into statuses (§34): VLESS/Trojan/SS/MTProto have first-class client ecosystems on Android/iOS/Windows/macOS; that's part of why they are PRODUCTION.
