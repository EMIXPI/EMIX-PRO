"""Unit tests for ip_quality.py — IP Quality Engine (Phase 9/28).

Focus on the PURE assess() classification (no network) plus provider
result plumbing. Never labels an IP CLEAN without evidence.
"""
import pytest

import ip_quality as ipq


def _prov(ok=True, proxy=None, hosting=None, rdns=None, cc="NL", org="Example BV",
          asn="AS0001", vpn=None, provider="p1"):
    return ipq.ProviderResult(provider=provider, ok=ok, asn=asn, org=org,
                              country="Netherlands", country_code=cc,
                              region="NH", city="Amsterdam", rdns=rdns,
                              is_proxy=proxy, is_hosting=hosting, is_vpn=vpn)


_TCP_OK = {"probes": 3, "ok": 3, "loss_pct": 0.0, "latency_ms": 35.0, "jitter_ms": 2.0}
_TLS_OK = {"tls_ok": True, "tls_ms": 90.0}


# ── CLEAN requires explicit negative evidence ──────────────────────────────

def test_clean_only_with_explicit_flags():
    # provider that reports proxy flags as False + reachable → CLEAN
    a = ipq.assess("1.1.1.1", [_prov(proxy=False, hosting=False)], _TCP_OK, _TLS_OK)
    assert a.classification == "CLEAN"

def test_good_when_flags_unverified():
    # providers that don't report proxy fields → GOOD (honest default)
    a = ipq.assess("1.1.1.1", [_prov()], _TCP_OK, _TLS_OK)
    assert a.classification == "GOOD"
    assert any("unverified" in n for n in a.notes)

def test_questionable_when_proxy_flagged():
    a = ipq.assess("1.1.1.1", [_prov(proxy=True)], _TCP_OK, _TLS_OK)
    assert a.classification == "QUESTIONABLE"
    assert any("negative reputation" in n for n in a.notes)

def test_questionable_when_hosting_flagged():
    a = ipq.assess("1.1.1.1", [_prov(hosting=True)], _TCP_OK, _TLS_OK)
    assert a.classification == "QUESTIONABLE"

def test_degraded_when_packet_loss():
    tcp = {"probes": 3, "ok": 2, "loss_pct": 33.3, "latency_ms": 40.0}
    a = ipq.assess("1.1.1.1", [_prov()], tcp, _TLS_OK)
    assert a.classification == "DEGRADED"

def test_blocked_when_unreachable():
    tcp = {"probes": 3, "ok": 0, "loss_pct": 100.0, "latency_ms": None}
    a = ipq.assess("1.1.1.1", [_prov()], tcp, {})
    assert a.classification == "BLOCKED"

def test_blocked_when_abuse_reported():
    p = _prov(proxy=False)
    p.abuse_confidence = 85
    a = ipq.assess("1.1.1.1", [p], _TCP_OK, _TLS_OK)
    assert a.classification == "BLOCKED"

def test_unknown_when_no_provider_answered():
    a = ipq.assess("1.1.1.1", [_prov(ok=False)], _TCP_OK, _TLS_OK)
    assert a.classification == "UNKNOWN"
    assert any("no provider" in n for n in a.notes)


# ── Confidence scoring ─────────────────────────────────────────────────────

def test_confidence_grows_with_evidence():
    one = ipq.assess("1.1.1.1", [_prov()], _TCP_OK, {})
    two = ipq.assess("1.1.1.1", [_prov(provider="p1"), _prov(provider="p2")], _TCP_OK, _TLS_OK)
    assert two.confidence >= one.confidence
    assert 0.0 <= one.confidence <= 1.0 and 0.0 <= two.confidence <= 1.0

def test_agreement_bonus():
    agree = ipq.assess("1.1.1.1", [_prov(cc="NL", provider="a"), _prov(cc="NL", provider="b")], _TCP_OK, _TLS_OK)
    disagree = ipq.assess("1.1.1.1", [_prov(cc="NL", provider="a"), _prov(cc="DE", provider="b")], _TCP_OK, _TLS_OK)
    assert agree.confidence > disagree.confidence


# ── Geo merge ──────────────────────────────────────────────────────────────

def test_geo_fields_merged_from_first_provider_that_reports():
    p1 = _prov(provider="a", org="A BV")
    p2 = _prov(provider="b", org="B BV", rdns="edge.example.net")
    a = ipq.assess("1.1.1.1", [p1, p2], _TCP_OK, _TLS_OK)
    assert a.org == "A BV"           # first wins
    assert a.rdns == "edge.example.net"  # p1 didn't report → p2's value

def test_reputation_signals_collected():
    p1 = _prov(provider="ip-api.com", proxy=False, hosting=True)
    a = ipq.assess("1.1.1.1", [p1], _TCP_OK, _TLS_OK)
    assert a.reputation_signals["ip-api.com:is_proxy"] is False
    assert a.reputation_signals["ip-api.com:is_hosting"] is True


# ── to_dict shape ──────────────────────────────────────────────────────────

def test_to_dict_shape():
    a = ipq.assess("1.1.1.1", [_prov()], _TCP_OK, _TLS_OK)
    d = a.to_dict()
    assert d["ip"] == "1.1.1.1"
    assert d["classification"] in ipq.CLASSIFICATIONS
    assert "checked_at_iso" in d
    assert "providers" in d and "tcp" in d and "tls" in d


# ── Provider registry defaults ─────────────────────────────────────────────

def test_default_providers_no_token():
    import os
    saved = os.environ.pop("EMIX_IPINFO_TOKEN", None)
    try:
        providers = ipq.default_providers()
        names = [p.name for p in providers]
        assert "ipapi.co" in names and "ip-api.com" in names
        assert "ipinfo.io" not in names
    finally:
        if saved:
            os.environ["EMIX_IPINFO_TOKEN"] = saved

def test_default_providers_with_token():
    import os
    os.environ["EMIX_IPINFO_TOKEN"] = "test-token"
    try:
        providers = ipq.default_providers()
        assert any(p.name == "ipinfo.io" for p in providers)
    finally:
        os.environ.pop("EMIX_IPINFO_TOKEN", None)


# ── Cache / history invariants ─────────────────────────────────────────────

def test_cache_and_summary_start_empty():
    assert ipq.all_cached() == {}
    s = ipq.summary()
    assert s["tracked"] == 0
    assert set(s["by_classification"]) == set(ipq.CLASSIFICATIONS)
