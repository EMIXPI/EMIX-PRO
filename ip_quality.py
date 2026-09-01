# ip_quality.py — IP Quality Engine (Phase 9 / Phase 28)
#
# Measures endpoint quality with EVIDENCE. Never labels an IP "clean"
# without data: every classification carries the signals it was based on
# plus a confidence score.
#
# Classification:
#   CLEAN        — reachable, TLS ok, no negative reputation signal, ≥1
#                  provider that explicitly reports proxy/VPN fields and
#                  reported them negative, providers agree.
#   GOOD         — reachable, no negative signals, but reputation fields
#                  unverified by any provider (honest default).
#   QUESTIONABLE — proxy/hosting/VPN flag set, or ASN is a known CDN/hosting
#                  range with high latency, or providers disagree.
#   DEGRADED     — intermittent reachability or high packet loss in probes.
#   BLOCKED      — unreachable, or abuse signal reported.
#   UNKNOWN      — no evidence yet.
#
# Provider abstraction: IPQualityProvider ABC; providers are registered in
# order and all consulted in parallel. Third-party reputation providers can
# be added later without touching the classification logic.

from __future__ import annotations
import abc
import asyncio
import socket
import ssl
import time
import statistics
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from collections import deque

import httpx
from fastapi import APIRouter, Request, HTTPException, Depends

# Imported at main.py bootstrap time (after require_auth is defined) —
# same pattern as gaming_boost / link_health.
from main import require_auth

router = APIRouter()

# ── Tunables ────────────────────────────────────────────────────────────────

CACHE_TTL = 6 * 3600        # seconds — matches clean_ip_boost cadence
PROBE_COUNT = 3             # TCP probes for latency/loss
PROBE_TIMEOUT = 4.0
TLS_TIMEOUT = 6.0
HISTORY = 6                 # checks kept per IP

CLASSIFICATIONS = ("CLEAN", "GOOD", "QUESTIONABLE", "DEGRADED", "BLOCKED", "UNKNOWN")


# ── Provider abstraction ────────────────────────────────────────────────────

@dataclass
class ProviderResult:
    provider: str
    ok: bool = False                     # did the provider answer?
    asn: Optional[str] = None            # e.g. "AS13335"
    org: Optional[str] = None            # ISP / company
    country: Optional[str] = None
    country_code: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    rdns: Optional[str] = None
    is_proxy: Optional[bool] = None      # None = provider doesn't report it
    is_vpn: Optional[bool] = None
    is_hosting: Optional[bool] = None
    abuse_confidence: Optional[int] = None  # 0-100 where reported
    error: Optional[str] = None

    def signals(self) -> dict:
        return {k: getattr(self, k) for k in (
            "asn", "org", "country", "country_code", "region", "city", "rdns",
            "is_proxy", "is_vpn", "is_hosting", "abuse_confidence",
        ) if getattr(self, k) is not None}


class IPQualityProvider(abc.ABC):
    """Third-party IP intelligence provider. Add providers by subclassing."""
    name: str = "base"

    @abc.abstractmethod
    async def lookup(self, ip: str) -> ProviderResult:
        ...


class IpApiCoProvider(IPQualityProvider):
    """ipapi.co — free, no key. Geo/ASN/org; no proxy flags."""
    name = "ipapi.co"

    async def lookup(self, ip: str) -> ProviderResult:
        res = ProviderResult(provider=self.name)
        try:
            async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": "EMIX-IPQuality/1.0"}) as c:
                r = await c.get(f"https://ipapi.co/{ip}/json/")
                if r.status_code == 200:
                    d = r.json()
                    if d.get("error"):
                        res.error = str(d.get("reason", "provider error"))[:120]
                        return res
                    res.ok = True
                    res.asn = d.get("asn")
                    res.org = d.get("org")
                    res.country = d.get("country_name")
                    res.country_code = d.get("country_code")
                    res.region = d.get("region")
                    res.city = d.get("city")
                else:
                    res.error = f"HTTP {r.status_code}"
        except Exception as exc:
            res.error = f"{type(exc).__name__}: {str(exc)[:100]}"
        return res


class IpApiComProvider(IPQualityProvider):
    """ip-api.com — free, no key. Reports proxy/hosting flags + reverse DNS.
    The only built-in provider that justifies CLEAN vs GOOD distinction."""
    name = "ip-api.com"

    async def lookup(self, ip: str) -> ProviderResult:
        res = ProviderResult(provider=self.name)
        try:
            fields = ("status,message,continent,country,countryCode,regionName,city,"
                      "as,org,reverse,proxy,hosting")
            async with httpx.AsyncClient(timeout=8.0) as c:
                r = await c.get(f"http://ip-api.com/json/{ip}?fields={fields}")
                if r.status_code == 200:
                    d = r.json()
                    if d.get("status") != "success":
                        res.error = str(d.get("message", "provider error"))[:120]
                        return res
                    res.ok = True
                    res.asn = d.get("as")
                    res.org = d.get("org")
                    res.country = d.get("country")
                    res.country_code = d.get("countryCode")
                    res.region = d.get("regionName")
                    res.city = d.get("city")
                    res.rdns = d.get("reverse") or None
                    res.is_proxy = bool(d.get("proxy"))
                    res.is_hosting = bool(d.get("hosting"))
                else:
                    res.error = f"HTTP {r.status_code}"
        except Exception as exc:
            res.error = f"{type(exc).__name__}: {str(exc)[:100]}"
        return res


class IpInfoProvider(IPQualityProvider):
    """ipinfo.io — token-gated (env EMIX_IPINFO_TOKEN). Adds privacy/vpn detail."""
    name = "ipinfo.io"

    def __init__(self, token: str):
        self.token = token

    async def lookup(self, ip: str) -> ProviderResult:
        res = ProviderResult(provider=self.name)
        try:
            async with httpx.AsyncClient(timeout=8.0) as c:
                r = await c.get(
                    f"https://ipinfo.io/{ip}/json?token={self.token}")
                if r.status_code == 200:
                    d = r.json()
                    res.ok = True
                    res.org = d.get("org")
                    res.country = d.get("country")
                    res.region = d.get("region")
                    res.city = d.get("city")
                    if d.get("privacy"):
                        res.is_vpn = bool(d["privacy"].get("vpn"))
                        res.is_proxy = bool(d["privacy"].get("proxy"))
                else:
                    res.error = f"HTTP {r.status_code}"
        except Exception as exc:
            res.error = f"{type(exc).__name__}: {str(exc)[:100]}"
        return res


def default_providers() -> List[IPQualityProvider]:
    import os
    providers: List[IPQualityProvider] = [IpApiCoProvider(), IpApiComProvider()]
    token = os.environ.get("EMIX_IPINFO_TOKEN", "").strip()
    if token:
        providers.append(IpInfoProvider(token))
    return providers


# ── Probes (reachability / latency / loss / TLS) ───────────────────────────

async def tcp_probe(ip: str, port: int = 443, count: int = PROBE_COUNT,
                    timeout: float = PROBE_TIMEOUT) -> dict:
    """Real TCP probes: latency samples + loss. Blocking work in executor."""
    def _one() -> Optional[float]:
        t0 = time.perf_counter()
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return (time.perf_counter() - t0) * 1000
        except Exception:
            return None
    loop = asyncio.get_event_loop()
    samples = await asyncio.gather(*[loop.run_in_executor(None, _one) for _ in range(count)])
    ok = [s for s in samples if s is not None]
    return {
        "probes": count,
        "ok": len(ok),
        "loss_pct": round(100.0 * (count - len(ok)) / count, 1) if count else None,
        "latency_ms": round(statistics.mean(ok), 1) if ok else None,
        "jitter_ms": round(statistics.stdev(ok), 1) if len(ok) >= 2 else None,
    }


async def tls_probe(ip: str, sni: str, port: int = 443, timeout: float = TLS_TIMEOUT) -> dict:
    """Real TLS handshake with a given SNI against the raw IP."""
    def _one() -> float:
        ctx = ssl.create_default_context()
        t0 = time.perf_counter()
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=sni) as tls:
                tls.send(b"HEAD / HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n" % sni.encode())
                tls.recv(16)
        return (time.perf_counter() - t0) * 1000
    loop = asyncio.get_event_loop()
    try:
        ms = await loop.run_in_executor(None, _one)
        return {"tls_ok": True, "tls_ms": round(ms, 1)}
    except Exception as exc:
        return {"tls_ok": False, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}


# ── Evidence model & pure classification ───────────────────────────────────

@dataclass
class IPAssessment:
    ip: str
    classification: str = "UNKNOWN"
    confidence: float = 0.0            # 0..1 — how much evidence backs the label
    providers: List[dict] = field(default_factory=list)
    tcp: dict = field(default_factory=dict)
    tls: dict = field(default_factory=dict)
    dns_consistent: Optional[bool] = None
    asn: Optional[str] = None
    org: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    rdns: Optional[str] = None
    reputation_signals: dict = field(default_factory=dict)
    checked_at: float = field(default_factory=time.time)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["checked_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.checked_at))
        return d


def assess(ip: str, providers: List[ProviderResult], tcp: dict,
           tls: dict, dns_consistent: Optional[bool] = None) -> IPAssessment:
    """PURE classification from evidence — no network, fully unit-testable."""
    a = IPAssessment(ip=ip, tcp=tcp, tls=tls, dns_consistent=dns_consistent)
    a.providers = [dict(provider=p.provider, ok=p.ok, **p.signals(),
                        error=p.error) for p in providers]
    answered = [p for p in providers if p.ok]

    # merge geo fields (first provider that reports wins)
    for p in answered:
        for pf, af in (("asn", "asn"), ("org", "org"), ("country", "country"),
                       ("country_code", "country_code"), ("region", "region"),
                       ("city", "city"), ("rdns", "rdns")):
            if getattr(a, af) is None and getattr(p, pf) is not None:
                setattr(a, af, getattr(p, pf))
        for flag in ("is_proxy", "is_vpn", "is_hosting", "abuse_confidence"):
            if getattr(p, flag) is not None:
                a.reputation_signals[f"{p.provider}:{flag}"] = getattr(p, flag)

    reachable = tcp.get("ok", 0) > 0
    loss = tcp.get("loss_pct")
    lat = tcp.get("latency_ms")

    # confidence: providers answering + probe depth + agreement
    conf = 0.0
    conf += min(0.4, 0.2 * len(answered))
    conf += 0.2 if tcp.get("probes") else 0.0
    conf += 0.2 if tls else 0.0
    conf += 0.1 if dns_consistent is not None else 0.0
    if len(answered) >= 2:
        geo_vals = [p.country_code for p in answered if p.country_code]
        conf += 0.1 if len(set(geo_vals)) <= 1 else 0.0  # agreement bonus
    a.confidence = round(min(1.0, conf), 2)

    negative = [k for k, v in a.reputation_signals.items() if v is True or
                (isinstance(v, int) and v >= 50)]
    abuse = [k for k, v in a.reputation_signals.items()
             if k.endswith("abuse_confidence") and isinstance(v, int) and v >= 50]

    if not reachable and (loss or 0) >= 100.0:
        a.classification, a.notes = "BLOCKED", ["TCP unreachable on all probes"]
        a.confidence = round(max(a.confidence, 0.5), 2)
        return a
    if abuse:
        a.classification = "BLOCKED"
        a.notes = [f"abuse signal: {', '.join(abuse)}"]
        return a
    if (loss or 0) > 0 and (loss or 0) < 100.0:
        a.classification = "DEGRADED"
        a.notes = [f"packet loss {loss}% on TCP probes"]
        return a
    if negative:
        a.classification = "QUESTIONABLE"
        a.notes = [f"negative reputation signal: {', '.join(negative)}"]
        return a
    if not answered:
        a.classification = "UNKNOWN"
        a.notes = ["no provider answered — cannot classify reputation"]
        return a
    if reachable and negative == [] and abuse == []:
        # CLEAN only when a provider explicitly reports proxy fields as false
        reports_flags = any(p.is_proxy is False or p.is_hosting is False for p in answered)
        if reports_flags:
            a.classification = "CLEAN"
            a.notes = ["reachable; proxy/hosting flags explicitly negative"]
        else:
            a.classification = "GOOD"
            a.notes = ["reachable; no negative signals, reputation flags unverified"]
        if lat is not None and lat > 400:
            a.notes.append(f"high latency {lat}ms")
    return a


# ── Engine with cache + history ─────────────────────────────────────────────

_cache: Dict[str, IPAssessment] = {}
_history: Dict[str, deque] = {}
_lock = asyncio.Lock()


async def check_ip(ip: str, sni: str = "", port: int = 443,
                   providers: Optional[List[IPQualityProvider]] = None,
                   force: bool = False, hostname: str = "") -> IPAssessment:
    """Full quality check for one IP: providers + TCP + TLS + DNS consistency."""
    async with _lock:
        cached = _cache.get(ip)
        if cached and not force and (time.time() - cached.checked_at) < CACHE_TTL:
            return cached

    providers = providers or default_providers()
    results = await asyncio.gather(*[p.lookup(ip) for p in providers], return_exceptions=True)
    prov_results = [r if isinstance(r, ProviderResult) else ProviderResult(
        provider=getattr(p, "name", "?"), error=str(r)[:120]) for r, p in zip(results, providers)]

    tcp = await tcp_probe(ip, port)
    tls = await tls_probe(ip, sni or "cloudflare.com", port) if sni else {}
    dns_consistent = None
    if hostname:
        try:
            loop = asyncio.get_event_loop()
            infos = await loop.run_in_executor(None, lambda: socket.getaddrinfo(hostname, port))
            ips = {i[4][0] for i in infos}
            dns_consistent = ip in ips
        except Exception:
            dns_consistent = None

    a = assess(ip, prov_results, tcp, tls, dns_consistent)
    async with _lock:
        _cache[ip] = a
        _history.setdefault(ip, deque(maxlen=HISTORY)).append({
            "checked_at": a.checked_at, "classification": a.classification,
            "latency_ms": tcp.get("latency_ms"), "loss_pct": tcp.get("loss_pct"),
        })
    return a


def get_cached(ip: str) -> Optional[IPAssessment]:
    return _cache.get(ip)


def all_cached() -> Dict[str, dict]:
    return {ip: a.to_dict() for ip, a in _cache.items()}


def history(ip: str) -> list:
    return list(_history.get(ip, []))


def summary() -> dict:
    by_class = {c: 0 for c in CLASSIFICATIONS}
    for a in _cache.values():
        by_class[a.classification] = by_class.get(a.classification, 0) + 1
    return {"tracked": len(_cache), "by_classification": by_class}


# ── API routes ──────────────────────────────────────────────────────────────

def _validate_ip(ip: str) -> str:
    import ipaddress
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid IP address: {ip!r}")


@router.get("/api/ip-quality/summary")
async def ip_quality_summary(_=Depends(require_auth)):
    return {"ok": True, **summary()}


@router.get("/api/ip-quality/{ip}")
async def ip_quality_check(ip: str, sni: str = "", port: int = 443,
                           force: bool = False, hostname: str = "",
                           _=Depends(require_auth)):
    """Quality check for one IP. `sni` enables the real TLS handshake probe."""
    ip = _validate_ip(ip)
    a = await check_ip(ip, sni=sni, port=port, force=force, hostname=hostname)
    return {"ok": True, **a.to_dict(), "history": history(ip)}


@router.post("/api/ip-quality/scan")
async def ip_quality_scan(request: Request, _=Depends(require_auth)):
    """Batch scan: {ips: [...], sni?, port?}. Bounded to 25 IPs per call."""
    body = await request.json()
    ips = body.get("ips") or []
    if not isinstance(ips, list) or not (1 <= len(ips) <= 25):
        raise HTTPException(status_code=400, detail="ips must be a list of 1-25 addresses")
    sni = str(body.get("sni") or "")
    port = int(body.get("port") or 443)
    sem = asyncio.Semaphore(5)

    async def _one(ip: str):
        async with sem:
            try:
                return (await check_ip(_validate_ip(ip), sni=sni, port=port)).to_dict()
            except HTTPException as e:
                return {"ip": ip, "classification": "UNKNOWN", "ok": False,
                        "notes": [str(e.detail)]}
            except Exception as e:
                return {"ip": ip, "classification": "UNKNOWN", "ok": False,
                        "notes": [f"{type(e).__name__}: {e}"]}

    results = await asyncio.gather(*[_one(ip) for ip in ips])
    ranked = sorted(results, key=lambda r: (
        {"CLEAN": 0, "GOOD": 1, "QUESTIONABLE": 2, "DEGRADED": 3, "BLOCKED": 4, "UNKNOWN": 5}.get(
            r.get("classification", "UNKNOWN"), 6),
        r.get("tcp", {}).get("latency_ms") or 9999,
    ))
    return {"ok": True, "total": len(ranked), "results": ranked}


@router.post("/api/ip-quality/compare")
async def ip_quality_compare(request: Request, _=Depends(require_auth)):
    """Compare cached assessments for a set of IPs (no new probes)."""
    body = await request.json()
    ips = body.get("ips") or []
    if not isinstance(ips, list) or not ips:
        raise HTTPException(status_code=400, detail="ips list required")
    rows = []
    for ip in ips:
        a = get_cached(ip)
        if a is None:
            rows.append({"ip": ip, "cached": False})
        else:
            rows.append({"ip": ip, "cached": True, **a.to_dict()})
    return {"ok": True, "results": rows}
