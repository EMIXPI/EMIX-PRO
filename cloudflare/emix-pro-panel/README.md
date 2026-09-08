# EMIX-PRO Panel — Cloudflare Workers Edition

نسخه‌ی **Cloudflare Workers** پنل EMIX-PRO — همان تجربه‌ی مدیریت کانفیگ هسته‌ی
Python، بدون تغییر هسته، روی لبه‌ی کلادفلیر با **D1 + KV**.

## چه چیزی سرو می‌شود؟

| بخش | توضیح |
|---|---|
| پنل RTL فارسی | ورود، داشبورد، کانفیگ‌ها، مسیریابی هوشمند، تنظیمات |
| API | login / links CRUD / stats / settings / export / smart-routing |
| پروکسی واقعی | **VLESS** روی `/ws/{uuid}` و **Trojan** روی `/trojan-ws` (WebSocket + TCP) |
| اشتراک | `/sub/{sub_secret}` (همه) و `/sub/{uuid}` (تک‌کانفیگ) — base64 |
| پینگ کلاینت | اندازه‌گیری از مرورگر + اعتبارسنجی ضد-جعل سمت سرور (≥۵ نمونه) |
| خودآغاز | در اولین request هر isolate: ساخت اسکیما + seed مقادیر (idempotent) |

## Bindings

| نام | نوع | نقش |
|---|---|---|
| `DB` | D1 (`emix-pro-db`) | داده‌ی پایدار: کانفیگ‌ها، تنظیمات، رویدادها، سشن‌ها |
| `SESSIONS` | KV (`EMIX_SESSIONS`) | کش سشن ورود (۷ روز TTL) + محدودسازی تلاش ورود |
| `ADMIN_PASSWORD` | secret | رمز اولیه‌ی seed — فقط بار اول؛ تغییر رمز از پنل |
| `PROJECT_SIGNING_KEY` | secret | کلید HMAC برای probe امضادار ورکر SR |

## دیپلوی

### الف) با اسکریپت آماده (REST API — بدون wrangler)

```bash
python3 scripts/deploy_panel_worker.py   # داخل مخزن EMIX-PRO
```

### ب) با wrangler

```bash
cd cloudflare/emix-pro-panel
wrangler d1 create emix-pro-db            # id را در wrangler.jsonc بگذارید
wrangler kv namespace create SESSIONS     # id را در wrangler.jsonc بگذارید
wrangler secret put ADMIN_PASSWORD
wrangler secret put PROJECT_SIGNING_KEY   # اختیاری — پیش‌فرض پروژه فعال
wrangler deploy
```

## امنیت و صداقت

- رمز پنل: SHA-256 تکراری (۲۵۶ دور) با نمک تصادفی؛ مقایسه timing-safe.
- هر Worker با SNI واقعی خودش روت می‌شود → **جعل SNI در مسیر Worker اعمال نمی‌شود**
  (پرچم ذخیره می‌شود اما هرگز در لینک نمی‌نشیند؛ هسته‌ی Python چون خودش TLS را
  terminate می‌کند این ویژگی را دارد).
- UDP/MUX در VLESS پشتیبانی نمی‌شود → اتصال صادقانه بسته می‌شود.
- مصرف بایت واقعی از لوله‌ی TCP↔WS شمرده و در D1 ثبت می‌شود.
- ساب دومین workers.dev ممکن است در ایران فیلتر شود → دامنه‌ی سفارشی توصیه می‌شود.

## هسته‌ی Python دست‌نخورده

این Worker مسیر استقرار **جديدی** است؛ سرویس Railway و کد هسته (`main.py` و
`pages.py`) بدون هیچ تغییری باقی می‌مانند.
