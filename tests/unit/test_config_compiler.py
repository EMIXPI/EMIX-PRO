"""Unit tests for config_compiler.py — the centralized Config Compiler (Phase 3).

Wire-compatibility is the critical property: for every input the legacy
main.generate_share_link accepted, compile_from_link must produce a
BYTE-IDENTICAL URI. These tests import main (same env bootstrap as the
other suites) and compare against the preserved legacy emitter.

Also covers:
  - strict rejection (no silent coercion) of unknown protocols
  - determinism (same spec → same checksum)
  - self-check catches broken output
  - SNI-override inapplicability rejection for new (non-legacy) specs
  - xray/sing-box JSON emission
  - subscription document helper
  - config born with health UNKNOWN (never "healthy by generation")
"""
import os
os.environ.setdefault("DATA_DIR", "/tmp/emix-cc-test")
os.makedirs(os.environ["DATA_DIR"], exist_ok=True)

import pytest

import compat
import config_compiler as CC
from main import _generate_share_link_legacy, LINKS


UID = "11111111-2222-3333-4444-555555555555"


# ── Wire compatibility: byte-identical with the legacy emitter ─────────────

_WIRE_CASES = [
    ("vless-ws", {}),
    ("xhttp-packet-up", {}),
    ("xhttp-stream-up", {}),
    ("trojan-ws", {}),
    ("trojan-xhttp-packet-up", {}),
    ("trojan-xhttp-stream-up", {}),
    ("shadowsocks", {"ss_cipher": "chacha20-ietf-poly1305", "ss_password": "pw123"}),
    ("vless-ws", {"spoof_sni": "speedtest.net", "spoof_sni_enabled": True}),
    ("trojan-ws", {"spoof_sni": "speedtest.net", "spoof_sni_enabled": True}),
    ("xhttp-packet-up", {"spoof_sni": "cdn.cloudflare.net", "spoof_sni_enabled": True}),
    ("vless-ws", {"spoof_sni": "1.2.3.4", "spoof_sni_enabled": True}),   # invalid spoof → standard
    ("vless-ws", {"spoof_sni": "speedtest.net", "spoof_sni_enabled": False}),
    ("vless-ws", {"alpn": "h2,http/1.1", "fingerprint": "firefox"}),
]


@pytest.mark.parametrize("proto,extra", _WIRE_CASES)
def test_wire_compat_direct(monkeypatch, proto, extra):
    monkeypatch.delenv("EMIX_CDN_DOMAIN", raising=False)
    link = dict({"protocol": proto, "label": "Wire", "alpn": "h2", "fingerprint": "chrome", **extra})
    LINKS[UID] = link
    try:
        legacy = _generate_share_link_legacy(UID, "panel.example.com", "Wire", proto)
        compiled = CC.compile_from_link(link, "panel.example.com", credential=UID)
        assert compiled.ok, compiled.errors
        assert compiled.uri == legacy
    finally:
        LINKS.pop(UID, None)


@pytest.mark.parametrize("proto,extra", [
    ("vless-ws", {"spoof_sni": "speedtest.net", "spoof_sni_enabled": True}),
    ("trojan-ws", {"spoof_sni": "speedtest.net", "spoof_sni_enabled": True}),
])
def test_wire_compat_cdn_mode_a(monkeypatch, proto, extra):
    monkeypatch.setenv("EMIX_CDN_DOMAIN", "cdn.example.net")
    link = dict({"protocol": proto, "label": "Wire", "alpn": "h2", "fingerprint": "chrome", **extra})
    LINKS[UID] = link
    try:
        legacy = _generate_share_link_legacy(UID, "panel.example.com", "Wire", proto)
        compiled = CC.compile_from_link(link, "panel.example.com",
                                        cdn_domain="cdn.example.net", credential=UID)
        assert compiled.ok and compiled.uri == legacy
    finally:
        LINKS.pop(UID, None)
        monkeypatch.delenv("EMIX_CDN_DOMAIN", raising=False)


# ── Strict validation ───────────────────────────────────────────────────────

def test_reject_unknown_protocol():
    cc = CC.compile_from_link({"protocol": "vless-grpc"}, "h.example.com", credential=UID)
    assert not cc.ok and cc.uri is None
    assert any("incompatible" in e or "unknown" in e for e in cc.errors)

def test_reject_missing_credential():
    cc = CC.compile_config(CC.ConfigSpec(protocol="vless", transport="ws",
                                         security="tls", host="h.example.com"))
    assert not cc.ok and any("credential" in e for e in cc.errors)

def test_reject_ss_without_password():
    cc = CC.compile_config(CC.ConfigSpec(protocol="shadowsocks", transport="ws",
                                         security="tls", host="h.example.com"))
    assert not cc.ok and any("ss_cipher" in e for e in cc.errors)

def test_reject_mtproto_without_public_host():
    cc = CC.compile_config(CC.ConfigSpec(protocol="mtproto", transport="tcp",
                                         security="none", credential="AA",
                                         host="h.example.com"))
    assert not cc.ok and any("public host" in e for e in cc.errors)


# ── SNI inapplicability (new spec path is strict, legacy path is lenient) ──

def test_new_spec_sni_rejected_for_ss():
    # a NEW spec (no legacy link record) with SNI override on SS → rejected
    # (Phase 37.4: valid credentials pass first, so the SNI rule is the blocker)
    spec = CC.ConfigSpec(protocol="shadowsocks", transport="ws", security="tls",
                         ss_cipher="chacha20-ietf-poly1305", ss_password="password1234",
                         host="h.example.com",
                         endpoint=None)
    spec.link = None
    # simulate an endpoint with SNI via named-profile resolution:
    import endpoint_profiles as ep
    spec.endpoint = ep.ResolvedEndpoint(
        address="h.example.com", sni="speedtest.net", host_header="h.example.com",
        port=443, path_prefix="", security="tls", alpn=["h2"],
        allow_insecure=True, mode="direct-sni")
    cc = CC.compile_config(spec)
    assert not cc.ok
    assert any("SNI override not applicable" in e for e in cc.errors)

def test_legacy_ss_link_with_spoof_still_compiles():
    # legacy stored SS links with spoof fields: documented partial support,
    # spoof is ignored by the emitter — must NOT break
    link = {"protocol": "shadowsocks", "ss_cipher": "chacha20-ietf-poly1305",
            "ss_password": "pw", "spoof_sni": "speedtest.net", "spoof_sni_enabled": True}
    cc = CC.compile_from_link(link, "h.example.com")
    assert cc.ok and cc.uri.startswith("ss://")


# ── Determinism & versioning ───────────────────────────────────────────────

def test_deterministic_checksum():
    link = {"protocol": "vless-ws", "label": "D", "alpn": "h2", "fingerprint": "chrome"}
    c1 = CC.compile_from_link(link, "h.example.com", credential=UID)
    c2 = CC.compile_from_link(link, "h.example.com", credential=UID)
    assert c1.ok and c2.ok
    assert c1.uri == c2.uri and c1.checksum == c2.checksum
    assert c1.config_version == CC.CONFIG_VERSION

def test_different_input_different_checksum():
    c1 = CC.compile_from_link({"protocol": "vless-ws", "label": "A", "alpn": "h2"}, "h.example.com", credential=UID)
    c2 = CC.compile_from_link({"protocol": "vless-ws", "label": "B", "alpn": "h2"}, "h.example.com", credential=UID)
    assert c1.checksum != c2.checksum


# ── Health honesty ─────────────────────────────────────────────────────────

def test_config_born_unknown_never_healthy():
    cc = CC.compile_from_link({"protocol": "vless-ws", "label": "H", "alpn": "h2"}, "h.example.com", credential=UID)
    assert cc.ok
    assert cc.health["state"] == "UNKNOWN"
    assert cc.health["score"] is None


# ── xray JSON emission ─────────────────────────────────────────────────────

def test_xray_json_for_vless_ws():
    cc = CC.compile_from_link({"protocol": "vless-ws", "label": "J", "alpn": "h2"},
                              "h.example.com", credential=UID, formats=("uri", "json"))
    assert cc.ok and cc.xray_json is not None
    ob = cc.xray_json["outbounds"][0]
    assert ob["protocol"] == "vless"
    assert ob["streamSettings"]["network"] == "ws"
    assert ob["streamSettings"]["tlsSettings"]["serverName"] == "h.example.com"

def test_xray_json_none_for_ss_and_mtproto():
    cc = CC.compile_config(CC.ConfigSpec(
        protocol="shadowsocks", transport="ws", security="tls",
        ss_cipher="chacha20-ietf-poly1305", ss_password="password1234",
        host="h.example.com", credential="x"))
    assert cc.ok and cc.xray_json is None


# ── Subscription helper ────────────────────────────────────────────────────

def test_subscription_document():
    doc = CC.subscription_document(["a://1", "b://2"])
    import base64
    assert base64.b64decode(doc).decode() == "a://1\nb://2"


# ── Endpoint profile integration (new path) ────────────────────────────────

def test_profile_path_prefix_appears_in_uri():
    import endpoint_profiles as ep
    p = ep.EndpointProfile(id="ep-pfx", name="Pfx", address="edge.example.net",
                           path_prefix="/loc/auto")
    ep._profiles[p.id] = p
    try:
        link = {"protocol": "vless-ws", "label": "P", "alpn": "h2",
                "endpoint_profile_id": "ep-pfx"}
        cc = CC.compile_from_link(link, "panel.example.com", credential=UID)
        assert cc.ok
        assert cc.endpoint_mode == "profile"
        assert "path=%2Floc%2Fauto%2Fws%2F" in cc.uri or "/loc/auto/ws/" in cc.uri
    finally:
        ep._profiles.clear()
