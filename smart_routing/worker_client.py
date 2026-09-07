# smart_routing/worker_client.py — ارتباط امضاشده با Worker جدید Cloudflare
# ══════════════════════════════════════════════════════════════════════════════
# Worker: emix-smart-routing-v1 (کاملاً جدید — workerهای قبلی EMIX دست‌نخورده‌اند).
#   • panel → worker: درخواست امضاشده (HMAC + ts + nonce + replay protection)
#   • worker → panel: همان طرح در جهت برگشت (گزارش cron)
#   • secret: هرگز hardcode — ثبت از UI/API در smart_settings (ذخیره در Volume)
#   • Worker فقط component شبکه‌ای/control-plane است — «VPN exit جادویی» نیست.
# ══════════════════════════════════════════════════════════════════════════════

import json
import time

import httpx

from . import db, security

WORKER_NAME = "emix-smart-routing-v1"


def worker_base() -> str:
    u = (db.get_setting("worker_url") or "").strip()
    return u.rstrip("/")


def worker_key() -> str:
    return (db.get_setting("worker_key") or "").strip()


def has_worker() -> bool:
    return bool(worker_base() and worker_key())


async def _signed_call(method: str, path: str, body: dict | None = None,
                       timeout: float = 20.0) -> dict:
    """درخواست امضاشده به Worker — خطاها honest برمی‌گردند (نه سبز جعلی).

    امضا روی «بدنه‌ی واقعاً ارسال‌شده» محاسبه می‌شود (GET بدون body → b"")."""
    base = worker_base()
    key = worker_key()
    if not base or not key:
        return {"ok": False, "error": "worker ثبت نشده (URL/کلید)"}
    send_body = (json.dumps(body or {}, ensure_ascii=False).encode()
                 if method.upper() in ("POST", "PUT") else b"")
    headers = security.make_signed_headers(key, method, path, send_body)
    headers["Content-Type"] = "application/json"
    try:
        async with httpx.AsyncClient(timeout=timeout) as cli:
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
        async with httpx.AsyncClient(timeout=15.0) as cli:
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
    """بررسی کامل Worker (اتصال، امضا، لبه، upstream) — گزارش honest."""
    out = {
        "worker": WORKER_NAME,
        "base": worker_base(),
        "registered": has_worker(),
        "health": await worker_health(),
        "edge_info": None,
        "probe_upstream": None,
    }
    if has_worker():
        out["edge_info"] = await worker_edge_info()
        out["probe_upstream"] = await worker_probe_upstream()
        auth_ok = bool((out["edge_info"] or {}).get("ok"))
        out["authenticated"] = auth_ok
        db.add_event("worker", f"worker-check: authenticated={auth_ok}, "
                               f"upstream_ok={(out['health'] or {}).get('upstream', {}).get('ok')}")
    return out


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
