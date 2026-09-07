# smart_routing/api.py — اندپوینت‌های /api/smart-routing/* (احراز هویت EMIX reuse)
# ══════════════════════════════════════════════════════════════════════════════
# طبق سند §API — authentication فعلی EMIX (require_auth) reuse می‌شود؛
# secret جدید hardcode نمی‌شود. Worker→panel با امضای HMAC (replay-guarded).
# ══════════════════════════════════════════════════════════════════════════════

import asyncio

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from . import (db, discovery, engine, egress, iran, pool, scoring, selector,
               security, worker_client)
from . import env_flag

_HEADERS_NO_STORE = {"Cache-Control": "no-store"}


def _guarded(guard: bool, msg: str):
    if not guard:
        raise HTTPException(status_code=503, detail=msg)


def register_routes(app) -> None:
    # main فقط اینجا import می‌شود (فراخواننده‌ی register_routes همیشه app از main
    # گرفته — یعنی main حتماً بارگذاری شده؛ ترتیب import هرگز circular نمی‌شود).
    from main import require_auth, LINKS, LINKS_LOCK, log_activity, save_state, \
        generate_share_link, get_host

    # ── startup: schema additive + شروع حلقه‌ها فقط اگر flag+settings روشن ────
    @app.on_event("startup")
    async def _sr_startup():
        try:
            db.ensure_schema()
            db.add_event("engine", f"Smart Routing v{__import__('smart_routing').__version__} "
                                   f"بارگذاری شد (env_flag={env_flag()})")
            engine.start_background()      # فقط وقتی env flag + settings هر دو روشن
        except Exception as e:
            db.add_event("engine", f"startup خطا: {str(e)[:80]}")

    # ═══ status ═════════════════════════════════════════════════════════════
    @app.get("/api/smart-routing/status")
    async def sr_status(_=Depends(require_auth)):
        return JSONResponse({
            "ok": True,
            "engine": engine.engine_status(),
            "worker": {"registered": worker_client.has_worker(),
                       "url": worker_client.worker_base() or None,
                       "name": worker_client.WORKER_NAME},
            "pool": pool.pool_summary(),
            "iran_egress": iran.iran_egress_report(),
            "iran_direct": iran.iran_direct_summary(),
            "feature": "Smart Routing Network v1",
            "sni_spoofing_independent": True,
        }, headers=_HEADERS_NO_STORE)

    # ═══ routes ════════════════════════════════════════════════════════════
    @app.get("/api/smart-routing/routes")
    async def sr_routes(_=Depends(require_auth)):
        return JSONResponse({"ok": True, "routes": selector.routes_report()},
                            headers=_HEADERS_NO_STORE)

    @app.get("/api/smart-routing/routes/best")
    async def sr_routes_best(_=Depends(require_auth)):
        best = selector.select_with_hysteresis("AUTO")
        if not best:
            return JSONResponse({"ok": False,
                                 "reason": "هیچ مسیر verified فعالی وجود ندارد — "
                                           "سیستم صریحاً اعلام می‌کند: مسیر معتبر نیست"},
                                headers=_HEADERS_NO_STORE)
        ep = best["endpoint"]
        return JSONResponse({"ok": True, "route": {
            "route_id": ep["id"], "endpoint": ep["address"], "port": ep.get("port"),
            "protocol": ep.get("protocol"), "transport": ep.get("transport"),
            "latency_ms": ep.get("latency_ms"), "country": ep.get("observed_country"),
            "asn": ep.get("observed_asn"), "health": ep.get("health_status"),
            "score": best.get("score"), "mode": best.get("mode"),
            "reason": best.get("reason"),
        }}, headers=_HEADERS_NO_STORE)

    # ═══ endpoints ═════════════════════════════════════════════════════════
    @app.get("/api/smart-routing/endpoints")
    async def sr_endpoints(_=Depends(require_auth)):
        out = []
        for ep in db.list_endpoints():
            out.append({
                "id": ep.get("id"), "endpoint": ep.get("address"), "port": ep.get("port"),
                "country": ep.get("observed_country"), "asn": ep.get("observed_asn"),
                "egress_ip": ep.get("observed_ip"),
                "latency_ms": ep.get("latency_ms"), "jitter_ms": ep.get("jitter_ms"),
                "packet_loss": ep.get("packet_loss"),
                "health": ep.get("health_status"), "status": ep.get("status"),
                "score": ep.get("score"),
                "last_check": ep.get("last_check"), "source": ep.get("source"),
                "capabilities": ep.get("capabilities"),
            })
        return JSONResponse({"ok": True, "endpoints": out}, headers=_HEADERS_NO_STORE)

    # ═══ health ════════════════════════════════════════════════════════════
    @app.get("/api/smart-routing/health")
    async def sr_health(_=Depends(require_auth)):
        eps = db.list_endpoints()
        active = [e for e in eps if e.get("status") == "ACTIVE"]
        lat = [e["latency_ms"] for e in active if e.get("latency_ms")]
        jit = [e["jitter_ms"] for e in active if e.get("jitter_ms")]
        loss = [e["packet_loss"] for e in active if e.get("packet_loss") is not None]
        return JSONResponse({"ok": True, "pool": pool.pool_summary(),
                             "metrics": {
                                 "best_latency_ms": min(lat) if lat else None,
                                 "avg_latency_ms": round(sum(lat) / len(lat), 1) if lat else None,
                                 "avg_jitter_ms": round(sum(jit) / len(jit), 1) if jit else None,
                                 "avg_packet_loss": round(sum(loss) / len(loss), 3) if loss else None,
                             },
                             "events": db.recent_events(15),
                             "last_health_pass": engine.engine_status().get("last_health_pass")},
                            headers=_HEADERS_NO_STORE)

    # ═══ test (pipeline کامل روی یک endpoint) ══════════════════════════════
    @app.post("/api/smart-routing/test")
    async def sr_test(request: Request, _=Depends(require_auth)):
        _guarded(env_flag(), "feature flag خاموش است (SMART_ROUTING_ENABLED)")
        allowed, retry = await security.rate_limit("sr-test", max_per_window=6)
        if not allowed:
            raise HTTPException(429, "نرخ تست زیاد است — چند لحظه بعد")
        body = {}
        try:
            body = await request.json()
        except Exception:
            body = {}
        ep_id = str(body.get("endpoint_id") or "").strip()
        if not ep_id:
            raise HTTPException(400, "endpoint_id الزامی است")
        result = await engine.verify_endpoint(ep_id)
        return JSONResponse({"ok": bool(result.get("ok")), **result},
                            headers=_HEADERS_NO_STORE)

    # ═══ refresh (discovery + verify همه) ══════════════════════════════════
    @app.post("/api/smart-routing/refresh")
    async def sr_refresh(_=Depends(require_auth)):
        _guarded(env_flag(), "feature flag خاموش است (SMART_ROUTING_ENABLED)")
        allowed, _ = await security.rate_limit("sr-refresh", max_per_window=3, window_s=300)
        if not allowed:
            raise HTTPException(429, "نرخ discovery زیاد است (سقف هر ۵ دقیقه ۳ بار)")
        result = await engine.run_full_cycle()
        log_activity("system", f"Smart Routing refresh: {result.get('discovery', {}).get('discovered', 0)} endpoint کشف، {len(result.get('verified', []))} verify", "ok")
        return JSONResponse({"ok": True, **result}, headers=_HEADERS_NO_STORE)

    # ═══ select (انتخاب دستی مسیر برای یک لینک) ═══════════════════════════
    @app.post("/api/smart-routing/select")
    async def sr_select(request: Request, _=Depends(require_auth)):
        _guarded(env_flag(), "feature flag خاموش است (SMART_ROUTING_ENABLED)")
        body = await request.json()
        uid = str(body.get("uid") or "").strip()
        mode = str(body.get("mode") or "OFF").upper()
        if mode not in scoring.MODES:
            raise HTTPException(400, f"mode نامعتبر — حالت‌ها: {', '.join(scoring.MODES)}")
        async with LINKS_LOCK:
            link = LINKS.get(uid)
            if not link:
                raise HTTPException(404, "کانفیگ یافت نشد")
            proto = link.get("protocol", "vless-ws")
            if mode != "OFF" and proto not in ("vless-ws", "trojan-ws"):
                raise HTTPException(400, "Smart Routing فقط برای کانفیگ‌های VLESS-WS و"
                                         " Trojan-WS قابل اعمال است (صداقت — نه سکوت)")
            link["smart_routing_mode"] = mode
        db.add_selection(uid, mode, "manual", "admin manual select", None)
        db.add_event("selection", f"حالت مسیریابی «{mode}» روی کانفیگ {uid} ست شد")
        log_activity("link", f"Smart Routing ({mode}) برای کانفیگ تنظیم شد", "ok")
        asyncio.create_task(save_state())
        route = None
        if mode != "OFF":
            best = selector.best_route(mode)
            if best:
                ep = best["endpoint"]
                route = {"route_id": ep["id"], "endpoint": ep["address"],
                         "latency_ms": ep.get("latency_ms"),
                         "country": ep.get("observed_country"),
                         "asn": ep.get("observed_asn"),
                         "health": ep.get("health_status"), "score": best.get("score")}
        return JSONResponse({"ok": True, "uid": uid, "mode": mode,
                             "selected_route": route or "هیچ مسیر verified فعالی نیست — لینک مستقیم می‌ماند"},
                            headers=_HEADERS_NO_STORE)

    # ═══ egress (گزارش verify واقعی) ══════════════════════════════════════
    @app.get("/api/smart-routing/egress")
    async def sr_egress(_=Depends(require_auth)):
        baseline = await egress.panel_egress_baseline()
        out = {"ok": True, "panel_baseline": baseline, "endpoints": []}
        for ep in db.list_endpoints():
            ver = (ep.get("verification") or {}).get("egress") or {}
            out["endpoints"].append({
                "endpoint": ep.get("address"),
                "status": ver.get("status", "UNVERIFIED"),
                "observed_ip": ep.get("observed_ip"),
                "observed_country": ep.get("observed_country"),
                "observed_asn": ep.get("observed_asn"),
                "iran_egress": bool((ep.get("capabilities") or {}).get("IRAN_EGRESS")),
                "probe": {k: (ver.get("source_a") or {}).get(k)
                          for k in ("ws_ms", "e2e_ms", "status_line")},
            })
        return JSONResponse(out, headers=_HEADERS_NO_STORE)

    # ═══ settings (تگل/تنظیم وزن‌ها/worker/iran-direct) ════════════════════
    @app.post("/api/smart-routing/settings")
    async def sr_settings(request: Request, _=Depends(require_auth)):
        body = await request.json()
        changed = []
        if "enabled" in body:
            val = bool(body["enabled"])
            db.set_setting("enabled", val)
            if val:
                engine.start_background()
            else:
                engine.stop_background()
            changed.append(f"enabled={val}")
            log_activity("system", f"Smart Routing {'روشن' if val else 'خاموش'} شد",
                         "ok" if val else "warn")
        if "worker_url" in body:
            u = str(body.get("worker_url") or "").strip().rstrip("/")
            if u:
                ok, reason = security.ssrf_safe_url(u)
                if not ok:
                    raise HTTPException(400, f"worker_url نامعتبر: {reason}")
            db.set_setting("worker_url", u)
            changed.append("worker_url")
        if "worker_key" in body:
            k = str(body.get("worker_key") or "").strip()
            db.set_setting("worker_key", k)
            changed.append("worker_key")
        if "score_weights" in body:
            w = body["score_weights"]
            if not isinstance(w, dict):
                raise HTTPException(400, "score_weights باید object باشد")
            total = sum(float(v) for v in w.values() if isinstance(v, (int, float)))
            if not (0.9 <= total <= 1.1):
                raise HTTPException(400, f"جمع وزن‌ها باید ≈۱ باشد (الان {round(total, 3)})")
            db.set_setting("score_weights", w)
            changed.append("score_weights")
        if "manual_candidates" in body:
            mc = body["manual_candidates"]
            if not isinstance(mc, list):
                raise HTTPException(400, "manual_candidates باید آرایه باشد")
            norm = []
            for c in mc[:50]:
                if isinstance(c, str):
                    c = {"address": c}
                n = discovery.normalize_candidate(c.get("address", ""), c.get("port", 443))
                if n:
                    norm.append({**n, "note": str(c.get("note", ""))[:120]})
            db.set_setting("manual_candidates", norm)
            changed.append(f"manual_candidates({len(norm)})")
        if "public_list_urls" in body:
            urls = [str(u).strip() for u in (body["public_list_urls"] or [])[:10]]
            for u in urls:
                if u and not u.lower().startswith("https://"):
                    raise HTTPException(400, "public_list فقط https مجاز است")
            db.set_setting("public_list_urls", [u for u in urls if u])
            changed.append("public_list_urls")
        if "iran_direct_enabled" in body:
            val = bool(body["iran_direct_enabled"])
            db.set_setting("iran_direct_enabled", val)
            changed.append(f"iran_direct_enabled={val}")
            log_activity("system", f"Iran Direct {'روشن' if val else 'خاموش'} شد",
                         "ok" if val else "warn")
        if "probe_rounds" in body:
            try:
                n = int(body["probe_rounds"])
                if not (2 <= n <= 10):
                    raise ValueError
                db.set_setting("probe_rounds", n)
                changed.append(f"probe_rounds={n}")
            except (TypeError, ValueError):
                raise HTTPException(400, "probe_rounds بین ۲ تا ۱۰")
        db.add_event("engine", "تنظیمات تغییر کرد: " + ", ".join(changed))
        return JSONResponse({"ok": True, "changed": changed,
                             "settings": db.all_settings()}, headers=_HEADERS_NO_STORE)

    @app.get("/api/smart-routing/settings")
    async def sr_get_settings(_=Depends(require_auth)):
        return JSONResponse({"ok": True, "env_flag": env_flag(),
                             "settings": db.all_settings()}, headers=_HEADERS_NO_STORE)

    # ═══ worker: گزارش cron از Worker (امضاشده — بدون session) ═════════════
    @app.post("/api/smart-routing/worker/report")
    async def sr_worker_report(request: Request):
        ok, reason, body = await worker_client.verify_worker_request(request)
        if not ok:
            return JSONResponse({"ok": False, "error": f"درخواست Worker رد شد: {reason}"},
                                status_code=401, headers=_HEADERS_NO_STORE)
        db.add_event("worker", f"گزارش Worker: upstream_ok={body.get('upstream_ok')} "
                               f"latency={body.get('upstream_latency_ms')}ms "
                               f"colo={body.get('colo')}")
        return JSONResponse({"ok": True, "received": True}, headers=_HEADERS_NO_STORE)

    @app.get("/api/smart-routing/worker/status")
    async def sr_worker_status(_=Depends(require_auth)):
        # بدون گارد env flag — بررسی Worker بخشی از راه‌اندازی است (قبل از روشن
        # کردن flag هم باید بتوان Worker را ثبت و تست کرد).
        report = await worker_client.worker_full_check()
        return JSONResponse({"ok": bool(report.get("authenticated")), **report},
                            headers=_HEADERS_NO_STORE)

    # ═══ فعال‌سازی env flag روی Railway (بعد از تست — سند) ═══════════════
    @app.post("/api/smart-routing/enable-env-flag")
    async def sr_enable_env_flag(request: Request, _=Depends(require_auth)):
        body = {}
        try:
            body = await request.json()
        except Exception:
            body = {}
        enable = bool(body.get("enable", True))
        from . import railway_flag
        result = await railway_flag.set_env_flag(enable)
        db.add_event("engine", f"درخواست فعال‌سازی env flag (enable={enable}): "
                               f"ok={result.get('ok')}")
        if result.get("ok"):
            msg = (f"SMART_ROUTING_ENABLED={enable} در Railway ثبت شد — "
                   "redeploy خودکار در راه است (~۱-۲ دقیقه)")
            level = "ok"
        else:
            msg = (f"SMART_ROUTING_ENABLED={enable} ثبت نشد — "
                   f"{result.get('error') or result.get('manual', '')}")
            level = "warn"
        log_activity("system", msg, level)
        return JSONResponse(result, headers=_HEADERS_NO_STORE)

    @app.get("/api/smart-routing/env-flag")
    async def sr_env_flag_info(_=Depends(require_auth)):
        from . import railway_flag
        return JSONResponse({"ok": True, "env_flag": env_flag(),
                             "has_railway_token": railway_flag.has_railway_token(),
                             "note": "فعال‌سازی: POST /api/smart-routing/enable-env-flag {\"enable\": true} — یا دستی در dashboard"},
                            headers=_HEADERS_NO_STORE)

    # ═══ iran-direct rules (دانلود پیکربندی split-routing) ════════════════
    @app.get("/api/smart-routing/iran-direct/rules")
    async def sr_iran_rules(_=Depends(require_auth)):
        if not iran.iran_direct_enabled():
            return JSONResponse({"ok": False,
                                 "reason": "Iran Direct خاموش است — ابتدا از تنظیمات فعال کنید"},
                                status_code=409, headers=_HEADERS_NO_STORE)
        # لینک پیش‌فرض پنل به‌عنوان outbound پروکسی (کلاینت جایگزین می‌کند)
        async with LINKS_LOCK:
            uid, link = next(iter(LINKS.items()), (None, None))
        proto = (link or {}).get("protocol", "vless-ws")
        proxy_link = (generate_share_link(uid, get_host(), remark="EMIX-Smart", protocol=proto)
                      if uid else "")
        cfg = iran.build_iran_direct_config(proxy_link)
        return JSONResponse({"ok": True, "config": cfg,
                             "domains": iran.IR_DIRECT_DOMAINS},
                            headers=_HEADERS_NO_STORE)
