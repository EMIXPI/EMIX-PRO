# CHANGELOG — EMIX-PRO

## v12.4.0-workspace (2026-09-04) — 🎯 PHASE 40: Configuration Center as the Single Network Workspace

**Mandate:** «کانفیگ‌ها = the single network workspace» — the whole product
experience rebuilt around ONE central configuration page. No competing builder
page, no fragmented network menus, no profile wall. The original EMIX
configuration flow (list page → cards → create → URI/QR/sub → persistence →
real ping) stays the functional source of truth; the visual and interaction
model is completely redesigned.

### THE ONE WORKSPACE — کانفیگ‌ها (rebuilt in place)
- **New header + live stats:** total / تأییدشده (VERIFIED = real E2E ping
  evidence — never «سالم» without a witness) / فعال / latest network state +
  `[+ ساخت کانفیگ]` opening the workspace.
- **Premium config cards (new information architecture):** protocol•transport
  chip, node badge, and the mandatory two-state model —
  `CONFIG ✓ VALID` (compiled + stored) vs `RUNTIME VERIFIED / FAILED / تست
  نشده` (from the real last_ping evidence; the chip itself is clickable →
  retest). Latency ms, TLS ✓ (only with E2E evidence), Tunnel ✓, and the
  routing line (IRAN_DIRECT / IRAN_PROXY / INTERNATIONAL_VPN …) from the
  builder metadata. Primary actions: تست / کپی / QR / ویرایش / more ▾
  (collapsible: usage, expiry, sub/IR-Direct/Iran-Exit subs, turbo, toggle,
  reset, delete — NOTHING deleted, §31).
- **Full-screen create workspace (`#ws-create`) INSIDE the Configurations
  page** — the unified step builder (۱ پروتکل → … → ۱۰ ساخت) with a live
  progress stepper, the REAL network verification panel (تست سریع / TLS /
  SNI / تونل E2E / توربو A/B / تشخیص کامل — the same Phase 39 engines),
  preview from the SAME canonical compiler, and mobile sticky
  پیش‌نمایش/ساخت نهایی bar. On generate → «کانفیگ زنده ساخته شد» panel
  (کپی لینک / QR local / کپی Sub / بازگشت به کانفیگ‌ها).

### ONE CONFIGURATION ENGINE — generate now creates the LIVE link (§25/§34)
- `config_builder` gained a link-factory seam wired from
  `main._create_link_core` — «ساخت نهایی» runs the SAME pipeline
  (capability → node → endpoint → routing validation → canonical compiler)
  AND persists a real, testable link (persistence + born-UNKNOWN health
  probe + worker UUID sync), carrying `routing_policy / node_id /
  transport / security / built_by` metadata onto the card.
- The compiled credential IS the live link's UUID (relay-authentic), the
  response carries a `link` block (uuid/share_link/sub_url/routing_policy),
  history entries reference their `link_uuid`, and regenerate is
  outputs-only (never duplicates the live link).
- Honest output-only paths: custom endpoints and non-panel nodes export
  artifacts with an explicit reason (no fake live link). preview NEVER
  creates links and never invents credentials.

### THE PROFILE WALL IS GONE (§32)
- The config-creation chain is now ALWAYS-ON core:
  `config_builder, capability_engine, iran_direct, iran_gateway,
  structured_events, turbo_boost, account_manager` (+ existing
  domestic_route_engine). CORE_SURFACE extended with the builder routes.
  Production (`EMIX_PROFILE=core`) gets the FULL workspace experience — the
  «EMIX_PROFILE=full را فعال کنید» message is replaced by an honest
  technical-failure notice (with جزئیات فنی) that only appears if an engine
  actually fails to boot.
- Engine registration stays fail-safe (try/except — a broken engine never
  breaks boot; turbo_boost registration is now guarded too).

### NAVIGATION — significantly simpler (§30, HIDE not delete)
- Sidebar: داشبورد / **کانفیگ‌ها** / حساب‌ها / گروه‌های ساب // سیستم
  (تنظیمات/بروزرسانی/بکاپ/پشتیبانی) // تشخیص و لاگ (سلامت/لاگ/خطا).
- 14 network-specialized pages (پل ایران، ZEUS، گیمینگ، چندلوکیشن، VPN Pro،
  مسیریابی، پروکسی ایران، سابسکریپشن، ترافیک، اتصالات، نود، آزمایشی،
  همه‌ی کانفیگ‌ها، builder) are HIDDEN from the sidebar but fully intact
  (reachable via command palette Ctrl+K — zero backend/JS removed).
- `navTo('builder')` redirects to کانفیگ‌ها + opens the workspace (all old
  links/palette/bookmarks keep working). Command palette ساخت کانفیگ
  entries route to the workspace.

### TESTS & GATES (real, not counts)
- NEW `tests/integration/test_phase40_workspace.py` — 22 tests: ALWAYS_ON
  contract, link-factory chain (generate→card→retestable), preview
  zero-side-effects, honest output-only paths, routing honesty
  (SPLIT_TUNNEL_NOT_SUPPORTED for uri clients, IRAN_PROXY blocked without a
  verified gateway), UI migration acceptance (hidden nav, workspace inside
  pg-links, standalone builder section gone, palette, profile-wall text
  gone, premium cards two-state model, mobile sticky bar, hidden pages
  intact), history link_uuid.
- Updated to the new reality (not weakened): phase38plus/39 UI markers,
  core_revival core-profile expectations (workspace chain present, optional
  engines still off), gaming_wte order-fragility fix (vless-only push
  contract preserved).
- **Full suite: 1032/1032 ×2 consecutive clean runs.** JS: 4/4 script
  blocks `node --check` OK. compileall OK. secret scan clean.
- **REAL boot gate 23/23** (`EMIX_PROFILE=core`, exact acceptance flows):
  §34 VLESS+XHTTP+TLS+IRAN_DIRECT → تست سریع REAL (DNS 2.0/TCP 6.1/TLS
  16.5ms) → تشخیص کامل → preview (no link) → generate → LIVE link → card
  with routing metadata → RETEST real E2E (ws 18.8ms/e2e 25.3ms) → card
  shows RUNTIME VERIFIED → QR local SVG. §35 international config real
  usable (E2E ws 16.5ms/e2e 21.2ms). §36 IRAN_PROXY honestly blocked
  (گیت‌وی اثبات‌شده‌ای موجود نیست).

## v12.3.0-ncc (2026-09-04) — 🛰 PHASE 39: EMIX Core Integration + Unified Network Control Center

**Mandate:** «EMIX Core + EMIX-PRO Control Plane + Unified Network Control UI» —
backend recovery verified against the healthy EMIX reference, then ONE unified
config experience replacing the fragmented build pages.

**Recon verdict (real evidence, not assumptions):**
- The data plane was NOT broken: EMIX-PRO's protocol core (vless/trojan/ss/
  mtproto) is the same lineage as healthy EMIX @ 05f2f2c (diff = v11.6.0
  weak-link tuning only) and the E2E probe engine measures REAL ws_ms/e2e_ms
  (verified: HTTP/1.1 200 OK through the tunnel, ws 2.7ms / e2e 0.4ms).
- The real gap: the build page had NO live test panel (real ping was invisible
  at config-creation time), config creation was fragmented across 5+ competing
  UI paths, and no ad-hoc DNS/TCP/TLS/SNI probe existed.
- Paper adapters (hysteria2/tuic/wg/…) honestly report DEFERRED — they stay
  hidden from the unified UI (capability-driven, zero fake support).

### NEW — Real Network Test Service (`network_test.py`)
- Staged REAL probe DNS → TCP → TLS → SNI, per-stage milliseconds, resolved
  IPs, certificate (CN/issuer/expiry-days/SAN/ALPN/verify), executed in an
  executor thread (never blocks the event loop), hard timeouts.
- Honest error contract: `DNS_ERROR / TCP_REFUSED / TIMEOUT / TLS_ERROR /
  SNI_ERROR / UNSUPPORTED` + real `error_detail`; `total_ms` only on success.
- Routes: `POST /api/network/test/{quick,tls,sni,diagnostic}` +
  `GET /api/network/test/targets`; every test emits a structured event
  (`source=emix_core`). CA bundle via certifi; insecure-mode certs parsed
  from DER via cryptography (SNI spoof verdicts: MATCH / MISMATCH, honest).
- Blocked-host posture preserved (localhost/127.0.0.1 refused — 400).

### NEW — Unified Network Control Center («مرکز کنترل شبکه»)
`pg-builder` replaced IN PLACE (nav «✨ ساخت کانفیگ» opens it directly):
- **Header:** Core/Backend status dots (from /health + /api/health/summary),
  selected node, refresh.
- **Sections:** protocol CARDS (only PRODUCTION-selectable; others visibly
  «پشتیبانی نمی‌شود») → node cards (state/region/TCP/TLS/UDP/egress badge) →
  transport chips (node capability-driven) → security → Endpoint Profile
  (SNI = TLS semantics only) → routing CARDS (ALL_VPN / IRAN_DIRECT /
  IRAN_PROXY / INTERNATIONAL_VPN / CUSTOM with leg explanations; IRAN_PROXY
  disabled + honest message until a VERIFIED Iranian gateway exists) →
  client output cards (split-tunnel badge) → advanced (ALPN/fingerprint/SS).
- **LIVE test panel:** [تست سریع] [تست TLS] [تست SNI] [تست تونل E2E] [توربو
  A/B] [تشخیص کامل] — every number is a real measurement rendered live in a
  diagnostic console; link selector for tunnel/turbo tests; «حقیقت مسیر از
  مرورگر شما» card (real browser WebSockets, dual vantage).
- **Two-status model (§31):** `CONFIGURATION: VALID` (canonical compiler) +
  `RUNTIME: VERIFIED / در انتظار instance / NOT VERIFIED` (from
  /api/railway/validation-matrix evidence).
- Mobile: stacked cards, sticky generate bar, touch-friendly test buttons.
- QR stays local (/api/qr — no third-party).

### MIGRATION
- Command palette «ساخت کانفیگ جدید» → `navTo('builder')` (the NCC); the old
  quick-add modal remains only on the links MANAGEMENT page.
- No second config page was created — the old builder was replaced in place
  (single `pg-builder`, single `ncc-console`).

### TESTS — see v12.3.0 gate below (merged on top of v12.2.0) × 2 consecutive clean runs
- +10 unit (`test_network_test.py`): real-socket staged probe, honest
  DNS/TCP failures, executor non-blocking, cert DER parsing, blocked hosts.
- +15 integration (`test_phase39_ncc.py`): REAL network tests against
  cloudflare.com (staged ms + real cert), honest failures, compiler chain,
  structured events, migration acceptance (nav→NCC markers, palette routing,
  old modal retained, no duplicate pages).
- Updated `test_phase38plus` markers for the bld→ncc element migration and
  made its dashboard test order-independent (authed).
- Gates: real uvicorn boot (python main.py) → FINAL GATE 13/13 with REAL
  measurements (DNS 1.6ms / TCP 5.7ms / TLS 13.7ms on cloudflare; E2E tunnel
  ws 2.7ms / e2e 0.4ms / HTTP 200; cert Google Trust Services 59d); rendered
  dashboard JS: ALL 4 script blocks pass node --check; compileall OK; secret
  scan clean.
---

## v12.2.0-iran-exit (2026-09-04) — 🇮🇷 Iran-Exit: «IP من با کانفیگ همچنان ایران»

**User request:** «در اصل می‌خواهم IP من با کانفیگ همچنان ایران باشد.»

### NEW — `exit=ir` در /sub-json (خروج کل ترافیک از گیت‌وی ایرانی)
- زنجیره‌ی `کلاینت → تونل EMIX → گیت‌وی ایرانی → اینترنت`:
  sing-box با `detour:"proxy"` · xray با `sockopt.dialerProxy` — IP ظاهری
  بین‌الملل = گیت‌وی ایرانی؛ مصرف داخلی همچنان DIRECT از ISP (همه‌جا ایران).
- انتخاب گیت‌وی: فقط `VERIFIED_IRAN_EGRESS` تازه + پروتکل قابل-dial
  (`http`/`socks5`) — `iran_gateway.best_client_chainable_gateway()`؛ بدون
  گیت‌وی واجد شرایط → `422 NO_VERIFIED_IRAN_GATEWAY` + راهنما (صداقت).
- `/api/links`: `sub_json_urls.singbox_ir` / `xray_ir`؛ دو دکمه‌ی پرچم در داشبورد.
- endpoint `422 INVALID_EXIT_MODE` برای exit نامعتبر؛ هدر `x-emix-ir-rules`
  حالا `exit=` هم دارد.
- `GatewayIn` credential فقط در مسیر ساخت کانفیگ کلاینت استفاده می‌شود
  (APIهای لیست ماسک می‌کنند — بدون تغییر).

### TESTS — ۹۸۵/۹۸۵ سبز
- +۶ تست unit (زنجیره‌ی sing-box/xray، auth، ردِ صادقانه بدون گیت‌وی،
  exit نامعتبر، auto-مستقل از گیت‌وی) و +۳ integration (۴۲۲ صادقانه،
  زنجیره‌ی واقعی روی اپ، exit نامعتبر).

---

## v12.1.0-ir-direct (2026-09-04) — 🇮🇷 IR-Direct: داخلی‌کردن مصرف حتی با کانفیگ

**User priority:** «مهم‌ترین چیزی که برای پنلم می‌خواهم sni spoofing یا
iran direct است — برای داخلی کردن مصرف حتی با کانفیگ.»

### NEW — `/sub-json/{uuid}` (هسته‌ی همیشه‌زنده)
- کانفیگ **کامل کلاینت** sing-box / xray با قواعد split-tunneling واقعی:
  پیشوندهای IR (۲,۵۲۸ RIPEstat) + دامنه‌های `.ir` → DIRECT از ISP کاربر؛
  بقیه → تونل EMIX. `?geosite=1` → rule-set ریموت geosite-ir.
- پروکسی‌ساید از `generate_share_link` پارس می‌شود → SNI Spoofing/CDN/
  allowInsecure خودکار منعکس می‌شود (single source of truth).
- ترکیب پشتیبانی‌نشده → `422 SPLIT_TUNNEL_NOT_SUPPORTED` (صداقت، نه ظاهرسازی).
- `/api/links` فیلد `sub_json_urls`؛ دو دکمه‌ی جدید در داشبورد (ساب IR-Direct).
- DNS داخلی: دامنه‌های ایران از DNS ایرانی (detour=direct) رزولو می‌شوند.

### CORE PROMOTION — موتور domestic همیشه‌روشن
- `boot_profile.ALWAYS_ON = {domestic_route_engine}` — پالیسی/تشخیص/CRUD در
  core هم حی است؛ job آپدیت روزانه‌ی دیتاست به jobهای هسته منتقل شد؛
  wiring رزالور/seed به `_wire_domestic_core()` (همیشه اجرا) منتقل شد.
- CORE_SURFACE اکنون ۹ مسیر است (+`/sub-json/{uuid}`).

### TESTS — ۹۷۶/۹۷۶ سبز
- `tests/unit/test_ir_client_rules.py` (۹ تست): ساختار sing-box/xray،
  بازتاب SNI spoof، رد صادقانه ss/xhttp-singbox، ماتریس پشتیبانی.
- `tests/integration/test_ir_direct_sub.py` (۵ تست): e2e با دیتاست واقعی،
  هدر `x-emix-ir-rules`، spoof، فیلد API.

---

## v12.0.0-core (2026-09-04) — 🏗️ REVIVAL: پروتکل پایه‌ی EMIX به‌عنوان هسته‌ی همیشه‌زنده

**User report:** «پنل باز می‌شود ولی کانفیگ‌ها وصل نمی‌شوند… EMIX اصلی پینگ
می‌دهد ولی EMIX-PRO نه. یکی از AIها پروژه را شلوغ و بی‌استفاده کرده. می‌خواهیم
بر اساس پروتکل پایه‌ی EMIX احیا شود.»

### ROOT CAUSE FIXED — چرخش UUID با هر ری‌دیپلوی (حادثه‌ی production)
- `_get_or_create_secret()`: خطای دیسک (Railway بدون Volume → `/data` غیرقابل
  نوشتن) کل زنجیره‌ی fallback را می‌پراند و حتی با وجود `RAILWAY_SERVICE_ID`
  secret رندوم برمی‌گشت → هر ری‌دیپلوی UUID همه‌ی کانفیگ‌های پیش‌فرض را عوض
  می‌کرد → «کانفیگ‌ها وصل نمی‌شوند» (reject 1008). حالا دیسک-فیلور فقط warning
  است و زنجیره کامل طی می‌شود (SECRET_KEY → فایل → RAILWAY_SERVICE_ID /
  EMIX_IDENTITY_SEED → رندوم با CRITICAL صادقانه).
- `IDENTITY_STABLE` دیگر همیشه-true نیست؛ هویت رندوم صادقانه «ناپایدار»
  برچسب می‌خورد.
- رگرسیون‌تست دقیق سناریوی Permission: `test_identity_stability.py §2.b`
  (روی کد قبل fail می‌شود — تست شده).

### BOOT PROFILE — هسته‌ی همیشه‌زنده (`boot_profile.py` جدید)
- `EMIX_PROFILE=core` (**پیش‌فرض**): فقط پروتکل پایه‌ی EMIX — پینگ/سلامت،
  رله‌ی VLESS/Trojan/SS/MTProto/XHTTP، لینک/ساب، داشبورد/لاگین، کامپایلر،
  jobهای حیاتی (۱۴۱ روت). ۲۷ موتور PRO اختیاری و پیش‌فرض خاموش.
- `EMIX_PROFILE=full`: دقیقاً رفتار v11 (۳۱۷ روت — superset تأییدشده).
- `EMIX_ENABLE=a,b` / `EMIX_DISABLE=a,b`: انتخاب granular.
- Self-check استارت‌آپ: ثبت‌شدن هر ۸ مسیر پایه راستی‌آزمایی می‌شود
  (`✅ CORE SURFACE OK` / `⚠️ CORE SURFACE BROKEN` در لاگ).
- `GET /api/boot-profile` (auth): گزارش زنده‌ی پروفایل/موتورها.
- `/api/deployment-version`: فیلد `boot_profile` اضافه شد.
- خاموشی موتور = انتخاب است نه خطا: `EngineDisabled` جدا از error لاگ می‌شود؛
  job موتورخاموش (مثل ip-quality-prune) اصلاً ثبت نمی‌شود؛ wiring فاز ۳۸ در
  core رد می‌شود؛ importهای پنهانِ موتورخاموش (gaming_boost در wiring) حذف شد.

### TESTS — از «سبز ولی کور» به ۹۶۲/۹۶۲ معنادار
- `tests/integration/test_core_revival.py` (جدید): سطح هسته در هر دو پروفایل،
  عدم ثبت موتورها در core، enable تک‌موتوره، **رله‌ی VLESS end-to-end واقعی**
  (WS → هدر VLESS → TCP-echo واقعی → roundtrip)، لینک خروجی کانفیگ پیش‌فرض
  (دامنه‌ی پنل + `/ws/{uuid}` + TLS)، گزارش نسخه/هویت.
- `test_net_connect.py::test_v4first_timeout_applies`: قطعی شد (وابسته به
  شبکه‌ی محیط نبود — mock؛ TEST-NET در بعضی sandbox ها accept می‌کرد).
- `tests/conftest.py`: پاک‌سازی state پابرجا در شروع session (totals تجمعی
  دیگر بین ران‌ها آلودگی نمی‌سازد) + `EMIX_PROFILE=full` برای پوشش کامل موتورها.
- نتیجه: **۹۶۲/۹۶۲ سبز در دو اجرای متوالی** (قبلاً ۹۵۱/۹۵۲ — یک فیلِ
  محیطی).

### MIGRATION
- بعد از دیپلوی یک‌بار کانفیگ‌ها را دوباره import کنید (آخرین جابه‌جایی UUID —
  از این به بعد بین ری‌دیپلوی‌ها ثابت می‌ماند). برای برگرداندن همه‌ی امکانات:
  `EMIX_PROFILE=full`. جزئیات: [`REVIVAL.md`](./REVIVAL.md).

---

## v11.6.0-revive (2026-09-03) — 🩺 REVIVAL via EMIX + RVG cross-audit (real-ping + weak-link + sub resilience)

**User report:** «کلاینت همچنان ارور میده و کانفیگ درست نشدن… پروتکل سالم پروژه
EMIX رو بهت میدم چک کنی… این پروژه الهام گرفته شده از RVG بوده و احتمالا آپدیت
داده… میخوام بخش‌های سالم با بررسی این دو پروژه دوباره احیا بشن و emix pro
دوباره سالم با پینگ واقعی بشه.»

**Cross-audit evidence (real, live):**
- **EMIX** (github.com/EMIXPI/EMIX @ 05f2f2c) = the known-healthy fork:
  restored to original c33ba43 after its own transport-protocol regression;
  updater LOCKED (`DISABLE_UPDATES=1` — no external rewrites).
- **RVG** (github.com/arvin341az-glitch/RVG @ ce2f878) = the family root; its
  auto-update worker (rvg-update.arvin341az.workers.dev, manifest v11.0.2 —
  sha1-identical to the repo) ships a **weak-link tuning profile**: smaller
  relay chunks, small OS buffers, early drain, TCP_USER_TIMEOUT.
- **Live production truth test** (real client emulation from sandbox):
  server healthy, identity stable; BOTH clean-SNI and spoofed-SNI delivered
  configs connect end-to-end through the real data plane (TLS → WS 101 →
  VLESS → real HTTP 200). Remaining client-side breakage is path/vantage
  specific (Iran→Railway direct blocked while CF-routed configs stay alive) —
  exactly what the revival below addresses.

### WHAT WAS REVIVED / PORTED
1. **RVG v11.0.2 weak-link tuning** — single source of truth
   `protocol/net_connect.py`: `RELAY_BUF 256KB` (was 1MB), `SOCK_BUF 512KB`
   (was 4MB — big OS buffers on weak links = bufferbloat), `WRITE_HIGH_WATER
   128KB` (was 512KB), `TCP_USER_TIMEOUT 20s` (half-dead mobile connections
   reaped instead of locking throughput). All protocols (VLESS/Trojan/SS/XHTTP)
   now import the shared profile via `apply_weak_link_tuning()`.
2. **پینگ واقعی از مرورگر شما (real client-vantage ping)** — new card on the
   configs page: the admin's browser (usually inside Iran) opens REAL
   WebSockets to both entry paths (Railway direct + Cloudflare gateway) and
   reports live/dead + ms from the user's actual network — the same thing
   Karing experiences, finally measurable in-panel. Per-config ping now runs
   server-tunnel + browser probes in parallel and shows
   `تونل Xms · من: مستقیم Yms · CF Zms`. New authed endpoint
   `GET /api/client-ping-config` provides the exact per-protocol target URLs.
3. **Sub resilience — CF gateway variant** — `/sub/{uuid}`, `/sub-all`,
   `/sub-group/{key}` now append a same-identity variant of every vless/trojan
   config routed through the Cloudflare worker tunnel (`/loc/auto/...`,
   host/sni=worker domain, allowInsecure=0). Modern clients pick whichever
   entry is reachable from the user's network — if the ISP blocks Railway
   direct, the CF-routed line keeps the config alive (verified: worker
   returned 101 and tunneled to the real panel auth layer).
4. **UUID auto-sync to the CF worker** — creating/deleting a vless link now
   triggers a background full-list sync to the worker KV (previously only
   manual build_links synced — forgettable, leaving WTE /vl stale).

### VERIFICATION (all real)
- Full suite **952/952 × 2 consecutive clean runs** (940 + 12 new:
  tests/unit/test_revive_v1160.py — §A tuning values/single-source/never-raise,
  §B client-ping-config auth+targets, §C sub variants (0/1/2 lines, path
  rewrite, honest CF suffix, ss/mtproto untouched), §D auto-sync on
  create/delete, §E UI source markers).
- Real boot (python main.py, Railway-style): version 11.6.0-revive; sub
  delivers 2 lines; local client E2E through the real tunnel (101 → VLESS →
  HTTP 200, 18ms); CF-worker tunnel path reaches the real panel auth layer
  (1008 for a foreign UUID — proof of end-to-end reachability).
- Dashboard HTML markers verified in served output; JS blocks node --check OK
  (pre-existing raw-f-string false positive unchanged).

## v11.5.1-hotfix-identity (2026-09-03) — 🔧 ROOT-CAUSE FIX: configs cut after redeploy

## v11.5.1-hotfix-identity (2026-09-03) — 🔧 ROOT-CAUSE FIX: configs cut after redeploy

**User report (production):** «با تغییرات آخر سلامت کلی پروژه به خطر افتاد و
کانفیگ‌هایی که پینگ می‌دادند همه قطع شدند.»

**Root cause (verified, not assumed):** the git push triggered a Railway
redeploy. Without a persistent Volume and without `SECRET_KEY`, the app
generated a **fresh random secret on every deploy** → default-config UUIDs
(derived from the secret) changed → every previously delivered config was
rejected by the tunnel with `1008 not authorized` → **all client configs cut**,
while the panel itself stayed green (ping 200, WS routes 101, vless engine
alive — all re-verified live against production). Reproduced locally: two
fresh boots produced different UUIDs (`934e3824…` vs `f632e0f1…`).

### FIXES
- **main.py — stable identity chain** in `_get_or_create_secret()`:
  `SECRET_KEY` env → `.rvg_secret` file (Volume; existing deployments
  unchanged) → **`RAILWAY_SERVICE_ID`** (stable across redeploys of the same
  Railway service — fixes the outage) → `EMIX_IDENTITY_SEED` (generic
  platform seed) → random last-resort with a CRITICAL warning.
  Honest labeling: derived seeds are STABLE, not secret — the UI/log/version
  endpoint keeps recommending `SECRET_KEY` for production.
- **main.py — public_host persistence**: the learned public domain
  (`_LEARNED_PUBLIC_HOST`) is now saved in state and restored on boot — after
  a redeploy, emitted links and probes use the real domain immediately
  (before: `localhost` until the first dashboard visit).
- **main.py — /api/deployment-version**: new `identity` block
  (`source`, `stable_across_redeploy`, `hint`) so deployment health is
  inspectable without shell access.
- **link_health.py — honest probe vantage fallback**: if a direct probe
  against the panel's own public base fails (e.g. Railway hairpin blocking),
  the same tunnel is re-measured from the panel's local address; success is
  reported `ok:true` with `fallback:"local"` + `fallback_note` carrying the
  public failure evidence. No evidence is fabricated — second vantage, fully
  labeled. Prevents blanket-UNREACHABLE/false-«همه قطع شدند» displays.

### VERIFICATION (all real, local + live)
- Full suite **940/940** (926 existing + 14 new: identity matrix, redeploy
  UUID stability via dual fresh-dir subprocess boots, public_host
  save/restore, probe fallback matrix incl. no-rescue cases).
- E2E: two simulated «redeploy without volume» boots with
  `RAILWAY_SERVICE_ID` fixed → **identical UUIDs** (fix verified);
  manual ws-tunnel ping ok (`ws_ms 4.1`, reply `HTTP/1.1 200 OK`).
- Live production probes during triage: panel UP on v11.5.0, WS routes 101
  (HTTP/1.1), vless engine rejecting test UUID with 1008 — code healthy;
  outage was identity/state, not protocol.

### OPERATOR ACTION (important)
- **Set `SECRET_KEY` (long random value) in Railway service variables** —
  guarantees stable AND high-entropy identity. (Or attach a Volume.)
- Configs delivered before this hotfix are NOT revivable (their UUIDs derived
  from the lost random secret) — re-deliver once from the panel; after this
  deploy they survive every future redeploy.

## v11.5.0-iran-direct (2026-09-02) — 🇮🇷 IRAN DIRECT Config Builder: Clean IP + Handshake

**User request:** in the IRAN_DIRECT section, be able to enter a healthy/set
Clean IP or a fake Handshake (SNI) and then build & receive a config — exactly
like the «ساخت کانفیگ» (Config Builder) section.

Baseline: v11.4.0-builder (904 tests) → **921/921 tests (2× consecutive clean
runs), real uvicorn boot, full HTTP smoke incl. real TLS probe, secret scan
clean.** This phase adds **22 tests** (17 unit + 5 integration).

### NEW ENGINE
- **iran_direct.py (§11/§12)** — IRAN_DIRECT endpoint-asset store:
  Clean-IP list + Handshake (SNI) list, persisted at
  DATA_DIR/iran_direct_assets.json (isolated — module removal hides only this
  UI card). Honest semantics enforced:
  - manual IP = **CONFIGURED_ENDPOINT** only — never presented as verified
    egress, never tied to any geographic claim;
  - Handshake/SNI = TLS/endpoint semantics only (SNI ≠ ROUTE ≠ GEO);
  - server-side probe = TCP_REACHABLE / TLS_VERIFIED with explicit caveat
    «measured from the panel server, NOT your ISP»;
  - use-counters/last-used bookkeeping after each generated config;
  - IRAN_DIRECT egress attribution unchanged: USER_ISP (user's own ISP).
  API (admin-auth, 401-verified): GET /api/iran-direct/assets, POST/DELETE
  /api/iran-direct/ips[/{id}], POST /api/iran-direct/handshakes[/{id}],
  POST /api/iran-direct/ips/{id}/probe, POST /api/iran-direct/use.
  **Zero emitters** — config generation goes ONLY through the canonical
  config_builder (custom_address=Clean IP, custom_sni=handshake,
  routing_policy=IRAN_DIRECT).

### UI (pg-routing — «مسیریابی هوشمند»)
- New card «🇮🇷 ساخت کانفیگ IRAN_DIRECT — IP سالم + هندشیک» mirroring the
  unified Config Builder step flow: ۱ پروتکل → ۲ نود → ۳ ترنسپورت →
  ۴ امنیت → ۵ IP سالم (+ saved list, probe ⚡ badge) → ۶ هندشیک (+ saved
  list) → ۷ پورت → ۸ خروجی کلاینت (URI/subscription honestly disabled for
  IRAN_DIRECT — SPLIT_TUNNEL_NOT_SUPPORTED) → preview/generate via the
  canonical API → URI + copy + QR + Xray JSON download + explainable
  IRAN_DIRECT legs + shared history filtered to IRAN_DIRECT.
  100% capability-driven (same /api/config-builder/capabilities source);
  isolated script block (node --check verified).

### CANONICAL VALIDATOR FIX (endpoint_profiles.py)
- validate_hostname previously accepted impossible dotted-quads (e.g.
  104.17.1.999 — octet > 255) via the hostname regex. Now: dotted-quad SHAPE
  ⇒ it IS an IP ⇒ real octet validation (0-255) or outright rejection.
  An impossible address can never again emit a config that cannot connect.

### EVENTS
- IRAN_DIRECT_ASSET_SAVED / IRAN_DIRECT_PROBE (severity-mapped), central
  secret-scrubbing unchanged.

## v11.4.0-builder (2026-09-02) — Phase 38+: Unified Config Builder, Capability Engine, IRAN_PROXY & Iran Gateway

**Master Network Platform Upgrade: Unified Routing, Egress, Iran Network,
Multi-Node, Protocol Engine & Config Builder.**

Baseline: v11.3.0-network (808 tests) → **904/904 tests, 3× consecutive clean
runs, real uvicorn boot 0 errors, 17/17 API smoke + 5 auth-401 gates,
7/7 UI markers, secret scan clean.** This phase adds **96 tests.**

### NEW ENGINES
- **capability_engine.py (§3-§5, §25)** — the protocol × transport × security
  × node × deployment × client capability engine. Railway compatibility model
  with FOUR distinct layers (RAILWAY_EDGE / RAILWAY_DEPLOYMENT /
  RAILWAY_OUTBOUND / ACTUAL_EGRESS — never conflated). Railway priority order
  (VLESS+XHTTP+TLS first; MTProto TCP via Railway TCP proxy). UDP-dependent
  protocols (WireGuard/Hysteria/TUIC/…) are NEVER exposed as Railway-native.
  Honest Railway validation matrix: CONFIG_VALID (real compile at request
  time) / RUNTIME_STARTED / LISTENER_REACHABLE (live app routes) —
  CLIENT_CONNECTED+ honestly NOT_TESTABLE_WITHOUT_REAL_CLIENT.
  API: GET /api/config-builder/capabilities, GET /api/railway/validation-matrix.
- **config_builder.py (§6-§7, §18-§21)** — the ONE canonical ConfigRequest →
  validation-before-generation (stage-labeled rejections: capability / node /
  endpoint / routing / compiler) → CANONICAL COMPILER (zero new emitters) →
  outputs (URI / Xray JSON / subscription / split-tunnel rules) → bounded
  history (کانفیگ‌های ساخته‌شده: view-masked / reveal-authed / deterministic
  regenerate / delete). IRAN_DIRECT with a non-split client is refused with
  SPLIT_TUNNEL_NOT_SUPPORTED; IRAN_PROXY without a gateway is refused.
  API: POST /api/config-builder/preview|generate, GET history, POST
  history/{id}/regenerate, DELETE history/{id}.
- **iran_gateway.py (§13)** — 🇮🇷 پروکسی ایران: real Iranian gateway registry
  with evidence-based state machine (UNCONFIGURED → CONFIGURED → REACHABLE →
  HEALTHY / VERIFIED_IRAN_EGRESS / ROUTE_MISMATCH / DEGRADED / UNREACHABLE /
  UNSUPPORTED). Real probes: TCP reachability + egress measurement through
  HTTP-proxy / SOCKS5 (minimal in-house CONNECT client) / emix-worker
  endpoints. A manually entered Iranian IP is CONFIGURED, never VERIFIED.
  API: /api/iran-gateway* (all admin-auth).
- **structured_events.py (§29)** — CONFIG_GENERATED / ROUTE_SELECTED /
  EGRESS_VERIFIED / ROUTE_MISMATCH / NODE_QUARANTINED / FAILOVER_TRIGGERED /
  IRAN_GATEWAY_CHECK / PROTOCOL_VALIDATION_FAILED / SPLIT_TUNNEL_COMPILED —
  bounded ring buffer with central secret-scrubbing (passwords/tokens/keys
  field blocklist + UUID redaction). API: GET /api/events.

### ROUTING POLICIES (§11-§13)
- domestic_route_engine: + IRAN_PROXY (Iranian destinations via a REAL
  gateway; honest IRAN_GATEWAY egress attribution with the live verdict
  embedded — warning when unverified, never a fake Iranian exit) and
  INTERNATIONAL_VVPN (BLOCK leg: domestic traffic never enters the tunnel;
  blackhole split rules for capable clients). POLICY_PRESETS now five.
- route_engine.ROUTE_POLICIES extended accordingly.

### FAILOVER CAPABILITY GATES (§15)
- select_replacement: HARD gates — protocol requirement, transport
  requirement (compat-decomposed capabilities) and EXIT_NODE role
  (valid-egress-evidence only). An incompatible node can NEVER be selected,
  regardless of health/latency score. FAILOVER_TRIGGERED structured event.

### UI (§6, §21, §23-§24)
- ✨ ساخت کانفیگ (pg-builder): 9-step capability-driven builder (protocol →
  node → transport → security → Endpoint Profile → routing → client/output →
  validation preview → generate); desktop two-column, mobile single-column;
  EVERY option renders from /api/config-builder/capabilities — zero
  protocol-support hardcoding in JS (source-level test enforced). Smart field
  visibility per protocol. Preview from the canonical compiler only.
- کانفیگ‌های ساخته‌شده: history cards (مشاهده/کپی، بازسازی، حذف) with
  masked credentials in list view.
- 🇮🇷 پروکسی ایران (pg-iranproxy): IRAN_DIRECT vs IRAN_PROXY explainer,
  gateway add form, gateway cards with state badges + evidence +
  بررسی-و-اثبات-خروج button.
- Isolated <script> block + scoped bld-/igw- CSS; all blocks node --check OK.

### FIXES
- network_health.ensure_record(): fresh configs get a born-UNKNOWN record
  SYNCHRONOUSLY (race fix — /api/health/links/{uid} could 404 in the window
  before the background initial probe landed; found via a rare full-suite
  flake after this phase's changes shifted timing; root-caused and fixed,
  6/6 clean runs after).

### WIRING / PERSISTENCE / JOBS
- main: fault-isolated registration of the four new engines; _wire_phase38
  extended (host/worker-domain/CDN providers; gateway status fn → domestic
  engine; live listener-path evidence for the validation matrix). Additive
  persistence keys iran_gateway + config_builder (defensive restores).
  New job: iran-gateway-check (6h). Diagnostics: +config_builder /
  iran_gateway / events / iran_routing sections. EMIX_VERSION=11.4.0-builder.

### DOCS (§32)
- MASTER_NETWORK_ARCHITECTURE_AUDIT.md (Phase A — pre-change recon),
  MASTER_NETWORK_ARCHITECTURE_FINAL.md, RAILWAY_PROTOCOL_COMPATIBILITY.md,
  ROUTE_EGRESS_ARCHITECTURE_FINAL.md, IRAN_NETWORK_ARCHITECTURE.md,
  UNIFIED_CONFIG_BUILDER_FINAL.md + updates (failover/accounts/readiness/
  competitive/README).

## v11.3.0-network (2026-09-02) — Phase 38: Real Network Architecture

**Production Network Architecture, Routing, Egress, Multi-Node Failover,
Accounts/Devices, Iran Domestic Direct Routing & Competitive Completion.**

Baseline: v11.2.0-egress (687 tests) → **808/808 tests, 3× consecutive clean
runs, real uvicorn boot 38/38 smoke PASS.** Phase 38 adds **121 tests**.

### NEW ENGINES
- **route_engine.py (P0)** — first-class Route objects:
  route_id / entry / relay[] / exit / expected-vs-observed country+ASN /
  health / labeled latency / packet_loss / jitter / last_verified /
  verification_state / route_policy. Bounded registry (500). Mismatch is
  never masked as HEALTHY. API: GET /api/routes, /api/routes/summary,
  /api/routes/{id} (admin-auth).
- **failover_engine.py (P1)** — never-blind failover: drain → explainable
  replacement selection (10-factor scoring with ranking_reason[]) → verify
  replacement health → verify route (egress 9-step) → verify egress →
  re-point routes → resume. Verdicts FAILOVER_SUCCESS / FAILED /
  NO_REPLACEMENT; failed failovers keep the old node drained.
  API: POST /api/failover/{node}, GET /api/failover/history|summary.
- **account_manager.py (P2+P3)** — Account/Subscription/Device/Session
  entities; PBKDF2-SHA256 password hashing; one-time device tokens (SHA-256
  stored, never logged); backend-enforced MAX_DEVICES /
  MAX_CONCURRENT_SESSIONS / quotas / expiry; connection gate
  (can_connect verdicts); subscription lifecycle
  ACTIVE/EXPIRED/REVOKED/SUSPENDED/DRAINING; config emission through the
  unified Config Compiler (injected — no duplicate URI logic).
  API: /api/accounts*, /api/devices/*, /api/subscriptions/*,
  /api/connect/authorize (admin-auth).
- **domestic_route_engine.py (P17)** — Iran domestic direct routing:
  prefix DB with longest-prefix match (CIDR/IP/RIPEstat range formats),
  classification IRAN_DOMESTIC / NON_IRAN / UNKNOWN (decision follows the
  ACTUAL resolved IP, never the domain suffix), policy presets ALL_VPN /
  IRAN_DIRECT, decision pipeline with honest egress attribution
  (DIRECT ⇒ USER_ISP — never Railway/Cloudflare/EMIX node), Cloudflare +
  Railway never-classified-as-Iranian guards, split-tunnel rule compilation
  (xray/xray-json/sing-box: GEOIP:IR + verified CIDRs; WireGuard/OpenVPN/
  URI: SPLIT_TUNNEL_NOT_SUPPORTED — honestly), traffic accounting
  (DOMESTIC_DIRECT / INTERNATIONAL_VPN / UNKNOWN), bounded decision history.
  API: /api/domestic/* (admin-auth).
- **domestic_rules_updater.py (P17)** — atomic dataset updates from a
  configurable trusted source (default: RIPEstat country-resource-list IR):
  validation (min threshold, parseable, checksum over normalized prefixes),
  versioning, rollback-by-retention (empty/malformed/small datasets NEVER
  replace a working one), TTL staleness flag, failure fallback, bounded
  history. Formats: RIPEstat JSON + plain CIDR text.
- **configs/iran_prefixes_seed.json** — REAL RIPEstat snapshot:
  2,528 prefixes (1,958 IPv4 + 570 IPv6), SHA-256 checksummed, with source
  metadata. Loaded at boot; refreshed daily by job (live update verified at
  boot: "dataset updated: 2528 prefixes").

### EXTENSIONS
- **node_manager.py** — node states extended with DRAINING (no new
  assignments, existing traffic continues), QUARANTINED (operator override,
  survives fresh heartbeats), UNKNOWN family; set_draining() /
  set_quarantine(); online_nodes() excludes drained/quarantined/maintenance;
  runtime gate still beats drain.
- **egress_engine.py** — HEALTH_LAYERS now includes PROTOCOL_HEALTH (P6)
  derived from the live protocol registry × compat.READINESS.
- **compat.py (P4)** — public status vocabulary (VALID→SUPPORTED,
  EXPERIMENTAL, INVALID, NOT_IMPLEMENTED); matrix_view() emits `status` +
  `public_states`; selectable_combinations() enforces "unsupported
  transports are never selectable".
- **diagnostics.py (P7)** — new sections: routes, egress (health layers +
  route history), accounts, domestic_routing, failover.
- **main.py** — Phase 38 bootstrap (fault-isolated registration),
  _wire_phase38_engines() (compiler injection, route repointing, real
  5s-bounded DNS resolver, seed loading), new jobs (domestic-rules-update
  daily, account-sweep 5 min), persistence keys (account_manager,
  domestic_routing — additive, defensive), EMIX_VERSION = 11.3.0-network.
- **pages.py (P8)** — new section **pg-routing** (مسیریابی هوشمند): Network
  Routing Mode cards (ALL_VPN / 🇮🇷 IRAN_DIRECT with honest descriptions),
  Test Route diagnostic tool (destination → resolved IP → classification →
  rule → decision → egress attribution), IR prefix dataset card
  (source/version/checksum + atomic update button), traffic accounting,
  client split-tunnel support table. New section **pg-accounts** (حساب‌ها):
  account creation, quota/expiry/limit surfaces, device list + one-time
  token display + revoke, subscription rows with status chips. Nav items +
  loaders registered; all data from real APIs; nothing hardcoded.

### TESTS (+121: 808 total)
- tests/unit/test_route_engine.py (15) — route semantics, mismatch,
  staleness, bounded registry, labeled latency, provider failure.
- tests/unit/test_failover_engine.py (24) — states, scoring factors,
  pipeline verdicts, drain retention.
- tests/unit/test_account_manager.py (32) — hashing, gates, limits,
  cascades, reconciliation, persistence, audit hygiene.
- tests/unit/test_domestic_routing.py (35) — the 13 mandatory P17 tests
  + updater robustness + seed dataset + DNS-follows-IP + CF/Railway guards.
- tests/integration/test_phase38_e2e.py (15) — the 10 mandatory flows
  (account→…→verified egress; control-plane→exit→egress verification;
  healthy node; failure→drain→failover→replacement; expected≠observed;
  configured≠actual; SNI invariance; NO_EXIT_NODE_AVAILABLE; expired
  subscription rejected; revoked device rejected) + domestic API +
  diagnostics coverage + persistence.

### PRODUCTION GATES (P16) — all PASS
Full suite 808×3 · compileall · old-state migration · real uvicorn boot
(0 errors) · 38/38 API smoke · JS node --check 3/3 · egress/route/failover/
account tests · security + secret scans clean · dependency versions current ·
git diff audited (no secrets, no generated artifacts).

### DOCS
PHASE38_ARCHITECTURE_AUDIT.md (recon) · PHASE38_ARCHITECTURE_FINAL.md ·
ROUTE_ENGINE_FINAL.md · EGRESS_ENGINE_FINAL.md · FAILOVER_ENGINE_FINAL.md ·
ACCOUNT_DEVICE_FINAL.md · PRODUCTION_READINESS_REPORT_V2.md (score 92/100,
test classification, honest GRAY list) · COMPETITIVE_MATRIX_V2.md ·
PROTOCOL_MATRIX_FINAL.md (P4 section) · MIGRATION_GUIDE_FINAL.md (v11.3
section) · this changelog.

---

## v11.2.0-egress (2026-09-01)
CRITICAL PRODUCTION DEFECT fix — FALSE EGRESS / Custom IP semantics.
Egress & Route Truth Engine (roles, VERIFIED/CONFIGURED_ONLY/UNKNOWN,
9-step validation, evidence TTL, labeled latencies, NO_EXIT_NODE_AVAILABLE,
ROUTE_MISMATCH). Custom IP field renamed to endpoint address; honest route
semantics in gaming links; worker v2.2.0-egress (/egress-test, /exit-ip with
ASN/IP-family). 45 new tests (687 total).

## v11.1.0-audit (2026-09-01)
Production audit: P0 security (phone-home removed, local QR, brute-force,
token, plaintext IP provider off) + P0 correctness (route shadow, sweep
persistence, dead Diagnostics UI, header crash) + persistence (sessions/
stats/SNI/WG keys) + real-data UI. 9 FINAL docs. 642 tests.

## v11.0.0-arch (2026-08-31)
Protocol Orchestrator + Config Compiler + Network Health Engine +
Endpoint Profiles (SNI-Spoof successor) + IP Quality + Jobs + Diagnostics.
