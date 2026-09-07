# smart_routing/worker_client.py — ارتباط امضاشده با Worker جدید Cloudflare
# ══════════════════════════════════════════════════════════════════════════════
# Worker: emix-smart-routing-v1 (کاملاً جدید — workerهای قبلی EMIX دست‌نخورده‌اند).
#   • panel → worker: درخواست امضاشده (HMAC + ts + nonce + replay protection)
#   • worker → panel: همان طرح در جهت برگشت (گزارش cron)
#   • secret: v13.6.0 — پیش‌فرض پروژه (PROJECT_SIGNING_KEY) + override با env
#     SR_SIGNING_KEY یا ثبت UI/API در smart_settings (هر دو مقدم‌اند).
#   • Worker فقط component شبکه‌ای/control-plane است — «VPN exit جادویی» نیست.
# ══════════════════════════════════════════════════════════════════════════════

import json
import os
import time

import httpx

from . import db, security
from . import PROJECT_SIGNING_KEY, PROJECT_WORKER_URL

WORKER_NAME = "emix-smart-routing-v1"

# v13.5.0: Worker پیش‌فرض پروژه — روی fresh-deploy بدون ثبت دستی، discovery و
# مسیریابی از همین فرانت شروع می‌شوند (public URL).
# v13.6.0: URL + کلید امضا هر دو از پروژه می‌آیند (درخواست مالک: مقادیر با
# هر دیپلوی خودکار ست شوند) — کلید اختصاصی اپراتور (env/DB) اولویت دارد.
DEFAULT_WORKER_URL = PROJECT_WORKER_URL


# ⚠ UA: لبه‌ی Cloudflare درخواست‌های client پیش‌فرض (python-httpx/…) را با خطای 1010
# می‌بندد (Browser Integrity Check) — UA مرورگرمانند الزامی است.
_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def worker_base() -> str:
    """URL پایه‌ی Worker — ثبت ادمین، یا پیش‌فرض پروژه (v13.5.0).

    تمایز صادق: row ثبت‌نشده → پیش‌فرض (fresh-deploy کار می‌کند)؛
    ثبتِ خالیِ صریح (پاک‌کردن از UI) → غیرفعال‌سازی (NOT_CONFIGURED)."""
    u = (db.get_setting("worker_url") or "").strip()
    if u:
        return u.rstrip("/")
    if db.has_setting("worker_url"):
        return ""                  # ادمین صریحاً پاک کرده
    return DEFAULT_WORKER_URL


def worker_key() -> str:
    """کلید HMAC — ترتیب اولویت: DB (ثبت UI/API) → env SR_SIGNING_KEY →
    کلید پیش‌فرض پروژه (v13.6.0 — با هر دیپلوی خودکار ست می‌شود).

    نتیجه: fresh-deploy بدون هیچ قدم دستی، امضای HMAC معتبر دارد و Worker
    بلافاصله HEALTHY است. کلید اختصاصی اپراتور همیشه بر پیش‌فرض مقدم است.
    (has_setting برای تمایز row واقعی از مقدار پیش‌فرضِ db لازم است — وگرنه
    پیش‌فرضِ db سایه‌ی env می‌شد.)"""
    row = db.get_setting("worker_key") if db.has_setting("worker_key") else ""
    k = (row or "").strip()
    if k:
        return k
    k = (os.environ.get("SR_SIGNING_KEY") or "").strip()
    if k:
        return k
    return PROJECT_SIGNING_KEY


def worker_key_source() -> str:
    """منبع کلید فعال — برای نمایش صادق در UI (db / env / project-default)."""
    if db.has_setting("worker_key") and (db.get_setting("worker_key") or "").strip():
        return "db"
    if (os.environ.get("SR_SIGNING_KEY") or "").strip():
        return "env"
    return "project-default"


def _candidate_keys() -> list[str]:
    """کلیدهای کاندید برای self-heal — اولویت‌دار و بدون تکرار."""
    seen, out = set(), []
    for k in (worker_key(),
              (os.environ.get("SR_SIGNING_KEY") or "").strip(),
              PROJECT_SIGNING_KEY):
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def has_worker() -> bool:
    return bool(worker_base() and worker_key())


async def _signed_call(method: str, path: str, body: dict | None = None,
                       timeout: float = 20.0, key: str | None = None) -> dict:
    """درخواست امضاشده به Worker — خطاها honest برمی‌گردند (نه سبز جعلی).

    امضا روی «بدنه‌ی واقعاً ارسال‌شده» محاسبه می‌شود (GET بدون body → b"").
    key اختیاری: برای self-heal (امتحان کاندیدهای دیگر) قابل override است."""
    base = worker_base()
    key = key or worker_key()
    if not base or not key:
        return {"ok": False, "error": "worker ثبت نشده (URL/کلید)"}
    send_body = (json.dumps(body or {}, ensure_ascii=False).encode()
                 if method.upper() in ("POST", "PUT") else b"")
    headers = security.make_signed_headers(key, method, path, send_body)
    headers["Content-Type"] = "application/json"
    try:
        async with httpx.AsyncClient(timeout=timeout, headers=_UA) as cli:
            r = await cli.request(method, base + path, headers=headers,
                                  content=send_body or None)
        try:
            return r.json()
        except Exception:
            return {"ok": False, "error": f"HTTP {r.status_code} — پاسخ غیر JSON",
                    "status": r.status_code}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:100]}"}


# ── تست‌های panel → worker ────────────────────────────────────────────────────
async def worker_health() -> dict:
    """سلامت عمومی Worker (بدون امضا — سبک) + upstream از دید Worker."""
    base = worker_base()
    if not base:
        return {"ok": False, "error": "worker ثبت نشده"}
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_UA) as cli:
            r = await cli.get(base + "/sr/health")
        return r.json()
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:100]}"}


async def worker_edge_info() -> dict:
    """اطلاعات لبه‌ی CF از دید Worker (colo/country/city) — vantage واقعی."""
    return await _signed_call("GET", "/sr/edge-info")


async def worker_egress() -> dict:
    """egress خود Worker (fetch از CF) — برچسب صادق: «worker-fetch-egress»
    (این egress مسیرِ تونل نیست؛ egress مسیر جداگانه از داخل تونل اندازه‌گیری
    می‌شود — engine. verify_endpoint_egress)."""
    return await _signed_call("GET", "/sr/egress-test")


async def worker_probe_upstream() -> dict:
    """Worker از لبه‌ی CF به upstream (پنل) WS-probe می‌زند — latency edge→panel."""
    out = await _signed_call("POST", "/sr/probe-upstream", {"ts": time.time()})
    db.add_event("worker", f"probe-upstream از Worker: ok={out.get('ok')} "
                           f"({out.get('latency_ms')}ms)")
    return out


async def worker_full_check() -> dict:
    """بررسی کامل Worker (اتصال، امضا، لبه، upstream) — گزارش honest.

    نتیجه‌ی هر بررسی در smart_settings («worker_check») ذخیره می‌شود تا
    state واقعی (REGISTERED ≠ DEPLOYED ≠ HEALTHY) بین sessionها زنده بماند."""
    out = {
        "worker": WORKER_NAME,
        "base": worker_base(),
        "registered": has_worker(),
        "health": await worker_health(),
        "edge_info": None,
        "probe_upstream": None,
    }
    if has_worker():
        # ── self-heal کلید (v13.6.0) ──────────────────────────────────────
        # اگر کلید فعلی (مثلاً کلید قدیمی ثبت‌شده در DB) با Worker امتبا نداشت،
        # کاندیدهای دیگر (env / کلید پیش‌فرض پروژه) امتحان می‌شوند؛ اولین کلید
        # معتبر در DB ذخیره می‌شود تا بررسی بعدی مستقیم کار کند.
        active_key = worker_key()
        out["edge_info"] = await _signed_call("GET", "/sr/edge-info", key=active_key)
        ei = out["edge_info"] or {}
        if not ei.get("ok") and not _auth_probably_missing_key(ei):
            for cand in _candidate_keys()[1:]:
                cand_ei = await _signed_call("GET", "/sr/edge-info", key=cand)
                if (cand_ei or {}).get("ok"):
                    out["edge_info"] = cand_ei
                    active_key = cand
                    try:
                        db.set_setting("worker_key", cand)
                        db.add_event("worker", "کلید امضای Worker خودکار به‌روزرسانی و ذخیره شد "
                                               "(کلید فعال پروژه اعمال شد)")
                    except Exception:
                        pass
                    break
        out["probe_upstream"] = await _signed_call(
            "POST", "/sr/probe-upstream", {"ts": time.time()}, key=active_key)
        pu = out["probe_upstream"] or {}
        db.add_event("worker", f"probe-upstream از Worker: ok={pu.get('ok')} "
                               f"({pu.get('latency_ms')}ms)")
        auth_ok = bool((out["edge_info"] or {}).get("ok"))
        out["authenticated"] = auth_ok
        db.add_event("worker", f"worker-check: authenticated={auth_ok}, "
                               f"upstream_ok={(out['health'] or {}).get('upstream', {}).get('ok')}")
    out["state"] = _derive_state(out)
    _persist_check(out)
    return out


def _auth_probably_missing_key(edge: dict) -> bool:
    """آیا خطای edge_info صرفاً به‌خاطر «نبودِ کلید» است؟ (نه امضای نامعتبر).

    وقتی اصلاً کلیدی موجود نیست، retry بی‌معنی است — مگر کاندید دیگری باشد."""
    r = str((edge or {}).get("error") or "").lower()
    return "worker ثبت نشده" in r


# ── Worker state machine (طبق سند: Registered ≠ Deployed ≠ Healthy) ──────────
# NOT_CONFIGURED : URL/کلید ثبت نشده
# REGISTERED     : ثبت شده اما هرگز بررسی نشده
# DEPLOYED       : Worker پاسخ می‌دهد (health ok) — اما upstream/امضا هنوز نامعلوم
# HEALTHY        : deployed + امضای HMAC معتبر + upstream سالم
# DEGRADED       : deployed + امضا معتبر اما upstream خراب
# FAILED         : Worker در دسترس نیست (unreachable / غیر JSON)
def _derive_state(check: dict) -> str:
    # v13.5.0: بدون URL → NOT_CONFIGURED؛ با URL ولی بدون کلید، Worker هنوز
    # بررسی‌پذیر است (health بدون امضا) → DEPLOYED/FAILED صادقانه (نه NOT_CONFIGURED).
    if not check.get("base"):
        return "NOT_CONFIGURED"
    h = check.get("health") or {}
    if not isinstance(h, dict) or not h.get("ok"):
        return "FAILED"
    up = (h.get("upstream") or {})
    upstream_ok = bool(up.get("ok")) if isinstance(up, dict) else False
    auth_ok = bool(check.get("authenticated"))
    if auth_ok and upstream_ok:
        return "HEALTHY"
    if auth_ok and not upstream_ok:
        return "DEGRADED"
    # پاسخ می‌دهد اما امضا بررسی نشده/نامعتبر → فقط «DEPLOYED» ادعا می‌شود
    return "DEPLOYED"


def _persist_check(check: dict) -> None:
    h = check.get("health") or {}
    up = (h.get("upstream") or {}) if isinstance(h, dict) else {}
    pu = check.get("probe_upstream") or {}
    summary = {
        "ts": time.time(),
        "state": check.get("state"),
        "worker": check.get("worker"),
        "base": check.get("base"),
        "authenticated": bool(check.get("authenticated")),
        "upstream_ok": bool(up.get("ok")) if isinstance(up, dict) else False,
        "upstream_latency_ms": up.get("latency_ms") if isinstance(up, dict) else None,
        "colo": (h.get("colo") if isinstance(h, dict) else None)
                or (pu.get("colo") if isinstance(pu, dict) else None),
        "edge_to_upstream_ms": (pu.get("edge_to_upstream_ms")
                                if isinstance(pu, dict) else None),
    }
    try:
        db.set_setting("worker_check", summary)
    except Exception:
        pass


def worker_state() -> dict:
    """state فعلی Worker از آخرین بررسی real (persisted) — بدون ادعای جعلی.

    هیچ عدد/وضعیتی ساخته نمی‌شود؛ فقط نتیجه‌ی آخرین worker_full_check
    واقعی برگردانده می‌شود (یا REGISTERED اگر هنوز بررسی نشده).
    v13.5.0: key_missing → کلید امضا (DB/env) موجود نیست — بررسی HMAC
    ممکن نیست، اما URL ثبت/پیش‌فرض شده است."""
    base = worker_base()
    key = worker_key()
    src = worker_key_source()
    if not base:
        return {"state": "NOT_CONFIGURED", "worker": WORKER_NAME, "base": None,
                "checked": False, "key_missing": not key, "key_source": src,
                "last_check": None}
    last = db.get_setting("worker_check") or None
    if not isinstance(last, dict) or not last.get("state"):
        return {"state": "REGISTERED", "worker": WORKER_NAME, "base": base,
                "checked": False, "key_missing": not key, "key_source": src,
                "last_check": None}
    return {"state": last.get("state"), "worker": WORKER_NAME, "base": base,
            "checked": True, "key_missing": not key, "key_source": src,
            "last_check": last}


# ── verify درخواست ورودی worker → panel ─────────────────────────────────────
async def verify_worker_request(request) -> tuple[bool, str, dict]:
    """بررسی امضای درخواست Worker (برای /api/smart-routing/worker/report).

    (ok, reason, body) — timestamp window + nonce replay + HMAC."""
    key = worker_key()
    if not key:
        return False, "کلید Worker تنظیم نشده", {}
    ts = request.headers.get(f"{security.SIGN_HEADER_PREFIX}timestamp", "")
    nonce = request.headers.get(f"{security.SIGN_HEADER_PREFIX}nonce", "")
    sig = request.headers.get(f"{security.SIGN_HEADER_PREFIX}signature", "")
    body = b""
    try:
        body = await request.body()
    except Exception:
        body = b""
    path = request.url.path
    ok, reason = await security.verify_signed_request(
        key, ts, nonce, sig, request.method, path, body,
        replay_check=db.nonce_seen,
    )
    try:
        parsed = json.loads(body or b"{}")
    except Exception:
        parsed = {}
    return ok, reason, parsed
