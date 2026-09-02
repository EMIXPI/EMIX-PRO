# UNIFIED CONFIG BUILDER — FINAL

**Version:** v11.4.0-builder · **Modules:** `config_builder.py` + `capability_engine.py` · **UI:** ✨ ساخت کانفیگ (pg-builder) · **API:** `/api/config-builder/*`

---

## 1. The canonical request (spec §7)

```
ConfigRequest
 ↓ capability validation      (capability_engine — protocol/transport/security × node × deployment × client)
 ↓ node endpoint resolution   (panel host / worker loc / managed node address)
 ↓ Endpoint Profile           (endpoint_profiles — the ONLY endpoint/TLS engine; preset id or custom)
 ↓ Routing Policy validation  (domestic presets; IRAN_DIRECT needs split-capable client; IRAN_PROXY needs a gateway)
 ↓ credential validation      (compiler — UUID/SS/MTProto secret formats; auto-generation on generate only)
 ↓ ConfigCompiler             (config_compiler.compile_config — THE emitter; this module never builds URIs)
 ↓ ValidatedConfig            (uri + xray_json + subscription + split rules)
 ↓ Client Output              (QR stays LOCAL via /api/qr; copy client-side)
 ↓ History entry              (bounded 200; server-side; masked in list; revealed in authed view)
```

**One compiler, no second emitter.** `config_builder.py` contains ZERO protocol-URI string assembly — every output originates from `config_compiler` (the same emitter behind `/api/links`, subscriptions, accounts, and the boost layer).

## 2. Validation BEFORE generation (spec §19)

Invalid input → explicit reason + failing stage; **nothing is generated**:

| Stage | Rejects |
|---|---|
| `capability` | unsupported protocol/transport/security on the selected deployment; unknown client format; unregistered node |
| `node` | panel host unknown; node without public address; worker domain not configured |
| `endpoint` | invalid address/port/SNI; unknown endpoint profile |
| `routing` | unknown policy; `SPLIT_TUNNEL_NOT_SUPPORTED` (IRAN_DIRECT/INTERNATIONAL_VPN with a non-split client); IRAN_PROXY without a configured gateway |
| `compiler` | credential format errors; endpoint semantic errors (compiler pipeline) |

Verified by tests: invalid combos → 422 with reasons; IRAN_DIRECT+uri → SPLIT_TUNNEL_NOT_SUPPORTED; IRAN_PROXY without gateway → explicit error.

## 3. Preview (spec §20) — from the same canonical compiler

`POST /api/config-builder/preview`: same pipeline, no history write, no credential invention (a labeled placeholder UUID covers format validation — `credential_placeholder: true`). The preview carries the explainable routing detail (per-leg decision + egress attribution + gateway verdict + split-rule summary). **No frontend-only fake preview exists.**

## 4. Outputs (spec §18)

| Output | Client formats | Notes |
|---|---|---|
| Share URI | uri / subscription | vless:// trojan:// ss:// tg:// from the compiler |
| Xray client JSON | xray-json | routing rules with GEOIP:ir / CIDR direct (or blackhole) outbounds from the verified dataset |
| Subscription body | subscription | base64 of the URI (`config_compiler.subscription_document`) |
| Split-tunnel rules | xray-json / sing-box | compiled by the domestic engine; NOT_SUPPORTED clients get an explicit refusal, never a look-alike config |
| QR | all | rendered LOCALLY by `/api/qr` (scheme allowlist, 2048 cap, rate-limited) — credentials never leave the panel |
| Copy | all | client-side clipboard |

WireGuard `.conf` / OpenVPN `.ovpn` file emission lives in VPN Pro (real emitters, control-plane-only on Railway) — they appear in the builder only when a UDP-capable node exists (none today → hidden, capability-driven). The QR implementation remains local; no third-party QR service.

## 5. History — کانفیگ‌های ساخته‌شده (spec §21)

- Bounded (200 entries) store in `rvg_state.json` (`config_builder` key) — server-side, same trust domain as LINKS uuid storage.
- Each entry: name, protocol/transport/security/node/endpoint-profile/routing/client-format, timestamp, status, checksum, full spec, generated URI.
- **Masking discipline:** list responses mask credentials (`<set>`) and omit the URI; the URI + credential are revealed ONLY in the authed `?reveal=1` view action. Structured events never carry credentials (central scrubbing + UUID redaction).
- Actions: **View/Copy** (reveal → URI + QR), **Regenerate** (re-compile from the stored spec — deterministic: same credential → identical URI → identical checksum, asserted by tests), **Delete**.
- Optional ownership: `account_id` / `subscription_id` fields + `?account_id=` list filter (accounts-engine linkage).

## 6. Capability-driven UI (spec §5-§6, §24)

The frontend renders ONLY from `GET /api/config-builder/capabilities`:
- **Protocol chips** — PRODUCTION selectable; BETA/EXPERIMENTAL shown disabled with readiness labels.
- **Node cards** — from the live node catalogue (panel + worker locations + managed nodes) with role, state, TCP/UDP/TLS truth and egress evidence badges (VERIFIED/CONFIGURED/UNKNOWN).
- **Transport chips** — filtered by the selected node's per-combo statuses; unavailable combos listed with reasons (e.g. gRPC = envelope mimicry).
- **Smart field visibility (§24):** VLESS+XHTTP shows xhttp settings; SS hides UUID/xhttp/grpc fields; WireGuard fields appear only on a real UDP node; IRAN_DIRECT auto-requires a split-capable client format.
- **Routing cards** — legs + egress + requirements; IRAN_PROXY card shows the live gateway state.
- Nothing about protocol support is hardcoded in JavaScript (source-level test asserts the API dependency).

## 7. Status

| Capability | Status |
|---|---|
| Canonical ConfigRequest + pipeline | VERIFIED |
| Validation-before-generation with stage-labeled rejections | VERIFIED |
| Preview from the canonical compiler | VERIFIED |
| History lifecycle (mask/reveal/regenerate-deterministic/delete/bound) | VERIFIED |
| Events (CONFIG_GENERATED / ROUTE_SELECTED / PROTOCOL_VALIDATION_FAILED / SPLIT_TUNNEL_COMPILED) | VERIFIED |
| Auth on every endpoint (401) | VERIFIED |
| Frontend pages + JS (node --check; markers in served HTML) | VERIFIED |
| Real client compatibility of generated configs | NOT_TESTABLE in CI (real client needed) |
