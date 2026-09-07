# smart_routing/selector.py — Route Selector + Failover + ضد oscillation
# ══════════════════════════════════════════════════════════════════════════════
# انتخاب مسیر فقط از میان endpointهای ACTIVE با egress VERIFIED.
#   • حالت‌ها: OFF / AUTO / LOW_LATENCY / STABLE / IRAN_OPTIMIZED
#   • IRAN_OPTIMIZED: فقط IRAN_EGRESS واقعی (verify دو منبع) اولویت می‌گیرد؛
#     اگر وجود نداشت → بهترین AUTO + یادداشت صادقانه (هرگز ایران جعل نمی‌شود).
#   • hysteresis: سوییچ فقط با اختلاف امتیاز ≥ gap (پیش‌فرض ۱۰٪) + cooldown.
#   • failover: اگر مسیر فعلی خراب شد → انتخاب مجدد فوری (بدون cooldown) +
#     event log — کاربر با refresh ساب لینک جدید می‌گیرد (بدون کانفیگ جدید).
#   • panel-direct: اگر بهترین مسیر خودِ پنل بود → لینک دقیقاً شکل پایه
#     می‌ماند (front == host → هیچ تغییری در لینک).
# ══════════════════════════════════════════════════════════════════════════════

import time

from . import db, scoring

def _main():
    import main
    return main

_SELECT_CACHE: dict[str, tuple[str, str | None, float, float, dict]] = {}
_CACHE_TTL_S = 30.0

PROBEABLE = ("vless-ws", "trojan-ws", "mixed")


def _active_candidates(mode: str) -> list[tuple[dict, dict]]:
    """(endpoint, score) — فقط ACTIVE + egress VERIFIED (قاعده‌ی سند)."""
    out = []
    for ep in db.list_endpoints("ACTIVE"):
        ver = ep.get("verification") or {}
        if (ver.get("egress") or {}).get("status") != "VERIFIED":
            continue
        sc = scoring.score_endpoint(ep, mode)
        out.append((ep, sc))
    return out


def best_route(mode: str = "AUTO") -> dict | None:
    """بهترین مسیر برای حالت — همراه امتیاز و دلیل (برای API/UI)."""
    if mode not in scoring.MODES:
        mode = "AUTO"
    cands = _active_candidates(mode)
    if not cands:
        return None

    def key(item):
        ep, sc = item
        caps = ep.get("capabilities") or {}
        # IRAN_OPTIMIZED: فقط IRAN_EGRESS واقعی (از verify، نه ادعا) اولویت می‌گیرد
        iran_bonus = 1000.0 if (mode == "IRAN_OPTIMIZED" and caps.get("IRAN_EGRESS")) else 0.0
        return iran_bonus + sc["score"]

    cands.sort(key=key, reverse=True)
    ep, sc = cands[0]
    reason = "highest composite score"
    if mode == "IRAN_OPTIMIZED":
        has_iran = any((e.get("capabilities") or {}).get("IRAN_EGRESS") for e, _ in cands)
        reason = ("iran-egress verified route" if (ep.get("capabilities") or {}).get("IRAN_EGRESS")
                  else "no verified iran-egress endpoint — best AUTO fallback (honest)")
    return {"endpoint": ep, "score": sc["score"], "sub": sc["sub"],
            "mode": mode, "reason": reason}


def select_with_hysteresis(mode: str = "AUTO") -> dict | None:
    """انتخاب با hysteresis + cooldown (ضد oscillation) + ثبت selection."""
    gap = float(db.get_setting("selection_gap_pct", 10))
    cooldown = float(db.get_setting("selection_cooldown_s", 120))
    now = time.time()
    best = best_route(mode)
    if best is None:
        return None
    prev = db.last_selection(mode)
    ep_id = best["endpoint"]["id"]
    if prev:
        prev_ep = db.get_endpoint(prev.get("chosen_endpoint_id"))
        prev_alive = prev_ep and prev_ep.get("status") == "ACTIVE" and (
            (prev_ep.get("verification") or {}).get("egress") or {}).get("status") == "VERIFIED"
        if prev_alive:
            prev_score = prev.get("score")
            if prev_score is not None:
                try:
                    if best["score"] <= float(prev_score) * (1 + gap / 100.0):
                        if now - float(prev.get("ts") or 0) < cooldown:
                            # همان مسیر قبلی — سوییچ لازم نیست (ضد oscillation)
                            best["endpoint"] = prev_ep
                            best["score"] = prev_score
                            best["reason"] = "kept previous (hysteresis)"
                            return best
                except (TypeError, ValueError):
                    pass
        else:
            # FAILOVER: مسیر قبلی مرده → انتخاب فوری + event
            db.add_event("failover",
                         f"failover حالت {mode}: مسیر قبلی خراب/غیرفعال → {best['endpoint']['address']}",
                         endpoint_id=ep_id)
            db.add_selection("panel", mode, ep_id, "failover: previous route dead",
                             best["score"])
            best["reason"] = "failover: previous route dead (immediate reselect)"
            return best
    db.add_selection("panel", mode, ep_id, best.get("reason", "selection"),
                     best["score"])
    return best


def _cached_selection(mode: str) -> dict | None:
    now = time.time()
    hit = _SELECT_CACHE.get(mode)
    if hit and now - hit[0] < _CACHE_TTL_S:
        ep = db.get_endpoint(hit[1])
        if ep and ep.get("status") == "ACTIVE":
            return {"endpoint": ep, "score": hit[2], "mode": mode,
                    "reason": hit[4].get("reason")}
    sel = select_with_hysteresis(mode)
    if sel:
        _SELECT_CACHE[mode] = (now, sel["endpoint"]["id"], sel["score"], now,
                               {"reason": sel.get("reason", "")})
    return sel


# ── hookهای main.py (emit-time — sync و fail-safe) ───────────────────────────
def route_front_for(host: str, link: dict, protocol: str):
    """آدرس فرانت برای لینک — None = مسیر مستقیم (بدون هیچ تغییری).

    شرایط: mode≠OFF + پروتکل قابل‌پروب + route ACTIVE/verified + فرانت ≠ host."""
    try:
        mode = ((link or {}).get("smart_routing_mode") or "OFF").upper()
        if mode not in scoring.MODES or mode == "OFF":
            return None
        if protocol not in PROBEABLE:
            return None                     # SS/MTProto/xhttp: صادقانه مستثنا
        sel = _cached_selection(mode)
        if not sel:
            return None
        ep = sel["endpoint"]
        front = ep.get("address")
        if not front:
            return None
        # لینک پایه‌ی EMIX همیشه :443 است → فقط فرانت‌های TLS/443 مسیر لینک می‌شوند
        # (فرانت‌های دیگر فقط پایش/امتیاز می‌گیرند — صداقت در برابر لینک خراب)
        try:
            if int(ep.get("port") or 443) != 443:
                return None
        except (TypeError, ValueError):
            return None
        if front == (host or "").lower() or front == _main().get_host():
            return None                     # مسیر بهترین = خود پنل → لینک پایه
        from . import security
        ok, _reason = security.ssrf_check_host(front)
        if not ok:
            return None
        return front
    except Exception:
        return None


def apply_route_params(params: dict, link: dict, protocol: str) -> None:
    """پارامترهای لینک برای مسیر فعال: sni=فرانت + host=پنل واقعی + بدون allowInsecure.

    دامنه‌ی واقعی از snapshot `_sr_real_host` (ست‌شده در generate_share_link) یا
    get_host() می‌آید. تداخل با SNI spoof (مستند CHANGELOG): پشت فرانت
    workers.dev، SNI جعلی مضر است (لبه‌ی CF SNI ناشناس را رد می‌کند — اندازه‌گیری
    فاز ۴۴) → وقتی route فعال است، spoof نادیده گرفته می‌شود و cert معتبر فرانت
    استفاده می‌شود. SNI Spoofing ماژول مستقل باقی می‌ماند و روی لینک‌های بدون
    route بی‌تغییر است."""
    try:
        from main import get_host as _gh
        _link = link or {}
        real_host = _link.get("_sr_real_host") or _gh()
        front = route_front_for(real_host, _link, protocol)
        if not front:
            return
        params["sni"] = front                 # cert معتبر فرانت (workers.dev)
        params["host"] = real_host            # هدر WS واقعی = دامنه‌ی پنل
        params.pop("allowInsecure", None)     # cert فرانت معتبر است — نیازی نیست
    except Exception:
        pass


# ── گزارش برای API/UI ─────────────────────────────────────────────────────────
def routes_report() -> list[dict]:
    out = []
    for mode in ("AUTO", "LOW_LATENCY", "STABLE", "IRAN_OPTIMIZED"):
        best = best_route(mode)
        if best:
            ep = best["endpoint"]
            out.append({
                "mode": mode, "route_id": ep["id"], "endpoint": ep["address"],
                "port": ep.get("port"), "protocol": ep.get("protocol"),
                "transport": ep.get("transport"), "score": best["score"],
                "latency_ms": ep.get("latency_ms"), "jitter_ms": ep.get("jitter_ms"),
                "packet_loss": ep.get("packet_loss"),
                "country": ep.get("observed_country"), "asn": ep.get("observed_asn"),
                "egress_ip": ep.get("observed_ip"),
                "health": ep.get("health_status"), "status": ep.get("status"),
                "iran_egress": bool((ep.get("capabilities") or {}).get("IRAN_EGRESS")),
                "reason": best.get("reason"),
            })
        else:
            out.append({"mode": mode, "route_id": None,
                        "note": "هیچ مسیر معتبر verified در این حالت نیست — صریح: نه سبز جعلی نه ایران جعلی"})
    return out
