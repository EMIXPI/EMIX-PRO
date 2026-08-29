# EMIX-PRO Protocol Support Matrix

**Last updated:** 2026-08-29
**Version:** 9.10.0-protocol-engine

Every entry below is backed by source code in `protocol_engine/` + `protocol_adapters/`. **No protocol is advertised as functional unless its source code actually implements it.**

---

## STABLE — Production-ready, working today

| Protocol | Transport | TCP | UDP | IPv4 | IPv6 | TLS | Link Gen | Health | Inbound | Adapter File |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| VLESS-WS | WebSocket | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | `protocol_adapters/existing/vless_ws.py` |
| VLESS-XHTTP | xHTTP (4 modes) | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | `protocol_adapters/existing/vless_xhttp.py` |
| Trojan-WS | WebSocket | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | `protocol_adapters/existing/trojan_ws.py` |
| Trojan-XHTTP | xHTTP (4 modes) | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | `protocol_adapters/existing/trojan_xhttp.py` |
| Shadowsocks (AEAD) | WebSocket | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | `protocol_adapters/existing/shadowsocks.py` |
| MTProto | TCP (FakeTLS) | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | `protocol_adapters/existing/mtproto.py` |
| HTTP Proxy | TCP (SSRF-protected) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | `protocol_adapters/existing/http_proxy.py` |
| Zeus SOCKS5 | TCP | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | `protocol_adapters/existing/zeus_socks5.py` |

All STABLE protocols have **zero wire-level changes** from the previous production state — the adapters wrap the existing `protocol/*` implementations.

---

## EXPERIMENTAL — Real implementation, not yet production-grade

| Protocol | What's real | What's missing | Adapter File |
|---|---|---|---|
| VMess | Link emission (base64-JSON share-link) via `link_emit.gen_vmess_link()` | No inbound (would need xray-core binary) | `protocol_adapters/vmess.py` |
| VLESS-Reality | Link emission (XTLS Vision, configurable SNI/pbk/sid/fp) via `link_emit.gen_vless_reality_link()` | No inbound (would need xray-core 1.8+ binary) | `protocol_adapters/vless_reality.py` |
| Shadowsocks-2022 | Link emission (AEAD-2022 ciphers) via `link_emit.gen_ss2022_link()` | No inbound (existing SS-AEAD inbound covers chacha20/aes-256-gcm only) | `protocol_adapters/ss2022.py` |
| gRPC (transport) | Capability detection; existing XHTTP already mimics gRPC wire envelope (`Content-Type: application/grpc`) | Real gRPC needs `grpcio` + `grpcio-tools` + Protocol Buffers schema | `protocol_adapters/grpc_transport.py` |
| HTTP-Upgrade | Capability detection (distinct from WebSocket + XHTTP) | No inbound yet — would need a new FastAPI route accepting `Upgrade:` header | `protocol_adapters/httpupgrade.py` |

These adapters are **truthful** — `Capabilities.status = EXPERIMENTAL`, so the smart selector skips them by default (score = 0). Admin can manually enable + test.

---

## DEFERRED — Real implementation requires external dependency

| Protocol | Why deferred | Path to enable | Adapter File |
|---|---|---|---|
| Hysteria2 | Requires QUIC + official Go binary (`apernet/hysteria`) | Run hysteria-server as a sidecar on a host with UDP egress | `protocol_adapters/hysteria2.py` |
| TUIC v5 | Requires QUIC + official Go binary (`ItsRyanTu/tuic`) | Same as Hysteria2 — external Go binary | `protocol_adapters/tuic.py` |
| WireGuard | Requires kernel module (not on Railway) or `wireguard-go` userspace binary | Client config emission works today; full server requires external host | `protocol_adapters/wireguard.py` |
| NaiveProxy | Requires Chromium-based C++ binary (not Railway-compatible) | Cannot deploy on Railway — would need a dedicated VPS | `protocol_adapters/naiveproxy.py` |
| OpenVPN | Requires `openvpn` binary + root + TUN device (not on Railway) | Client `.ovpn` config emission works today; server requires external host | `protocol_adapters/openvpn.py` |
| SSH | Requires `asyncssh` library (not in requirements.txt) | Add `asyncssh>=2.14` to requirements + implement SSHClientTunnel | `protocol_adapters/ssh.py` |

DEFERRED adapters **refuse to `start()`** and return `LinkResult(ok=False)` with a clear error message. They never pretend to be functional.

---

## NOT IMPLEMENTED — Out of scope

The following protocols were considered but **intentionally NOT implemented** because they lack mature, maintained Python-compatible libraries or would require unsafe custom cryptography:

- **Tor Snowflake** — requires the Tor browser's snowflake binary, not a clean Python library
- **Conjure** — academic protocol, no maintained implementation
- **Custom cryptographic protocols** — never implement crypto from scratch
- **WebTransport / HTTP3** — `aioquic` is experimental; not safe for production
- **mKCP** — requires KCP binary, not maintained in Python
- **Brook, Snell, SOCKS5-over-TLS, DoH/DoT proxy** — niche; would each need their own binary or significant custom code

For these, the `Capabilities` registry simply does not include an entry — they're absent from `/api/protocols`. Protocol count is less important than reliability.

---

## Smart Selector

The smart selector scores enabled protocols by:

```
score = w_reliability * success_rate
      + w_latency    * normalized_latency
      + w_throughput * normalized_throughput
      + w_availability * availability_flag
      + profile_bonus
```

Weights are configurable via env vars (defaults in parens):
- `EMIX_SELECTOR_W_RELIABILITY` (0.40)
- `EMIX_SELECTOR_W_LATENCY` (0.25)
- `EMIX_SELECTOR_W_THROUGHPUT` (0.15)
- `EMIX_SELECTOR_W_AVAILABILITY` (0.20)

Network profiles (preferences, not guarantees):
- `mobile` — prefer TCP/WS, avoid QUIC (UDP may be flaky on mobile)
- `stable` — balanced, no transport preference
- `high_latency` — favor WS/XHTTP (better loss tolerance)
- `udp_friendly` — prefer QUIC/UDP transports
- `restricted` — only protocols with recent successful health check

**No hard-coded "best for X"** — the system measures the actual network.

---

## API Endpoints (all authed via session cookie)

| Method | Path | Description |
|---|---|---|
| GET | `/api/protocols` | List all 19 protocols + capabilities + metrics |
| GET | `/api/protocols/{name}` | Single protocol detail |
| GET | `/api/protocols/{name}/health` | Rolling health metrics (5-min window) |
| POST | `/api/protocols/{name}/test` | Run a health check now |
| POST | `/api/protocols/{name}/enable` | Admin-enable |
| POST | `/api/protocols/{name}/disable` | Admin-disable |
| GET | `/api/protocols/selector/rank?profile=stable` | Rank by smart-selector score |
| GET | `/api/protocols/selector/best?profile=stable` | Single best protocol |
| GET | `/api/protocols/selector/profiles` | List network profiles |
| POST | `/api/protocols/{name}/generate-link` | Generate a share-link |

Never exposes: passwords, hashes, UUIDs of links, auth tokens, cookies, private keys.

---

## Testing

198 tests, all passing:
- 9 unit tests for the registry
- 4 unit tests for capabilities
- 10 unit tests for the smart selector
- 5 unit tests for the fallback chain
- 95 integration tests (parametrized × 19 adapters × 5 invariants each)
- 75 existing regression tests (preserved from prior hardening pass)

Run: `pytest tests/ -v`

---

## Railway Compatibility

The protocol engine is **fully Railway-compatible**:
- No new dependencies added
- No privileged kernel access required
- No persistent disk required
- No Docker-in-Docker required
- No UDP assumption (DEFERRED protocols correctly report this)
- Single-worker (correct — all state is in-process)

Every adapter reports `Capabilities.status` as one of:
- `STABLE` — real, tested, working
- `EXPERIMENTAL` — real but untested in production
- `DEFERRED` — needs external dependency
- `UNAVAILABLE` — not implementable in this environment

A broken optional adapter **never prevents EMIX from starting** — `safe_register` swallows the error.
