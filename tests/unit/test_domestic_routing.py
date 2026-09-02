# tests/unit/test_domestic_routing.py — Phase 38 / P17
# The 13 mandatory domestic-routing tests from the spec + engine internals.
# All network access is injected/faked — NO REAL_NETWORK tests here.

import asyncio
import ipaddress
import time

import pytest

import domestic_route_engine as dre
import domestic_rules_updater as dru


@pytest.fixture(autouse=True)
def clean():
    dre.reset_for_tests()
    # small known dataset for deterministic tests (the real 2.5k-prefix
    # RIPEstat seed is exercised separately in test_seed_dataset)
    dre._db.load_prefixes(["5.10.0.0/16", "2.144.0.0/14", "185.5.228.0/22",
                           "2001:db8:aa::/48"], {
        "version": 42, "source": "test", "confidence": "test"})
    dru.reset_for_tests()
    yield
    dre.reset_for_tests()
    dru.reset_for_tests()




# ── 1-3: classification ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_iranian_cidr_is_iran_domestic():
    cls, meta = dre._db.classify("5.10.7.7")
    assert cls == "IRAN_DOMESTIC"
    assert meta["prefix"] == "5.10.0.0/16"


@pytest.mark.asyncio
async def test_non_iranian_cidr_is_non_iran():
    cls, _ = dre._db.classify("8.8.8.8")
    assert cls == "NON_IRAN"


@pytest.mark.asyncio
async def test_unparseable_ip_is_unknown_never_guessed():
    cls, meta = dre._db.classify("not-an-ip")
    assert cls == "UNKNOWN"
    assert meta is None


@pytest.mark.asyncio
async def test_ipv6_classification():
    cls, meta = dre._db.classify("2001:db8:aa::1")
    assert cls == "IRAN_DOMESTIC"
    assert meta["prefix"] == "2001:db8:aa::/48"
    assert dre._db.classify("2606:4700::1")[0] == "NON_IRAN"


@pytest.mark.asyncio
async def test_longest_prefix_match_wins():
    dre._db.load_prefixes(["5.0.0.0/8", "5.10.0.0/16"], {"version": 43})
    cls, meta = dre._db.classify("5.10.1.1")
    assert meta["prefix"] == "5.10.0.0/16"          # longest match
    cls, meta = dre._db.classify("5.99.1.1")
    assert meta["prefix"] == "5.0.0.0/8"


# ── 4-6: policy application ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_iran_domestic_plus_iran_direct_is_direct():
    v = await (dre.decide_route("5.10.1.1", dre.get_policy("IRAN_DIRECT")))
    assert v["classification"] == "IRAN_DOMESTIC"
    assert v["decision"] == "DIRECT"
    assert v["vpn_bypassed"] is True
    assert v["egress"] == "USER_ISP"                 # ← the critical semantic
    assert v["domestic_status"] == "DOMESTIC_ROUTE_VERIFIED"


@pytest.mark.asyncio
async def test_non_iran_plus_iran_direct_is_vpn():
    v = await (dre.decide_route("8.8.8.8", dre.get_policy("IRAN_DIRECT")))
    assert v["classification"] == "NON_IRAN"
    assert v["decision"] == "VPN"
    assert v["egress"] == "EMIX_ROUTE"


@pytest.mark.asyncio
async def test_unknown_plus_default_vpn_is_vpn():
    v = await (dre.decide_route("unresolvable.example", dre.get_policy("IRAN_DIRECT")))
    assert v["classification"] == "UNKNOWN"
    assert v["decision"] == "VPN"                    # default policy for unknown
    assert v["resolved_ip"] is None


@pytest.mark.asyncio
async def test_all_vpn_policy_never_directs_even_iranian():
    v = await (dre.decide_route("5.10.1.1", dre.get_policy("ALL_VPN")))
    assert v["decision"] == "VPN"
    assert v["domestic_status"] == "DOMESTIC_ELIGIBLE"


@pytest.mark.asyncio
async def test_default_policy_not_silently_changed():
    # user default (unknown leg) stays VPN under IRAN_DIRECT preset
    p = dre.get_policy("IRAN_DIRECT")
    assert p.unknown == "VPN"
    v = await (dre.decide_route("999.999.999.999", p))
    assert v["decision"] == "VPN"


# ── 7-8: updater robustness (invalid/empty never replace working dataset) ──

def _snapshot():
    return dre.dataset_status()


@pytest.mark.asyncio
async def test_invalid_ruleset_retains_previous():
    before = _snapshot()
    with pytest.raises(ValueError):
        dre.apply_dataset({"prefixes": ["garbage-not-a-prefix"] * 60},
                          require_min=10)
    assert _snapshot()["version"] == before["version"]
    assert _snapshot()["prefix_count"] == before["prefix_count"]


@pytest.mark.asyncio
async def test_empty_update_retains_previous():
    before = _snapshot()
    with pytest.raises(ValueError):
        dre.apply_dataset({"prefixes": []})
    assert _snapshot()["prefix_count"] == before["prefix_count"]
    assert _snapshot()["version"] == before["version"]


@pytest.mark.asyncio
async def test_checksum_mismatch_retains_previous():
    before = _snapshot()
    with pytest.raises(ValueError):
        dre.apply_dataset({"prefixes": ["5.0.0.0/8"] * 60,
                           "checksum": "0" * 64}, require_min=10)
    assert _snapshot()["prefix_count"] == before["prefix_count"]


@pytest.mark.asyncio
async def test_updater_network_failure_keeps_previous_dataset():
    async def failing_fetch(url, timeout):
        raise RuntimeError("network down")
    dru.set_fetch_fn(failing_fetch)
    before = _snapshot()
    report = await (dru.update_rules())
    assert report["ok"] is False
    assert "previous known-good dataset retained" in report["fallback"]
    assert _snapshot()["prefix_count"] == before["prefix_count"]


@pytest.mark.asyncio
async def test_updater_applies_valid_ripestat_json():
    async def ok_fetch(url, timeout):
        return ('{"data": {"query_time": "2026-09-01T00:00:00", "resources": '
                '{"ipv4": ["5.10.0.0/16", "2.144.0.0/14", "1.2.3.0/24", '
                '"4.5.6.0/24", "7.8.9.0/24"], "ipv6": []}}}')
    dru.set_fetch_fn(ok_fetch)
    report = await (dru.update_rules(require_min=1))
    assert report["ok"] is True
    assert report["applied"] >= 5
    assert dre._db.classify("5.10.1.1")[0] == "IRAN_DOMESTIC"
    st = dru.status()
    assert st["last_successful_update"] is not None
    assert st["last_error"] is None


@pytest.mark.asyncio
async def test_updater_accepts_plain_text_format():
    async def ok_fetch(url, timeout):
        return "\n".join(["5.10.0.0/16", "2.144.0.0/14"] + [f"10.{i}.0.0/16" for i in range(20)])
    dru.set_fetch_fn(ok_fetch)
    report = await (dru.update_rules(require_min=1))
    assert report["ok"] is True
    assert dre._db.classify("2.144.1.1")[0] == "IRAN_DOMESTIC"


@pytest.mark.asyncio
async def test_updater_rejects_malformed_payload():
    async def bad_fetch(url, timeout):
        return "not json and not ^^^^^ cidr lines !!"
    dru.set_fetch_fn(bad_fetch)
    before = _snapshot()
    report = await (dru.update_rules())
    assert report["ok"] is False
    assert _snapshot()["prefix_count"] == before["prefix_count"]


@pytest.mark.asyncio
async def test_ripestat_range_format_is_normalized():
    async def ok_fetch(url, timeout):
        return ('{"data": {"resources": {"ipv4": '
                '["5.10.0.0-5.10.255.255", "2.144.0.0/14", "9.9.9.0/24", '
                '"8.8.8.0/24", "7.7.7.0/24"], "ipv6": []}}}')
    dru.set_fetch_fn(ok_fetch)
    report = await (dru.update_rules(require_min=1))
    assert report["ok"] is True
    assert dre._db.classify("5.10.200.1")[0] == "IRAN_DOMESTIC"   # from range


# ── 9: DNS changes → route follows actual destination IP ───────────────────

@pytest.mark.asyncio
async def test_route_follows_resolved_ip_not_domain_name():
    async def resolver(domain):
        return "5.10.1.1"          # .com domain resolving to an IRANIAN IP
    dre.set_resolver(resolver)
    v = await (dre.decide_route("somesite.com", dre.get_policy("IRAN_DIRECT")))
    assert v["resolved_ip"] == "5.10.1.1"
    assert v["classification"] == "IRAN_DOMESTIC"
    assert v["decision"] == "DIRECT"
    assert v["resolved_by"] == "dns"


@pytest.mark.asyncio
async def test_dns_change_to_international_flips_to_vpn():
    calls = {"n": 0}

    async def resolver(domain):
        calls["n"] += 1
        return "8.8.8.8" if calls["n"] > 1 else "5.10.1.1"
    dre.set_resolver(resolver)
    v1 = await (dre.decide_route("site.com", dre.get_policy("IRAN_DIRECT")))
    v2 = await (dre.decide_route("site.com", dre.get_policy("IRAN_DIRECT")))
    assert v1["decision"] == "DIRECT"
    assert v2["decision"] == "VPN"                  # route follows the NEW IP
    assert v2["classification"] == "NON_IRAN"


@pytest.mark.asyncio
async def test_no_ir_suffix_heuristic():
    # classification NEVER derived from domain suffix (spec: no .ir-only rule)
    async def resolver(domain):
        return "8.8.4.4" if domain.endswith(".ir") else "5.10.1.1"
    dre.set_resolver(resolver)
    v = await (dre.decide_route("international.ir", dre.get_policy("IRAN_DIRECT")))
    assert v["classification"] == "NON_IRAN"        # .ir but international IP
    assert v["decision"] == "VPN"


# ── 10-11: Cloudflare / Railway never Iranian egress ───────────────────────

@pytest.mark.asyncio
async def test_cloudflare_ip_never_iranian_egress():
    v = await (dre.decide_route("104.16.132.229", dre.get_policy("IRAN_DIRECT")))
    assert v["classification"] == "NON_IRAN"
    assert any("cloudflare-anycast" in n for n in v["notes"])
    assert v["decision"] == "VPN"                   # CF anycast ≠ Iranian exit


@pytest.mark.asyncio
async def test_cloudflare_ipv6_never_iranian_egress():
    v = await (dre.decide_route("2606:4700:4700::1111", dre.get_policy("IRAN_DIRECT")))
    assert v["classification"] == "NON_IRAN"
    assert any("cloudflare-anycast" in n for n in v["notes"])


@pytest.mark.asyncio
async def test_railway_host_never_iranian_exit():
    v = await (dre.decide_route("emix-pro-production.up.railway.app",
                             dre.get_policy("IRAN_DIRECT")))
    assert v["decision"] == "VPN"                   # control plane ≠ IR exit
    assert any("railway-control-plane" in n for n in v["notes"])


# ── 12: DIRECT egress labeled USER_ISP ──────────────────────────────────────

@pytest.mark.asyncio
async def test_direct_traffic_egress_is_user_isp():
    v = await (dre.decide_route("5.10.9.9", dre.get_policy("IRAN_DIRECT")))
    assert v["decision"] == "DIRECT"
    assert v["egress"] == "USER_ISP"
    assert "local ISP" in v["egress_note"]
    assert v["vpn_bypassed"] is True
    assert v["domestic_status"] == "DOMESTIC_ROUTE_VERIFIED"


# ── 13: unsupported client → SPLIT_TUNNEL_NOT_SUPPORTED ─────────────────────

@pytest.mark.asyncio
async def test_unsupported_client_split_tunnel_not_supported():
    r = dre.compile_split_tunnel_rules(dre.get_policy("IRAN_DIRECT"), "wireguard")
    assert r["verdict"] == "SPLIT_TUNNEL_NOT_SUPPORTED"
    r2 = dre.compile_split_tunnel_rules(dre.get_policy("IRAN_DIRECT"), "openvpn")
    assert r2["verdict"] == "SPLIT_TUNNEL_NOT_SUPPORTED"
    r3 = dre.compile_split_tunnel_rules(dre.get_policy("IRAN_DIRECT"), "uri")
    assert r3["verdict"] == "SPLIT_TUNNEL_NOT_SUPPORTED"


@pytest.mark.asyncio
async def test_supported_client_gets_real_rules():
    r = dre.compile_split_tunnel_rules(dre.get_policy("IRAN_DIRECT"), "xray-json")
    assert r["verdict"] == "SPLIT_TUNNEL_SUPPORTED"
    assert any(rule["type"] == "GEOIP" and rule["value"] == "ir"
               for rule in r["rules"])
    cidr_rule = next(rule for rule in r["rules"] if rule["type"] == "CIDR")
    assert "5.10.0.0/16" in cidr_rule["value"]
    assert r["dataset_version"] == 42


@pytest.mark.asyncio
async def test_all_vpn_policy_needs_no_split_rules():
    r = dre.compile_split_tunnel_rules(dre.get_policy("ALL_VPN"), "xray-json")
    assert r["verdict"] == "SPLIT_TUNNEL_NOT_APPLICABLE"


# ── traffic accounting ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_traffic_accounting_categories():
    dre.account_traffic("DOMESTIC_DIRECT", bytes_sent=100, bytes_received=50,
                        connections=1, duration_s=2.0)
    dre.account_traffic("INTERNATIONAL_VPN", bytes_sent=1000, connections=1)
    s = dre.accounting_summary()
    assert s["DOMESTIC_DIRECT"]["bytes_sent"] == 100
    assert s["DOMESTIC_DIRECT"]["bytes_received"] == 50
    assert s["DOMESTIC_DIRECT"]["connections"] == 1
    assert s["INTERNATIONAL_VPN"]["bytes_sent"] == 1000
    assert s["DOMESTIC_DIRECT"]["duration_s"] == 2.0


@pytest.mark.asyncio
async def test_invalid_accounting_category_falls_to_unknown():
    dre.account_traffic("MADE_UP", bytes_sent=10)
    assert dre.accounting_summary()["UNKNOWN"]["bytes_sent"] == 10


@pytest.mark.asyncio
async def test_decision_history_bounded():
    for i in range(250):
        await (dre.decide_route(f"5.10.0.{i % 250 + 1}", dre.get_policy("IRAN_DIRECT")))
    assert len(dre.decision_history(1000)) == dre.DECISION_HISTORY_BOUND


# ── the real RIPEstat seed dataset (REAL DATA, no network — bundled) ────────

@pytest.mark.asyncio
async def test_seed_dataset_loads_and_classifies_real_prefixes():
    n = dre.load_seed()
    assert n >= 2000                                    # full dataset, not a tiny list
    # 2.144.0.0/14 is a well-known Iranian allocation present in RIPE data
    cls, meta = dre._db.classify("2.144.10.20")
    assert cls == "IRAN_DOMESTIC"
    # 8.8.8.8 (Google) is not Iranian
    assert dre._db.classify("8.8.8.8")[0] == "NON_IRAN"
    st = dre.dataset_status()
    assert st["source_name"] and "RIPEstat" in st["source_name"]
    assert st["checksum"]                               # checksummed dataset


@pytest.mark.asyncio
async def test_dns_policy_recommendation():
    d = dre.dns_policy_for(dre.get_policy("IRAN_DIRECT"))
    assert "split DNS" in d["recommended"]
    assert d["decision_basis"].startswith("destination IP")


@pytest.mark.asyncio
async def test_status_shape():
    s = dre.summary()
    assert set(s["policy_presets"].keys()) >= {"ALL_VPN", "IRAN_DIRECT"}
    assert s["engine"].startswith("domestic_route_engine/")
    assert s["dataset"]["prefix_count"] > 0


@pytest.mark.asyncio
async def test_updater_default_threshold_rejects_small_dataset():
    """A source that suddenly returns 5 prefixes does NOT gut a 2.5k dataset."""
    dre.load_seed()                                     # real 2.5k dataset
    before = dre.dataset_status()["prefix_count"]

    async def tiny_fetch(url, timeout):
        return ('{"data": {"resources": {"ipv4": ["5.10.0.0/16"], "ipv6": []}}}')
    dru.set_fetch_fn(tiny_fetch)
    report = await (dru.update_rules())                    # default require_min=50
    assert report["ok"] is False
    assert "min 50" in report["error"]
    assert dre.dataset_status()["prefix_count"] == before
