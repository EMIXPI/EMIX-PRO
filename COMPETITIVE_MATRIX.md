# EMIX-PRO — Competitive Matrix

**Date:** 2026-09-01
**Benchmark set:** vpn-ui, RVG, SpiderPanel, Nyx, Zeus (concept-level study — no proprietary code copied).
**Purpose:** honest gap analysis after the v11 "Architecture Release", with priorities.

Legend: ✅ EMIX advantage · ⚖️ comparable · ❌ competitor advantage · 🚧 planned (this repo's roadmap)

| # | Dimension | EMIX v11 | vpn-ui | SpiderPanel | RVG | Nyx | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Protocol data-plane depth (VLESS/Trojan/SS/XHTTP×4/MTProto/SOCKS5 in-process) | ✅ real relays + AEAD + quota gates | deep (OpenVPN/WG native) | Xray-centric | modular | — | ⚖️ different strengths: EMIX = pure-Python in-process; vpn-ui = kernel/native runtimes |
| 2 | Link-only protocols honesty (VMess/Reality/SS2022) | ✅ BETA-labeled, health = NOT_TESTABLE (this release) | mixed | often claims support | mixed | — | ✅ EMIX never fakes health for link-only protocols |
| 3 | Config Compiler (single deterministic emitter) | ✅ normalize→validate→emit→self-check→checksum (this release) | ⚖️ | ⚖️ | ⚖️ | ⚖️ | ✅ wire-compat proven byte-identical + versioned + fallback-protected |
| 4 | Compatibility matrix (protocol×transport×security) | ✅ declarative `/api/config-matrix` (this release) | partial | partial | partial | — | ✅ frontend can render only valid combos; 400 with reasons otherwise |
| 5 | Endpoint/transport profiles | ✅ Endpoint Profile Engine (this release) + legacy spoof migration | ⚖️ SNI in inbound forms | ⚖️ | ⚖️ | — | ✅ structured profiles + strict compat validation, SNI-Spoof naming retired |
| 6 | Per-config real testing | ✅ protocol-authentic probes (WS/TLS/UUID/egress) + UNKNOWN at birth (this release) | ping-only mostly | ping/TCP | ⚖️ | health-based | ✅ evidence over assumption |
| 7 | Health state machine per config | ✅ HEALTHY/DEGRADED/UNREACHABLE/INVALID/UNKNOWN + score (this release) | ❌ (binary) | ❌ | ❌ | ⚖️ close | ✅ vs most; Nyx comparable conceptually |
| 8 | Weighted smart routing | ✅ 40/20/20/20 formula, hysteresis failover | ❌ | ❌ | ⚖️ | ✅ | ⚖️ Nyx-level; both refuse lowest-ping-only |
| 9 | IP quality classification | ✅ evidence-based CLEAN/GOOD/QUESTIONABLE/DEGRADED/BLOCKED/UNKNOWN + confidence + provider abstraction (this release) | ❌ | ⚖️ "clean IP" lists w/o evidence | ❌ | ⚖️ | ✅ no "100% clean" claims anywhere |
| 10 | Background job system | ✅ retry/timeout/backoff/lock/dedup/observability (this release) | ⚖️ systemd/cron style | ⚖️ | ⚖️ | ⚖️ | ⚖️ |
| 11 | Observability | ✅ structured errors (code/component/severity/request-id), slow-request capture, `/api/diagnostics` + UI page (this release) | ⚖️ | ⚖️ | ❌ | ⚖️ | ✅ single-call system snapshot incl. engines |
| 12 | Subscription engine | ✅ base64+headers+profiles ALL/FASTEST/HEALTHIEST (this release) | ⚖️ | ✅ rich | ⚖️ | ⚖️ | ⚖️ SpiderPanel still richer (per-sub node merging pre-existed here too) |
| 13 | Traffic accounting | ✅ per-relay atomic + hourly aggregation + quota gate | ✅ | ✅ | ✅ | ✅ | ⚖️ table stakes |
| 14 | Device management per account | ❌ MISSING | ✅ | ⚖️ | ⚖️ | ⚖️ | ❌ vpn-ui advantage — 🚧 roadmap item (needs session fingerprints per protocol) |
| 15 | Native WireGuard/AmneziaWG runtime | ❌ config-gen only (no TUN on Railway) | ✅ kernel/native | ❌ | ❌ | ❌ | ❌ vpn-ui advantage (different deployment model) — 🚧 requires VPS node runtime |
| 16 | OpenVPN full lifecycle | ⚖️ config+crypto real, provisioning DEFERRED | ✅ | ❌ | ❌ | ❌ | ❌ partial — 🚧 |
| 17 | Multi-node federation | ✅ snapshot push/pull, circuit breakers, node keys | ⚖️ | ⚖️ | ⚖️ | ✅ | ⚖️ |
| 18 | Failover automation for subscriptions | 🚧 hysteresis engine exists; auto-rewrite of subs not yet wired | ❌ | ❌ | ⚖️ | ✅ | ⚖️ |
| 19 | Deployment resilience (Railway) | ✅ volume checks, atomic JSON, startup recovery, restart-safe | ⚖️ | ✅ Railway-first | ⚖️ | ⚖️ | ⚖️ |
| 20 | Edge/CDN abstraction | ✅ Worker v2.1 (VLESS-in-worker + WTE) + reverse proxy + EdgeProvider-optional design | ⚖️ | ✅ | ❌ | ❌ | ⚖️ SpiderPanel comparable; EMIX core does not depend on CF |
| 21 | Zero-fake-features policy enforcement | ✅ audited + 6 fake-health adapters fixed (this release) | ❌ panels commonly over-claim | ❌ | ❌ | ⚖️ | ✅ measurable, tested |
| 22 | Test suite | ✅ 550 tests (383 pre-existing preserved + 167 new) | ❌ | ❌ | ⚖️ | ❌ | ✅ |
| 23 | UI consistency with backend truth | ⚖️ Diagnostics page added; full Phase-26 wizard-style flow still 🚧 | ✅ mature | ✅ mature | ⚖️ | ✅ | ❌ competitors' UX polish — 🚧 |
| 24 | Worker deployment automation | ❌ manual paste (no CF API client) | ❌ | ⚖️ | ❌ | ❌ | ⚖️ all manual today — 🚧 needs CF API token flow |

## Strategic conclusions

1. **EMIX's differentiators** (keep investing): per-config real health evidence, honest protocol classification, compiler determinism, evidence-based IP quality, structured observability.
2. **Biggest honest gaps**: device management, native WG/OVPN runtime (blocked by Railway model — needs a VPS node runtime, architectural groundwork exists via node federation + vpn_pro generators), failover automation into subscriptions.
3. **Do NOT chase**: raw protocol count. Panels that list 15 protocols with 4 real runtimes lose on trust; EMIX's PRODUCTION/BETA/EXPERIMENTAL labeling is the defensible position.
4. **Migration priorities** (next 3 releases): (a) devices per account → (b) subscription auto-failover wiring → (c) VPS-node WG runtime via node federation.
