# tests/integration/test_phase43_health_core.py — Phase 43:
# «بخش سلامت پنل» MUST NOT have a profile wall.
#
# User report on production (EMIX_PROFILE=core): "بخش سلامت پنل از کار افتاده
# و نتیجه نمی‌دهد" — the dashboard health button, the volume banner, the
# diagnostics IP-quality card and the «تست همه‌ی کانفیگ‌ها» button were all
# rendered by the UI but their engines (railway_infra / ip_quality / smart_route)
# are OFF under core → silent 404s.
#
# Coverage:
#   §A boot contract: under EMIX_PROFILE=core the panel-health surface is
#      registered (health-all / infra status / ensure-volume / ip-quality).
#   §B functional: a REAL core-profile boot answers /api/system/health-all
#      with a multi-section report (panel/volume/links/modules…) — the exact
#      button the user pressed — plus /api/system/infra/status and
#      /api/ip-quality/summary.
#   §C always-on reporting: railway_infra + ip_quality appear under
#      always_on loaded=True and NOT as "optional engines off".
#   §D frontend honesty: the served dashboard wires diagProbeAll to the
#      ungated core endpoint /api/links/ping-all (with a visible result
#      toast) and no longer calls the core-dead /api/exp/route/configs/probe-all.
#   §E no collateral: other optional engines stay OFF under core (the
#      promotion is surgical — only the health surface, not a backdoor to
#      full profile).

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _boot_core(code: str) -> dict:
    """Boot the real app in a subprocess under EMIX_PROFILE=core and run `code`."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("EMIX_PROFILE", "EMIX_ENABLE", "EMIX_DISABLE")}
    env["EMIX_PROFILE"] = "core"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, cwd=str(REPO), env=env, timeout=180)
    assert out.returncode == 0, f"core boot failed: {out.stderr[-800:]}"
    return json.loads(out.stdout.strip().splitlines()[-1])


_HEALTH_CODE = """
import json, os
from fastapi.testclient import TestClient
import main

paths = sorted({getattr(r, "path", None) for r in main.app.routes})
rep = main.boot_profile.report()

with TestClient(main.app) as client:
    # login — conftest sets ADMIN_PASSWORD (default fallback kept for parity)
    client.post("/api/login", json={"password": os.environ.get("ADMIN_PASSWORD", "123456")})
    ha = client.get("/api/system/health-all")
    ha_body = ha.json() if ha.status_code == 200 else None
    infra = client.get("/api/system/infra/status")
    ipq = client.get("/api/ip-quality/summary")

html = client.get("/dashboard").text if False else ""
print(json.dumps({
    "paths": paths,
    "always_on": rep.get("always_on", {}),
    "summary": rep["summary"],
    "profile": rep["profile"],
    "health_all": {
        "status": ha.status_code,
        "ok": (ha_body or {}).get("ok"),
        "sections": sorted((ha_body or {}).get("sections", {}).keys()),
        "panel_ok": ((ha_body or {}).get("sections", {}).get("panel", {}) or {}).get("ok"),
        "links_ok": ((ha_body or {}).get("sections", {}).get("links", {}) or {}).get("ok"),
        "volume_ok": ((ha_body or {}).get("sections", {}).get("volume", {}) or {}).get("ok"),
    } if ha_body else {"status": ha.status_code},
    "infra_status": infra.status_code,
    "ipq_status": ipq.status_code,
}))
"""


def test_core_profile_registers_panel_health_surface():
    """§A — the health-section endpoints exist under the production profile."""
    info = _boot_core(_HEALTH_CODE)
    for must in ("/api/system/health-all",
                 "/api/system/infra/status",
                 "/api/system/infra/ensure-volume",
                 "/api/ip-quality/summary"):
        assert must in info["paths"], f"{must} missing under EMIX_PROFILE=core"


def test_core_health_all_button_functional():
    """§B — the exact button the user pressed returns a real report."""
    info = _boot_core(_HEALTH_CODE)
    ha = info["health_all"]
    assert ha["status"] == 200, f"health-all not 200 under core: {ha}"
    assert ha["ok"] in (True, False), "health-all must return a structured report"
    # the report must cover the core sections the dashboard renders
    for section in ("panel", "volume", "links"):
        assert section in ha["sections"], f"section {section} missing: {ha['sections']}"
    assert ha["panel_ok"] is True
    assert ha["links_ok"] in (True, False)  # count-based; must be present
    assert info["infra_status"] == 200, "volume banner endpoint dead"
    assert info["ipq_status"] == 200, "IP-quality card endpoint dead"


def test_core_health_engines_reported_always_on():
    """§C — the boot report tells the truth: loaded, not 'optional off'."""
    info = _boot_core(_HEALTH_CODE)
    for engine in ("railway_infra", "ip_quality"):
        assert info["always_on"].get(engine, {}).get("loaded") is True, (
            f"{engine} must be loaded under core")
    # surgical promotion: optional engines summary must still be all-OFF
    assert info["summary"]["engines_enabled"] == 0
    assert info["summary"]["engines_failed"] == 0


def test_dashboard_diag_probe_uses_core_endpoint():
    """§D — the «تست همه‌ی کانفیگ‌ها» button calls the ungated core path."""
    from fastapi.testclient import TestClient
    import main
    with TestClient(main.app) as client:
        client.post("/api/login", json={"password": os.environ.get("ADMIN_PASSWORD", "123456")})
        html = client.get("/dashboard").text
    assert "/api/links/ping-all" in html, (
        "diagProbeAll must use the ungated /api/links/ping-all")
    # the old silently-404 wiring must be gone from the served frontend
    assert "/api/exp/route/configs/probe-all" not in html, (
        "diag page must not call the core-dead smart_route endpoint")
    # visible Persian result feedback (the «نتیجه نمی‌دهد» complaint)
    assert "تست واقعی همه‌ی کانفیگ‌ها" in html


def test_core_promotion_is_surgical():
    """§E — only the health surface became core; no other engine slipped in."""
    info = _boot_core(_HEALTH_CODE)
    for still_optional in ("/api/egress/verify", "/api/vpn/nodes",
                           "/api/security/sni/profiles",
                           "/api/exp/route/configs/probe-all"):
        assert still_optional not in info["paths"], (
            f"{still_optional} must stay OFF under core (surgical promotion)")
