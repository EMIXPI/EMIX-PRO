# iran_direct.py
# ══════════════════════════════════════════════════════════════════════════════
# 🇮🇷 IRAN_DIRECT — دارایی‌های اندپوینت (IP سالم + هندشیک) + ساخت کانفیگ
#
# هدف (درخواست کاربر): در بخش IRAN_DIRECT بتوان IP سالم (Clean IP) و هندشیک
# (SNI/Host جعلی) را وارد/ذخیره کرد و سپس دقیقاً مثل «ساخت کانفیگ» کانفیگ
# ساخت و تحویل گرفت.
#
# 🔒 قواعد معماری (Phase 38+ — نقض‌ناپذیر):
#   ۱) این ماژول هرگز خودش کانفیگ نمی‌سازد — صفر emitter. ساخت کانفیگ فقط از
#      مسیر کانونی config_builder (preview/generate) انجام می‌شود؛ این ماژول
#      فقط «دارایی‌های اندپوینت» را نگه می‌دارد و اعتبارسنجی می‌کند.
#   ۲) IP سالم دستی = فقط CONFIGURED_ENDPOINT (ورودی اتصال) — هرگز «خروج
#      اثبات‌شده» نیست و هیچ ادعای جغرافیایی به آن گره نمی‌خورد.
#   ۳) هندشیک (SNI) صرفاً معنای TLS/اندپوینت دارد — نه مسیریابی، نه خروج
#      جغرافیایی (SNI ≠ ROUTE ≠ GEO EGRESS).
#   ۴) پروب سرور = فقط شاهد «در دسترس بودن از سرور پنل» — سالم‌بودن از دید
#      ISP کاربر باید از مرورگر خود کاربر سنجیده شود (صادقانه برچسب می‌خورد).
#   ۵) IRAN_DIRECT یعنی خروج ترافیک داخلی از ISP خود کاربر (USER_ISP) —
#      این دارایی‌ها هیچ‌چیز را در تخصیص خروج تغییر نمی‌دهند.
#
# ⚙️ اندپوینت‌ها (همگی require_auth):
#   GET    /api/iran-direct/assets              → {ips, handshakes}
#   POST   /api/iran-direct/ips                 → افزودن IP سالم (اعتبارسنجی‌شده)
#   DELETE /api/iran-direct/ips/{asset_id}      → حذف IP
#   POST   /api/iran-direct/handshakes          → افزودن هندشیک (SNI — hostname)
#   DELETE /api/iran-direct/handshakes/{id}     → حذف هندشیک
#   POST   /api/iran-direct/ips/{id}/probe      → پروب TCP/TLS از سرور پنل
#   POST   /api/iran-direct/use                 → ثبت استفاده (پس از ساخت کانفیگ)
#
# 💾 وضعیت: DATA_DIR/iran_direct_assets.json (ایزوله — حذف ماژول = فقط این
#    بخش از UI غیب می‌شود؛ صفر تغییر در هسته).
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import re
import ssl
import time
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse

try:
    import structured_events as events
except Exception:  # events are best-effort — never block the engine
    events = None

try:
    import endpoint_profiles as ep
except Exception:  # pragma: no cover
    ep = None

# Pydantic models MUST live at module level (function-local classes are
# unresolvable under `from __future__ import annotations` — 422 trap;
# same rule as config_builder/iran_gateway).
from pydantic import BaseModel


class IpIn(BaseModel):
    address: str
    label: str = ""
    port: int = 443
    notes: str = ""


class HandshakeIn(BaseModel):
    sni: str
    label: str = ""
    notes: str = ""


class ProbeIn(BaseModel):
    sni: str = ""
    handshake_id: str = ""


class UseIn(BaseModel):
    ip_id: str = ""
    handshake_id: str = ""

logger = logging.getLogger("emix.iran-direct")

ENGINE_VERSION = "1.0.0"
# Same env var as main.DATA_DIR (no main import — Phase 38+ engine pattern;
# register_routes receives require_auth via DI from main's bootstrap).
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
ASSET_FILE = DATA_DIR / "iran_direct_assets.json"
PROBE_TIMEOUT = 6.0
MAX_ASSETS = 100          # bound per list — a store, not a scanner dump
IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _log(event: str, severity: str = "INFO", **fields) -> None:
    if events is not None:
        try:
            events.log_event(event, severity=severity, **fields)
        except Exception:
            pass


# ── store (JSON, atomic-ish, isolated) ───────────────────────────────────────

def _load() -> dict:
    try:
        if ASSET_FILE.exists():
            data = json.loads(ASSET_FILE.read_text(encoding="utf-8"))
            return {
                "ips": list(data.get("ips", []))[:MAX_ASSETS],
                "handshakes": list(data.get("handshakes", []))[:MAX_ASSETS],
                "updated_at": data.get("updated_at"),
            }
    except Exception as exc:
        logger.warning(f"[iran-direct] load failed: {exc}")
    return {"ips": [], "handshakes": [], "updated_at": None}


def _save(state: dict) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = time.time()
        ASSET_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"[iran-direct] save failed: {exc}")


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _validate_address(value: str) -> str:
    """Endpoint address — IP or hostname (the ONLY endpoint engine decides)."""
    if ep is not None:
        ok, why = ep.validate_hostname(value, allow_ip=True)
        if not ok:
            raise HTTPException(status_code=400,
                                detail=f"آدرس نامعتبر است ({why or value!r})")
    elif not (IPV4_RE.match(value) or re.match(
            r"^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$", value)):
        raise HTTPException(status_code=400, detail="آدرس نامعتبر است")
    return value


def _validate_sni(value: str) -> str:
    """Handshake/SNI — MUST be a hostname (TLS SNI can never be an IP)."""
    if ep is not None:
        ok, why = ep.validate_hostname(value, allow_ip=False)
        if not ok:
            raise HTTPException(
                status_code=400,
                detail=f"هندشیک (SNI) باید دامنه باشد نه IP ({why or value!r})")
    elif _is_ip(value) or not re.match(
            r"^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$", value):
        raise HTTPException(status_code=400,
                            detail="هندشیک (SNI) باید دامنه باشد نه IP")
    return value


def _find(lst: list, asset_id: str) -> Optional[dict]:
    for item in lst:
        if item.get("id") == asset_id:
            return item
    return None


# ── honest server-side probe (evidence, correctly labeled) ───────────────────

async def _probe_address(address: str, port: int,
                         sni: str = "") -> dict:
    """Probe from the PANEL SERVER — never presented as «clean from Iran».

    Two honest levels:
      TCP_REACHABLE — TCP connect to address:port succeeded.
      TLS_VERIFIED  — full TLS handshake with server_hostname=sni and a
                      certificate that actually verifies for that name.
    The result is stored on the asset as last_probe and is shown with the
    caveat that it was measured from the panel deployment, not the user's ISP.
    """
    t0 = time.perf_counter()
    # Level 1: plain TCP reachability
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(address, port), timeout=PROBE_TIMEOUT)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        tcp_ms = round((time.perf_counter() - t0) * 1000)
    except Exception as exc:
        return {"state": "UNREACHABLE", "error": type(exc).__name__,
                "checked_at": time.time(), "from": "panel-server"}

    # Level 2: TLS with SNI (only when a hostname SNI exists)
    if sni:
        t1 = time.perf_counter()
        ctx = ssl.create_default_context()
        try:
            _, tls_writer = await asyncio.wait_for(
                asyncio.open_connection(address, port, ssl=ctx,
                                        server_hostname=sni),
                timeout=PROBE_TIMEOUT)
            tls_ms = round((time.perf_counter() - t1) * 1000)
            try:
                tls_writer.close()
                await tls_writer.wait_closed()
            except Exception:
                pass
            return {"state": "TLS_VERIFIED", "tcp_ms": tcp_ms, "tls_ms": tls_ms,
                    "sni": sni, "checked_at": time.time(),
                    "from": "panel-server"}
        except Exception as exc:
            return {"state": "TCP_REACHABLE", "tcp_ms": tcp_ms, "sni": sni,
                    "tls_error": type(exc).__name__, "checked_at": time.time(),
                    "from": "panel-server"}
    return {"state": "TCP_REACHABLE", "tcp_ms": tcp_ms,
            "checked_at": time.time(), "from": "panel-server"}


# ── API ──────────────────────────────────────────────────────────────────────

def register_routes(app, require_auth) -> None:
    """DI: main passes require_auth (Phase 38+ pattern — no main import)."""
    _auth = [Depends(require_auth)]

    @app.get("/api/iran-direct/assets", dependencies=_auth)
    async def iran_direct_assets():
        state = _load()
        return {"ok": True, "engine": f"iran_direct/{ENGINE_VERSION}",
                "ips": state["ips"], "handshakes": state["handshakes"],
                "note": ("IP/هندشیک دستی فقط CONFIGURED_ENDPOINT است — خروج "
                         "ترافیک داخلی در IRAN_DIRECT از ISP خود کاربر "
                         "(USER_ISP) می‌باشد و به این دارایی‌ها وابسته نیست")}

    @app.post("/api/iran-direct/ips", dependencies=_auth)
    async def iran_direct_ip_add(body: IpIn):
        address = _validate_address(body.address.strip())
        port = int(body.port or 443)
        if ep is not None:
            okp, p = ep.validate_port(port)
            if not okp:
                raise HTTPException(status_code=400,
                                    detail=f"پورت نامعتبر است: {port}")
            port = p
        state = _load()
        if any(i.get("address") == address for i in state["ips"]):
            raise HTTPException(status_code=409,
                                detail="این IP قبلاً ثبت شده است")
        entry = {
            "id": f"ip-{int(time.time()*1000):x}-{len(state['ips'])}",
            "address": address, "label": body.label.strip(),
            "port": port, "notes": body.notes.strip(),
            "created_at": time.time(), "use_count": 0,
            "last_used_at": None, "last_probe": None,
            "verification": "CONFIGURED_ENDPOINT",
        }
        state["ips"].append(entry)
        del state["ips"][:-MAX_ASSETS]
        _save(state)
        _log("IRAN_DIRECT_ASSET_SAVED", kind="ip", address=address, port=port)
        return {"ok": True, "asset": entry}

    @app.delete("/api/iran-direct/ips/{asset_id}", dependencies=_auth)
    async def iran_direct_ip_del(asset_id: str):
        state = _load()
        item = _find(state["ips"], asset_id)
        if item is None:
            return JSONResponse({"ok": False, "errors": ["not found"]},
                                status_code=404)
        state["ips"].remove(item)
        _save(state)
        return {"ok": True, "deleted": asset_id}

    @app.post("/api/iran-direct/handshakes", dependencies=_auth)
    async def iran_direct_hs_add(body: HandshakeIn):
        sni = _validate_sni(body.sni.strip())
        state = _load()
        if any(h.get("sni") == sni for h in state["handshakes"]):
            raise HTTPException(status_code=409,
                                detail="این هندشیک قبلاً ثبت شده است")
        entry = {
            "id": f"hs-{int(time.time()*1000):x}-{len(state['handshakes'])}",
            "sni": sni, "label": body.label.strip(),
            "notes": body.notes.strip(),
            "created_at": time.time(), "use_count": 0, "last_used_at": None,
        }
        state["handshakes"].append(entry)
        del state["handshakes"][:-MAX_ASSETS]
        _save(state)
        _log("IRAN_DIRECT_ASSET_SAVED", kind="handshake", sni=sni)
        return {"ok": True, "asset": entry}

    @app.delete("/api/iran-direct/handshakes/{asset_id}", dependencies=_auth)
    async def iran_direct_hs_del(asset_id: str):
        state = _load()
        item = _find(state["handshakes"], asset_id)
        if item is None:
            return JSONResponse({"ok": False, "errors": ["not found"]},
                                status_code=404)
        state["handshakes"].remove(item)
        _save(state)
        return {"ok": True, "deleted": asset_id}

    @app.post("/api/iran-direct/ips/{asset_id}/probe", dependencies=_auth)
    async def iran_direct_probe(asset_id: str, body: ProbeIn | None = None):
        body = body or ProbeIn()
        state = _load()
        item = _find(state["ips"], asset_id)
        if item is None:
            return JSONResponse({"ok": False, "errors": ["not found"]},
                                status_code=404)
        # SNI for the probe: explicit body sni > handshake_id > none
        sni = (body.sni or "").strip()
        if not sni and body.handshake_id:
            hs = _find(state["handshakes"], body.handshake_id.strip())
            if hs:
                sni = hs.get("sni", "")
        if sni:
            _validate_sni(sni)
        elif _is_ip(item["address"]):
            # TLS to a bare IP without a handshake cannot verify anything —
            # fall back to TCP-only probe (honest, labeled).
            sni = ""
        result = await _probe_address(item["address"], int(item.get("port") or 443), sni)
        item["last_probe"] = result
        _save(state)
        _log("IRAN_DIRECT_PROBE",
             severity="INFO" if result["state"] != "UNREACHABLE" else "WARNING",
             address=item["address"], state=result["state"])
        result["caveat"] = ("اندازه‌گیری از سرور پنل (نه ISP شما) — سالم‌بودن "
                            "از دید اینترنت خودتان را باید از مرورگر تست کنید")
        return {"ok": True, "asset_id": asset_id, "probe": result}

    @app.post("/api/iran-direct/use", dependencies=_auth)
    async def iran_direct_use(body: UseIn):
        """Bump use-counters after a config was generated from the assets."""
        state = _load()
        changed = []
        if body.ip_id:
            item = _find(state["ips"], body.ip_id.strip())
            if item:
                item["use_count"] = int(item.get("use_count", 0)) + 1
                item["last_used_at"] = time.time()
                changed.append(body.ip_id)
        if body.handshake_id:
            item = _find(state["handshakes"], body.handshake_id.strip())
            if item:
                item["use_count"] = int(item.get("use_count", 0)) + 1
                item["last_used_at"] = time.time()
                changed.append(body.handshake_id)
        if changed:
            _save(state)
        return {"ok": True, "marked": changed}


def reset_for_tests() -> None:
    """Tests: wipe the in-file store — each test starts from a clean slate."""
    try:
        if ASSET_FILE.exists():
            ASSET_FILE.unlink()
    except Exception:
        pass


def engine_summary() -> dict:
    state = _load()
    return {"engine": f"iran_direct/{ENGINE_VERSION}",
            "ips": len(state["ips"]),
            "handshakes": len(state["handshakes"])}
