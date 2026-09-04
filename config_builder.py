# config_builder.py — Unified Config Builder engine (Phase 38+ spec §6-§7, §18-§21)
#
# ONE canonical ConfigRequest → validation → CANONICAL COMPILER → outputs.
#
#   ConfigRequest
#    ↓ ProtocolCapabilities   (capability_engine — deployment/node truth)
#    ↓ EndpointProfile        (endpoint_profiles — the ONLY endpoint/TLS engine)
#    ↓ Node                   (node catalogue + egress evidence)
#    ↓ RoutingPolicy          (domestic_route_engine presets + iran_gateway)
#    ↓ ConfigCompiler         (config_compiler.compile_config — THE emitter)
#    ↓ ValidatedConfig        (uri + xray json + subscription + split rules)
#    ↓ Client Output          (QR stays LOCAL via /api/qr; copy client-side)
#
# Zero-new-emitter rule: this module NEVER builds a protocol URI itself —
# every output originates from config_compiler (canonical) or the documented
# config-file emitters (vpn_pro WG/OVPN — not selectable without a UDP node).
#
# Validation BEFORE generation (spec §19): invalid input → explicit reason,
# nothing generated. Preview comes from the same pipeline (spec §20) — no
# frontend-only fake preview.
#
# History (spec §21): bounded store; entries are server-side (same trust
# domain as LINKS uuid storage). LIST responses mask credentials; the
# credential is revealed only in the authed "view" action. Secrets are never
# logged (structured_events scrubs centrally).

from __future__ import annotations
import asyncio
import base64
import time
import uuid as _uuid
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Callable

import compat
import config_compiler as cc
import capability_engine as caps
import structured_events as events

# Pydantic models MUST live at module level (function-local classes are
# unresolvable under `from __future__ import annotations` — FastAPI then
# treats the parameter as a query arg → 422 "Field required").
from pydantic import BaseModel


class BuilderRequest(BaseModel):
    name: str = ""
    protocol: str = "vless"
    transport: str = "xhttp-packet-up"
    security: str = "tls"
    node_id: str = "panel"
    endpoint_profile_id: str = ""
    custom_address: str = ""
    custom_sni: str = ""
    custom_port: int = 443
    routing_policy: str = "ALL_VPN"
    client_format: str = "xray-json"
    remark: str = "EMIX"
    credential: str = ""
    ss_cipher: str = "chacha20-ietf-poly1305"
    ss_password: str = ""
    alpn: str = "h2,http/1.1"
    fingerprint: str = "chrome"
    account_id: str = ""
    subscription_id: str = ""
    persist: bool = True
    persist_link: bool = True

ENGINE_VERSION = "1.0.0"
HISTORY_BOUND = 200

SELECTABLE_PROTOCOLS = tuple(sorted(compat.PROTOCOLS))     # panel-runtime protocols
CLIENT_FORMATS = ("uri", "xray-json", "sing-box", "subscription")

# DI seams (no import cycles — main wires these):
_host_provider: Optional[Callable[[], str]] = None          # main.get_host
_worker_domain_provider: Optional[Callable[[], str]] = None # gaming_boost worker domain
_cdn_domain_provider: Optional[Callable[[], str]] = None
# Phase 40 §25/§34 — زنجیره‌ی کانونی هم‌گرا: «ساخت نهایی» فقط خروجی‌مصنوع
# نیست؛ همان pipeline یک لینکِ زنده‌ی قابل‌تست هم می‌سازد (از طریق
# _create_link_core پنل — persistence + health probe + worker sync). بدون
# این seam، کانفیگِ ساخته‌شده هرگز روی کارت‌ها ظاهر نمی‌شد و «Retest» واقعی
# ناممکن بود.
_link_factory: Optional[Callable] = None                     # main._create_link_core


def set_host_provider(fn) -> None:
    global _host_provider
    _host_provider = fn


def set_worker_domain_provider(fn) -> None:
    global _worker_domain_provider
    _worker_domain_provider = fn


def set_cdn_domain_provider(fn) -> None:
    global _cdn_domain_provider
    _cdn_domain_provider = fn


def set_link_factory(fn) -> None:
    """main.py این را وصل می‌کند: async fn(body: dict) -> dict — همان
    مسیر واقعی ساخت لینک (persist + probe + sync). فقط generate استفاده
    می‌کند؛ preview هرگز لینک نمی‌سازد."""
    global _link_factory
    _link_factory = fn


def _panel_host() -> str:
    if _host_provider is not None:
        try:
            return _host_provider() or ""
        except Exception:
            return ""
    return ""


def _worker_domain() -> str:
    if _worker_domain_provider is not None:
        try:
            return _worker_domain_provider() or ""
        except Exception:
            return ""
    return ""


# ── The canonical request (spec §7) ──────────────────────────────────────────

@dataclass
class ConfigRequest:
    name: str = ""                       # history label
    protocol: str = "vless"
    transport: str = "xhttp-packet-up"
    security: str = "tls"
    node_id: str = "panel"               # "panel" | "loc:<name>" | managed node id
    endpoint_profile_id: str = ""        # canonical Endpoint Profile preset
    custom_address: str = ""             # custom endpoint (when no profile)
    custom_sni: str = ""
    custom_port: int = 443
    routing_policy: str = "ALL_VPN"      # domestic engine preset
    client_format: str = "xray-json"
    remark: str = "EMIX"
    credential: str = ""                 # uuid / password / secret (auto-gen if empty)
    ss_cipher: str = "chacha20-ietf-poly1305"
    ss_password: str = ""
    alpn: str = "h2,http/1.1"
    fingerprint: str = "chrome"
    account_id: str = ""                 # optional ownership (accounts engine)
    subscription_id: str = ""
    persist: bool = True                 # write to history (preview → False)
    persist_link: bool = True            # Phase 40: also create a LIVE link
                                          # (panel node + non-custom endpoint only)


# ── Node → endpoint resolution (honest, evidence-labeled) ────────────────────

async def _resolve_node_endpoint(req: ConfigRequest) -> dict:
    """Resolve (endpoint_host, path_prefix, node_info) for the selected node.
    Returns {ok, problems[], host, path_prefix, node}."""
    problems: List[str] = []
    node_info: dict = {}
    host = ""
    path_prefix = ""

    if req.node_id == "panel":
        host = _panel_host()
        node_info = {"node_id": "panel", "role": "CONTROL_PLANE",
                     "deployment": "panel",
                     "label": "EMIX Control Plane (Railway)"}
        if not host:
            problems.append("panel public host is not known yet — set the server "
                            "host in settings or open the panel via its public URL")
    elif req.node_id.startswith("loc:"):
        name = req.node_id[4:]
        host = _worker_domain()
        path_prefix = f"/loc/{name}"
        node_info = {"node_id": req.node_id, "role": "EDGE_NODE/RELAY",
                     "deployment": "worker",
                     "label": f"Worker location {name}",
                     "note": "connection via the Cloudflare Worker tunnel"}
        if not host:
            problems.append("worker domain is not configured — set it in the "
                            "gaming/multi-location settings first")
    else:
        try:
            import node_manager as nm
            rec = nm.get_node(req.node_id)
        except Exception:
            rec = None
        if rec is None:
            problems.append(f"node '{req.node_id}' is not registered")
        else:
            host = rec.address
            node_info = {"node_id": rec.id, "role": rec.kind,
                         "deployment": "vps" if rec.kind in ("vps", "external") else
                         ("exit-node" if rec.kind == "exit" else "worker"),
                         "label": rec.name, "state": rec.state}
            if not host:
                problems.append(f"node '{req.node_id}' has no public address")
    return {"ok": not problems, "problems": problems, "host": host,
            "path_prefix": path_prefix, "node": node_info}


async def _resolve_endpoint(req: ConfigRequest, host: str,
                            path_prefix: str) -> dict:
    """Endpoint resolution — through the ONE canonical engine (endpoint_profiles).
    Preset id → resolve(); custom fields → explicit ResolvedEndpoint; else standard."""
    import endpoint_profiles as ep
    problems: List[str] = []
    resolved: Optional[ep.ResolvedEndpoint] = None
    mode = "standard"

    if req.endpoint_profile_id:
        # canonical resolution path: profile store → ResolvedEndpoint (mode "profile")
        link_like = {"endpoint_profile_id": req.endpoint_profile_id}
        profile = await ep.get_profile(req.endpoint_profile_id)
        if profile is None:
            problems.append(f"endpoint profile '{req.endpoint_profile_id}' not found")
        else:
            resolved = ep.resolve(link_like, host, _cdn_domain_provider() if _cdn_domain_provider else "")
            mode = "profile"
    elif req.custom_address:
        ok, _ = ep.validate_hostname(req.custom_address, allow_ip=True)
        if not ok:
            problems.append(f"invalid custom endpoint address: {req.custom_address!r}")
        else:
            okp, port = ep.validate_port(req.custom_port or 443)
            if not okp:
                problems.append(f"invalid custom port: {req.custom_port!r}")
            else:
                sni = req.custom_sni or req.custom_address
                if req.custom_sni:
                    oks, _ = ep.validate_hostname(req.custom_sni)
                    if not oks:
                        problems.append(f"invalid custom SNI: {req.custom_sni!r} "
                                        "(must be a hostname, not an IP)")
                resolved = ep.ResolvedEndpoint(
                    address=req.custom_address, sni=sni,
                    host_header=req.custom_sni or req.custom_address,
                    port=port, path_prefix=path_prefix, security="tls",
                    alpn=[a.strip() for a in req.alpn.split(",") if a.strip()],
                    allow_insecure=False, mode="standard",
                    notes=["custom endpoint from Config Builder"],
                )
                mode = "custom"
    else:
        sni = host
        resolved = ep.ResolvedEndpoint(
            address=host, sni=sni, host_header=host, port=443,
            path_prefix=path_prefix, security="tls",
            alpn=[a.strip() for a in req.alpn.split(",") if a.strip()],
            allow_insecure=False, mode="standard",
        )
    return {"ok": not problems, "problems": problems, "endpoint": resolved,
            "mode": mode}


# ── Routing policy validation (client capability honest — spec §26) ─────────

def _validate_routing(req: ConfigRequest) -> dict:
    import domestic_route_engine as dre
    problems: List[str] = []
    policy = None
    if req.routing_policy not in dre.PRESET_POLICIES:
        problems.append(f"unknown routing policy '{req.routing_policy}' — "
                        f"supported: {list(dre.PRESET_POLICIES)}")
    else:
        policy = dre.PRESET_POLICIES[req.routing_policy]
    client_split = "SPLIT_TUNNEL_SUPPORTED" if req.client_format in \
        ("xray-json", "sing-box") else "SPLIT_TUNNEL_NOT_SUPPORTED"
    if policy is not None and policy.iran == "DIRECT" and \
            client_split != "SPLIT_TUNNEL_SUPPORTED":
        problems.append(
            "SPLIT_TUNNEL_NOT_SUPPORTED — the selected client format "
            f"'{req.client_format}' cannot enforce client-side split tunneling; "
            "IRAN_DIRECT cannot be honored (choose xray-json/sing-box, or a "
            "different policy)")
    if policy is not None and policy.iran == "BLOCK" and \
            client_split != "SPLIT_TUNNEL_SUPPORTED":
        problems.append(
            "SPLIT_TUNNEL_NOT_SUPPORTED — blocking the domestic leg "
            "(INTERNATIONAL_VVPN) needs a split-tunnel-capable client "
            "(xray-json/sing-box)")
    gateway = None
    if req.routing_policy == "IRAN_PROXY":
        gateway = dre.gateway_egress_status()
        if not gateway.get("configured"):
            problems.append(
                "IRAN_PROXY requires a real Iranian gateway — none is configured "
                "(🇮🇷 پروکسی ایران → add and verify a gateway)")
    return {"ok": not problems, "problems": problems, "policy": policy,
            "client_split": client_split, "gateway": gateway}


# ── Credential auto-generation (only for GENERATE, not preview) ─────────────

def _auto_credentials(req: ConfigRequest, generate: bool) -> dict:
    """Credentials for the request. Auto-generation ONLY on real generation
    (preview never invents a credential — nothing is emitted half-baked)."""
    problems: List[str] = []
    credential = (req.credential or "").strip()
    ss_password = req.ss_password
    if req.protocol in ("vless", "trojan"):
        if not credential and generate:
            credential = str(_uuid.uuid4())
    elif req.protocol == "shadowsocks":
        if generate and not ss_password:
            import secrets as _secrets
            ss_password = _secrets.token_urlsafe(12)
        if not req.ss_cipher:
            req.ss_cipher = "chacha20-ietf-poly1305"
    return {"credential": credential, "ss_password": ss_password,
            "problems": problems}


# ── The build pipeline (validation BEFORE generation — spec §19) ────────────

async def build_config(req: ConfigRequest, for_preview: bool = False) -> dict:
    """Validate → compile (canonical compiler) → outputs.
    for_preview=True: same pipeline, no history write, no credential invention."""
    # 1. protocol/transport/security × deployment/node capability
    combo = caps.validate_request_combination(
        req.protocol, req.transport, req.security, req.node_id, req.client_format)
    if not combo["ok"]:
        events.log_event("PROTOCOL_VALIDATION_FAILED", severity="WARNING",
                         protocol=req.protocol, transport=req.transport,
                         security=req.security, node=req.node_id,
                         problems=combo["problems"])
        return {"ok": False, "errors": combo["problems"], "stage": "capability"}

    # 2. node → endpoint
    node_res = await _resolve_node_endpoint(req)
    if not node_res["ok"]:
        return {"ok": False, "errors": node_res["problems"], "stage": "node"}

    # 3. endpoint profile resolution (canonical engine)
    ep_res = await _resolve_endpoint(req, node_res["host"], node_res["path_prefix"])
    if not ep_res["ok"]:
        return {"ok": False, "errors": ep_res["problems"], "stage": "endpoint"}

    # 4. routing policy validation (client capability + gateway)
    route_res = _validate_routing(req)
    if not route_res["ok"]:
        return {"ok": False, "errors": route_res["problems"], "stage": "routing"}

    # 5. credentials (auto-generation only on real generation; preview uses a
    #    syntactically-valid placeholder so validation covers the full pipeline)
    creds = _auto_credentials(req, generate=not for_preview)
    if for_preview and req.protocol in ("vless", "trojan") and not \
            (req.credential or "").strip():
        creds["credential"] = "00000000-0000-0000-0000-00000000c0de"
        creds["credential_placeholder"] = True
    if for_preview and req.protocol == "shadowsocks" and not creds["ss_password"]:
        creds["ss_password"] = "preview-password"
        creds["credential_placeholder"] = True

    # 5.b Phase 40 §25/§34 — LIVE LINK CREATION (generate only; never preview).
    #     همان pipeline، همان کامپایلر — ولی «ساخت نهایی» حالا یک لینک زنده‌ی
    #     قابل‌تست هم می‌سازد (persist + health-probe + worker-sync از مسیر
    #     واقعی پنل). کانفیگ ساخته‌شده روی کارت‌ها ظاهر می‌شود و Retest واقعی
    #     (تونل E2E) روی آن ممکن است. preview هرگز لینک نمی‌سازد.
    link_result: Optional[dict] = None
    link_note = ""
    live_link = bool(
        (not for_preview) and req.persist_link
        and _link_factory is not None
        and req.node_id == "panel"
        and ep_res["mode"] != "custom"
    )
    if (not for_preview) and req.persist_link and not live_link:
        if req.node_id != "panel":
            link_note = (f"output-only: links live on the panel deployment — "
                         f"node '{req.node_id}' configs are exported, not hosted here")
        elif ep_res["mode"] == "custom":
            link_note = ("output-only: custom endpoints are exported as artifacts; "
                         "select an endpoint profile (or standard) to also create "
                         "a live, testable link")
    if live_link:
        try:
            body = {
                "label": (req.name or f"{req.protocol}-{req.transport}")[:60],
                "protocol": compat.compose(req.protocol, req.transport),
                "alpn": req.alpn,
                "fingerprint": req.fingerprint,
                "sub_id": req.subscription_id or None,
                "endpoint_profile_id": req.endpoint_profile_id or None,
                "ss_cipher": req.ss_cipher,
                "_builder_meta": {
                    "routing_policy": req.routing_policy,
                    "node_id": req.node_id,
                    "transport": req.transport,
                    "security": req.security,
                    "client_format": req.client_format,
                    "built_by": "config_builder",
                    "builder_name": req.name,
                },
            }
            link_result = await _link_factory(body)
        except Exception as exc:  # honest failure — no half-built anything
            events.log_event("CONFIG_GENERATED", severity="ERROR",
                             stage="link", error=str(exc)[:200])
            return {"ok": False,
                    "errors": [f"live link creation failed: {type(exc).__name__}: "
                               f"{str(exc)[:200]}"],
                    "stage": "link"}
        if link_result:
            if req.protocol in ("vless", "trojan"):
                creds["credential"] = link_result.get("uuid") or creds["credential"]
            elif req.protocol == "shadowsocks":
                creds["ss_password"] = (link_result.get("ss_password")
                                        or creds["ss_password"])
            elif req.protocol == "mtproto":
                creds["credential"] = (link_result.get("mtproto_secret")
                                       or creds.get("credential") or "")

    # write generated credentials back so HISTORY stores the real values and
    # regeneration is deterministic (same credential → same URI → same checksum)
    if not for_preview:
        if creds["credential"]:
            req.credential = creds["credential"]
        if creds["ss_password"]:
            req.ss_password = creds["ss_password"]
    if req.protocol == "mtproto" and not for_preview:
        # mtproto needs a public TCP-proxy host/port — explicit when missing
        # (only when NO live link provided its real instance secret already)
        if not (req.credential or "").strip():
            req.credential = "ee" + _uuid.uuid4().hex[:30]
            creds["credential"] = req.credential

    # 6. compile — THE canonical compiler (this module never emits URIs)
    _mt_host = ((link_result or {}).get("mtproto_public_host")
                or req.custom_address or node_res["host"])
    _mt_port = ((link_result or {}).get("mtproto_public_port")
                or req.custom_port or 443)
    spec = cc.ConfigSpec(
        protocol=req.protocol, transport=req.transport, security=req.security,
        credential=creds["credential"], remark=req.remark or "EMIX",
        host=node_res["host"], cdn_domain="",
        endpoint=ep_res["endpoint"], alpn=req.alpn, fingerprint=req.fingerprint,
        ss_cipher=req.ss_cipher, ss_password=creds["ss_password"],
        mtproto_public_host=_mt_host,
        mtproto_public_port=_mt_port,
        requested_formats=("uri", "xray_json"),
    )
    compiled = cc.compile_config(spec)
    if not compiled.ok:
        events.log_event("PROTOCOL_VALIDATION_FAILED", severity="WARNING",
                         protocol=req.protocol, transport=req.transport,
                         stage="compiler", problems=compiled.errors)
        return {"ok": False, "errors": compiled.errors, "stage": "compiler"}

    # 7. routing outputs (split rules / gateway status / policy explanation)
    out_routing = _compile_routing_outputs(req, route_res)

    # 8. outputs
    outputs: Dict[str, object] = {"uri": compiled.uri}
    if req.client_format == "xray-json" and compiled.xray_json:
        outputs["xray_json"] = compiled.xray_json
    if req.client_format == "sing-box":
        outputs["note_sing_box"] = ("rules emitted in the shared GEOIP/CIDR "
                                    "structure — map to sing-box route.rules")
    if req.client_format == "subscription":
        outputs["subscription"] = cc.subscription_document([compiled.uri])
    if out_routing.get("split_rules"):
        outputs["split_rules"] = out_routing["split_rules"]
        events.log_event("SPLIT_TUNNEL_COMPILED", policy=req.routing_policy,
                         client=req.client_format,
                         rules=len(out_routing["split_rules"].get("rules", [])))

    result = {
        "ok": True,
        "validation": "VALID",
        "credential_placeholder": bool(creds.get("credential_placeholder")),
        "request": _request_view(req, mask=not for_preview),
        "preview": {
            "protocol": compiled.protocol,
            "transport": compiled.transport,
            "security": compiled.security,
            "endpoint_profile": req.endpoint_profile_id or ep_res["mode"],
            "endpoint_mode": compiled.endpoint_mode,
            "node": node_res["node"],
            "routing": req.routing_policy,
            "routing_detail": out_routing,
        },
        "outputs": outputs,
        "checksum": compiled.checksum,
        "config_version": compiled.config_version,
        "qr": "/api/qr?data=" if compiled.uri else None,   # frontend appends the URI (LOCAL rendering)
        "generated_at": time.time(),
    }

    # 8.b Phase 40 — the live-link block (two-state model, honest):
    #     CONFIGURATION ✓ VALID + a REAL link the cards can show & retest.
    if for_preview:
        result["link"] = {"created": False,
                          "reason": "preview — same compiler, no link created"}
    elif link_result:
        result["link"] = {
            "created": True,
            "uuid": link_result.get("uuid"),
            "label": link_result.get("label"),
            "protocol": link_result.get("protocol"),
            "share_link": link_result.get("vless_link"),
            "sub_url": link_result.get("sub_url"),
            "routing_policy": req.routing_policy,
            "runtime_state": "UNKNOWN until first real probe",
        }
        events.log_event("LINK_CREATED", name=link_result.get("label") or "",
                         uuid=link_result.get("uuid"), protocol=link_result.get("protocol"),
                         routing=req.routing_policy, source="config_builder")
    else:
        result["link"] = {"created": False, "reason": link_note or
                          "output-only (persist_link=False)"}

    events.log_event("ROUTE_SELECTED", node=req.node_id, policy=req.routing_policy,
                     protocol=req.protocol, transport=req.transport,
                     reason="config-builder selection")

    # 9. history (never on preview)
    if not for_preview and req.persist:
        entry = _history_append(req, result)
        entry["uri"] = compiled.uri      # server-side (LINKS-uuid trust domain)
        entry["link_uuid"] = (link_result or {}).get("uuid")
        result["history_id"] = entry["history_id"]
        events.log_event("CONFIG_GENERATED", name=req.name or "(unnamed)",
                         protocol=compiled.protocol, transport=compiled.transport,
                         security=compiled.security, node=req.node_id,
                         routing=req.routing_policy, client=req.client_format,
                         checksum=compiled.checksum, history_id=result["history_id"],
                         link_uuid=entry["link_uuid"])
    return result


def _compile_routing_outputs(req: ConfigRequest, route_res: dict) -> dict:
    import domestic_route_engine as dre
    policy = route_res.get("policy")
    detail: dict = {}
    if policy is None:
        return detail
    detail["policy"] = policy.to_dict()
    legs = {}
    for cls, leg_name in (("IRAN_DOMESTIC", "iran"), ("NON_IRAN", "international"),
                          ("UNKNOWN", "unknown")):
        leg = {"IRAN_DOMESTIC": policy.iran, "NON_IRAN": policy.international,
               "UNKNOWN": policy.unknown}[cls]
        if leg == "DIRECT":
            egress = "USER_ISP (VPN BYPASSED)"
        elif leg == "BLOCK":
            egress = "NONE (refused)"
        elif leg_name == "iran" and policy.name == "IRAN_PROXY":
            egress = "IRAN_GATEWAY (expected — VERIFIED only with evidence)"
        else:
            egress = "EMIX exit node (verified separately)"
        legs[cls] = {"decision": leg, "egress": egress}
    detail["legs"] = legs
    if policy.name == "IRAN_PROXY":
        detail["iran_gateway"] = route_res.get("gateway")
    if policy.iran in ("DIRECT", "BLOCK"):
        rules = dre.compile_split_tunnel_rules(policy, req.client_format, True)
        if rules.get("verdict") == "SPLIT_TUNNEL_SUPPORTED":
            detail["split_rules"] = rules
    return detail


def _request_view(req: ConfigRequest, mask: bool = True) -> dict:
    d = asdict(req)
    if mask:
        if d.get("credential"):
            d["credential"] = "<set>"
        if d.get("ss_password"):
            d["ss_password"] = "<set>"
    return d


# ── Generated config history (spec §21 — bounded, server-side) ──────────────

_history: List[dict] = []
_hist_lock = asyncio.Lock()


def _history_append(req: ConfigRequest, result: dict) -> dict:
    entry = {
        "history_id": f"cfg-{_uuid.uuid4().hex[:10]}",
        "name": req.name or f"{req.protocol}-{req.transport}",
        "created_at": time.time(),
        "status": "GENERATED",
        "checksum": result.get("checksum"),
        # full spec stored SERVER-SIDE (same trust domain as LINKS uuid storage);
        # masked in list responses, revealed only in the authed view action
        "spec": asdict(req),
        "outputs_summary": {
            "protocol": req.protocol, "transport": req.transport,
            "security": req.security, "node": req.node_id,
            "endpoint_profile": req.endpoint_profile_id or "standard",
            "routing": req.routing_policy, "client_format": req.client_format,
        },
        "account_id": req.account_id or "",
        "subscription_id": req.subscription_id or "",
    }
    _history.append(entry)
    del _history[:-HISTORY_BOUND]
    return entry


def list_history(limit: int = 100, account_id: str = "") -> List[dict]:
    out = []
    for e in reversed(_history):
        if account_id and e.get("account_id") != account_id:
            continue
        out.append({
            "history_id": e["history_id"], "name": e["name"],
            "created_at": e["created_at"],
            "created_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                            time.gmtime(e["created_at"])),
            "status": e["status"], "checksum": e["checksum"],
            "link_uuid": e.get("link_uuid"),
            **e["outputs_summary"], "account_id": e.get("account_id", ""),
        })
        if len(out) >= limit:
            break
    return out


async def get_history_entry(history_id: str, reveal: bool = False) -> Optional[dict]:
    for e in _history:
        if e["history_id"] == history_id:
            out = dict(e)
            out["created_at_iso"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(e["created_at"]))
            if not reveal:
                out["spec"] = _request_view(ConfigRequest(**{
                    k: v for k, v in e["spec"].items()
                    if k in ConfigRequest.__dataclass_fields__}))
                out.pop("uri", None)     # credential-bearing URI only on reveal
            return out
    return None


async def regenerate(history_id: str) -> dict:
    """Regenerate from the stored spec — the SAME pipeline (compiler + routing).
    Deterministic compiler + same credential → same output (checksum match).
    Phase 40: outputs-only — a regenerated artifact never duplicates the live
    link (the original link stays the single testable object)."""
    entry = await get_history_entry(history_id, reveal=True)
    if entry is None:
        return {"ok": False, "errors": [f"history entry '{history_id}' not found"]}
    spec = {k: v for k, v in entry["spec"].items()
            if k in ConfigRequest.__dataclass_fields__}
    req = ConfigRequest(**spec)
    req.persist = True
    req.persist_link = False      # outputs-only; the live link is not duplicated
    result = await build_config(req, for_preview=False)
    if result.get("ok"):
        # record regeneration linkage
        result["regenerated_from"] = history_id
        if result.get("checksum") == entry.get("checksum"):
            result["deterministic_match"] = True
        else:
            result["deterministic_match"] = False
            result["note"] = ("checksum differs — the stored spec carried "
                              "auto-generated credentials that are re-emitted "
                              "identically only when the compiler inputs match")
    return result


async def delete_history(history_id: str) -> dict:
    async with _hist_lock:
        for i, e in enumerate(_history):
            if e["history_id"] == history_id:
                del _history[i]
                return {"ok": True, "deleted": history_id}
    return {"ok": False, "errors": [f"history entry '{history_id}' not found"]}


def history_summary() -> dict:
    by_protocol: Dict[str, int] = {}
    for e in _history:
        p = e["outputs_summary"].get("protocol", "?")
        by_protocol[p] = by_protocol.get(p, 0) + 1
    return {"entries": len(_history), "bound": HISTORY_BOUND,
            "by_protocol": by_protocol, "engine": f"config_builder/{ENGINE_VERSION}"}


# ── Persistence (rvg_state.json additive key "config_builder") ───────────────

def persist_snapshot() -> dict:
    return {"history": [dict(e) for e in _history]}


def restore_snapshot(data: dict) -> None:
    _history.clear()
    for e in (data or {}).get("history", []):
        try:
            if all(k in e for k in ("history_id", "spec", "created_at")):
                _history.append(e)
        except Exception:
            continue
    del _history[:-HISTORY_BOUND]


def reset_for_tests() -> None:
    _history.clear()
    global _host_provider, _worker_domain_provider, _cdn_domain_provider, _link_factory
    _host_provider = None
    _worker_domain_provider = None
    _cdn_domain_provider = None
    _link_factory = None


# ── API (authed — spec §28) ─────────────────────────────────────────────────

def register_routes(app, require_auth) -> None:
    from fastapi import Depends, Query
    from fastapi.responses import JSONResponse

    _auth = [Depends(require_auth)]

    @app.post("/api/config-builder/preview", dependencies=_auth)
    async def api_preview(body: BuilderRequest):
        req = ConfigRequest(**body.model_dump())
        req.persist = False
        out = await build_config(req, for_preview=True)
        return JSONResponse(out, status_code=200 if out.get("ok") else 422)

    @app.post("/api/config-builder/generate", dependencies=_auth)
    async def api_generate(body: BuilderRequest):
        req = ConfigRequest(**body.model_dump())
        out = await build_config(req, for_preview=False)
        return JSONResponse(out, status_code=200 if out.get("ok") else 422)

    @app.get("/api/config-builder/history", dependencies=_auth)
    async def api_history(limit: int = Query(100, ge=1, le=200),
                          account_id: str = Query("")):
        return {"ok": True, "history": list_history(limit, account_id),
                **history_summary()}

    @app.get("/api/config-builder/history/{history_id}", dependencies=_auth)
    async def api_history_view(history_id: str, reveal: bool = Query(False)):
        entry = await get_history_entry(history_id, reveal=reveal)
        if entry is None:
            return JSONResponse({"ok": False, "errors": ["not found"]},
                                status_code=404)
        return {"ok": True, "entry": entry}

    @app.post("/api/config-builder/history/{history_id}/regenerate",
              dependencies=_auth)
    async def api_history_regenerate(history_id: str):
        out = await regenerate(history_id)
        return JSONResponse(out, status_code=200 if out.get("ok") else 404)

    @app.delete("/api/config-builder/history/{history_id}", dependencies=_auth)
    async def api_history_delete(history_id: str):
        out = await delete_history(history_id)
        return JSONResponse(out, status_code=200 if out.get("ok") else 404)
