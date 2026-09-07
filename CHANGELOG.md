# Changelog — EMIX-PRO

تمام تغییرات قابل‌توجه این پروژه در این فایل ثبت می‌شود.
قالب بر اساس [Keep a Changelog](https://keepachangelog.com/) است.

## [13.3.0-emix-pro] — 2026-09-07

### Smart Routing Network v1 (Phase 47) — ماژول مستقل مسیریابی هوشمند

- **معماری کاملاً افزودنی (`smart_routing/` — ۱۴ زیرماژول)**: Endpoint
  Discovery / Registry / Verification / Latency Engine / Route Scoring /
  Proxy-Relay Pool / Route Selector / Failover / Health Monitor / Egress
  Verification / Geo-ASN Verification / Cloudflare Worker Integration /
  Admin UI-API. هسته‌ی EMIX و SNI Spoofing و Config Builder پایه دست‌نخورده
  (تست‌های additive-diff فاز ۴۵ همچنان سبز؛ تغییرات main.py فقط درج است).
- **Feature Flag**: `SMART_ROUTING_ENABLED` (env، پیش‌فرض **خاموش** طبق سند) +
  تگل ادمین در تنظیمات. با flag خاموش: لینک‌ها بایت‌به‌بایت شکل پایه می‌مانند
  (تست رگرسیون §A)، APIهای موتور 503، UI صفحه‌ی وضعیت صادق نشان می‌دهد.
  Rollback = خاموش کردن flag؛ کاربران موجود هیچ تغییری نمی‌بینند.
- **NO FAKE SUCCESS**: موفقیت یعنی route established + traffic از مسیر عبور
  کرده + egress از بیرون دیده و از **دو منبع مستقل** verify شده (ip-api از
  داخل تونل + ipwho.is از بیرون) + health پاس. در غیر این صورت UNVERIFIED.
  IRAN_EGRESS فقط با تأیید هر دو منبع true می‌شود — هیچ‌گاه از SNI/هدر/کشورِ
  تنظیمی. GeoIP spoofing به‌عنوان egress ممنوع.
- **Endpoint Discovery بدون اسکن کنترل‌نشده**: فقط منابع allowlist‌شده —
  لینک‌های خود پنل، Worker ثبت‌شده، candidateهای دستی اپراتور، و URLهای
  https منابع عمومی (پیش‌فرض خالی). همه‌ی candidateها SSRF-guard می‌شوند
  (localhost/RFC1918/metadata/CGNAT مسدود — حتی resolve به IP خصوصی).
- **متریک‌های واقعی چند-پروبی**: latency = Real Delay (پاسخ HTTP واقعی از
  داخل تونل، همان موتور link_health)، jitter = انحراف معیار ≥۲ پروب،
  packet_loss = نسبت شکست، tcp_ms جداگانه (تفکیک صادق).
- **Scoring ترکیبی با وزن‌های قابل‌تنظیم** (پیش‌فرض: Latency 30% / Jitter 15%
  / Loss 20% / Uptime 15% / Availability 10% / Egress 10%) + penalties
  (jitter بالا، instability، unverified-egress؛ verify ناموفق = score صفر +
  INVALID). حالت‌ها: OFF/AUTO/LOW_LATENCY/STABLE/IRAN_OPTIMIZED.
- **Pool پویا**: UNKNOWN→ACTIVE فقط بعد از verify کامل؛ DEGRADED/UNHEALTHY/
  QUARANTINED با خروج/بازگشت خودکار؛ تاریخچه‌ی ۲۰ چک آخر مبنای امتیاز است.
- **Failover بدون oscillation**: hysteresis (فاصله‌ی امتیاز ≥۱۰٪ قابل تنظیم
  + cooldown ۱۲۰ث)؛ مرده شدن مسیر → انتخاب مجدد فوری + event؛ کاربر با
  refresh ساب لینک جدید می‌گیرد (بدون کانفیگ جدید).
- **Worker جدید Cloudflare `emix-smart-routing-v1`** (کاملاً مستقل —
  workerهای قبلی EMIX دست‌نخورده): relay شفاف WS/HTTP به upstream +
  /sr/health + /sr/edge-info + /sr/egress-test (برچسب صادق
  worker-fetch-egress) + /sr/probe-upstream (edge→upstream) + Cron گزارش
  دوره‌ای. KV جدید SR_STATE (nonce replay)؛ اسرار فقط از bindings؛
  امضای HMAC-SHA256 (ts±۹۰s + nonce یک‌بارمصرف + sha256 body) هر دو جهت.
- **ذخیره‌سازی**: SQLite افزودنی `smart_routing.db` در DATA_DIR (Railway
  volume) — جداول smart_endpoints/smart_routes/route_health_checks/
  route_events/route_selections/smart_settings؛ migration فقط CREATE IF NOT
  EXISTS (غیر destructive؛ rvg_state.json هرگز دست نمی‌خورد).
- **Iran Direct (DOMESTIC_ROUTE)**: قابلیت خاموش/روشن + تولید پیکربندی
  split-routing واقعی کلاینت (geoip:private/geoip:ir + دامنه‌های ایرانی →
  مستقیم؛ بقیه → تونل). IP کاربر جعل نمی‌شود؛ server پنل مسیر ترافیک محلی
  کاربر را تغییر نمی‌دهد (صادقانه در UI اعلام شده).
- **Config Builder integration (فقط لایه‌ی افزودنی)**: فیلد حالت در مودال
  ویرایش + PATCH /api/links/{uid} + بج مسیر روی کارت. وقتی route فعال
  است: آدرس لینک = فرانتِ 443-only، sni=فرانت (cert معتبر)، host=دامنه‌ی
  واقعی پنل. تداخل مستند با SNI Spoofing: route فعال = spoof نادیده (پشت
  فرانت workers.dev مضر است — اندازه‌گیری فاز ۴۴)؛ spoof روی لینک‌های بدون
  route بی‌تغییر و کاملاً مستقل می‌ماند.
- **API** (احراز هویت فعلی EMIX — require_auth): status/routes/routes/best/
  endpoints/health/test/refresh/select/egress + settings + worker/status +
  worker/report (امضاشده) + iran-direct/rules. Rate limit روی discovery/test.
- **UI**: صفحه‌ی «مسیریابی هوشمند» (nav + بخش pg-smart) — داشبورد متریک‌ها،
  جدول endpointها (responsive)، کارت مسیرها به تفکیک حالت، ثبت Worker،
  Iran-Direct، وزن‌های امتیاز، رخدادها؛ دکمه‌های Refresh Discovery /
  Run Health Check / Test Best Route / روشن-خاموش. موبایل کاملاً responsive.
- **تست‌ها**: `tests/test_smart_routing.py` (۵۴ تست): رگرسیون flag-off
  بایت‌به‌بایت، SSRF، scoring، pool، migration امن، E2E واقعی pipeline
  (verify کامل با egress واقعی از داخل تونل)، امضای HMAC + replay،
  failover/hysteresis، integration لینک‌ساز (فرانت 443 + ترکیب spoof)،
  Iran صادق، static-checkهای Worker (بدون secret هاردکد؛ بدون ارجاع به
  workerهای قبلی)، rate limit، version pin. کل سوئیت: ۱۰۷/۱۰۷ ×۲ متوالی.

## [13.2.0-emix-pro] — 2026-09-07

### قابلیت‌های سفارش‌شده‌ی کاربر (Phase 46) — توربو، جعل SNI، Real Delay، لاگین

- **توربو 0-RTT روی هر کانفیگ (`turbo_boost.py` + پشتیبانی سرور Early-Data)**:
  - سرور: `protocol/{vless,trojan}/websocket.py` هدر `Sec-WebSocket-Protocol`
    (base64url بدون padding — دقیقاً قرارداد `ed=2048` xray) را می‌خواند و بار
    اولیه را بدون صبر برای اولین فریم پردازش می‌کند. ۱۰۰٪ سازگار با گذشته:
    بدون این هدر، مسیر عادیِ پایه طی می‌شود.
  - لینک: فعال‌سازی توربو، `?ed=2048` را به path لینک اضافه می‌کند (فقط WS —
    xhttp عمداً ed نمی‌گیرد).
  - **تک‌شانهای**: فقط یک کانفیگ هم‌زمان توربو می‌تواند باشد (فعال کردن روی
    یکی، قبلی را خاموش می‌کند) — طبق درخواست صریح کاربر.
  - **تست A/B واقعی** (`POST /api/links/{uid}/turbo-ab`): همان تونل، یک بار
    عادی و یک بار 0-RTT (هر کدام ۲ اجرا، کمینه) — تفاوت اندازه‌گیری‌شده
    نمایش داده می‌شود؛ ادعا نیست، اندازه‌گیری است.
  - UI: دکمه‌ی ⚡ روی هر کارت VLESS-WS/Trojan-WS + بج «توربو 0-RTT» + فیلد
    در مودال ویرایش.
- **جعل SNI (Mode B) برای هر کانفیگ دلخواه**: `spoof_sni` + `spoof_sni_enabled`
  روی لینک → لینکِ تولیدی `sni=<جعلی>` + `allowInsecure=1` + `host=<دامنه‌ی
  واقعی>` می‌گیرد (فرمت wire اثبات‌شده‌ی v12.4.2). SS/MTProto صادقانه رد
  می‌شوند (فرمت لینکشان SNI ندارد). اعتبارسنجی کامل (hostname معتبر، بدون IP).
  - **پینگ صادق از همان مسیر**: برای لینک‌های جعلی، verdict اصلی از پروب مسیر
    کلاینت می‌آید (TLS با `server_hostname=جعلی` + هندشیک WS با `Host=واقعی` +
    بایت‌های واقعی پروتکل + پاسخ HTTP واقعی از داخل تونل)؛ شواهد مسیر تمیز
    جداگانه (`clean_path`) گزارش می‌شود؛ مسیر مرده هرگز سبز نمی‌شود.
  - UI: دکمه‌ی 🎭 روی کارت + بج `SNI: www.bale.ir` + فیلد با پریست‌های ایرانی
    (بله/اسنپ/speedtest/cloudflare) در مودال ویرایش.
- **Real Delay تفکیک‌شده از TCP (پاسخ به «فقط تست TCP می‌گیره»)**: نتیجه‌ی پینگ
  حالا سه استیج جدا گزارش می‌کند — `tcp_ms` (TCP خام؛ همان چیزی که به‌تنهایی
  غیرواقعی است)، `ws_ms` (هندشیک TLS+WS) و `e2e_ms` (**Real Delay**: پاسخ
  HTTP واقعی از داخل تونل). بج و توست کارت‌ها با برچسب «Real Delay» و پاسخِ
  دریافتی نمایش داده می‌شوند تا واقعی بودن قابل دیدن باشد.
- **UI همیشه تازه (رفع «بخش‌های جدید را پیدا نمی‌کنم»)**: middleware یک خطیِ
  `Cache-Control: no-store` روی همه‌ی پاسخ‌های HTML — مرورگر دیگر هرگز نسخه‌ی
  کش‌شده‌ی قدیمی پنل را نشان نمی‌دهد؛ بعد از هر دیپلوی UI جدید بلافاصله دیده
  می‌شود (ریشه‌ی گزارش کاربر: HTML قدیمی از کش مرورگر).
- **صفحه‌ی لاگین (سفارش صریح)**: باکس «رمز پیش‌فرض سیستم» حذف شد؛ به‌جای آن
  `123456` به‌صورت کمرنگ (placeholder مونواسپیس با letter-spacing) داخل خودِ
  کادر رمز دیده می‌شود — صفحه از پنل‌های مشابه متمایز می‌شود و رنگ‌ها/استایل
  پایه دست‌نخورده ماند.
- **تست‌ها**: مجموعه‌ی جدید `tests/test_phase46_real_features.py` (۲۸ تست):
  فرمت لینک‌ها (ed/sni/allowInsecure)، تک‌شانهای بودن توربو، رد مقدار خراب،
  E2E واقعی Early-Data (payload داخل هندشیک → پاسخ HTTP از تونل)، A/B واقعی،
  E2E واقعی مسیر جعلی از پشت لبه‌ی TLS واقعی، قواعد composition (بدون سبزِ
  جعلی)، صفحه‌ی لاگین، no-store، و پین نسخه. کل مجموعه: ۵۳/۵۳.
  Gate لوکال با state واقعی پروداکشن: ۴۳/۴۳ (شامل A/B واقعی و 0-RTT و مسیر
  جعلی از پشت TLS edge).
- **اصالت**: `main.py` فقط درجِ افزودنی (هیچ خطِ پایه حذف نشد)؛ تغییر پروتکل
  فقط دو فایل WS با افزودنِ سازگارِ Early-Data (مستثنای مستند در تست اصالت)؛
  `pages.py` فقط حذفِ مستندِ باکس راهنمای لاگین (سفارش کاربر).

## [13.1.0-emix-pro] — 2026-09-07

### ادغام ویژگی‌های سالم روی هسته‌ی EMIX پایه (Phase 45)
- **رفع باگ پنهان پروتکل Trojan (`protocol/trojan/trojan.py` — تنها تغییر پروتکل، ۳ خط)**:
  HashCache هش‌های Trojan بر اساس «طول» LINKS invalidated می‌شد؛ وقتی یک لینک حذف و
  هم‌زمان یکی ساخته می‌شد (طول یکسان)، cache کهنه می‌ماند و لینک جدید Trojan با
  «trojan auth failed» رد می‌شد — کانفیگی ظاهراً سالم که قطع بود. باگ با تست E2E
  واقعی بازتولید شد (تسلسل ساخت→تست→حذف روی ۷ پروتکل: دقیقاً بعد از اولین حذف+ساخت،
  auth لینک جدید می‌شکست) و درمانِ «rebuild در صورت miss» اعمال شد؛ رگرسیون تست
  اختصاصی دارد (`test_trojan_hashcache_delete_create_regression`).
- **تست واقعی پینگ کانفیگ‌ها (link_health.py)** — برای هر پروتکل یک کلاینت مینیاتوری
  واقعی ساخته می‌شود و کل زنجیره از بیرون سنجیده می‌شود: اتصال → هندشیک TLS/WS →
  هدر واقعی پروتکل (UUID/پسورد) → تونل → پاسخ HTTP واقعی از داخل تونل.
  متریک‌ها: `ws_ms` (زمان هندشیک) و `e2e_ms` (رفت‌وبرگشت کامل). موتورِ اثبات‌شده‌ی
  EMIX-PRO (v12.4.x) روی مسیرهای پروتکلیِ بایت‌به‌بایت یکسانِ EMIX پایه.
  - `POST /api/links/{uid}/ping` — تست تک‌کانفیگ
  - `POST /api/links/ping-all` — تست گروهی با هم‌زمانی محدود + گزارش مرحله‌ای
  - `POST /api/links/best` — رتبه‌بندی کانفیگ‌ها بر اساس زمان واقعی
  - `GET /api/ping` — heartbeat سبک برای healthcheck دیپلوی
  - نتیجه‌ی هر تست روی خود لینک ذخیره می‌شود (`last_ping`) و روی کارت کانفیگ
    نمایش داده می‌شود («تست‌شده ✓ Xms» یا دلیل دقیق قطعی).
- **گزارش جامع سلامت (emix_pro.py)** — `GET /api/system/health-all` با بخش‌های
  مستقل و fail-safe: پنل (نسخه/آپتایم/اتصالات زنده)، کانفیگ‌ها (کل/فعال/توزیع
  پروتکل/شواهد تست واقعی)، خروج واقعی IP (اندازه‌گیری بیرونی — الهام از
  EgressTracer پروژه‌ی mlmvpn_android)، Volume پایدار، و زمان اجرا.
- **رابط کاربری**: دکمه‌ی «سلامت سیستم» روی داشبورد (مودال کامل)، دکمه‌ی
  «تست همه‌ی کانفیگ‌ها» روی صفحه‌ی کانفیگ‌ها، دکمه‌ی تست واقعی روی هر کارت
  کانفیگ، و بج نتیجه‌ی آخرین تست روی هر کارت.
- **اصالت پروژه**: هسته‌ی EMIX (`05f2f2c` — «Restore to healthy original state»)
  بایت‌به‌بایت دست‌نخورده: `main.py` فقط یک بلوک افزودنی ۱۲ خطی در انتهای فایل،
  `pages.py` فقط ۵ نقطه‌ی درجِ افزودنی، و پوشه‌ی `protocol/` اصلاً لمس نشده.
  هیچ Cloudflare/Worker/گیت‌وی/مسیر اضافه‌ای در کد نیست.

## [13.0.0-base] — 2026-09-07

### بازسازی کامل روی پایه‌ی سالم EMIX (Phase 45)
- **درخواست صریح اپراتور**: سالم‌ترین نسخه‌ی پنل، ریپوی EMIX بوده است — این
  نسخه به‌عنوان مرجع و پایه قرار گرفت و هیچ‌چیز از پروژه‌ی پایه تغییر نکرد.
- **حذف کامل worker و Cloudflare و بخش‌های اضافی** برای بازگشت اصالت پروژه:
  cf_gateway_worker، cloudflare_edge، smart_route، route_engine، iran_gateway،
  sni_management، multiloc، bridge/turbo/gaming/clean-ip boosts، exit_node،
  config_builder/capability engine، boot profiles، experimental APIs و ۳۵+ ماژول
  دیگر حذف شدند. بخش سلامتِ v12.4.x به‌صورت سالم و بازنویسی‌شده روی پایه
  ادغام شد (بالا را ببینید).
- **سازگاری داده‌ها حفظ شد**: فرمت state (`rvg_state.json` v9.2)، فایل `.rvg_secret`
  و ساختار لینک‌ها با پنل زنده‌ی قبلی یکسان است — ۲۰/۲۰ کانفیگ موجود بدون
  هیچ تغییری روی پنل جدید بالا می‌آیند (تأییدشده با بکاپ واقعی پروداکشن).
- `railway.toml` (تنظیمات دیپلوی) حفظ شد؛ اندپوینت `/api/ping` توسط ماژول
  افزودنی تأمین می‌شود تا healthcheck دیپلوی مثل قبل کار کند.

## تاریخچه‌ی نسخه‌های قبل از v13
پروژه‌ی EMIX-PRO از v1 تا v12.4.5 روی فورک سنگینی از همین هسته ساخته شده بود
(۴۰+ ماژول). کل آن مسیر در commit `28cecee` (v12.4.5-public-host) به پایان رسید و
تاریخچه‌ی کامل آن در CHANGELOG قبلی همان commit قابل مشاهده است.
