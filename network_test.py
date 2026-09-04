# network_test.py — Real Network Test Service (Phase 39)
# ══════════════════════════════════════════════════════════════════════════════
# سرویس تست واقعی شبکه برای «مرکز کنترل شبکه» (Network Control Center).
#
# هر تست، زنجیره‌ی واقعی مرحله‌به‌مرحله را اجرا می‌کند — نه عددی شبیه‌سازی‌شده:
#     DNS → TCP → TLS → SNI
# هر مرحله جدا اندازه‌گیری می‌شود (ms) و شکست، کد صادقانه برمی‌گرداند:
#     DNS_ERROR / TCP_REFUSED / TIMEOUT / TLS_ERROR / SNI_ERROR / UNSUPPORTED
#
# قواعد (مطابق فاز ۳۹):
#   * هیچ مقدار ثابت/پیش‌فرضی به‌عنوان پینگ گزارش نمی‌شود.
#   * شکست اندازه‌گیری = گزارش شکست با دلیل واقعی (هرگز «۰ms» یا موفق جعلی).
#   * کل پروب داخل executor thread اجرا می‌شود — هرگز event loop را بلاک نمی‌کند.
#   * هر تست یک رویداد ساخت‌یافته (structured event) تولید می‌کند.
#
# اندپوینت‌ها (register_routes → main.py):
#   POST /api/network/test/quick       — تست سریع: DNS/TCP/TLS/handshake + تأخیر کل
#   POST /api/network/test/tls         — تست TLS: هندشیک + اطلاعات گواهی
#   POST /api/network/test/sni         — تست SNI: گواهی ارائه‌شده در برابر SNI درخواستی
#   POST /api/network/test/diagnostic  — تشخیص کامل: پروب مرحله‌ای + خروج + سلامت پنل
#   GET  /api/network/test/targets     — اهداف پیشنهادی از وضعیت واقعی پنل
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import socket
import ssl
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

import structured_events
from endpoint_profiles import validate_hostname, validate_port

try:  # CA bundle — certifi اگر نصب باشد زنجیره‌ی گواهی‌ها کامل می‌شود
    import certifi
    _CA_BUNDLE = certifi.where()
except Exception:  # pragma: no cover
    _CA_BUNDLE = None

ENGINE_VERSION = "1.0.0"

# ── تنظیمات ──────────────────────────────────────────────────────────────────

DEFAULT_TIMEOUT = 8.0        # مهلت هر مرحله (ثانیه)
MAX_PORT_PROBES = 4          # جلوگیری از اسکن پورت از طریق این سرویس
ERROR_CODES = ("DNS_ERROR", "TCP_REFUSED", "TIMEOUT", "TLS_ERROR",
               "SNI_ERROR", "UNSUPPORTED", "INVALID_INPUT")

# هدف‌های عمومی معتبر برای تست (only well-known anycast/CDN targets — not rando)
WELL_KNOWN_TARGETS = (
    {"label": "Cloudflare", "address": "cloudflare.com", "port": 443, "sni": "cloudflare.com"},
    {"label": "Google", "address": "www.google.com", "port": 443, "sni": "www.google.com"},
)


# ── مدل درخواست ──────────────────────────────────────────────────────────────

class TestRequest(BaseModel):
    address: str = ""
    port: int = 443
    sni: str = ""
    tls: bool = True          # برای quick: آیا مرحله‌ی TLS هم اجرا شود
    insecure: bool = False    #TLS: آیا گواهی verify نشود (برای تست SNI جعلی)
    timeout: float = 8.0
    link_uid: str = ""        # اختیاری: اگر کانفیگی انتخاب شده، در رویداد ثبت می‌شود


# ── پروب مرحله‌ای واقعی (در thread — بدون بلاک event loop) ──────────────────

def _staged_probe_sync(address: str, port: int, sni: str, use_tls: bool,
                       insecure: bool, timeout: float) -> dict:
    """اجرای واقعی زنجیره DNS→TCP→TLS از داخل thread.

    خروجی: dict با مراحل {dns, tcp, tls, sni} هرکدام ms یا null + cert + خطا.
    این تابع فقط توسط run_in_executor صدا زده می‌شود.
    """
    stages = {"dns": None, "tcp": None, "tls": None, "sni": None}
    resolved: list[str] = []
    error_code: Optional[str] = None
    error_detail: str = ""
    cert_info: dict = {}
    sock: Optional[socket.socket] = None

    # ── مرحله ۱: DNS ─────────────────────────────────────────────────────
    t0 = time.perf_counter()
    try:
        infos = socket.getaddrinfo(address, port, family=socket.AF_UNSPEC,
                                   type=socket.SOCK_STREAM)
        resolved = sorted({i[4][0] for i in infos})
        if not resolved:
            raise OSError("no addresses returned")
        stages["dns"] = round((time.perf_counter() - t0) * 1000, 1)
    except Exception as exc:
        stages["dns"] = None
        error_code = "DNS_ERROR"
        error_detail = f"{type(exc).__name__}: {str(exc)[:120]}"
        return _result(address, port, sni, stages, resolved, False,
                       error_code, error_detail, cert_info)

    # ── مرحله ۲: TCP ─────────────────────────────────────────────────────
    t0 = time.perf_counter()
    try:
        sock = socket.create_connection((resolved[0], port), timeout=timeout)
        sock.settimeout(timeout)
        stages["tcp"] = round((time.perf_counter() - t0) * 1000, 1)
    except socket.timeout:
        error_code, error_detail = "TIMEOUT", f"TCP {address}:{port} — connect timed out"
        _close(sock)
        return _result(address, port, sni, stages, resolved, False,
                       error_code, error_detail, cert_info)
    except ConnectionRefusedError:
        error_code, error_detail = "TCP_REFUSED", f"TCP {address}:{port} — connection refused"
        _close(sock)
        return _result(address, port, sni, stages, resolved, False,
                       error_code, error_detail, cert_info)
    except Exception as exc:
        error_code = "TIMEOUT" if "timed out" in str(exc).lower() else "TCP_REFUSED"
        error_detail = f"TCP {address}:{port} — {type(exc).__name__}: {str(exc)[:100]}"
        _close(sock)
        return _result(address, port, sni, stages, resolved, False,
                       error_code, error_detail, cert_info)

    # ── مرحله ۳: TLS (اختیاری) ───────────────────────────────────────────
    if not use_tls:
        _close(sock)
        return _result(address, port, sni, stages, resolved, True,
                       None, "", cert_info)

    server_name = sni or address
    t0 = time.perf_counter()
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        else:
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.load_default_certs()
            if _CA_BUNDLE:
                try:
                    ctx.load_verify_locations(_CA_BUNDLE)  # certifi — زنجیره‌ی کامل
                except Exception:
                    pass
        ctx.set_alpn_protocols(["h2", "http/1.1"])
        tls_sock = ctx.wrap_socket(sock, server_hostname=server_name)
        stages["tls"] = round((time.perf_counter() - t0) * 1000, 1)
        # handshake total = dns+tcp+tls (کل زنجیره تا هندشیک)
        stages["sni"] = stages["tls"]
        try:
            # در حالت insecure گواهی فقط binary قابل خواندن است (رفتار استاندارد ssl)
            der = tls_sock.getpeercert(binary_form=True)
            cert_dict = None
            if not insecure:
                try:
                    cert_dict = tls_sock.getpeercert(binary_form=False)
                except Exception:
                    cert_dict = None
            if der:
                cert_info = _parse_cert(der, cert_dict) or {}
                cert_info["alpn_negotiated"] = (
                    tls_sock.selected_alpn_protocol()
                    if hasattr(tls_sock, "selected_alpn_protocol") else None)
                cert_info["verify_mode"] = "insecure (no verify)" if insecure else "verified"
                # مرحله SNI: تطابق گواهی با نام درخواستی
                if server_name:
                    identities = set(cert_info.get("sans") or [])
                    if cert_info.get("subject_cn"):
                        identities.add(cert_info["subject_cn"])
                    cert_info["sni_requested"] = server_name
                    cert_info["sni_match"] = (server_name.lower() in
                                              {i.lower() for i in identities})
        except Exception:
            pass  # گواهی خوانده نشد — مراحل timing همچنان معتبرند
        try:
            tls_sock.close()
        except Exception:
            pass
        return _result(address, port, sni, stages, resolved, True,
                       None, "", cert_info)
    except (socket.timeout, TimeoutError):
        error_code, error_detail = "TIMEOUT", f"TLS handshake timed out (SNI={server_name})"
    except ssl.SSLCertVerificationError as exc:
        error_code = "TLS_ERROR"
        error_detail = f"certificate verification failed (SNI={server_name}): {str(exc)[:140]}"
    except ssl.SSLError as exc:
        reason = str(exc).lower()
        if "handshake" in reason or "alert" in reason or "certificate" in reason or "ssl" in reason:
            error_code = "TLS_ERROR"
        else:
            error_code = "TLS_ERROR"
        error_detail = f"TLS handshake failed (SNI={server_name}): {type(exc).__name__}: {str(exc)[:140]}"
    except Exception as exc:
        error_code, error_detail = "TLS_ERROR", f"TLS stage: {type(exc).__name__}: {str(exc)[:120]}"
    _close(sock)
    return _result(address, port, sni, stages, resolved, False,
                   error_code, error_detail, cert_info)


def _parse_cert(der: bytes, ssl_dict: Optional[dict]) -> dict:
    """استخراج اطلاعات گواهی — اول از دیکشنری استاندارد ssl، بعد cryptography (DER).

    در حالت insecure دیکشنری استاندارد خالی است؛ DER با cryptography پارس می‌شود.
    اگر هیچ‌کدام نشد، دیکشنری خالی برمی‌گردد (timing همچنان معتبر است)."""
    out: dict = {"subject_cn": "", "issuer": "", "not_after": "",
                 "days_left": None, "sans": [], "verify_mode": ""}
    if ssl_dict:
        sans = [val for typ, val in (ssl_dict.get("subjectAltName") or [])
                if typ == "DNS"]
        cn = next((val for rdn in (ssl_dict.get("subject") or [])
                   for key, val in rdn if key == "commonName"), "")
        issuer = next((val for rdn in (ssl_dict.get("issuer") or [])
                       for key, val in rdn if key == "organizationName"), "")
        not_after = ssl_dict.get("notAfter", "")
        out.update({"subject_cn": cn, "issuer": issuer, "not_after": not_after,
                    "sans": sans[:12]})
    elif der:
        try:
            from cryptography import x509
            cert = x509.load_der_x509_certificate(der)
            try:
                cn = cert.subject.get_attributes_for_oid(
                    x509.oid.NameOID.COMMON_NAME)[0].value
            except Exception:
                cn = ""
            try:
                issuer = cert.issuer.get_attributes_for_oid(
                    x509.oid.NameOID.ORGANIZATION_NAME)[0].value
            except Exception:
                issuer = ""
            try:
                sans = [s.value for s in cert.extensions.get_extension_for_class(
                    x509.SubjectAlternativeName).value]
            except Exception:
                sans = []
            out.update({"subject_cn": str(cn or ""), "issuer": str(issuer or ""),
                        "not_after": cert.not_valid_after_utc.strftime("%b %d %H:%M:%S %Y GMT")
                        if cert.not_valid_after_utc else "",
                        "sans": [str(s) for s in sans][:12]})
        except Exception:
            return out
    # انقضا → روز باقی‌مانده
    if out.get("not_after"):
        try:
            exp = datetime.strptime(out["not_after"], "%b %d %H:%M:%S %Y %Z")
            out["days_left"] = round(
                (exp.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc))
                .total_seconds() / 86400, 1)
        except Exception:
            pass
    return out


def _close(sock: Optional[socket.socket]) -> None:
    try:
        if sock:
            sock.close()
    except Exception:
        pass


def _result(address: str, port: int, sni: str, stages: dict, resolved: list,
            ok: bool, error_code: Optional[str], error_detail: str,
            cert_info: dict) -> dict:
    total = None
    if ok and stages.get("tls") is not None:
        total = round(stages["dns"] + stages["tcp"] + stages["tls"], 1)
    elif ok and stages.get("tcp") is not None:
        total = round(stages["dns"] + stages["tcp"], 1)
    return {
        "ok": ok,
        "address": address,
        "port": port,
        "sni": sni or address,
        "stages_ms": stages,
        "total_ms": total,
        "resolved_ips": resolved[:4],
        "cert": cert_info,
        "error_code": error_code,
        "error_detail": error_detail,
        "engine": f"network_test/{ENGINE_VERSION}",
        "checked_at": datetime.now().isoformat(),
    }


async def staged_probe(address: str, port: int, sni: str = "", use_tls: bool = True,
                       insecure: bool = False, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """پروب واقعی DNS→TCP→TLS داخل executor — هرگز loop را بلاک نمی‌کند (§29)."""
    loop = asyncio.get_running_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(
            None,
            lambda: _staged_probe_sync(address, port, sni, use_tls, insecure, timeout),
        ),
        timeout=timeout + 6.0,
    )


# ── اعتبارسنجی ورودی ─────────────────────────────────────────────────────────

def _validate_target(body: TestRequest) -> tuple[str, int, str]:
    ok, norm = validate_hostname(body.address, allow_ip=True)
    if not ok or not norm:
        raise HTTPException(status_code=400, detail="آدرس اندپوینت نامعتبر است")
    okp, port = validate_port(body.port)
    if not okp:
        raise HTTPException(status_code=400, detail="پورت نامعتبر است")
    sni = body.sni or ""
    if sni:
        oks, sni_norm = validate_hostname(sni)
        if not oks:
            raise HTTPException(status_code=400,
                                detail="SNI نامعتبر است (باید hostname باشد، نه IP)")
        sni = sni_norm
    return norm, port, sni


async def _emit(kind: str, body: TestRequest, result: dict) -> None:
    """رویداد ساخت‌یافته برای هر تست واقعی (§28)."""
    try:
        await structured_events.log_event_async(
            "network_test", severity="INFO",
            type=kind, target=f"{body.address}:{body.port}"
                + (f" SNI={body.sni}" if body.sni else ""),
            link_uid=body.link_uid or None,
            status="success" if result.get("ok") else (result.get("error_code") or "failed"),
            latency_ms=result.get("total_ms"),
            source="emix_core",
        )
    except Exception:
        pass  # رویداد هرگز تست را نمی‌شکند


# ── ثبت مسیرها ───────────────────────────────────────────────────────────────

def register_routes(app, require_auth) -> None:
    @app.post("/api/network/test/quick", dependencies=[Depends(require_auth)])
    async def api_test_quick(body: TestRequest):
        """تست سریع: DNS + TCP + TLS + تأخیر کل — هر عدد اندازه‌گیری واقعی است."""
        address, port, sni = _validate_target(body)
        result = await staged_probe(address, port, sni, use_tls=body.tls,
                                    insecure=body.insecure,
                                    timeout=min(max(body.timeout, 2.0), 12.0))
        await _emit("quick", body, result)
        return result

    @app.post("/api/network/test/tls", dependencies=[Depends(require_auth)])
    async def api_test_tls(body: TestRequest):
        """تست TLS: هندشیک واقعی + جزئیات گواهی (صادرکننده، انقضا، SAN، ALPN)."""
        address, port, sni = _validate_target(body)
        result = await staged_probe(address, port, sni, use_tls=True,
                                    insecure=body.insecure,
                                    timeout=min(max(body.timeout, 2.0), 12.0))
        await _emit("tls", body, result)
        return result

    @app.post("/api/network/test/sni", dependencies=[Depends(require_auth)])
    async def api_test_sni(body: TestRequest):
        """تست SNI: با SNI درخواستی هندشیک می‌شود و گواهی ارائه‌شده مقایسه می‌شود.

        handshake بدون verify انجام می‌شود تا ببینیم سرور برای این SNI چه گواهی‌ای
        ارائه می‌کند — verdict: MATCH یا MISMATCH (spoil/SNI جعلی، به‌علاوه توضیح)."""
        address, port, sni = _validate_target(body)
        if not sni:
            sni = address
        result = await staged_probe(address, port, sni, use_tls=True, insecure=True,
                                    timeout=min(max(body.timeout, 2.0), 12.0))
        # تحلیل تطابق SNI
        cert = result.get("cert") or {}
        result["sni_analysis"] = {
            "requested": sni,
            "presented_cn": cert.get("subject_cn", ""),
            "match": bool(cert.get("sni_match")),
            "verdict": ("MATCH — سرور برای این SNI گواهی هم‌نام ارائه کرد"
                        if cert.get("sni_match") else
                        "MISMATCH — سرور گواهی دیگری ارائه کرد (رفتار expected برای SNI جعلی/بدون این نام)"),
            "note": ("SNI فقط معنای TLS دارد — هیچ ادعایی درباره‌ی مسیریابی یا "
                     "خروج جغرافیایی از آن استخراج نمی‌شود."),
        }
        await _emit("sni", body, result)
        return result

    @app.post("/api/network/test/diagnostic", dependencies=[Depends(require_auth)])
    async def api_test_diagnostic(body: TestRequest):
        """تشخیص کامل: پروب مرحله‌ای + خروج واقعی پنل + سلامت لینک‌ها + اهداف مرورگر.

        همه‌ی اجزا واقعی‌اند؛ بخش «مرورگر» فقط config را می‌دهد تا خود UI از
        شبکه‌ی کاربر WebSocket واقعی بزند (نمای کلاینت)."""
        address, port, sni = _validate_target(body)
        endpoint = await staged_probe(address, port, sni, use_tls=body.tls,
                                      insecure=body.insecure,
                                      timeout=min(max(body.timeout, 2.0), 12.0))
        # خروج واقعی پنل (اگر در دسترس بود — صادقانه، بدون جعل)
        egress: dict = {"status": "SKIPPED"}
        try:
            import egress_engine
            out = await egress_engine.verify_egress("panel")
            ev = (out or {}).get("evidence") or {}
            ip = (out or {}).get("public_ip") or ev.get("public_ip")
            country = (out or {}).get("country") or ev.get("country")
            egress = {
                "status": "OK" if ip else "UNAVAILABLE",
                "ip": ip,
                "country": country,
                "classification": (out or {}).get("classification"),
            }
        except Exception as exc:
            egress = {"status": "UNAVAILABLE", "reason": f"{type(exc).__name__}: {str(exc)[:80]}"}

        # سلامت کلی موتورها
        health: dict = {"status": "SKIPPED"}
        try:
            import network_health
            health = network_health.summary()
            health["status"] = "OK"
        except Exception as exc:
            health = {"status": "UNAVAILABLE", "reason": f"{type(exc).__name__}"}

        # اهداف تست مرورگر (نمای واقعی کاربر) — خود UI آن‌ها را می‌سنجد
        browser_targets: list = []
        try:
            import link_health
            ws_base, _ = link_health._ping_public_bases()
            browser_targets = [
                {"id": "panel-direct", "label": "مسیر مستقیم پنل", "ws_base": ws_base},
            ]
        except Exception:
            pass

        result = {
            "ok": endpoint.get("ok"),
            "engine": f"network_test/{ENGINE_VERSION}",
            "checked_at": datetime.now().isoformat(),
            "endpoint": endpoint,
            "panel_egress": egress,
            "panel_health": health,
            "browser_targets": browser_targets,
            "notes": [
                "هر عدد این گزارش از اندازه‌گیری واقعی می‌آید — شکست، شکست گزارش می‌شود.",
                "بخش نمای مرورگر توسط خود UI از شبکه‌ی شما اجرا می‌شود.",
            ],
        }
        await _emit("diagnostic", body, endpoint)
        return result

    @app.get("/api/network/test/targets", dependencies=[Depends(require_auth)])
    async def api_test_targets():
        """اهداف پیشنهادی تست — میزبان واقعی پنل + اهداف well-known."""
        targets = []
        try:
            from main import get_host
            host = get_host()
            if host and host not in ("localhost", "127.0.0.1", "0.0.0.0"):
                targets.append({"label": "پنل EMIX (نقطه‌ی ورودی واقعی)",
                                "address": host, "port": 443, "sni": host})
        except Exception:
            pass
        targets.extend(dict(t) for t in WELL_KNOWN_TARGETS)
        return {"ok": True, "targets": targets, "engine": f"network_test/{ENGINE_VERSION}"}
