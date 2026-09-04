# iran_gateway.py — Iran Gateway / IRAN_PROXY engine (Phase 38+ spec §13)
#
# "🇮🇷 پروکسی ایران" — a REAL Iranian gateway/exit for Iranian destinations.
#
#   IRAN_DIRECT : no Iranian server required (client-side split tunnel, USER_ISP)
#   IRAN_PROXY  : requires a REAL Iranian gateway — this engine.
#
# Architecture:
#   Client → EMIX Entry/Relay → Iran Gateway → Iran Internet
#
# Honesty rules (spec §13 — absolute):
#   * A manually entered Iranian IP is CONFIGURED, never VERIFIED.
#   * SNI is never proof. Hostname is never proof. Cloudflare is never proof.
#     Railway region is never proof. ONLY network evidence establishes egress.
#   * VERIFIED_IRAN_EGRESS requires a measured egress IP geolocated to IR.
#   * Observed egress outside IR → ROUTE_MISMATCH (never masked as Iran).
#   * Provider failures become UNKNOWN, never HEALTHY.
#
# Gateway states (spec §13):
#   UNCONFIGURED → CONFIGURED → REACHABLE → HEALTHY → DEGRADED → UNREACHABLE
#   plus egress verdicts: VERIFIED_IRAN_EGRESS | ROUTE_MISMATCH | UNKNOWN
#   plus UNSUPPORTED (probe not possible for this gateway protocol).

from __future__ import annotations
import asyncio
import json
import re
import time
import uuid as _uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, List

import structured_events as events

# Pydantic models MUST live at module level (function-local classes are
# unresolvable under `from __future__ import annotations` — 422 trap).
from pydantic import BaseModel


class GatewayIn(BaseModel):
    gateway_id: str = ""
    name: str
    endpoint: str
    port: int
    protocol: str = "custom"
    auth_username: str = ""
    auth_password: str = ""
    endpoint_profile_id: str = ""
    notes: str = ""
    enabled: bool = True

ENGINE_VERSION = "1.0.0"

GATEWAY_STATES = (
    "UNCONFIGURED", "CONFIGURED", "REACHABLE", "HEALTHY", "DEGRADED",
    "UNREACHABLE", "VERIFIED_IRAN_EGRESS", "ROUTE_MISMATCH", "UNSUPPORTED",
    "UNKNOWN",
)

# Gateway protocols the probe layer can actually verify today.
SUPPORTED_PROTOCOLS = ("http", "socks5", "emix-worker")
# "custom" = operator-managed gateway with no probeable surface (egress UNKNOWN).

EGRESS_TTL_S = 3600.0        # measured egress evidence validity
REACH_TTL_S = 600.0          # reachability evidence validity
PROBE_TIMEOUT_S = 12.0
IR_COUNTRY_CODES = ("IR",)

DEFAULT_EGRESS_PROBE_URL = "https://ipapi.co/json/"   # JSON: ip, country_code, asn, org
_HTTP_FALLBACK_PROBE_URL = "http://ifconfig.me/ip"   # socks5 plain-HTTP path (IP only)


# ── Registry model ───────────────────────────────────────────────────────────

@dataclass
class Gateway:
    gateway_id: str
    name: str
    endpoint: str                     # hostname or IP (public address; not secret)
    port: int
    protocol: str = "custom"          # http | socks5 | emix-worker | custom
    enabled: bool = True
    auth_username: str = ""           # gateway auth (if required) — NEVER logged,
    auth_password: str = ""           # masked in API, used only by probes/compile
    endpoint_profile_id: str = ""     # optional TLS/endpoint semantics (canonical EP engine)
    notes: str = ""
    created_at: float = field(default_factory=time.time)
    # observed evidence (never configured claims):
    last_check: Optional[dict] = None  # reachability + latency + error
    last_egress: Optional[dict] = None  # measured egress evidence

    def to_dict(self, mask_secrets: bool = True) -> dict:
        d = dict(self.__dict__)
        if mask_secrets:
            d.pop("auth_password", None)
            d["auth_username"] = self.auth_username if self.auth_username else ""
            d["auth_configured"] = bool(self.auth_username or self.auth_password)
            d.pop("auth_username", None) if self.auth_password and not self.auth_username else None
        d["created_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.created_at))
        d["state"] = gateway_state(self)
        d["state_reason"] = state_reason(self)
        return d


_gateways: Dict[str, Gateway] = {}
_lock = asyncio.Lock()

# DI seams (no import cycles): fetch for the emix-worker HTTP probe
_fetch_http = None


def set_fetch_fn(fn) -> None:
    global _fetch_http
    _fetch_http = fn


def reset_for_tests() -> None:
    _gateways.clear()
    global _fetch_http
    _fetch_http = None


# ── State derivation (evidence-based, never optimistic) ─────────────────────

def _egress_fresh(gw: Gateway) -> bool:
    ev = gw.last_egress or {}
    ts = ev.get("timestamp")
    return bool(ts) and (time.time() - float(ts)) <= EGRESS_TTL_S


def _reach_fresh(gw: Gateway) -> bool:
    ck = gw.last_check or {}
    ts = ck.get("at")
    return bool(ts) and (time.time() - float(ts)) <= REACH_TTL_S


def gateway_state(gw: Gateway) -> str:
    if not gw.enabled:
        return "CONFIGURED" if (gw.last_check or gw.last_egress) else "UNCONFIGURED"
    if gw.protocol not in SUPPORTED_PROTOCOLS:
        # custom gateways: egress can never be verified by this engine
        ck = gw.last_check
        if ck and _reach_fresh(gw):
            return "UNSUPPORTED" if ck.get("reachable") else "UNREACHABLE"
        return "CONFIGURED" if ck is None else ("UNSUPPORTED" if (ck or {}).get("reachable") else "UNREACHABLE")
    # egress verdict has precedence when fresh
    ev = gw.last_egress or {}
    if _egress_fresh(gw) and ev.get("ok"):
        cc = (ev.get("country_code") or "").upper()
        if cc in IR_COUNTRY_CODES:
            return "VERIFIED_IRAN_EGRESS"
        if cc:
            return "ROUTE_MISMATCH"
        return "UNKNOWN"
    ck = gw.last_check or {}
    if not _reach_fresh(gw) and ck:
        return "DEGRADED" if ck.get("reachable") else "UNREACHABLE"
    if not ck:
        return "CONFIGURED"
    if ck.get("reachable"):
        return "HEALTHY" if ck.get("ok") else "REACHABLE"
    return "UNREACHABLE"


def state_reason(gw: Gateway) -> str:
    st = gateway_state(gw)
    ev = gw.last_egress or {}
    ck = gw.last_check or {}
    reasons = {
        "UNCONFIGURED": "no Iranian gateway is registered",
        "CONFIGURED": "registered — not yet verified (configured ≠ verified)",
        "REACHABLE": f"TCP reachable ({ck.get('latency_ms')}ms) — egress not yet measured",
        "HEALTHY": "reachable + probe healthy — egress not yet classified",
        "DEGRADED": "evidence stale — re-verification required",
        "UNREACHABLE": (ck.get("error") or "last reachability check failed"),
        "VERIFIED_IRAN_EGRESS": f"measured egress {ev.get('public_ip')} → {ev.get('country')} (IR) — network evidence",
        "ROUTE_MISMATCH": f"measured egress {ev.get('public_ip')} → {ev.get('country_code')} "
                          f"— expected IR; this is NOT Iranian egress",
        "UNSUPPORTED": "gateway protocol has no probeable egress surface — egress stays UNKNOWN",
        "UNKNOWN": "no usable evidence",
    }
    return reasons.get(st, "unknown state")


# ── Registry CRUD ───────────────────────────────────────────────────────────

_NAME_RE = re.compile(r"^[\w\-\u0600-\u06FF .:]{1,64}$")
_HOST_RE = re.compile(r"^[a-zA-Z0-9._\-]+$")


def validate_gateway(name: str, endpoint: str, port: int, protocol: str) -> List[str]:
    problems = []
    if not name or not _NAME_RE.fullmatch(name or ""):
        problems.append("name required (1-64 chars)")
    if not endpoint or not _HOST_RE.fullmatch((endpoint or "").strip()):
        problems.append(f"invalid endpoint {endpoint!r} — hostname or IP expected")
    try:
        p = int(port)
        if not (1 <= p <= 65535):
            raise ValueError
    except (TypeError, ValueError):
        problems.append(f"invalid port {port!r} (1-65535)")
    if protocol not in SUPPORTED_PROTOCOLS + ("custom",):
        problems.append(f"unsupported gateway protocol {protocol!r} — "
                        f"{SUPPORTED_PROTOCOLS + ('custom',)}")
    return problems


async def upsert_gateway(gateway_id: str = "", name: str = "", endpoint: str = "",
                         port: int = 0, protocol: str = "custom",
                         auth_username: str = "", auth_password: str = "",
                         endpoint_profile_id: str = "", notes: str = "",
                         enabled: bool = True) -> dict:
    """Create or update. Updating an existing gateway KEEPS its evidence
    (unless the endpoint changed — then evidence is invalidated: a new
    endpoint is a new network reality)."""
    problems = validate_gateway(name, endpoint, port, protocol)
    if problems:
        return {"ok": False, "errors": problems}
    async with _lock:
        gid = (gateway_id or "").strip() or f"gw-{_uuid.uuid4().hex[:10]}"
        existing = _gateways.get(gid)
        if existing is not None and (existing.endpoint != endpoint.strip()
                                     or int(existing.port) != int(port)):
            existing.last_check = None
            existing.last_egress = None
            events.log_event("IRAN_GATEWAY_CHECK", severity="WARNING",
                             action="endpoint-changed-evidence-reset",
                             gateway=gid, note="configured endpoint changed — "
                             "previous verification no longer applies")
        gw = existing or Gateway(gateway_id=gid, name="", endpoint="", port=0,
                                 protocol=protocol)
        gw.name = name.strip()
        gw.endpoint = endpoint.strip()
        gw.port = int(port)
        gw.protocol = protocol.strip().lower()
        gw.enabled = bool(enabled)
        if auth_username is not None:
            gw.auth_username = auth_username.strip()
        if auth_password:
            gw.auth_password = auth_password        # only overwrite when provided
        elif existing is not None and auth_password == "":
            gw.auth_password = existing.auth_password if existing else ""
        gw.endpoint_profile_id = (endpoint_profile_id or "").strip()
        gw.notes = (notes or "").strip()
        _gateways[gid] = gw
        out = gw.to_dict()
    return {"ok": True, "gateway": out}


async def delete_gateway(gateway_id: str) -> dict:
    async with _lock:
        removed = _gateways.pop(gateway_id, None)
    if removed is None:
        return {"ok": False, "errors": [f"gateway '{gateway_id}' not found"]}
    return {"ok": True, "deleted": gateway_id}


def get_gateway(gateway_id: str) -> Optional[Gateway]:
    return _gateways.get(gateway_id)


def list_gateways() -> List[dict]:
    return [gw.to_dict() for gw in _gateways.values()]


# ── Client-config chaining (v12.2 Iran-Exit) ─────────────────────────────────
# فقط گیت‌وی‌هایی که کلاینت می‌تواند hop زنجیره‌ای dial کند (http/socks5) و
# خروجی‌شان «اندازه‌گیری‌شده» ایرانی است — CONFIGURED هرگز کافی نیست.

CLIENT_CHAINABLE_PROTOCOLS = ("http", "socks5")


def best_client_chainable_gateway() -> Optional[dict]:
    """بهترین گیت‌وی برای زنجیره‌ی Iran-Exit در کانفیگ کلاینت:
    VERIFIED_IRAN_EGRESS تازه + پروتکل قابل-dial (http/socks5).
    credential واقعی فقط از این مسیر بیرون می‌رود (ساخت کانفیگ کلاینت)؛
    APIهای لیست همیشه ماسک می‌کنند. بدون گیت‌وی واجد شرایط → None
    (تماس‌گیرنده صادقانه NO_VERIFIED_IRAN_GATEWAY می‌دهد)."""
    best: Optional[Gateway] = None
    best_ts = -1.0
    for gw in _gateways.values():
        if not gw.enabled or gw.protocol not in CLIENT_CHAINABLE_PROTOCOLS:
            continue
        if gateway_state(gw) != "VERIFIED_IRAN_EGRESS":
            continue
        ts = float((gw.last_egress or {}).get("timestamp") or 0)
        if ts > best_ts:
            best, best_ts = gw, ts
    if best is None:
        return None
    return {
        "gateway_id": best.gateway_id, "name": best.name,
        "endpoint": best.endpoint, "port": best.port,
        "protocol": best.protocol,
        "username": best.auth_username or "",
        "password": best.auth_password or "",
        "egress_ip": (best.last_egress or {}).get("public_ip"),
    }


# ── Probes (real network evidence) ───────────────────────────────────────────

async def _tcp_reachable(endpoint: str, port: int, timeout: float = PROBE_TIMEOUT_S) -> dict:
    t0 = time.time()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(endpoint, port), timeout=timeout)
        latency_ms = round((time.time() - t0) * 1000, 1)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return {"reachable": True, "latency_ms": latency_ms, "ok": True}
    except Exception as exc:
        return {"reachable": False, "error": str(exc)[:200], "ok": False,
                "at": time.time()}


async def _probe_egress_http(gw: Gateway) -> dict:
    """HTTP forward-proxy gateway: measure egress through the proxy (httpx)."""
    try:
        import httpx
    except Exception as exc:
        return {"ok": False, "error": f"httpx unavailable: {exc}"}
    proxy_auth = ""
    if gw.auth_username or gw.auth_password:
        proxy_auth = f"{gw.auth_username}:{gw.auth_password}@"
    proxy_url = f"http://{proxy_auth}{gw.endpoint}:{gw.port}"
    t0 = time.time()
    try:
        async with httpx.AsyncClient(proxy=proxy_url, timeout=PROBE_TIMEOUT_S,
                                     headers={"User-Agent": "EMIX-IranGateway/1.0"},
                                     follow_redirects=True) as client:
            r = await client.get(DEFAULT_EGRESS_PROBE_URL)
            data = r.json()
            return {
                "ok": True, "public_ip": data.get("ip"),
                "country": data.get("country"), "country_code": data.get("country_code"),
                "asn": data.get("asn"), "isp": data.get("org"),
                "latency_ms": round((time.time() - t0) * 1000, 1),
                "measurement_source": f"gateway-http-proxy:{gw.endpoint}",
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


async def _probe_egress_socks5(gw: Gateway) -> dict:
    """SOCKS5 gateway: minimal SOCKS5 CONNECT + plain-HTTP IP echo through the
    tunnel (real TCP egress measurement; no DNS-through-tunnel tricks)."""
    t0 = time.time()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(gw.endpoint, gw.port), timeout=PROBE_TIMEOUT_S)
    except Exception as exc:
        return {"ok": False, "error": f"connect: {exc}"[:200]}
    try:
        # greeting: we support no-auth (0) or user/pass (2)
        methods = b"\x05\x01\x00" if not (gw.auth_username or gw.auth_password) else b"\x05\x01\x02"
        writer.write(methods)
        await writer.drain()
        resp = await asyncio.wait_for(reader.readexactly(2), timeout=PROBE_TIMEOUT_S)
        if resp[0] != 0x05:
            raise ValueError(f"bad SOCKS version {resp[0]}")
        chosen = resp[1]
        if chosen == 0x02:
            u = (gw.auth_username or "").encode()
            p = (gw.auth_password or "").encode()
            if len(u) > 255 or len(p) > 255:
                raise ValueError("socks5 credentials too long")
            writer.write(bytes([0x01, len(u)]) + u + bytes([len(p)]) + p)
            await writer.drain()
            auth_resp = await asyncio.wait_for(reader.readexactly(2), timeout=PROBE_TIMEOUT_S)
            if auth_resp[1] != 0x00:
                raise ValueError("socks5 auth rejected")
        elif chosen == 0xFF:
            raise ValueError("socks5: no acceptable auth method")
        # CONNECT to ifconfig.me:80 (plain HTTP echo — fine for IP measurement)
        host = b"ifconfig.me"
        writer.write(b"\x05\x01\x00\x03" + bytes([len(host)]) + host +
                     (80).to_bytes(2, "big"))
        await writer.drain()
        hdr = await asyncio.wait_for(reader.readexactly(4), timeout=PROBE_TIMEOUT_S)
        if hdr[1] != 0x00:
            raise ValueError(f"socks5 CONNECT failed (code {hdr[1]})")
        atyp = hdr[3]
        if atyp == 0x01:
            await reader.readexactly(4 + 2)
        elif atyp == 0x04:
            await reader.readexactly(16 + 2)
        elif atyp == 0x03:
            ln = (await reader.readexactly(1))[0]
            await reader.readexactly(ln + 2)
        # tunnel established → plain HTTP GET
        writer.write(b"GET /ip HTTP/1.1\r\nHost: ifconfig.me\r\n"
                     b"User-Agent: EMIX-IranGateway/1.0\r\nConnection: close\r\n\r\n")
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(4096), timeout=PROBE_TIMEOUT_S)
        text = raw.decode("utf-8", "replace")
        m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", text)
        if not m:
            raise ValueError("no IP found in probe response")
        public_ip = m.group(1)
        out = {"ok": True, "public_ip": public_ip,
               "latency_ms": round((time.time() - t0) * 1000, 1),
               "measurement_source": f"gateway-socks5:{gw.endpoint}"}
        # enrich with geo lookup from the panel (measured IP → country)
        geo = await _geo_lookup(public_ip)
        if geo.get("ok"):
            out.update({"country": geo.get("country"),
                        "country_code": geo.get("country_code"),
                        "asn": geo.get("asn"), "isp": geo.get("isp")})
        else:
            out["geo_note"] = "IP measured through the gateway; geolocation lookup failed — country UNKNOWN"
        return out
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _probe_egress_worker(gw: Gateway) -> dict:
    """emix-worker gateway: the gateway exposes /exit-check-style JSON."""
    url = f"https://{gw.endpoint}:{gw.port}/exit-check"
    headers = {}
    if gw.auth_password:
        headers["x-emix-token"] = gw.auth_password
    fetch = _fetch_http
    t0 = time.time()
    try:
        if fetch is not None:
            data = await fetch(url, headers=headers)
        else:
            import httpx
            async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S, headers=headers,
                                         follow_redirects=True) as client:
                r = await client.get(url)
                r.raise_for_status()
                data = r.json()
        if isinstance(data, dict) and (data.get("exit_ip") or data.get("public_ip") or data.get("ip")):
            return {
                "ok": True,
                "public_ip": data.get("exit_ip") or data.get("public_ip") or data.get("ip"),
                "country": data.get("exit_country") or data.get("country"),
                "country_code": (data.get("exit_country_code") or data.get("country_code") or "").upper(),
                "asn": data.get("exit_asn") or data.get("asn"),
                "isp": data.get("exit_isp") or data.get("isp"),
                "latency_ms": round((time.time() - t0) * 1000, 1),
                "measurement_source": f"gateway-worker:{gw.endpoint}",
            }
        return {"ok": False, "error": "unexpected probe response shape"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


async def _geo_lookup(ip: str) -> dict:
    """Panel-side geolocation of a MEASURED IP (configures nothing)."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"https://ipapi.co/{ip}/json/",
                                 headers={"User-Agent": "EMIX-IranGateway/1.0"})
            data = r.json()
            if data.get("error"):
                return {"ok": False, "error": str(data.get("reason", "provider error"))[:120]}
            return {"ok": True, "country": data.get("country"),
                    "country_code": (data.get("country_code") or "").upper(),
                    "asn": data.get("asn"), "isp": data.get("org")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:120]}


async def check_gateway(gateway_id: str) -> dict:
    """Full check: reachability + (protocol-dependent) egress measurement.
    Verdicts: VERIFIED_IRAN_EGRESS / ROUTE_MISMATCH / reachable-only / failure."""
    gw = _gateways.get(gateway_id)
    if gw is None:
        return {"ok": False, "errors": [f"gateway '{gateway_id}' not found"]}
    reach = await _tcp_reachable(gw.endpoint, gw.port)
    reach["at"] = time.time()
    gw.last_check = reach
    egress: dict = {"ok": False, "error": "not probed"}
    if reach.get("reachable") and gw.protocol in SUPPORTED_PROTOCOLS:
        if gw.protocol == "http":
            egress = await _probe_egress_http(gw)
        elif gw.protocol == "socks5":
            egress = await _probe_egress_socks5(gw)
        elif gw.protocol == "emix-worker":
            egress = await _probe_egress_worker(gw)
        egress["timestamp"] = time.time()
        gw.last_egress = egress
    elif not reach.get("reachable"):
        gw.last_egress = None  # unreachable gateway invalidates egress evidence
    state = gateway_state(gw)
    # structured event — never secrets (scrubbed centrally)
    events.log_event("IRAN_GATEWAY_CHECK",
                     severity="INFO" if state == "VERIFIED_IRAN_EGRESS" else
                     ("WARNING" if state in ("ROUTE_MISMATCH", "UNREACHABLE", "DEGRADED") else "INFO"),
                     gateway=gateway_id, name=gw.name, state=state,
                     reachable=reach.get("reachable"),
                     latency_ms=reach.get("latency_ms"),
                     egress_ip=egress.get("public_ip"),
                     egress_country=egress.get("country_code"))
    return {
        "ok": True, "gateway_id": gateway_id, "state": state,
        "state_reason": state_reason(gw),
        "reachability": reach,
        "egress": egress if egress.get("ok") or gw.protocol in SUPPORTED_PROTOCOLS else None,
        "expected_country": "IR",
        "note": "only network evidence establishes Iranian egress — a configured "
                "Iranian IP alone is never VERIFIED",
    }


async def check_all() -> dict:
    results = {}
    for gid in list(_gateways.keys()):
        results[gid] = await check_gateway(gid)
    return results


# ── IRAN_PROXY attribution (consumed by domestic_route_engine via DI) ────────

def iran_proxy_egress_status() -> dict:
    """The honest IRAN_PROXY egress answer for routing decisions.
    VERIFIED_IRAN_EGRESS only with fresh measured evidence."""
    best = None
    for gw in _gateways.values():
        if not gw.enabled:
            continue
        st = gateway_state(gw)
        if st == "VERIFIED_IRAN_EGRESS":
            best = gw
            break
        if best is None and st in ("HEALTHY", "REACHABLE"):
            best = best or gw
    if best is None and _gateways:
        first = next(iter(_gateways.values()))
        st = gateway_state(first)
        verdict = ("ROUTE_MISMATCH" if st == "ROUTE_MISMATCH"
                   else "NO_VERIFIED_IRAN_GATEWAY")
        return {"configured": True, "state": st,
                "egress": "IRAN_GATEWAY (UNVERIFIED — no healthy gateway)",
                "verdict": verdict}
    if best is None:
        return {"configured": False, "state": "UNCONFIGURED",
                "egress": "NONE — IRAN_PROXY requires a real Iranian gateway",
                "verdict": "IRAN_GATEWAY_UNCONFIGURED"}
    ev = (best.last_egress or {})
    st = gateway_state(best)
    return {
        "configured": True, "gateway": best.name, "state": st,
        "egress": f"IRAN_GATEWAY ({best.endpoint})" if st == "VERIFIED_IRAN_EGRESS"
                  else f"IRAN_GATEWAY (state {st} — expected egress, NOT verified)",
        "egress_ip": ev.get("public_ip") if st == "VERIFIED_IRAN_EGRESS" else None,
        "country_code": ev.get("country_code") if st == "VERIFIED_IRAN_EGRESS" else None,
        "verdict": "VERIFIED_IRAN_EGRESS" if st == "VERIFIED_IRAN_EGRESS" else
                   ("ROUTE_MISMATCH" if st == "ROUTE_MISMATCH" else "NO_VERIFIED_IRAN_GATEWAY"),
    }


def summary() -> dict:
    gateways = list_gateways()
    states = {}
    for g in gateways:
        states[g["state"]] = states.get(g["state"], 0) + 1
    verified = [g for g in gateways if g["state"] == "VERIFIED_IRAN_EGRESS"]
    overall = "UNCONFIGURED" if not gateways else (
        "VERIFIED_IRAN_EGRESS" if verified else
        (gateways[0]["state"] if len(gateways) == 1 else "MIXED"))
    return {
        "engine": f"iran_gateway/{ENGINE_VERSION}",
        "state": overall,
        "gateways": len(gateways),
        "by_state": states,
        "verified_count": len(verified),
        "iran_proxy_status": iran_proxy_egress_status(),
        "rule": "IRAN_DIRECT needs no Iranian server (USER_ISP). IRAN_PROXY needs a "
                "REAL gateway — VERIFIED_IRAN_EGRESS only from measured evidence.",
    }


# ── Persistence (rvg_state.json additive key "iran_gateway") ─────────────────

def persist_snapshot() -> dict:
    return {"gateways": [
        {k: v for k, v in gw.__dict__.items()} for gw in _gateways.values()
    ]}


def restore_snapshot(data: dict) -> None:
    _gateways.clear()
    for d in (data or {}).get("gateways", []):
        try:
            keep = {k: v for k, v in d.items() if k in Gateway.__dataclass_fields__}
            _gateways[keep["gateway_id"]] = Gateway(**keep)
        except Exception:
            continue


# ── API (authed — spec §28) ─────────────────────────────────────────────────

def register_routes(app, require_auth) -> None:
    from fastapi import Depends, Query
    from fastapi.responses import JSONResponse
    @app.get("/api/iran-gateway", dependencies=[Depends(require_auth)])
    async def api_list():
        return JSONResponse({"ok": True, "gateways": list_gateways(), **summary()})

    @app.post("/api/iran-gateway", dependencies=[Depends(require_auth)])
    async def api_upsert(body: GatewayIn):
        out = await upsert_gateway(**body.model_dump())
        code = 200 if out.get("ok") else 400
        return JSONResponse(out, status_code=code)

    @app.get("/api/iran-gateway/status", dependencies=[Depends(require_auth)])
    async def api_status():
        return JSONResponse({"ok": True, **summary()})

    @app.post("/api/iran-gateway/{gateway_id}/check",
              dependencies=[Depends(require_auth)])
    async def api_check(gateway_id: str):
        out = await check_gateway(gateway_id)
        return JSONResponse(out, status_code=200 if out.get("ok") else 404)

    @app.delete("/api/iran-gateway/{gateway_id}",
                dependencies=[Depends(require_auth)])
    async def api_delete(gateway_id: str):
        out = await delete_gateway(gateway_id)
        return JSONResponse(out, status_code=200 if out.get("ok") else 404)
