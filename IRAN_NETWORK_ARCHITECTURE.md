# IRAN NETWORK ARCHITECTURE

**Version:** v11.5.0-iran-direct · **Modules:** `domestic_route_engine.py`, `iran_gateway.py`, `capability_engine.py`, `iran_direct.py` · **UI:** مسیریابی هوشمند (pg-routing, incl. 🇮🇷 IRAN DIRECT Builder: Clean IP + Handshake) + 🇮🇷 پروکسی ایران (pg-iranproxy) + ساخت کانفیگ routing step

---

## 1. The two Iranian routing modes (fundamentally different)

```
IRAN_DIRECT (client-side split tunneling — no Iranian server needed):
    Client in Iran
        ├── Iranian destination ──► DIRECT ──► user's local ISP (USER_ISP)
        └── International ────────► EMIX VPN ─► Exit node ─► Internet

IRAN_PROXY (server-side route through a REAL Iranian gateway):
    Client → EMIX Entry/Relay → Iran Gateway (real, verified) → Iran Internet
```

| | IRAN_DIRECT | IRAN_PROXY |
|---|---|---|
| Iranian server required | **No** | **Yes — a real gateway** |
| Egress for Iranian destinations | `USER_ISP` (VPN BYPASSED) | `IRAN_GATEWAY` (expected; `VERIFIED_IRAN_EGRESS` only with measured evidence) |
| Enforcement point | client (split-tunnel rules: xray/sing-box) | EMIX route (server-side) |
| Client requirement | split-tunnel-capable client, else `SPLIT_TUNNEL_NOT_SUPPORTED` | none (routing happens in the EMIX route) |
| Without the prerequisite | builder refuses with the client-capability reason | builder refuses: `IRAN_PROXY requires a real Iranian gateway — none is configured` |

## 2. Policy vocabulary (domestic engine presets)

| Policy | iran leg | international leg | unknown leg | Egress attribution |
|---|---|---|---|---|
| `ALL_VPN` | VPN | VPN | VPN | EMIX exit node |
| `IRAN_DIRECT` | DIRECT | VPN | VPN | USER_ISP for Iranian destinations |
| `IRAN_PROXY` | VPN (via gateway) | VPN | VPN | IRAN_GATEWAY for Iranian destinations |
| `INTERNATIONAL_VPN` | **BLOCK** | VPN | VPN | NONE for Iranian destinations (refused — domestic traffic never enters the tunnel) |
| `CUSTOM` | admin-defined | | | per leg |

`INTERNATIONAL_VVPN` compiles blackhole rules for Iranian prefixes (GEOIP:ir + CIDR from the verified dataset) for split-tunnel-capable clients. `IRAN_PROXY` compiles NO client-side domestic rules (server-side routing — honest NOT_APPLICABLE verdict).

## 3. Classification (unchanged from v11.3, restated)

- `IRAN_DOMESTIC` / `NON_IRAN` / `UNKNOWN` decided on the **actual resolved destination IP** (longest-prefix match, 2,528-prefix real RIPEstat dataset, checksummed, atomic daily updates with rollback).
- **Never** by domain suffix. **Never** SNI. **Never** hostname.
- Cloudflare anycast ranges are flagged and can never be classified as Iranian egress. Railway is CONTROL_PLANE — never an Iranian exit.

## 4. Iran Gateway engine (new)

Registry entry: `name, endpoint, port, protocol (http | socks5 | emix-worker | custom), auth (masked, never logged), endpoint_profile_id (optional TLS semantics), enabled, notes` + observed evidence (never configured claims).

**State machine (evidence-based, never optimistic):**

```
UNCONFIGURED → CONFIGURED (registered — NOT verified)
CONFIGURED → REACHABLE (TCP connect ok) → HEALTHY (probe ok)
REACHABLE/HEALTHY + measured egress in IR  → VERIFIED_IRAN_EGRESS
REACHABLE/HEALTHY + measured egress NOT IR → ROUTE_MISMATCH (never masked as Iran)
stale evidence (TTL egress 3600s / reach 600s) → DEGRADED
TCP fail → UNREACHABLE (invalidates egress evidence)
custom protocol → UNSUPPORTED (no probeable egress surface — egress stays UNKNOWN)
```

**Probes (real network evidence):**
- `http`: httpx through the forward proxy → ipapi.co (measured IP + country).
- `socks5`: minimal SOCKS5 CONNECT handshake (no-auth/user-pass) → plain-HTTP IP echo through the tunnel → panel-side geolocation of the MEASURED IP.
- `emix-worker`: the gateway exposes `/exit-check`-style JSON.
- `custom`: reachability only — egress UNKNOWN (honest).

**Truth rules (absolute):** a manually entered Iranian IP is CONFIGURED, never VERIFIED. SNI is never proof. Hostname is never proof. Cloudflare is never proof. Railway region is never proof. Only network evidence establishes Iranian egress. A gateway whose measured egress is outside IR is `ROUTE_MISMATCH` — announced (structured event `IRAN_GATEWAY_CHECK`), never masked.

**Integration:** `domestic_route_engine.set_gateway_status_fn(iran_gateway.iran_proxy_egress_status)` (wired by main) — every IRAN_PROXY decision embeds the live gateway verdict; unverified/unconfigured gateways produce an explicit warning in the routing decision. Periodic re-verification job: `iran-gateway-check` (every 6h + manual "بررسی و اثبات خروج").

## 5. IRAN DIRECT endpoint assets — Clean IP + Handshake builder (v11.5.0)

The user-facing promise: in the IRAN_DIRECT section the operator enters a
**healthy/set Clean IP** (ایپی سالم) and/or a **fake Handshake** (هندشیک —
SNI/Host domain) and then builds & receives a config **exactly like the
unified Config Builder** (ساخت کانفیگ).

**Engine:** `iran_direct.py` — an endpoint-asset store (NOT a config emitter):

```
Clean-IP asset:   {id, address (IP|hostname), port, label, notes,
                   created_at, use_count, last_used_at,
                   last_probe: {state, ms, sni, checked_at, from} | None,
                   verification: CONFIGURED_ENDPOINT}          ← honest label
Handshake asset:  {id, sni (hostname — NEVER an IP), label, notes,
                   created_at, use_count, last_used_at}
Store:            DATA_DIR/iran_direct_assets.json (bounded 100/list)
```

**Config generation flow (canonical — zero new emitters):**

```
pg-routing «🇮🇷 ساخت کانفیگ IRAN_DIRECT» card
  → POST /api/config-builder/preview|generate     (THE canonical API)
      custom_address = Clean IP (or the handshake domain alone)
      custom_sni     = Handshake
      routing_policy = IRAN_DIRECT
  → capability → node → endpoint (endpoint_profiles) → routing →
    compiler → URI + Xray JSON (+ GEOIP:ir/CIDR split rules) → history
```

**Honesty rules (unchanged by this feature):**
- A manual Clean IP is `CONFIGURED_ENDPOINT` — connection address only,
  never verified egress, never a geographic claim.
- The Handshake is TLS/endpoint semantics only (SNI ≠ ROUTE ≠ GEO).
- IRAN_DIRECT egress attribution stays **USER_ISP** — these assets never
  change where domestic traffic exits.
- IP without a handshake is refused (TLS SNI can never be an IP).
- URI/subscription client formats stay refused for IRAN_DIRECT
  (`SPLIT_TUNNEL_NOT_SUPPORTED`) — only split-tunnel-capable clients.
- Server-side probe (`⚡`) measures **from the panel server** and is labeled
  `TCP_REACHABLE` / `TLS_VERIFIED` with the explicit caveat that
  «clean-from-your-ISP» must be measured from the user's own browser.
- Events: `IRAN_DIRECT_ASSET_SAVED`, `IRAN_DIRECT_PROBE` (severity-mapped).

**Canonical validator fix shipped with this phase (endpoint_profiles):**
dotted-quad-shaped strings are now always treated as IPs and must have valid
octets (0-255) — `104.17.1.999` is rejected outright instead of sneaking
through as a "hostname" and emitting an unconnectable config.

## 6. Status

| Capability | Status |
|---|---|
| Classification on real IP with real dataset | VERIFIED (35 tests incl. 13 mandatory P17) |
| IRAN_DIRECT policy + split-tunnel compilation (xray/sing-box; honest NOT_SUPPORTED elsewhere) | VERIFIED |
| IRAN_PROXY policy + gateway attribution (unconfigured/unverified/verified verdicts) | VERIFIED (unit + integration with faked probes) |
| Gateway state machine + probes (http/socks5/emix-worker) | IMPLEMENTED + PARTIALLY_VERIFIED — probe code paths tested with fakes; a real Iranian gateway is needed for a full e2e (NOT_TESTABLE in CI) |
| INTERNATIONAL_VPN BLOCK leg + blackhole rules | VERIFIED |
| Traffic accounting categories | VERIFIED |
| Data-plane enforcement of IRAN_DIRECT | client-capability-dependent (documented; builder refuses incapable clients) |
| Data-plane enforcement of IRAN_PROXY through the gateway | gateway deployment is operator work; egress attribution is expected-vs-VERIFIED (honest) |
| IRAN_DIRECT asset store (Clean IP + Handshake) + CRUD/validation | VERIFIED (17 unit + 5 integration tests) |
| Clean IP + Handshake → canonical IRAN_DIRECT config (URI/Xray JSON/split rules) | VERIFIED (compiler pipeline; real uvicorn smoke) |
| Server-side probe (TCP/TLS with SNI) from panel | VERIFIED (real network in smoke: TLS_VERIFIED, honest caveat) |
| «Clean from the user's ISP» browser-side measurement | NOT_TESTABLE from panel — documented caveat shown in UI |
| IRD UI (capability-driven steps, honest off-chips, shared history filter) | IMPLEMENTED (node --check + served-HTML markers; visual QA pending deploy) |
