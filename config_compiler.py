# config_compiler.py — centralized Config Compiler (Phase 3)
#
# THE single emitter for client configurations. Legacy scattered emitters
# (main.generate_share_link inline if/elif, link_emit partial re-implements,
# adapter-side string building) become facades over this module.
#
# Pipeline (strict order):
#   normalize → validate compatibility → validate completeness →
#   generate deterministic output → self-check → version + checksum
#
# Wire compatibility guarantee: for any input that the legacy
# main.generate_share_link accepted, compile() produces a byte-identical
# URI (the endpoint resolver reproduces Mode-A/Mode-B/standard semantics,
# path_prefix="" on the legacy path).
#
# Zero-fake rule: every CompiledConfig is born with health state UNKNOWN.
# Only the Network Health Engine (network_health.py) may set HEALTHY.

from __future__ import annotations
import base64
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, List
from urllib.parse import quote

import compat
import endpoint_profiles

CONFIG_VERSION = 1


# ── Input spec ──────────────────────────────────────────────────────────────

@dataclass
class ConfigSpec:
    protocol: str                      # "vless" | "trojan" | "shadowsocks" | "mtproto"
    transport: str = "ws"              # compat.TRANSPORTS (+ "tcp" for mtproto)
    security: str = "tls"
    credential: str = ""               # uuid (vless/trojan) / password (ss) / secret (mtproto)
    remark: str = "EMIX"
    host: str = ""                     # panel public host (fallback endpoint)
    cdn_domain: str = ""               # EMIX_CDN_DOMAIN (legacy Mode A)
    endpoint: Optional[endpoint_profiles.ResolvedEndpoint] = None
    alpn: str = "h2,http/1.1"
    fingerprint: str = "chrome"
    # protocol payloads
    ss_cipher: str = ""                # shadowsocks
    ss_password: str = ""
    mtproto_public_host: str = ""      # mtproto (address actually reachable)
    mtproto_public_port: int = 0
    mtproto_domain: str = ""
    mtproto_link_builder: Optional[Callable[[], str]] = None  # facade injects mtg helper
    link: Optional[dict] = None        # raw LINKS record (legacy fields path)
    requested_formats: tuple = ("uri",)


# ── Output ──────────────────────────────────────────────────────────────────

@dataclass
class CompiledConfig:
    ok: bool
    errors: List[str] = field(default_factory=list)
    uri: Optional[str] = None
    fused_protocol: str = ""
    protocol: str = ""
    transport: str = ""
    security: str = ""
    endpoint_mode: str = ""
    config_version: int = CONFIG_VERSION
    checksum: str = ""
    generated_at: float = field(default_factory=time.time)
    xray_json: Optional[dict] = None
    health: dict = field(default_factory=lambda: {"state": "UNKNOWN", "score": None, "checked_at": None})

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": list(self.errors),
            "uri": self.uri,
            "fused_protocol": self.fused_protocol,
            "protocol": self.protocol,
            "transport": self.transport,
            "security": self.security,
            "endpoint_mode": self.endpoint_mode,
            "config_version": self.config_version,
            "checksum": self.checksum,
            "generated_at": self.generated_at,
            "xray_json": self.xray_json,
            "health": dict(self.health),
        }

    def base64(self) -> Optional[str]:
        if not self.uri:
            return None
        return base64.b64encode(self.uri.encode()).decode()


# ── Normalization ───────────────────────────────────────────────────────────

def normalize_spec(spec: ConfigSpec) -> ConfigSpec:
    """Idempotent normalization — lowercase enums, trimmed strings, defaults."""
    spec.protocol = (spec.protocol or "").strip().lower()
    spec.transport = (spec.transport or "ws").strip().lower()
    spec.security = (spec.security or "tls").strip().lower()
    spec.fingerprint = (spec.fingerprint or "chrome").strip().lower()
    if spec.fingerprint not in ("chrome", "firefox", "ios", "safari", "android"):
        spec.fingerprint = "chrome"
    spec.alpn = (spec.alpn or "h2,http/1.1").strip()
    spec.remark = (spec.remark or "EMIX").strip()
    spec.cdn_domain = (spec.cdn_domain or "").strip().lower()
    if spec.protocol == "mtproto":
        spec.security = "none"
        spec.transport = "tcp"
    return spec


# ── Deterministic checksum ──────────────────────────────────────────────────

def _checksum(spec: ConfigSpec, uri: str) -> str:
    basis = json.dumps({
        "v": CONFIG_VERSION,
        "p": spec.protocol, "t": spec.transport, "s": spec.security,
        "c": spec.credential, "h": spec.host, "cdn": spec.cdn_domain,
        "alpn": spec.alpn, "fp": spec.fingerprint,
        "ep": None if spec.endpoint is None else {
            "address": spec.endpoint.address, "sni": spec.endpoint.sni,
            "host": spec.endpoint.host_header, "port": spec.endpoint.port,
            "prefix": spec.endpoint.path_prefix, "mode": spec.endpoint.mode,
            "insecure": spec.endpoint.allow_insecure,
        },
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((basis + "|" + (uri or "")).encode()).hexdigest()[:16]


# ── URI emitters (byte-identical with legacy formats) ───────────────────────

def _emit_vless_ws(spec: ConfigSpec, ep: endpoint_profiles.ResolvedEndpoint, uuid: str) -> str:
    path = f"{ep.path_prefix}/ws/{uuid}"
    params = {
        "encryption": "none",
        "security": "tls",
        "type": "ws",
        "host": ep.host_header,
        "path": path,
        "sni": ep.sni,
        "fp": spec.fingerprint,
        "alpn": spec.alpn,
    }
    if ep.allow_insecure:
        params["allowInsecure"] = "1"
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return f"vless://{uuid}@{ep.address}:{ep.port}?{query}#{quote(spec.remark)}"


def _emit_vless_xhttp(spec: ConfigSpec, ep: endpoint_profiles.ResolvedEndpoint, uuid: str, mode: str) -> str:
    path = f"{ep.path_prefix}/xhttp-siz10/{mode}/{uuid}"
    params = {
        "encryption": "none",
        "security": "tls",
        "type": "xhttp",
        "mode": mode,
        "host": ep.host_header,
        "path": path,
        "sni": ep.sni,
        "fp": spec.fingerprint,
        "alpn": spec.alpn,
    }
    if ep.allow_insecure:
        params["allowInsecure"] = "1"
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return f"vless://{uuid}@{ep.address}:{ep.port}?{query}#{quote(spec.remark)}"


def _emit_trojan_ws(spec: ConfigSpec, ep: endpoint_profiles.ResolvedEndpoint, uuid: str) -> str:
    params = {
        "security": "tls",
        "type": "ws",
        "host": ep.host_header,
        "path": f"{ep.path_prefix}/trojan-ws",
        "sni": ep.sni,
        "fp": spec.fingerprint,
        "alpn": spec.alpn,
    }
    if ep.allow_insecure:
        params["allowInsecure"] = "1"
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return f"trojan://{uuid}@{ep.address}:{ep.port}?{query}#{quote(spec.remark)}"


def _emit_trojan_xhttp(spec: ConfigSpec, ep: endpoint_profiles.ResolvedEndpoint, uuid: str, mode: str) -> str:
    path = f"{ep.path_prefix}/txhttp-siz10/{mode}/{uuid}"
    params = {
        "security": "tls",
        "type": "xhttp",
        "mode": mode,
        "host": ep.host_header,
        "path": path,
        "sni": ep.sni,
        "fp": spec.fingerprint,
        "alpn": spec.alpn,
    }
    if ep.allow_insecure:
        params["allowInsecure"] = "1"
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return f"trojan://{uuid}@{ep.address}:{ep.port}?{query}#{quote(spec.remark)}"


def _emit_ss(spec: ConfigSpec, ep: endpoint_profiles.ResolvedEndpoint) -> str:
    # Legacy format: address AND plugin host both use the connection host
    # (SS SNI override documented as not applicable in compat matrix).
    host = ep.address
    userinfo = base64.urlsafe_b64encode(
        f"{spec.ss_cipher}:{spec.ss_password}".encode()
    ).decode().rstrip("=")
    plugin = quote(f"v2ray-plugin;tls;mux=0;path=/ss-ws;host={host}")
    return f"ss://{userinfo}@{host}:{ep.port}/?plugin={plugin}#{quote(spec.remark)}"


# ── xray/sing-box style client config ───────────────────────────────────────

def _emit_xray_json(spec: ConfigSpec, ep: endpoint_profiles.ResolvedEndpoint, uri: str) -> Optional[dict]:
    if spec.protocol not in ("vless", "trojan"):
        return None
    stream: dict = {
        "network": "ws" if spec.transport == "ws" else "xhttp",
        "security": "tls",
        "tlsSettings": {
            "serverName": ep.sni,
            "allowInsecure": ep.allow_insecure,
            "fingerprint": spec.fingerprint,
            "alpn": [a.strip() for a in spec.alpn.split(",") if a.strip()],
        },
    }
    if spec.transport == "ws":
        stream["wsSettings"] = {
            "path": f"{ep.path_prefix}/ws/{spec.credential}" if spec.protocol == "vless" else f"{ep.path_prefix}/trojan-ws",
            "headers": {"Host": ep.host_header},
        }
    else:
        mode = spec.transport.replace("xhttp-", "")
        stream["xhttpSettings"] = {
            "path": f"{ep.path_prefix}/{'xhttp' if spec.protocol=='vless' else 'txhttp'}-siz10/{mode}/{spec.credential}",
            "host": ep.host_header,
            "mode": mode,
        }
    outbound = {
        "tag": "proxy",
        "protocol": spec.protocol,
        "settings": (
            {"vnext": [{"address": ep.address, "port": ep.port,
                        "users": [{"id": spec.credential, "encryption": "none"}]}]}
            if spec.protocol == "vless"
            else {"servers": [{"address": ep.address, "port": ep.port,
                               "password": spec.credential}]}
        ),
        "streamSettings": stream,
    }
    return {
        "outbounds": [outbound, {"tag": "direct", "protocol": "freedom"}],
        "emix": {"config_version": CONFIG_VERSION, "checksum_hint": _checksum(spec, uri)},
    }


# ── Self-check (generated config must parse back to the same spec) ──────────

def _self_check(uri: str, spec: ConfigSpec, ep: endpoint_profiles.ResolvedEndpoint) -> List[str]:
    problems: List[str] = []
    if not uri:
        problems.append("emitter returned empty URI")
        return problems
    scheme = uri.split("://", 1)[0]
    expected = {"vless": "vless", "trojan": "trojan", "shadowsocks": "ss", "mtproto": "tg"}.get(spec.protocol, "")
    if expected and scheme != expected:
        problems.append(f"scheme mismatch: got {scheme}, expected {expected}")
    if "@" not in uri and spec.protocol in ("vless", "trojan"):
        problems.append("missing credential separator '@'")
    if f"{ep.address}" not in uri:
        problems.append(f"endpoint address '{ep.address}' missing from URI")
    if spec.security == "tls" and spec.protocol in ("vless", "trojan"):
        if "security=tls" not in uri:
            problems.append("tls security parameter missing")
        if ep.allow_insecure and "allowInsecure" not in uri:
            problems.append("allowInsecure endpoint flag not reflected in URI")
    if ep.path_prefix and ep.path_prefix.rstrip("/") not in uri:
        problems.append(f"path_prefix '{ep.path_prefix}' missing from URI")
    return problems


# ── The compiler entrypoint ─────────────────────────────────────────────────

def compile_config(spec: ConfigSpec) -> CompiledConfig:
    spec = normalize_spec(spec)
    errors: List[str] = []

    # 1. protocol/transport/security compatibility (strict, no coercion)
    c = compat.validate(spec.protocol, spec.transport, spec.security)
    if not c.ok:
        return CompiledConfig(ok=False, errors=[f"incompatible combination: {'; '.join(c.reasons)}"])

    # 2. completeness
    if spec.protocol in ("vless", "trojan") and not spec.credential:
        errors.append("credential (uuid/password) required")
    if spec.protocol == "shadowsocks" and not (spec.ss_cipher and spec.ss_password):
        errors.append("ss_cipher and ss_password required for shadowsocks")
    if spec.protocol == "mtproto" and not (spec.mtproto_public_host and spec.mtproto_public_port):
        errors.append("mtproto requires public host/port (Railway TCP proxy)")
    if not spec.host and spec.endpoint is None:
        errors.append("host or endpoint required")
    if errors:
        return CompiledConfig(ok=False, errors=errors)

    # 3. resolve endpoint (legacy fields path when spec.link given)
    ep = spec.endpoint
    if ep is None:
        if spec.link is not None:
            ep = endpoint_profiles.resolve(spec.link, spec.host or "", spec.cdn_domain)
        else:
            ep = endpoint_profiles.ResolvedEndpoint(
                address=spec.host, sni=spec.host, host_header=spec.host,
                port=443, path_prefix="", security="tls",
                alpn=[a.strip() for a in spec.alpn.split(",")], allow_insecure=False,
                mode="standard",
            )

    # 4. SNI applicability (honesty: refuse combos where the override would
    #    be silently dropped — except the legacy stored-link path which must
    #    keep its documented "partial support" behavior)
    if ep.mode in ("cdn", "direct-sni") and not compat.sni_override_supported(
            compat.compose(spec.protocol, spec.transport)) and spec.link is None:
        return CompiledConfig(ok=False, errors=[
            f"SNI override not applicable to {spec.protocol}/{spec.transport} — "
            f"the link format carries no sni parameter"
        ])

    # 5. emit URI
    uri: Optional[str] = None
    if spec.protocol == "mtproto":
        if spec.mtproto_link_builder is not None:
            uri = spec.mtproto_link_builder()
        else:
            uri = (f"tg://proxy?server={quote(spec.mtproto_public_host)}"
                   f"&port={spec.mtproto_public_port}"
                   f"&secret={quote(spec.credential)}#{quote(spec.remark)}")
    elif spec.protocol == "shadowsocks":
        uri = _emit_ss(spec, ep)
    elif spec.protocol == "trojan":
        uri = (
            _emit_trojan_ws(spec, ep, spec.credential) if spec.transport == "ws"
            else _emit_trojan_xhttp(spec, ep, spec.credential, spec.transport.replace("xhttp-", ""))
        )
    else:  # vless
        uri = (
            _emit_vless_ws(spec, ep, spec.credential) if spec.transport == "ws"
            else _emit_vless_xhttp(spec, ep, spec.credential, spec.transport.replace("xhttp-", ""))
        )

    # 6. self-check
    errors.extend(_self_check(uri or "", spec, ep))
    if errors:
        return CompiledConfig(ok=False, errors=errors, uri=uri)

    out = CompiledConfig(
        ok=True, uri=uri,
        fused_protocol=compat.compose(spec.protocol, spec.transport),
        protocol=spec.protocol, transport=spec.transport, security=spec.security,
        endpoint_mode=ep.mode,
        checksum=_checksum(spec, uri),
    )
    if "xray_json" in spec.requested_formats or "json" in spec.requested_formats:
        out.xray_json = _emit_xray_json(spec, ep, uri)
    return out


# ── Subscription emission helpers ───────────────────────────────────────────

def subscription_document(uris: List[str]) -> str:
    """Deterministic base64 subscription body (order preserved by caller)."""
    return base64.b64encode("\n".join(uris).encode()).decode()


def compile_from_link(link: dict, host: str, cdn_domain: str = "",
                      mtproto_link_builder: Optional[Callable[[], str]] = None,
                      formats: tuple = ("uri",), credential: str = "") -> CompiledConfig:
    """Facade for the legacy LINKS-record path (used by main.py + adapters).

    `credential` — the link UUID / password (LINKS records key by uid and do
    not store it inside the record; the caller knows the key).
    """
    p, t = compat.decompose(link.get("protocol", "vless-ws"))
    spec = ConfigSpec(
        protocol=p, transport=t,
        security="none" if p == "mtproto" else "tls",
        credential=credential or link.get("uuid", "") or link.get("mtproto_secret", ""),
        remark=link.get("label", "EMIX"),
        host=host, cdn_domain=cdn_domain, link=link,
        alpn=link.get("alpn", "h2"),
        fingerprint=link.get("fingerprint", "chrome"),
        ss_cipher=link.get("ss_cipher", ""),
        ss_password=link.get("ss_password", ""),
        mtproto_public_host=link.get("mtproto_public_host", ""),
        mtproto_public_port=link.get("mtproto_public_port") or 0,
        mtproto_domain=link.get("mtproto_domain", ""),
        mtproto_link_builder=mtproto_link_builder,
        requested_formats=formats,
    )
    return compile_config(spec)
