# tests/unit/test_route_engine.py — Phase 38 / P0 route abstraction

import asyncio
import time

import pytest

import route_engine as re_eng
import egress_engine as ee


@pytest.fixture(autouse=True)
def clean():
    re_eng.reset_for_tests()
    ee.reset_for_tests()
    yield
    re_eng.reset_for_tests()
    ee.reset_for_tests()




def _evidence(country="Netherlands", asn="AS60794", ok=True, age=0.0):
    ev = ee.EgressEvidence(target_id="loc:nl-01", ok=ok, country=country,
                           asn=asn, isp="Test ISP", public_ip="1.2.3.4",
                           timestamp=time.time() - age)
    return ev


@pytest.mark.asyncio
async def test_route_object_fields():
    r = re_eng.Route(route_id="r1", entry_node="railway-control",
                     relay_nodes=[], exit_node="nl-01",
                     expected_country="Netherlands", expected_asn="AS60794")
    d = r.to_dict()
    assert d["route_id"] == "r1"
    assert d["exit_node"] == "nl-01"
    assert d["expected_country"] == "Netherlands"
    assert d["health"] == "UNKNOWN"
    assert d["verification_state"] == "UNKNOWN"
    assert d["stale"] is True            # never verified → stale/unknown


@pytest.mark.asyncio
async def test_register_and_get_route():
    r = re_eng.Route(route_id="r1", entry_node="e", exit_node="x")
    await (re_eng.register_route(r))
    got = re_eng.get_route("r1")
    assert got["route_id"] == "r1"
    assert re_eng.get_route("missing") is None


@pytest.mark.asyncio
async def test_registry_is_bounded():
    for i in range(re_eng.ROUTE_REGISTRY_BOUND + 25):
        await (re_eng.register_route(
            re_eng.Route(route_id=f"r{i}", entry_node="e")))
    assert len(re_eng.list_routes()) == re_eng.ROUTE_REGISTRY_BOUND


@pytest.mark.asyncio
async def test_assess_route_verified_egress_healthy():
    await (ee.store_evidence(_evidence(country="Netherlands", asn="AS60794")))
    r = re_eng.Route(route_id="r1", entry_node="e", exit_node="loc:nl-01",
                     expected_country="Netherlands", expected_asn="AS60794")
    ev = ee.evidence_for("loc:nl-01")
    r = re_eng.assess_route(r, ev)
    assert r.verification_state == "VERIFIED_EGRESS"
    assert r.observed_country == "Netherlands"
    assert r.observed_asn == "AS60794"
    assert r.health == "HEALTHY"
    assert r.last_verified is not None


@pytest.mark.asyncio
async def test_assess_route_mismatch_is_never_healthy():
    # Expected Turkey, observed Netherlands → ROUTE_MISMATCH (spec rule)
    await (ee.store_evidence(_evidence(country="Netherlands", asn="AS60794")))
    r = re_eng.Route(route_id="r1", entry_node="e", exit_node="loc:nl-01",
                     expected_country="Turkey", expected_asn=None)
    r = re_eng.assess_route(r, ee.evidence_for("loc:nl-01"))
    assert r.health == "ROUTE_MISMATCH"
    assert r.observed_country == "Netherlands"


@pytest.mark.asyncio
async def test_assess_route_no_exit_node():
    r = re_eng.Route(route_id="r1", entry_node="railway-control", exit_node=None,
                     expected_country="Turkey")
    r = re_eng.assess_route(r, None)
    assert r.health == "NO_EXIT_NODE_AVAILABLE"
    assert r.verification_state == "UNKNOWN"


@pytest.mark.asyncio
async def test_assess_route_no_evidence_is_unknown():
    r = re_eng.Route(route_id="r1", entry_node="e", exit_node="loc:xx",
                     expected_country="Netherlands")
    r = re_eng.assess_route(r, None)
    assert r.verification_state == "UNKNOWN"
    assert r.health == "UNKNOWN"
    assert r.observed_country is None          # never invented


@pytest.mark.asyncio
async def test_assess_route_stale_evidence_degrades():
    await (ee.store_evidence(_evidence(age=ee.EGRESS_EVIDENCE_TTL + 10)))
    r = re_eng.Route(route_id="r1", entry_node="e", exit_node="loc:nl-01",
                     expected_country="Netherlands")
    r = re_eng.assess_route(r, ee.evidence_for("loc:nl-01"))
    assert r.verification_state != "VERIFIED_EGRESS"
    assert r.observed_country is None          # expired → not reported


@pytest.mark.asyncio
async def test_route_status_labels():
    r = re_eng.Route(route_id="r", entry_node="cf-edge", exit_node="nl-01")
    assert re_eng.route_status_label(r) in ee.ROUTE_STATUSES
    r2 = re_eng.Route(route_id="r2", entry_node="railway-control", exit_node=None)
    # control plane with no exit node → traffic exits from the current node
    assert re_eng.route_status_label(r2) == "DIRECT"


@pytest.mark.asyncio
async def test_metrics_providers_fill_labeled_latency():
    r = re_eng.Route(route_id="r", entry_node="e", exit_node="x")
    re_eng.set_metrics_provider("route_rtt", lambda route: 42.5)
    async def async_loss(route):
        return 0.2
    re_eng.set_metrics_provider("packet_loss", async_loss)
    r = await (re_eng.measure_route_metrics(r))
    assert r.latency["route_rtt"] == 42.5
    assert r.packet_loss == 0.2
    assert r.latency["node_rtt"] is None       # no provider → stays UNKNOWN


@pytest.mark.asyncio
async def test_metrics_provider_failure_leaves_unknown():
    def boom(route):
        raise RuntimeError("probe failed")
    re_eng.set_metrics_provider("node_rtt", boom)
    r = re_eng.Route(route_id="r", entry_node="e", exit_node="x")
    r = await (re_eng.measure_route_metrics(r))
    assert r.latency["node_rtt"] is None       # failure → UNKNOWN, never fake


@pytest.mark.asyncio
async def test_latency_labels_present_in_dict():
    r = re_eng.Route(route_id="r", entry_node="e", exit_node="x",
                     latency={"route_rtt": 55.0})
    d = r.to_dict()
    assert d["latency_labeled"]["route_rtt"]["measure"] == "route_rtt"
    assert d["latency_labeled"]["route_rtt"]["ms"] == 55.0


@pytest.mark.asyncio
async def test_remove_route():
    await (re_eng.register_route(re_eng.Route(route_id="r", entry_node="e")))
    assert await (re_eng.remove_route("r")) is True
    assert await (re_eng.remove_route("r")) is False


@pytest.mark.asyncio
async def test_summary_shape():
    await (re_eng.register_route(re_eng.Route(route_id="r", entry_node="e",
                                           exit_node="x", health="UNKNOWN")))
    s = re_eng.summary()
    assert s["routes"] >= 1
    assert "by_verification" in s and "by_health" in s
    assert s["engine"].startswith("route_engine/")


@pytest.mark.asyncio
async def test_direct_egress_constant_is_user_isp():
    assert re_eng.DIRECT_EGRESS == "USER_ISP"
