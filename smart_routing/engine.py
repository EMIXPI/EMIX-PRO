# smart_routing/engine.py — ارکستراتور: pipeline کامل + حلقه‌های پس‌زمینه
# ══════════════════════════════════════════════════════════════════════════════
# Pipeline هر endpoint (سند §ENDPOINT DISCOVERY — به‌ترتیب):
#   REACHABILITY(TCP واقعی) → PROTOCOL(مسیر کلاینت واقعی: TLS+WS+بایت‌های
#   پروتکل+HTTP از تونل) → EGRESS(از داخل تونل + منبع مستقل دوم) →
#   GEO/ASN → LATENCY/JITTER/LOSS(چند-پروبی) → SECURITY/POLICY(SSRF) →
#   SCORE(ترکیبی) → POOL(state machine)
#
#   «NO FAKE SUCCESS»: تا traffic واقعاً از مسیر عبور نکند و egress از بیرون
#   دیده نشود، وضعیت UNVERIFIED است — نه SUCCESS.
#
# حلقه‌ها (فقط وقتی flag+settings روشن):
#   discovery هر ۱۵ دقیقه (configurable) · health: فعال ۶۰ث / idle ۳۰۰ث /
#   قرنطینه ۶۰۰ث · egress re-verify وقتی کهنه(>۱h) شد.
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import time

from . import db, discovery, egress, metrics, pool, scoring, security, iran

_tasks: list[asyncio.Task] = []
_STARTED = False
_SEM = asyncio.Semaphore(4)              # هم‌زمانی محدود تست‌ها
_EGRESS_STALE_S = 3600.0
_ENGINE: dict = {"last_health_pass": None, "last_discovery": None,
                 "probe_uid": None, "probe_protocol": None}

HISTORY_LEN = 20                          # سند: آخرین ۲۰ چک


def _ws_base(ep: dict) -> str:
    host, port = ep.get("address"), int(ep.get("port") or 443)
    if port == 443:
        return f"wss://{host}"
    return f"ws://{host}:{port}"


async def _probe_context() -> tuple[str, str] | None:
    """(uid, protocol) لینک پروب معتبر — بدون آن verify واقعی ممکن نیست."""
    if _ENGINE["probe_uid"]:
        return _ENGINE["probe_uid"], _ENGINE["probe_protocol"]
    picked = await metrics.pick_probe_link()
    if not picked:
        return None
    uid, link = picked
    _ENGINE["probe_uid"] = uid
    _ENGINE["probe_protocol"] = link.get("protocol", "vless-ws")
    return _ENGINE["probe_uid"], _ENGINE["probe_protocol"]


def _front_protocol(ep: dict, probe_protocol: str) -> str:
    """پروتکل پروب برای فرانت: اگر فرانت پروتکل خاصی دارد و probe سازگار است."""
    p = ep.get("protocol") or "mixed"
    if p in ("vless-ws", "trojan-ws") and p == probe_protocol:
        return p
    return probe_protocol              # فرانت mixed/ناسازگار → با پروتکل لینک پروب


# ── REACHABILITY ──────────────────────────────────────────────────────────────
async def stage_reachability(ep: dict) -> dict:
    host, port = ep.get("address"), int(ep.get("port") or 443)
    ok, reason = security.ssrf_check_host(host)
    if not ok:
        return {"ok": False, "stage": "reachability",
                "detail": f"SECURITY/POLICY رد شد: {reason}"}
    r = await metrics._link_health()._tcp_ping_only(host, port)
    return {"ok": bool(r.get("ok")), "stage": "reachability",
            "tcp_ms": r.get("tcp_ms"), "detail": r.get("detail")}


# ── PROTOCOL + METRICS (مسیر کلاینت واقعی) ────────────────────────────────────
async def stage_protocol_and_metrics(ep: dict, rounds: int | None = None) -> dict:
    ctx = await _probe_context()
    if ctx is None:
        return {"ok": False, "stage": "protocol",
                "detail": "هیچ لینک فعال WS برای پروب واقعی وجود ندارد —"
                          " verify ممکن نیست (UNVERIFIED، نه شکست جعلی)"}
    uid, probe_protocol = ctx
    proto = _front_protocol(ep, probe_protocol)
    rounds = int(rounds or db.get_setting("probe_rounds", 5))
    m = await metrics.measure_front(ep.get("address"), int(ep.get("port") or 443),
                                    uid, proto, rounds=rounds)
    out = {"ok": bool(m.get("ok")), "stage": "protocol+metrics",
           "latency_ms": m.get("latency_ms"), "jitter_ms": m.get("jitter_ms"),
           "packet_loss": m.get("packet_loss"), "tcp_ms": m.get("tcp_ms"),
           "samples": m.get("samples"), "replies": m.get("replies"),
           "detail": m.get("detail")}
    return out


# ── EGRESS + GEO/ASN ──────────────────────────────────────────────────────────
async def stage_egress(ep: dict) -> dict:
    ctx = await _probe_context()
    if ctx is None:
        return {"ok": False, "status": "UNVERIFIED", "stage": "egress",
                "detail": "لینک پروب موجود نیست"}
    uid, probe_protocol = ctx
    proto = _front_protocol(ep, probe_protocol)
    return await egress.verify_endpoint_egress(
        ep.get("address"), int(ep.get("port") or 443), uid, proto)


# ── PIPELINE کامل یک endpoint ─────────────────────────────────────────────────
async def verify_endpoint(ep_id: str, rounds: int | None = None) -> dict:
    """اجرای pipeline کامل و ثبت نتیجه — خروجی گزارش شفاف stage به stage."""
    ep = db.get_endpoint(ep_id)
    if not ep:
        return {"ok": False, "error": "endpoint یافت نشد"}
    ver: dict = {}
    now = time.time()

    async with _SEM:
        # 1) REACHABILITY (+ SECURITY/POLICY داخل همان)
        r = await stage_reachability(ep)
        ver["reachability"] = r
        if not r.get("ok"):
            ep.update({"latency_ms": None, "jitter_ms": None,
                       "packet_loss": 1.0})
            ep["verification"] = ver
            ep = pool.apply_pool_status(ep, "UNHEALTHY", "reachability fail")
            db.add_event("verify", f"reachability ناموفق: {ep.get('address')} — "
                                   f"{r.get('detail')}", endpoint_id=ep_id)
            _save(ep)
            return {"ok": False, "endpoint": ep.get("address"), "stages": ver,
                    "status": ep.get("status")}

        # 2) PROTOCOL + 3) LATENCY/JITTER/LOSS
        m = await stage_protocol_and_metrics(ep, rounds)
        ver["metrics"] = m
        if not m.get("ok"):
            ep.update({"latency_ms": m.get("latency_ms"),
                       "jitter_ms": m.get("jitter_ms"),
                       "packet_loss": m.get("packet_loss")})
            ep["verification"] = ver
            ep = pool.apply_pool_status(ep, "UNHEALTHY",
                                        "protocol/metrics fail: " + str(m.get("detail"))[:80])
            _save(ep)
            return {"ok": False, "endpoint": ep.get("address"), "stages": ver,
                    "status": ep.get("status")}

        ep.update({"latency_ms": m.get("latency_ms"), "jitter_ms": m.get("jitter_ms"),
                   "packet_loss": m.get("packet_loss")})

        # 4) EGRESS (از داخل تونل) + 5) GEO/ASN (منبع مستقل دوم)
        eg = await stage_egress(ep)
        ver["egress"] = eg
        if eg.get("status") == "INVALID":
            ep["verification"] = ver
            ep = pool.mark_invalid(ep, "egress mismatch: " + json_str(eg.get("mismatch")))
            _save(ep)
            return {"ok": False, "endpoint": ep.get("address"), "stages": ver,
                    "status": "INVALID",
                    "note": "egress با metadata سازگار نیست — endpoint انتخاب نمی‌شود"}

        if eg.get("ok"):
            ep.update({
                "observed_ip": eg.get("observed_ip"),
                "observed_country": eg.get("observed_country"),
                "observed_asn": eg.get("observed_asn"),
                "observed_asn_num": eg.get("observed_asn_num"),
                "egress_ip": eg.get("observed_ip"),
            })
            ep = iran.set_iran_capability(ep, eg)
        else:
            ep = iran.set_iran_capability(ep, {"ok": False, "status": "UNVERIFIED"})

    # 6) SCORE + 7) POOL
    sc = scoring.score_endpoint(ep)
    ep["score"] = sc["score"]
    ep["verification"] = ver
    hist = (ep.get("history") or [])
    hist.insert(0, {"ok": True, "ts": now, "latency_ms": ep.get("latency_ms"),
                    "jitter_ms": ep.get("jitter_ms"),
                    "packet_loss": ep.get("packet_loss")})
    ep["history"] = hist[:HISTORY_LEN]
    ep["uptime_pct"] = _uptime_pct(ep["history"])
    ep["health_status"] = "HEALTHY"
    ep["last_check"] = now
    ep = pool.promote_if_verified(ep)
    _save(ep)
    db.add_health_check(ep_id, True, ep.get("latency_ms"), ep.get("jitter_ms"),
                        ep.get("packet_loss"), {"stages": "full"})
    db.add_event("verify", f"verify کامل: {ep.get('address')} → score={sc['score']} "
                           f"status={ep.get('status')}", endpoint_id=ep_id)
    return {"ok": ep.get("status") == "ACTIVE", "endpoint": ep.get("address"),
            "stages": ver, "score": sc, "status": ep.get("status")}


def json_str(obj) -> str:
    import json as _j
    try:
        return _j.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def _uptime_pct(history: list) -> float:
    if not history:
        return 0.0
    ok_n = sum(1 for h in history if h.get("ok"))
    return round(100.0 * ok_n / len(history), 1)


def _save(ep: dict) -> None:
    ep["updated_at"] = time.time()
    db.upsert_endpoint(ep)


# ── HEALTH PASS (سبک — برای endpointهای موجود در pool) ─────────────────────────
async def health_check_endpoint(ep_id: str) -> dict:
    """چک سلامت دوره‌ای: پروب سبک (۲ راند) + گذار وضعیت pool.

    egress هر ساعت یا در صورت INVALID دوباره verify می‌شود (stale check)."""
    ep = db.get_endpoint(ep_id)
    if not ep:
        return {"ok": False, "error": "endpoint یافت نشد"}
    now = time.time()
    m = await stage_protocol_and_metrics(ep, rounds=2)
    ok = bool(m.get("ok"))
    ep["latency_ms"] = m.get("latency_ms", ep.get("latency_ms"))
    ep["jitter_ms"] = m.get("jitter_ms", ep.get("jitter_ms"))
    ep["packet_loss"] = m.get("packet_loss", ep.get("packet_loss"))
    ep["health_status"] = "HEALTHY" if ok else "UNHEALTHY"
    hist = (ep.get("history") or [])
    hist.insert(0, {"ok": ok, "ts": now, "latency_ms": ep.get("latency_ms"),
                    "jitter_ms": ep.get("jitter_ms"),
                    "packet_loss": ep.get("packet_loss")})
    ep["history"] = hist[:HISTORY_LEN]
    ep["uptime_pct"] = _uptime_pct(ep["history"])
    ep["last_check"] = now

    # egress re-verify وقتی کهنه یا INVALID — چک مکرر سبک نیست
    ver = ep.get("verification") or {}
    eg = ver.get("egress") or {}
    eg_stale = (not eg.get("ts")) or (now - float(eg.get("ts") or 0) > _EGRESS_STALE_S)
    if eg.get("status") == "INVALID" or (eg.get("status") == "VERIFIED" and eg_stale):
        eg2 = await stage_egress(ep)
        eg2["ts"] = now
        ver["egress"] = eg2
        if eg2.get("ok"):
            ep.update({"observed_ip": eg2.get("observed_ip"),
                       "observed_country": eg2.get("observed_country"),
                       "observed_asn": eg2.get("observed_asn")})
            ep = iran.set_iran_capability(ep, eg2)
    ep["verification"] = ver

    ep = pool.apply_pool_status(ep, pool.transition_status(ep, ok),
                                "healthy check" if ok else "check failed")
    sc = scoring.score_endpoint(ep)
    ep["score"] = sc["score"]
    _save(ep)
    db.add_health_check(ep_id, ok, ep.get("latency_ms"), ep.get("jitter_ms"),
                        ep.get("packet_loss"))
    return {"ok": ok, "endpoint": ep.get("address"), "status": ep.get("status"),
            "score": ep.get("score"), "latency_ms": ep.get("latency_ms")}


# ── discovery + verify همه‌ی endpointهای جدید ─────────────────────────────────
async def run_full_cycle() -> dict:
    disc = await discovery.run_discovery()
    verified = []
    for ep in db.list_endpoints():
        if (ep.get("status") or "UNKNOWN") in ("UNKNOWN", "INVALID"):
            v = await verify_endpoint(ep["id"])
            verified.append({"endpoint": ep.get("address"), "ok": v.get("ok"),
                             "status": v.get("status")})
    _ENGINE["last_discovery"] = time.time()
    return {"discovery": disc, "verified": verified}


async def run_health_pass() -> dict:
    """یک پاس سلامت روی همه‌ی endpointها (بر اساس بازه‌ی وضعیتشان)."""
    results = []
    now = time.time()
    for ep in db.list_endpoints():
        status = ep.get("status") or "UNKNOWN"
        interval = {
            "ACTIVE": float(db.get_setting("health_interval_active_s", 60)),
            "DEGRADED": 30.0,
            "UNHEALTHY": float(db.get_setting("health_interval_idle_s", 300)),
            "QUARANTINED": float(db.get_setting("health_interval_quarantine_s", 600)),
            "INVALID": float(db.get_setting("health_interval_idle_s", 300)),
        }.get(status, 300.0)
        last = ep.get("last_check") or 0
        if now - float(last or 0) < interval:
            continue
        r = await health_check_endpoint(ep["id"])
        results.append(r)
    _ENGINE["last_health_pass"] = now
    if results:
        db.add_event("health", f"health pass: {sum(1 for r in results if r.get('ok'))}"
                               f"/{len(results)} سالم")
    return {"checked": len(results), "healthy": sum(1 for r in results if r.get("ok"))}


# ── حلقه‌های پس‌زمینه ──────────────────────────────────────────────────────────
async def _discovery_loop() -> None:
    while True:
        try:
            await run_full_cycle()
        except asyncio.CancelledError:
            return
        except Exception as e:
            db.add_event("engine", f"discovery loop خطا: {str(e)[:80]}")
        await asyncio.sleep(float(db.get_setting("discovery_interval_s", 900)))


async def _health_loop() -> None:
    while True:
        try:
            await run_health_pass()
        except asyncio.CancelledError:
            return
        except Exception as e:
            db.add_event("engine", f"health loop خطا: {str(e)[:80]}")
        await asyncio.sleep(15.0)          # پاس‌های سبک هر ۱۵ ثانیه اسکن می‌شوند


def start_background() -> bool:
    """شروع حلقه‌ها — فقط وقتی env flag + settings enabled هر دو روشن."""
    global _STARTED
    from . import env_flag
    if _STARTED or not env_flag() or not db.get_setting("enabled", False):
        return False
    _STARTED = True
    _tasks.append(asyncio.create_task(_discovery_loop()))
    _tasks.append(asyncio.create_task(_health_loop()))
    db.add_event("engine", "موتور Smart Routing روشن شد (حلقه‌های discovery + health)")
    return True


def stop_background() -> None:
    global _STARTED
    for t in _tasks:
        t.cancel()
    _tasks.clear()
    if _STARTED:
        db.add_event("engine", "موتور Smart Routing خاموش شد (rollback)")
    _STARTED = False


def engine_status() -> dict:
    from . import env_flag
    return {
        "env_flag": env_flag(),
        "settings_enabled": bool(db.get_setting("enabled", False)),
        "active": env_flag() and bool(db.get_setting("enabled", False)),
        "running_loops": _STARTED,
        "last_discovery": db.get_setting("last_discovery"),
        "last_health_pass": _ENGINE.get("last_health_pass"),
        "db": db.db_status(),
        "pool": pool.pool_summary(),
    }
