# smart_routing/discovery.py — Endpoint Discovery (منابع عمومی مجاز)
# ══════════════════════════════════════════════════════════════════════════════
# قاعده‌ی سند: «Discovery نباید اینترنت را به شکل uncontrolled scan کند».
# منابع مجاز (allowlist — اسکن تصادفی ممنوع و پیاده‌سازی نشده):
#   1) panel-links   → endpointهای واقعی خود پنل (آدرس عمومی + پروتکل‌ها)
#   2) cf-worker     → Worker جدید emix-smart-routing-v1 (پس از ثبت در settings)
#   3) manual        → candidateهای اپراتور (host:port) — SSRF-guarded
#   4) public-list   → URLهای https منابع عمومی (پیش‌فرض خالی؛ فقط https؛
#                      هر خط host[:port]؛ SSRF-guarded؛ rate-limited)
#
# Pipeline (سند):
#   DISCOVER → NORMALIZE → REACHABILITY → PROTOCOL → EGRESS → GEO/ASN →
#   LATENCY → JITTER → PACKET LOSS → SECURITY/POLICY → SCORE → POOL
#   (استیج‌های بعدی در engine.run_pipeline اجرا می‌شوند)
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import re

import httpx

from . import db, security

def _main():
    import main
    return main

# شکل قابل قبول candidate: hostname[:port] یا host:port
_HOST_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.\_]*[a-zA-Z0-9])?$")


def normalize_candidate(address: str, port=443) -> dict | None:
    """NORMALIZE: hostname معتبر کوچک/بدون اسلش — نامعتبر → None.

    ورودی «host:port» هم پذیرفته می‌شود (port جدا‌گانه اولویت دارد)."""
    a = (address or "").strip().lower().rstrip(".")
    if not a:
        return None
    if a.startswith("http://") or a.startswith("https://"):
        a = a.split("://", 1)[1].split("/", 1)[0]
    if "/" in a or "@" in a:
        return None
    # شکل host:port — پورت داخل رشته
    if ":" in a:
        host_part, _, port_part = a.rpartition(":")
        if host_part and port_part.isdigit():
            a = host_part
            try:
                port = int(port_part)
            except ValueError:
                port = 443
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", a):
        ok, reason = security.ssrf_check_host(a)
        if not ok:
            return None
    elif not _HOST_RE.match(a):
        return None
    try:
        p = int(port)
    except (TypeError, ValueError):
        p = 443
    if not (1 <= p <= 65535):
        return None
    return {"address": a, "port": p}


def _new_ep(address: str, port: int, source: str, protocol: str = "mixed",
            transport: str = "ws", capabilities: dict | None = None) -> dict:
    eid = db.endpoint_id_for(address, port)
    return {
        "id": eid, "address": address, "port": port, "protocol": protocol,
        "transport": transport, "tls": 1, "sni": address,
        "source": source, "status": "UNKNOWN", "health_status": "UNKNOWN",
        "capabilities": capabilities or {}, "verification": {}, "history": [],
        "created_at": None, "updated_at": None, "last_check": None,
    }


async def discover_from_panel_links() -> list[dict]:
    """منبع ۱ — endpoint خود پنل (آدرس عمومی). همه‌ی لینک‌های WS یک فرانت مشترک
    دارند → یک endpoint با قابلیت‌های پروتکل تجمیعی."""
    m = _main()
    host = m.get_host()
    if not host or host in ("localhost", "127.0.0.1", "0.0.0.0"):
        # حالت لوکال/تست: فرانت محلی معتبر است اما status UNKNOWN می‌ماند
        host = host or "127.0.0.1"
    protos = set()
    async with m.LINKS_LOCK:
        for l in m.LINKS.values():
            p = l.get("protocol", m.DEFAULT_PROTOCOL)
            if p in ("vless-ws", "trojan-ws"):
                protos.add(p)
    if not protos:
        protos = {"vless-ws"}       # فرانت پنل همیشه VLESS-WS دارد (default link)
    ep = _new_ep(host, 443, "panel-link", protocol=",".join(sorted(protos)),
                 capabilities={"PANEL_DIRECT": True})
    return [ep]


async def discover_from_worker() -> list[dict]:
    """منبع ۲ — Worker جدید (emix-smart-routing-v1)؛ فقط اگر URL ثبت شده باشد."""
    wurl = (db.get_setting("worker_url") or "").strip()
    if not wurl:
        return []
    ok, reason = security.ssrf_safe_url(wurl)
    if not ok:
        db.add_event("discovery", f"worker_url رد شد (SSRF/نامعتبر): {reason}")
        return []
    host = wurl.split("://", 1)[1].split("/", 1)[0].rsplit(":", 1)[0]
    ep = _new_ep(host, 443, "cf-worker", protocol="mixed",
                 capabilities={"CF_EDGE": True})
    return [ep]


async def discover_from_manual() -> list[dict]:
    """منبع ۳ — candidateهای اپراتور (هرگز بدون verify فعال نمی‌شوند)."""
    out = []
    for c in (db.get_setting("manual_candidates") or []):
        if isinstance(c, str):
            c = {"address": c}
        norm = normalize_candidate(c.get("address", ""), c.get("port", 443))
        if not norm:
            db.add_event("discovery",
                         f"candidate دستی نامعتبر رد شد: {c.get('address')!r}")
            continue
        ok, reason = security.ssrf_check_host(norm["address"])
        if not ok:
            db.add_event("discovery",
                         f"candidate دستی رد شد ({reason}): {norm['address']}")
            continue
        out.append(_new_ep(norm["address"], norm["port"], "manual",
                           capabilities={"OPERATOR_ADDED": True,
                                         "note": str(c.get("note", ""))[:120]}))
    return out


async def discover_from_public_lists() -> list[dict]:
    """منبع ۴ — URLهای عمومی https (پیش‌فرض خالی = هیچ fetchای)."""
    out = []
    urls = db.get_setting("public_list_urls") or []
    for u in urls:
        u = str(u).strip()
        if not u:
            continue
        ok, reason = security.ssrf_safe_url(u)
        if not ok or not u.lower().startswith("https://"):
            db.add_event("discovery", f"public-list رد شد: {reason or 'https الزامی'} — {u[:60]}")
            continue
        allowed, _ = await security.rate_limit(f"public-list:{u}", max_per_window=2, window_s=300)
        if not allowed:
            continue
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as cli:
                r = await cli.get(u)
            if r.status_code != 200:
                db.add_event("discovery", f"public-list HTTP {r.status_code}: {u[:60]}")
                continue
            lines = [ln.strip() for ln in r.text.splitlines() if ln.strip()]
        except Exception as e:
            db.add_event("discovery", f"public-list خطا: {str(e)[:60]} — {u[:60]}")
            continue
        for ln in lines[:200]:               # سقف safety
            parts = ln.split()
            cand = parts[0] if parts else ""
            port = 443
            if ":" in cand and cand.rsplit(":", 1)[1].isdigit():
                cand, port = cand.rsplit(":", 1)
            norm = normalize_candidate(cand, port)
            if not norm:
                continue
            okh, _ = security.ssrf_check_host(norm["address"])
            if okh:
                out.append(_new_ep(norm["address"], norm["port"], "public-list"))
    return out


async def run_discovery() -> dict:
    """DISCOVER همه‌ی منابع → ثبت UNKNOWN (verify جداگانه — هرگز auto-active)."""
    results = await asyncio.gather(
        discover_from_panel_links(),
        discover_from_worker(),
        discover_from_manual(),
        discover_from_public_lists(),
        return_exceptions=True,
    )
    found: list[dict] = []
    errors = []
    for r in results:
        if isinstance(r, Exception):
            errors.append(str(r)[:80])
        elif isinstance(r, list):
            found.extend(r)
    now = _now()
    for ep in found:
        old = db.get_endpoint(ep["id"])
        if old:                            # discovery مجدد: متادیتای جدید، status فعلی حفظ
            merged = {**old, "address": ep["address"], "port": ep["port"],
                      "source": ep["source"], "protocol": ep["protocol"],
                      "capabilities": {**(old.get("capabilities") or {}),
                                       **(ep.get("capabilities") or {})},
                      "updated_at": now}
            db.upsert_endpoint(merged)
        else:
            ep["created_at"] = now
            db.upsert_endpoint(ep)
            db.add_event("discovery", f"endpoint کشف شد: {ep['address']}:{ep['port']} "
                                      f"(منبع: {ep['source']})", endpoint_id=ep["id"])
    db.set_setting("last_discovery", now)
    db.add_event("discovery", f"Discovery کامل شد: {len(found)} endpoint "
                              f"({len(errors)} خطای منبع)")
    return {"discovered": len(found), "errors": errors,
            "sources": ["panel-links", "cf-worker", "manual", "public-list"],
            "note": "endpoints به‌صورت UNKNOWN ثبت شدند — ورود به pool فقط با verify کامل"}


def _now() -> float:
    import time
    return time.time()
