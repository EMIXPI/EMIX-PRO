"""Unit tests for endpoint_profiles.py — Endpoint & Transport Profile Engine
(Phase 4/25 — the SNI-Spoofing successor with full migration compatibility).

Covers:
  - hostname/port validation
  - profile structural validation (bad address, bad port, bad alpn...)
  - profile↔protocol compatibility (SNI inapplicable to SS/MTProto rejected)
  - resolve(): legacy Mode A (CDN) / Mode B (direct+allowInsecure) /
    standard / named-profile / inline-endpoint paths
  - persistence snapshot round-trip
"""
import pytest

import compat
import endpoint_profiles as ep


# ── Validation primitives ─────────────────────────────────────────────────

def test_validate_hostname_ok():
    ok, norm = ep.validate_hostname("Example.COM")
    assert ok and norm == "example.com"

def test_validate_hostname_rejects_ip():
    assert not ep.validate_hostname("1.2.3.4")[0]

def test_validate_hostname_accepts_ip_when_allowed():
    assert ep.validate_hostname("1.2.3.4", allow_ip=True)[0]

def test_validate_hostname_rejects_localhost():
    assert not ep.validate_hostname("localhost")[0]
    assert not ep.validate_hostname("127.0.0.1")[0]

def test_validate_hostname_rejects_garbage():
    assert not ep.validate_hostname("")[0]
    assert not ep.validate_hostname("a b c")[0]
    assert not ep.validate_hostname(None)[0]

def test_validate_port_bounds():
    assert ep.validate_port(443)[0]
    assert ep.validate_port(1)[0]
    assert ep.validate_port(65535)[0]
    assert not ep.validate_port(0)[0]
    assert not ep.validate_port(65536)[0]
    assert not ep.validate_port("abc")[0]


# ── Profile validation ─────────────────────────────────────────────────────

def _base_profile(**kw):
    d = dict(id="ep-x01", name="X", address="edge.example.net")
    d.update(kw)
    return ep.EndpointProfile(**d)

def test_profile_valid_by_default():
    assert ep.validate_profile(_base_profile()) == []

def test_profile_rejects_bad_address():
    errs = ep.validate_profile(_base_profile(address="not a host"))
    assert any("address" in e for e in errs)

def test_profile_rejects_bad_port():
    errs = ep.validate_profile(_base_profile(port=99999))
    assert any("port" in e for e in errs)

def test_profile_rejects_bad_alpn():
    errs = ep.validate_profile(_base_profile(alpn=["h2", "h2"]))
    assert any("alpn" in e for e in errs)

def test_profile_rejects_bad_path_prefix():
    errs = ep.validate_profile(_base_profile(path_prefix="loc/auto"))
    assert any("path_prefix" in e for e in errs)

def test_profile_rejects_bad_ip_version():
    errs = ep.validate_profile(_base_profile(ip_version="ipv9"))
    assert any("ip_version" in e for e in errs)

def test_profile_sni_must_be_hostname_not_ip():
    errs = ep.validate_profile(_base_profile(sni="1.2.3.4"))
    assert any("sni" in e for e in errs)


# ── Profile ↔ protocol compatibility ──────────────────────────────────────

def test_profile_with_sni_rejected_for_shadowsocks():
    p = _base_profile(sni="speedtest.net")
    errs = ep.validate_profile_for_protocol(p, "shadowsocks")
    assert any("not applicable" in e for e in errs)

def test_profile_with_sni_rejected_for_mtproto():
    p = _base_profile(sni="speedtest.net")
    errs = ep.validate_profile_for_protocol(p, "mtproto")
    assert errs

def test_profile_with_sni_accepted_for_vless_ws():
    p = _base_profile(sni="speedtest.net")
    assert ep.validate_profile_for_protocol(p, "vless-ws") == []

def test_profile_without_sni_ok_for_shadowsocks():
    p = _base_profile()  # no sni
    assert ep.validate_profile_for_protocol(p, "shadowsocks") == []

def test_profile_transport_mismatch_rejected():
    p = _base_profile(transport="ws")
    errs = ep.validate_profile_for_protocol(p, "trojan-xhttp-packet-up")
    assert any("transport" in e for e in errs)


# ── resolve(): migration compatibility with legacy spoof fields ────────────

HOST = "panel.example.com"

def test_resolve_standard_no_fields():
    r = ep.resolve({}, HOST)
    assert r.mode == "standard"
    assert r.address == HOST and r.sni == HOST and r.host_header == HOST
    assert not r.allow_insecure

def test_resolve_legacy_mode_b_direct_sni():
    r = ep.resolve({"spoof_sni": "speedtest.net", "spoof_sni_enabled": True}, HOST)
    assert r.mode == "direct-sni"
    assert r.address == HOST and r.sni == "speedtest.net"
    assert r.allow_insecure  # legacy Mode B semantics
    assert any("allowInsecure" in n for n in r.notes)

def test_resolve_legacy_mode_a_cdn():
    r = ep.resolve({"spoof_sni": "speedtest.net", "spoof_sni_enabled": True},
                   HOST, cdn_domain="cdn.example.net")
    assert r.mode == "cdn"
    assert r.address == "cdn.example.net"
    assert r.sni == "speedtest.net"
    assert not r.allow_insecure

def test_resolve_legacy_spoof_invalid_falls_back():
    r = ep.resolve({"spoof_sni": "1.2.3.4", "spoof_sni_enabled": True}, HOST)
    assert r.mode == "standard"
    assert r.sni == HOST

def test_resolve_legacy_disabled_ignored():
    r = ep.resolve({"spoof_sni": "speedtest.net", "spoof_sni_enabled": False}, HOST)
    assert r.mode == "standard" and r.sni == HOST

def test_resolve_named_profile():
    p = _base_profile(id="ep-named", name="Named", address="edge.example.net",
                      sni="sni.example.net", host_header="hh.example.net",
                      path_prefix="/loc/auto", port=8443)
    ep._profiles[p.id] = p
    try:
        r = ep.resolve({"endpoint_profile_id": "ep-named"}, HOST)
        assert r.mode == "profile"
        assert r.address == "edge.example.net"
        assert r.sni == "sni.example.net"
        assert r.host_header == "hh.example.net"
        assert r.port == 8443
        assert r.path_prefix == "/loc/auto"
    finally:
        ep._profiles.clear()

def test_resolve_missing_profile_falls_back_with_note():
    r = ep.resolve({"endpoint_profile_id": "ep-nope"}, HOST)
    assert r.mode == "standard"
    assert any("not found" in n for n in r.notes)

def test_resolve_inline_endpoint():
    r = ep.resolve({"endpoint": {"address": "edge.example.net", "sni": "s.example.net",
                                 "path_prefix": "/loc/auto"}}, HOST)
    assert r.mode == "profile"
    assert r.address == "edge.example.net"
    assert r.path_prefix == "/loc/auto"


# ── Persistence ────────────────────────────────────────────────────────────

def test_persistence_round_trip():
    p = _base_profile(id="ep-p1", name="Persist")
    ep._profiles.clear()
    ep._profiles[p.id] = p
    snap = ep.persist_snapshot()
    ep._profiles.clear()
    ep.restore_snapshot(snap)
    assert "ep-p1" in ep._profiles
    assert ep._profiles["ep-p1"].address == "edge.example.net"
    ep._profiles.clear()

def test_restore_survives_garbage():
    ep.restore_snapshot({"endpoint_profiles": [{"id": "bad", "garbage": True}]})
    assert ep._profiles == {}


# ── CRUD engine (async) ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_update_delete_profile():
    import asyncio
    p = _base_profile(id="ep-crud", name="CRUD")
    created = await ep.create_profile(p)
    assert created.id == "ep-crud"
    # duplicate id rejected
    with pytest.raises(ValueError):
        await ep.create_profile(_base_profile(id="ep-crud", name="Other"))
    # duplicate name rejected
    with pytest.raises(ValueError):
        await ep.create_profile(_base_profile(id="ep-crud2", name="CRUD"))
    # update
    updated = await ep.update_profile("ep-crud", {"port": 8443})
    assert updated.port == 8443
    # update with invalid port rejected
    with pytest.raises(ValueError):
        await ep.update_profile("ep-crud", {"port": 99999})
    # delete
    assert await ep.delete_profile("ep-crud") is True
    assert await ep.delete_profile("ep-crud") is False
