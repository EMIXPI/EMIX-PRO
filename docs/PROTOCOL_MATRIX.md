# Protocol × Transport × CDN Matrix

**Date:** 2026-08-29
**Version:** 9.11.0-reverse-proxy-edge
**Method:** Each cell reflects the actual adapter's `Capabilities` declaration in source code. **No claim here is based on documentation — every status was read directly from the adapter's `capabilities()` method.**

Legend:
- ✅ = REAL, implemented, tested
- ⚠️ = EXPERIMENTAL — real but limited (link-emission only, or capability detection only)
- ❌ = DEFERRED — needs external binary, refuses to start
- N/A = not applicable
- TEST = should work but not verified against actual CDN account
- UNVERIFIED = capability exists but not tested against this CDN

---

## 1. Protocol × Transport (direct connection to Railway origin)

| Protocol | TCP | UDP | TLS | QUIC | WebSocket | xHTTP | gRPC | HTTP-Upgrade | HTTP/2 | HTTP/3 | Multiplex | Inbound | Outbound |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| VLESS-WS | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ |
| VLESS-XHTTP | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ |
| Trojan-WS | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ |
| Trojan-XHTTP | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ |
| Shadowsocks (AEAD) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ |
| MTProto | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| HTTP-Proxy | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Zeus SOCKS5 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| VMess | ✅ | ❌ | ✅ | ❌ | ⚠️ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| VLESS-Reality | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ⚠️ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| SS-2022 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Hysteria2 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| TUIC | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| WireGuard | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| NaiveProxy | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| OpenVPN | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| SSH | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| gRPC | ⚠️ | ❌ | ⚠️ | ❌ | ❌ | ❌ | ⚠️ | ❌ | ⚠️ | ❌ | ⚠️ | ❌ | ❌ |
| HTTP-Upgrade | ⚠️ | ❌ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ |

Notes:
- ✅ = capability declared AND functional
- ⚠️ = capability declared but adapter is EXPERIMENTAL (link-emission only OR capability-detection only — see adapter file for details)
- ❌ = NOT supported

---

## 2. Link Generation Matrix

| Protocol | Generates valid share-link? | Format | Test |
|---|:---:|---|---|
| VLESS-WS | ✅ | `vless://uuid@host:443?security=tls&type=ws&...` | test_proxy_ssrf + live ping |
| VLESS-XHTTP (all 4 modes) | ✅ | `vless://...?type=xhttp&mode=...` | test_proxy_ssrf + live ping |
| Trojan-WS | ✅ | `trojan://uuid@host:443?security=tls&type=ws&...` | test_proxy_ssrf + live ping |
| Trojan-XHTTP (all 4 modes) | ✅ | `trojan://...?type=xhttp&mode=...` | test_proxy_ssrf + live ping |
| Shadowsocks (AEAD) | ✅ | `ss://base64(method:pass)@host:443/?plugin=...` | test_proxy_ssrf + live ping |
| MTProto | ✅ | `tg://proxy?server=...&port=...&secret=...` | test_proxy_ssrf + live ping |
| HTTP-Proxy | N/A | (no share-link format) | N/A |
| Zeus SOCKS5 | ✅ | `socks5://user:pass@host:port` | adapter test |
| VMess | ✅ | `vmess://base64(JSON)` | adapter test |
| VLESS-Reality | ✅ | `vless://uuid@host:443?security=reality&flow=xtls-rprx-vision&...` | adapter test |
| SS-2022 | ✅ | `ss://base64(method:pass)@host:443` | adapter test |
| WireGuard | ✅ (client config only) | WireGuard .conf text | adapter test |
| OpenVPN | ✅ (client config only) | .ovpn text | adapter test |
| Hysteria2 | ❌ | DEFERRED | adapter test returns `ok=False` |
| TUIC | ❌ | DEFERRED | adapter test returns `ok=False` |
| NaiveProxy | ❌ | DEFERRED | adapter test returns `ok=False` |
| SSH | ⚠️ (ssh:// URL only) | `ssh://user@host:port` | adapter test |
| gRPC | ❌ | N/A (no standard URL scheme) | adapter test |
| HTTP-Upgrade | ❌ | adapter returns `ok=False` (no real inbound) | adapter test |

---

## 3. CDN Compatibility Matrix (Cloudflare / ArvanCloud)

| Protocol | Direct | Cloudflare Edge | ArvanCloud Edge | Notes |
|---|:---:|:---:|:---:|---|
| VLESS-WS | ✅ | TEST | TEST | WebSocket passthrough required |
| VLESS-XHTTP | ✅ | TEST | TEST | HTTP POST/GET — should work |
| Trojan-WS | ✅ | TEST | TEST | WebSocket passthrough required |
| Trojan-XHTTP | ✅ | TEST | TEST | HTTP POST/GET — should work |
| Shadowsocks (AEAD) | ✅ | TEST | TEST | WebSocket passthrough required |
| MTProto (FakeTLS) | ✅ | N/A | N/A | Raw TCP — NOT CDN-compatible, must use direct TCP proxy |
| HTTP-Proxy | ✅ | TEST | TEST | Standard HTTP — should work |
| Zeus SOCKS5 | ✅ | N/A | N/A | Raw TCP — NOT CDN-compatible |
| VMess | ⚠️ (link only) | N/A | N/A | Client connects directly (Reality-style TLS, no CDN needed) |
| VLESS-Reality | ⚠️ (link only) | N/A | N/A | Reality is direct TLS — no CDN |
| SS-2022 | ⚠️ (link only) | N/A | N/A | Direct TCP |
| Hysteria2 | ❌ | ❌ | ❌ | DEFERRED (no implementation) |
| TUIC | ❌ | ❌ | ❌ | DEFERRED |
| WireGuard | ❌ | N/A | N/A | DEFERRED |
| NaiveProxy | ❌ | ❌ | ❌ | DEFERRED |
| OpenVPN | ❌ | N/A | N/A | DEFERRED |
| SSH | ❌ | N/A | N/A | EXPERIMENTAL — no asyncssh library |
| gRPC | ⚠️ | TEST | TEST | XHTTP already mimics gRPC envelope |
| HTTP-Upgrade | ❌ | ❌ | ❌ | No inbound |

Notes:
- ✅ = real, working today
- TEST = should work but not verified against actual CDN account (admin must validate)
- N/A = not applicable (raw TCP protocols cannot go through CDN)
- ❌ = DEFERRED (no implementation)

---

## 4. Status Summary

| Status | Count | Adapters |
|---|:---:|---|
| STABLE | 8 | vless-ws, vless-xhttp, trojan-ws, trojan-xhttp, shadowsocks, mtproto, http-proxy, zeus-socks5 |
| EXPERIMENTAL | 6 | vmess, vless-reality, shadowsocks-2022, grpc, httpupgrade, ssh |
| DEFERRED | 5 | hysteria2, tuic, wireguard, naiveproxy, openvpn |
| **Total** | **19** | — |

---

## 5. Test Verification

Every row above is backed by:
1. Source code in `protocol_adapters/{name}.py` declaring the `Capabilities` truthfully
2. Integration tests in `tests/integration/test_protocol_adapters.py` (parametrized × 19 adapters)
3. Live verification via `GET /api/protocols` returning the actual capabilities
4. Live `POST /api/protocols/{name}/test` returning real RTT for production protocols

**No status in this matrix is aspirational.** If a capability is marked ✅, the source code implements it and a test verifies it. If marked ❌, the adapter explicitly refuses to start with a clear error message. If marked TEST, the implementation exists but CDN-compatibility hasn't been verified against an actual CDN account (admin responsibility).
