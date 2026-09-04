# NETWORK CONTROL CENTER — Phase 39 Final Architecture

> **حکمطلق پروژه:** هسته‌ی شبکه‌ی واقعیِ سالم > زیبایی معماری > تعداد قابلیت.
> EMIX-PRO از این فاز به بعد = **EMIX Core + EMIX-PRO Control Plane + Unified Network Control UI**.

## 1. معماری نهایی (data flow)

```
EMIX Core (protocol/ — همان lineage سالم EMIX @ 05f2f2c + weak-link tuning v11.6.0)
        │
        ├── link_health.py ──── پروب E2E واقعی (ws_ms + e2e_ms، کلاینت مینیاتوری هر پروتکل)
        │        └── /api/links/{uid}/ping · /api/links/ping-all · /api/health/links/{uid}/probe
        │
        ├── network_test.py ─── پروب مرحله‌ای واقعی DNS→TCP→TLS→SNI + گواهی (فاز ۳۹)
        │        └── /api/network/test/{quick,tls,sni,diagnostic} · /api/network/test/targets
        │
        ├── capability_engine ── SSoT قابلیت (پروتکل × ترنسپورت × امنیت × نود × دیپلوی)
        │        └── /api/config-builder/capabilities · /api/railway/validation-matrix
        │
        ├── config_builder ──── کامپایلر کانونی (تنها مسیر تولید کانفیگ)
        │        └── /api/config-builder/{preview,generate,history}
        │
        ├── network_health ──── ماشین‌حالت سلامت (HEALTHY/DEGRADED/UNREACHABLE/…؛ ۱۵min TTL)
        │
        └── egress_engine / iran_gateway / endpoint_profiles / structured_events
                 │
        FastAPI (main.py — register_routes واحد برای هر موتور)
                 │
        Unified Network Control Center (pages.py §pg-builder — «مرکز کنترل شبکه»)
          هدر سلامت · کارت پروتکل/نود/مسیریابی/کلاینت · پنل تست زنده‌ی واقعی
          پیش‌نمایش = خروجی همان کامپایلر · QR محلی
```

**قاعده‌ی مرزها:** UI هیچ فرضی درباره‌ی قابلیت هاردکد ندارد — همه‌چیز از
`/api/config-builder/capabilities` می‌آید؛ ترکیب نامعتبر در بک‌ند رد می‌شود.

## 2. چه چیز از EMIX (reference) دوباره تأیید/احیا شد

| بخش | EMIX (سالم) | EMIX-PRO (فاز ۳۹) | اقدام |
|---|---|---|---|
| هسته‌ی پروتکل‌ها (vless/trojan/ss/mtproto) | working | همان lineage + tuning | دست‌نخورده (معیار: diff) |
| پینگ واقعی | TCP probe ساده | E2E کامل پروتکل‌محور | حفظ و ارتقا (پیش از فاز ۳۹) |
| پروب مرحله‌ای DNS/TCP/TLS/SNI | — | **network_test.py جدید** | ساخته شد (فاز ۳۹) |
| تجربه‌ی ساخت کانفیگ | مودال ساده | NCC یکپارچه | بازطراحی (فاز ۳۹) |

## 3. API های تست زنده (همه REAL — هیچ عدد جعلی)

| اندپوینت | کار | واقعی بودن |
|---|---|---|
| `POST /api/network/test/quick` | DNS+TCP+TLS+کل با ms مرحله‌ای | getaddrinfo + create_connection + ssl.wrap_socket واقعی؛ در executor thread |
| `POST /api/network/test/tls` | هندشیک + گواهی (CN/issuer/انقضا/SAN/ALPN) | همان زنجیره + x509 parse |
| `POST /api/network/test/sni` | گواهی ارائه‌شده در برابر SNI درخواستی + verdict MATCH/MISMATCH | هندشیک insecure برای مشاهده‌ی گواهی + تحلیل صادق |
| `POST /api/network/test/diagnostic` | پروب + خروج واقعی پنل + سلامت موتورها + اهداف مرورگر | ترکیبِ چند اندازه‌گیری واقعی |
| `POST /api/links/{uid}/ping` | تونل E2E کامل (ws_ms/e2e_ms/HTTP reply) | کلاینت مینیاتوری همان پروتکل (پیش‌موجود) |
| `POST /api/turbo/links/{uid}/ab` | A/B عادی در برابر 0-RTT | دو پروب واقعی، کمینه‌ی ۲ اجرا |
| `GET /api/client-ping-config` | اهداف نمای مرورگر | + WebSocket واقعی سمت مرورگر |

**قواعد صداقت:** شکست = `DNS_ERROR / TCP_REFUSED / TIMEOUT / TLS_ERROR / SNI_ERROR`
با `error_detail` واقعی؛ `total_ms` فقط روی موفقیت؛ هر تست یک رویداد
`structured_events` با `source=emix_core` می‌سازد.

## 4. معانی مسیریابی (روتینگ)

- **ALL_VPN** — همه‌ی ترافیک از تونل.
- **IRAN_DIRECT** — مقاصد ایرانی از ISP خود کاربر (USER_ISP)، بقیه از VPN.
  split tunnel سمت کلایست؛ **سرور ایرانی نمی‌خواهد**.
- **IRAN_PROXY** — مقاصد ایرانی از گیت‌وی ایرانی **اثبات‌شده**. بدون
  `VERIFIED_IRAN_EGRESS` → کارت در UI غیرفعال + پیام صادقانه؛ کانفیگ ساخته نمی‌شود.
- **INTERNATIONAL_VPN** — مقاصد بین‌المللی از VPN (ایرانی بلاک).
- **CUSTOM** — قواعد ادمین.

**SNI = فقط معنای TLS.** هیچ SNI/دامنه‌/IP تنظیم‌شده‌ای «خروج ایران» نیست.

## 5. دو وضعیت (Control plane ≠ Data plane)

هر نتیجه‌ی کامپایل دو وضعیت دارد:
- `CONFIGURATION: VALID` — از کامپایلر کانونی.
- `RUNTIME: VERIFIED / در انتظار instance / NOT VERIFIED` — از
  `/api/railway/validation-matrix` (شواهد RUNTIME_STARTED / LISTENER_REACHABLE).

## 6. مهاجرت UI (پذیرش)

- ناوبری «✨ ساخت کانفیگ» (`data-pg="builder"`) → همان مسیر قبلی →
  **pg-builder حالا NCC است** (جایگزینی درجا؛ صفحه‌ی دوم ساخته نشد).
- Command palette «ساخت کانفیگ جدید» → `navTo('builder')` (NCC).
- مودال قدیمی فقط به‌عنوان افزودنِ سریع در صفحه‌ی مدیریت کانفیگ‌ها (pg-links) ماند.
- موتورهای کاغذی (adapters هیستریا/TUIC/…) از قبل DEFERRED و در capabilities
  غیرقابل‌انتخاب‌اند — در NCC عرضه نمی‌شوند (§ «فقط پروتکل‌های واقعاً فعال»).

## 7. محدودیت‌های Railway (صادقانه)

- UDP روی دیپلوی Railway: `NOT_PROVIDED` — WireGuard/OpenVPN-UDP قابل ادعا نیست.
- gRPC/HTTPUpgrade: mimicry/آزمایشی — REALITY فقط با هسته‌ی واقعی عرضه می‌شود.
- MTProto: runtime=subprocess per-link؛ پروب = TCP-connect عمومی.
- پروب از «داخل» دیپلوی به دامنه‌ی عمومی خودش ممکن است hairpin-block باشد →
  fallback صادقانه‌ی local (برچسب `fallback=local`) — الگوی v11.5.1.
