# smart_routing/pool.py — Proxy/Relay Pool پویا (state machine)
# ══════════════════════════════════════════════════════════════════════════════
# وضعیت‌ها (سند §PROXY/RELAY POOL):
#   UNKNOWN     → تازه کشف‌شده؛ هرگز در rotation نیست تا verify کامل
#   ACTIVE      → در rotation (فقط بعد از pipeline کامل موفق)
#   DEGRADED    → کیفیت افت کرده ولی هنوز قابل استفاده با اولویت پایین‌تر
#   UNHEALTHY   → از rotation خارج؛ در انتظار recovery
#   QUARANTINED → مشکوک/خراب؛ چک کند با recovery خودکار
#   INVALID     → verify خراب (egress/metadata mismatch) — تا verify مجدد
#
# قواعد:
#   • هیچ endpoint صرفاً به‌خاطر «در discovery پیدا شدن» active نمی‌شود.
#   • خروج خودکار از rotation و بازگشت خودکار بعد از سلامت پایدار.
#   • همه‌ی گذارها event log می‌شوند (route_events).
# ══════════════════════════════════════════════════════════════════════════════

import time

from . import db

STATUSES = ("UNKNOWN", "ACTIVE", "DEGRADED", "UNHEALTHY", "QUARANTINED", "INVALID")

# آستانه‌های گذار (fail-closed: بدبینانه — سلامت باید «پایدار» باشد)
FAILS_TO_DEGRADED = 2
FAILS_TO_UNHEALTHY = 3
RECOVERY_OK_NEEDED = 2          # دو چک سالم متوالی برای بازگشت
QUARANTINE_RECOVERY_OK_NEEDED = 3
QUARANTINE_MIN_S = 600          # حداقل ۱۰ دقیقه قرنطینه


def _last_history(ep: dict, n: int) -> list:
    h = ep.get("history") or []
    return h[:n]


def transition_status(ep: dict, check_ok: bool) -> str:
    """وضعیت جدید بر اساس تاریخچه + نتیجه‌ی چک تازه (خروجی فقط پیشنهاد وضعیت)."""
    status = ep.get("status") or "UNKNOWN"
    hist = ep.get("history") or []
    recent = [bool(h.get("ok")) for h in hist[:FAILS_TO_UNHEALTHY]]
    if status in ("UNKNOWN", "INVALID"):
        # فقط pipeline کامل (engine) می‌تواند به ACTIVE ببرد — اینجا نمی‌رویم
        return status
    if check_ok:
        ok_run = 0
        for ok in recent:
            if ok:
                ok_run += 1
            else:
                break
        need = (QUARANTINE_RECOVERY_OK_NEEDED if status == "QUARANTINED"
                else RECOVERY_OK_NEEDED)
        if status in ("DEGRADED", "UNHEALTHY") and ok_run >= need:
            return "ACTIVE"
        if status == "QUARANTINED":
            last_q = (ep.get("verification") or {}).get("quarantined_at") or 0
            if ok_run >= need and time.time() - last_q >= QUARANTINE_MIN_S:
                return "ACTIVE"
            return "QUARANTINED"
        return status
    # چک خراب
    fails = 0
    for ok in recent:
        if not ok:
            fails += 1
        else:
            break
    if fails >= FAILS_TO_UNHEALTHY:
        return "UNHEALTHY"
    if fails >= FAILS_TO_DEGRADED:
        return "DEGRADED"
    return status


def apply_pool_status(ep: dict, new_status: str, reason: str) -> dict:
    """ثبت گذار وضعیت + event log — endpoint به‌روز شده برمی‌گردد."""
    old = ep.get("status") or "UNKNOWN"
    if new_status not in STATUSES:
        new_status = "UNKNOWN"
    if new_status != old:
        db.add_event("status", f"وضعیت {ep.get('address')}: {old} → {new_status} — {reason}",
                     endpoint_id=ep.get("id"), detail={"from": old, "to": new_status,
                                                       "reason": reason})
        ep["status"] = new_status
    if new_status == "QUARANTINED":
        ver = ep.get("verification") or {}
        ver["quarantined_at"] = time.time()
        ep["verification"] = ver
    return ep


def promote_if_verified(ep: dict) -> dict:
    """بعد از pipeline موفق: UNKNOWN → ACTIVE (تنها مسیر ورود به rotation).

    استیج‌های الزامی (engine.verify_endpoint): reachability + metrics
    (شامل protocol واقعی از مسیر کلاینت) + egress VERIFIED."""
    if (ep.get("status") or "UNKNOWN") in ("UNKNOWN", "INVALID", "QUARANTINED"):
        ver = ep.get("verification") or {}
        pipeline_ok = all(
            ver.get(k, {}).get("ok")
            for k in ("reachability", "metrics")
        ) and (ver.get("egress") or {}).get("status") == "VERIFIED"
        if pipeline_ok:
            ep["status"] = "ACTIVE"
            db.add_event("status",
                         f"endpoint فعال شد (verify کامل): {ep.get('address')}",
                         endpoint_id=ep.get("id"))
        else:
            ep["status"] = "UNKNOWN" if ep.get("status") != "QUARANTINED" else "QUARANTINED"
    return ep


def quarantine(ep: dict, reason: str) -> dict:
    ver = ep.get("verification") or {}
    ver["quarantined_at"] = time.time()
    ep["verification"] = ver
    return apply_pool_status(ep, "QUARANTINED", reason)


def mark_invalid(ep: dict, reason: str) -> dict:
    ver = ep.get("verification") or {}
    ver["invalid_reason"] = reason
    ep["verification"] = ver
    return apply_pool_status(ep, "INVALID", reason)


def pool_summary() -> dict:
    eps = db.list_endpoints()
    out = {s: 0 for s in STATUSES}
    for e in eps:
        out[e.get("status") or "UNKNOWN"] = out.get(e.get("status") or "UNKNOWN", 0) + 1
    out["total"] = len(eps)
    return out
