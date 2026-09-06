# tests/integration/test_phase44_gateway_host.py — Phase 44:
# Host routing through the CF gateway (the Iran-reachable path) — honest,
# measured, whitelist-gated.
#
# User spec: panel + configs dead from Iran-direct while EMIX works. New live
# evidence (check-host.net IR nodes): the EMIX-PRO ingress IP is TCP-blackholed
# from Iran; the CF gateway (workers.dev) is reachable (TCP+TLS+HTTP 200).
# Cure: RAILWAY_PUBLIC_DOMAIN -> gateway domain (deterministic get_host) +
# spoof skipped behind a CF-worker front.
#
# Coverage:
#   §A resolve() CF-front guard: spoof link + workers.dev host → CLEAN
#      (mode=standard, sni=host, no allowInsecure); spoof + railway ingress →
#      Mode B preserved (wire compat); spoof + other hosts → Mode B preserved;
#      spoof + cdn workers.dev → clean via cdn; spoof + other cdn → Mode A.
#   §B link_health._link_spoof_sni honesty: get_host()=workers.dev → None
#      (client path is clean; no false-red spoof probes), even with spoof
#      enabled; railway host → spoof still returned.
#   §C infra variable endpoint: auth-gated; whitelist enforced (403 for
#      non-whitelisted name); value validation (hostname only); _upsert via
#      saved token with graceful GraphQL shape ladder; list masks non-whitelist
#      values.
#   §D get_host() precedence contract: RAILWAY_PUBLIC_DOMAIN env wins over
#      the learned host (the deterministic-host fix).
#   §E UI: dashboard serves the public-host card (input + save button +
#      loadPublicHost wiring).

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import main  # real app — same boot path as Railway (MUST be first: railway_infra imports FROM main)
import endpoint_profiles as ep
import railway_infra


# ── §A resolver: CF-worker front guard ───────────────────────────────────────

RAILWAY = "emix-pro-production.up.railway.app"
GATEWAY = "emix-gateway.personalemixone.workers.dev"
SPOOF = {"spoof_sni": "www.bale.ir", "spoof_sni_enabled": True}


def test_spoof_behind_gateway_resolves_clean():
    r = ep.resolve(SPOOF, GATEWAY)
    assert r.mode == "standard"
    assert r.address == GATEWAY and r.sni == GATEWAY
    assert r.host_header == GATEWAY
    assert r.allow_insecure is False, "clean link must not need allowInsecure"
    assert any("CF-worker front" in n for n in r.notes)


def test_spoof_on_railway_ingress_keeps_mode_b():
    r = ep.resolve(SPOOF, RAILWAY)
    assert r.mode == "direct-sni"
    assert r.sni == "www.bale.ir"
    assert r.allow_insecure is True


def test_spoof_on_other_hosts_untouched():
    r = ep.resolve(SPOOF, "panel.example.com")
    assert r.mode == "direct-sni" and r.sni == "www.bale.ir"


def test_spoof_with_workers_cdn_resolves_clean_via_cdn():
    r = ep.resolve(SPOOF, RAILWAY, cdn_domain=GATEWAY)
    assert r.mode == "standard"
    assert r.address == GATEWAY and r.sni == GATEWAY
    assert r.allow_insecure is False


def test_spoof_with_other_cdn_keeps_mode_a():
    r = ep.resolve(SPOOF, RAILWAY, cdn_domain="cdn.example.net")
    assert r.mode == "cdn" and r.address == "cdn.example.net"


def test_clean_link_behind_gateway_is_standard():
    r = ep.resolve({}, GATEWAY)
    assert r.mode == "standard" and r.sni == GATEWAY


def test_is_cf_worker_front():
    assert ep._is_cf_worker_front("x.workers.dev")
    assert ep._is_cf_worker_front("X.WORKERS.DEV")
    assert not ep._is_cf_worker_front(RAILWAY)
    assert not ep._is_cf_worker_front("localhost")
    assert not ep._is_cf_worker_front("")


# ── §B link_health spoof gating follows the front ───────────────────────────

def test_link_spoof_sni_none_behind_gateway(monkeypatch):
    import link_health
    monkeypatch.setattr(link_health, "get_host", lambda: GATEWAY)
    monkeypatch.delenv("EMIX_CDN_DOMAIN", raising=False)
    assert link_health._link_spoof_sni(SPOOF) is None


def test_link_spoof_sni_kept_on_railway(monkeypatch):
    import link_health
    monkeypatch.setattr(link_health, "get_host", lambda: RAILWAY)
    monkeypatch.delenv("EMIX_CDN_DOMAIN", raising=False)
    assert link_health._link_spoof_sni(SPOOF) == "www.bale.ir"


# ── §C infra variable endpoint (whitelist + honesty) ────────────────────────

@pytest.fixture(scope="module")
def client():
    with TestClient(main.app) as c:
        c.post("/api/login", json={"password": os.environ.get("ADMIN_PASSWORD", "123456")})
        yield c


def test_variable_endpoint_requires_auth():
    with TestClient(main.app) as c:
        assert c.get("/api/system/infra/variables").status_code == 401
        assert c.post("/api/system/infra/variable", json={"name": "RAILWAY_PUBLIC_DOMAIN", "value": "x.workers.dev"}).status_code == 401


def test_variable_whitelist_enforced(client):
    r = client.post("/api/system/infra/variable",
                    json={"name": "ADMIN_PASSWORD", "value": "evil.workers.dev"})
    assert r.status_code == 403
    r = client.post("/api/system/infra/variable",
                    json={"name": "RAILWAY_SERVICE_ID", "value": "x.workers.dev"})
    assert r.status_code == 403

def test_variable_value_validation(client):
    r = client.post("/api/system/infra/variable",
                    json={"name": "RAILWAY_PUBLIC_DOMAIN", "value": "not a host!"})
    assert r.status_code == 400
    r = client.post("/api/system/infra/variable",
                    json={"name": "RAILWAY_PUBLIC_DOMAIN", "value": "nodot"})
    assert r.status_code == 400


def test_variable_upsert_uses_saved_token_and_shapes(client, monkeypatch):
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "svc-1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "env-1")
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "prj-1")
    called = []

    async def fake_gql(token, query, variables):
        called.append((token, query, variables))
        if "projectId" not in str(variables):
            raise RuntimeError("خطای GraphQL: projectId required")
        return {"variableUpsert": True}

    monkeypatch.setattr(railway_infra, "_gql", fake_gql)
    monkeypatch.setattr(railway_infra.bottokentcpproxy, "load_token", lambda: "tok")

    r = client.post("/api/system/infra/variable",
                    json={"name": "RAILWAY_PUBLIC_DOMAIN", "value": "gate.workers.dev"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["value"] == "gate.workers.dev"
    assert body["shape"] == 1, "verified introspected shape must be tried first"
    # token passed as bearer + verified input shape incl. required projectId
    tok, query, variables = called[0]
    assert tok == "tok"
    assert variables["input"]["projectId"] == "prj-1"
    assert variables["input"]["environmentId"] == "env-1"
    assert variables["input"]["serviceId"] == "svc-1"
    assert variables["input"]["name"] == "RAILWAY_PUBLIC_DOMAIN"
    assert variables["input"]["value"] == "gate.workers.dev"
    # Boolean return — no selection set in the mutation document
    assert "{ id name }" not in query


def test_variable_upsert_no_token_honest_error(client, monkeypatch):
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "svc-1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "env-1")
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "prj-1")
    monkeypatch.setattr(railway_infra.bottokentcpproxy, "load_token", lambda: None)
    r = client.post("/api/system/infra/variable",
                    json={"name": "RAILWAY_PUBLIC_DOMAIN", "value": "g.workers.dev"})
    assert r.status_code == 502
    assert "توکن" in r.json()["detail"]


def test_variables_listing_masks_non_whitelisted(client, monkeypatch):
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "svc-1")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", "env-1")
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "prj-1")

    async def fake_gql(token, query, variables):
        assert variables["projectId"] == "prj-1"
        return {"variables": {
            "RAILWAY_PUBLIC_DOMAIN": "gate.workers.dev",
            "DATABASE_URL": "postgres://secret",
        }}

    monkeypatch.setattr(railway_infra, "_gql", fake_gql)
    monkeypatch.setattr(railway_infra.bottokentcpproxy, "load_token", lambda: "tok")
    r = client.get("/api/system/infra/variables")
    assert r.status_code == 200
    j = r.json()
    by_name = {v["name"]: v for v in j["variables"]}
    assert by_name["RAILWAY_PUBLIC_DOMAIN"]["value"] == "gate.workers.dev"
    assert "secret" not in json.dumps(by_name["DATABASE_URL"])
    assert by_name["DATABASE_URL"]["safe"] is False


# ── §D get_host precedence — the deterministic-host cure ─────────────────────

def test_get_host_explicit_env_wins_over_everything(monkeypatch):
    # EMIX_PUBLIC_HOST — the operator-explicit host (Railway rewrites its own
    # RAILWAY_PUBLIC_DOMAIN on redeploy, so the explicit var is the cure)
    monkeypatch.setenv("EMIX_PUBLIC_HOST", GATEWAY)
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", RAILWAY)
    monkeypatch.setattr(main, "_LEARNED_PUBLIC_HOST", RAILWAY)
    assert main.get_host() == GATEWAY


def test_get_host_railway_env_wins_over_learned(monkeypatch):
    monkeypatch.delenv("EMIX_PUBLIC_HOST", raising=False)
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", RAILWAY)
    monkeypatch.setattr(main, "_LEARNED_PUBLIC_HOST", RAILWAY)
    assert main.get_host() == RAILWAY


def test_get_host_learned_when_no_env(monkeypatch):
    monkeypatch.delenv("RAILWAY_PUBLIC_DOMAIN", raising=False)
    monkeypatch.setattr(main, "_LEARNED_PUBLIC_HOST", RAILWAY)
    assert main.get_host() == RAILWAY


# ── §E UI needles ─────────────────────────────────────────────────────────────

def test_dashboard_serves_public_host_card(client):
    html = client.get("/dashboard").text
    assert "EMIX_PUBLIC_HOST" in html
    assert 'id="pubhost-input"' in html
    assert 'savePublicHost' in html
    assert 'loadPublicHost' in html
    assert "/api/system/infra/variable" in html or "infra/variables" in html
