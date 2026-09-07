# emix-smart-routing-v1 — Worker جدید Cloudflare برای Smart Routing Network

**کاملاً جدید و مستقل** — از workerهای قبلی EMIX (مثل `emix-gateway`) هیچ
خطی بازاستفاده نشده و آن workerها دست‌نخورده باقی می‌مانند.

## نقش واقعی (بدون overclaim)

- edge component / control-plane روی Cloudflare
- relay شفاف WS/HTTP به upstream (پنل EMIX-PRO روی Railway)
- اندازه‌گیری latency لبه→upstream و گزارش دوره‌ای (Cron Trigger)
- گزارش egress واقعیِ fetchهای خود Worker (برچسب صادق `worker-fetch-egress`)

این Worker یک «VPN exit جادویی» نیست — egress واقعی تونل کاربر همان
upstream (پنل) است و Smart Routing آن را مستقلاً از داخل تونل verify می‌کند.

## Bindings (هیچ‌کدام در source نیست — در deploy ست می‌شوند)

| Binding | نوع | مقدار |
|---|---|---|
| `EMIX_UPSTREAM` | secret_text | host عمومی پنل (Railway) |
| `SR_SIGNING_KEY` | secret_text | کلید HMAC مشترک با پنل (تصادفی، تولید در deploy) |
| `SR_STATE` | kv_namespace | کش nonce + آخرین گزارش (namespace جدید و مستقل) |

## مسیرها

| مسیر | روش | دسترسی | توضیح |
|---|---|---|---|
| `/sr/health` | GET | عمومی سبک | سلامت Worker + upstream + colo |
| `/sr/edge-info` | GET | امضاشده | colo/country/city/مختصات لبه |
| `/sr/egress-test` | GET | امضاشده | egress واقعی fetchهای Worker |
| `/sr/probe-upstream` | POST | امضاشده | latency واقعی edge→upstream |
| `/sr/report` | POST | امضاشده | ثبت گزارش در KV |
| `/sr/report/last` | GET | امضاشده | آخرین گزارش ذخیره‌شده |
| `/*` (بقیه) | همه | عمومی | relay شفاف به upstream (WS + HTTP) |

## امنیت

- امضای HMAC-SHA256: `ts.nonce.METHOD.path.sha256(body)` — پنجره ±۹۰s
- nonce یک‌بارمصرف (KV با TTL ۶۰۰s) → replay protection
- proxy فقط به `EMIX_UPSTREAM` ثابت → SSRF به مقصد آزاد ساختاراً غیرممکن
- Workerهای موجود EMIX هرگز overwrite نمی‌شوند

## Cron

`*/30 * * * *` — گزارش سلامت امضاشده به `POST /api/smart-routing/worker/report`
پنل (که خودش nonce را در SQLite replay-guard می‌کند).

## Deploy (عملیات — از خارج از این repo)

```
scripts/deploy_sr_worker.py
```
1. ساخت KV namespace جدید `SR_STATE` (اگر نباشد)
2. تولید `SR_SIGNING_KEY` تصادفی
3. PUT اسکریپت با bindings بالا (اسم: `emix-smart-routing-v1`)
4. PUT schedules (cron `*/30 * * * *`)
5. تست زنده: `/sr/health` + probe امضاشده

سپس در پنل: تنظیمات Smart Routing → ثبت `worker_url` + `worker_key`
(ذخیره در Volume پنل — نه در source code).
