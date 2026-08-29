"""Unit tests for the reverseproxy subsystem (Phases 31-39)."""
import os
import asyncio
import time
import pytest

# Set env vars BEFORE importing reverseproxy
os.environ["EMIX_REVERSE_PROXY_ENABLED"] = "1"
os.environ["EMIX_REVERSE_PROXY_ROUTES_JSON"] = '[{"host":"emix.example.com","path":"/","upstreams":[{"url":"http://127.0.0.1:8000","weight":2,"priority":1}],"transport":"http"}]'
os.environ["EMIX_TRUSTED_EDGES"] = "cloudflare.com,*.workers.dev,arvancloud.com"
os.environ["EMIX_ORIGIN_AUTH_SECRET"] = "test-secret-32-bytes-long-aaaaaaaaa"
os.environ.setdefault("PORT", "8765")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PASSWORD", "test-password")
os.environ.setdefault("RAILWAY_PUBLIC_DOMAIN", "test.example.com")
os.environ.setdefault("DATA_DIR", "/tmp/emix-test-rp-data")
os.makedirs(os.environ["DATA_DIR"], exist_ok=True)

from reverseproxy import (
    get_proxy_config, reload_proxy_config,
    is_tunnel_path, add_cache_safety_headers,
    is_trusted_edge, get_real_client_ip,
    verify_origin_signature, build_origin_signature,
    HMAC_ORIGIN_HEADER, HMAC_TIMESTAMP_HEADER,
    get_upstream_health, all_upstream_health,
)
from reverseproxy.headers import check_header_injection
from reverseproxy.loadbalancer import LoadBalancer, get_balancer
from reverseproxy.config import Route, Upstream, ReverseProxyConfig


@pytest.fixture(autouse=True)
def _reload_config_per_test():
    """Force-reload the reverse-proxy singleton config before each test.
    Other test files may have run first and triggered the singleton's
    initial load with different env vars."""
    reload_proxy_config()
    yield


def test_config_loaded_from_env():
    cfg = get_proxy_config()
    assert cfg.enabled is True
    assert len(cfg.routes) == 1
    assert cfg.routes[0].host == "emix.example.com"
    assert cfg.routes[0].upstreams[0].url == "http://127.0.0.1:8000"
    assert cfg.routes[0].upstreams[0].weight == 2
    assert cfg.origin_auth_enabled is True


def test_trusted_edges_glob():
    cfg = get_proxy_config()
    assert cfg.is_trusted_edge("cloudflare.com") is True
    assert cfg.is_trusted_edge("emix-gateway.personalemixone.workers.dev") is True  # *.workers.dev
    assert cfg.is_trusted_edge("arvancloud.com") is True
    assert cfg.is_trusted_edge("evil.com") is False
    assert cfg.is_trusted_edge("notcloudflare.com") is False  # not a glob match


def test_route_matching():
    cfg = get_proxy_config()
    route = cfg.routes[0]
    assert route.matches("emix.example.com", "/api/links") is True
    assert route.matches("emix.example.com", "/") is True
    assert route.matches("other.com", "/api") is False


def test_is_tunnel_path_ws():
    assert is_tunnel_path("/ws/c3efb57c-eb89") is True
    assert is_tunnel_path("/trojan-ws") is True
    assert is_tunnel_path("/ss-ws") is True
    assert is_tunnel_path("/xhttp-siz10/stream-up/uid/sid") is True
    assert is_tunnel_path("/sub/abc") is True
    assert is_tunnel_path("/api/login") is True
    assert is_tunnel_path("/api/links") is True
    assert is_tunnel_path("/api/protocols/vless-ws/test") is True  # state-changing
    assert is_tunnel_path("/api/protocols") is False  # GET (read-only) — could be cached
    assert is_tunnel_path("/") is False
    assert is_tunnel_path("/dashboard") is False


def test_add_cache_safety_headers_on_tunnel_path():
    headers = {"Content-Type": "text/plain"}
    out = add_cache_safety_headers(headers, "/ws/test")
    assert out["Cache-Control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert out["Pragma"] == "no-cache"
    assert out["Expires"] == "0"
    assert out["CDN-Cache-Control"] == "no-store"  # ArvanCloud convention


def test_add_cache_safety_headers_noop_on_public_path():
    headers = {"Content-Type": "text/html"}
    out = add_cache_safety_headers(headers, "/dashboard")
    assert "Cache-Control" not in out  # not modified
    assert out == headers


def test_check_header_injection():
    assert check_header_injection("value\r\nSet-Cookie: bad=1") is True
    assert check_header_injection("value\nSet-Cookie: bad=1") is True
    assert check_header_injection("normal value") is False
    assert check_header_injection("") is False


def test_get_real_client_ip_direct_connection():
    """When no edge headers are present, return remote_addr."""
    headers = {}
    ip = get_real_client_ip(headers, "203.0.113.5:12345")
    assert ip == "203.0.113.5"


def test_get_real_client_ip_from_trusted_edge():
    """When a trusted-edge header is present, trust X-Forwarded-For."""
    headers = {"cf-connecting-ip": "1.2.3.4", "x-forwarded-for": "5.6.7.8, 10.0.0.1"}
    ip = get_real_client_ip(headers, "10.0.0.1:12345")
    # Should extract the first XFF entry (real client IP)
    assert ip == "5.6.7.8"


def test_get_real_client_ip_xrealip_fallback():
    headers = {"x-real-ip": "9.9.9.9"}
    ip = get_real_client_ip(headers, "10.0.0.1:12345")
    assert ip == "9.9.9.9"


def test_build_and_verify_origin_signature():
    """Round-trip: build a signature, then verify it."""
    cfg = get_proxy_config()
    sig, ts = build_origin_signature(cfg.origin_auth_secret, "POST", "/api/links", b"{}")
    ok, err = verify_origin_signature(
        method="POST", path="/api/links", body=b"{}",
        incoming_signature=sig, incoming_timestamp=str(ts),
    )
    assert ok is True
    assert err is None


def test_verify_origin_signature_replay_rejected():
    """Timestamp outside the replay window should be rejected."""
    cfg = get_proxy_config()
    # Sign with a stale timestamp (10 minutes ago)
    old_ts = int(time.time()) - 600
    sig, _ = build_origin_signature(cfg.origin_auth_secret, "POST", "/api/links", b"{}", )
    # Recompute with the old timestamp
    import hmac, hashlib
    msg = f"POST|/api/links|{old_ts}|".encode() + b"{}"
    expected_sig = hmac.new(cfg.origin_auth_secret.encode(), msg, hashlib.sha256).hexdigest()
    ok, err = verify_origin_signature(
        method="POST", path="/api/links", body=b"{}",
        incoming_signature=expected_sig, incoming_timestamp=str(old_ts),
    )
    assert ok is False
    assert "replay" in (err or "").lower() or "window" in (err or "").lower()


def test_verify_origin_signature_mismatch_rejected():
    """Tampered signature must be rejected."""
    cfg = get_proxy_config()
    ts = int(time.time())
    # Wrong secret
    bad_sig, _ = build_origin_signature("wrong-secret", "POST", "/api/links", b"{}")
    ok, err = verify_origin_signature(
        method="POST", path="/api/links", body=b"{}",
        incoming_signature=bad_sig, incoming_timestamp=str(ts),
    )
    assert ok is False
    assert "mismatch" in (err or "").lower()


def test_verify_origin_signature_disabled_when_no_secret():
    """When origin auth is not configured, verification is skipped (ok=True)."""
    # Save current secret and remove it
    cfg = get_proxy_config()
    old_secret = cfg.origin_auth_secret
    try:
        # Reload with no secret
        os.environ.pop("EMIX_ORIGIN_AUTH_SECRET", None)
        new_cfg = reload_proxy_config()
        assert new_cfg.origin_auth_enabled is False
        ok, err = verify_origin_signature(
            method="POST", path="/api/links", body=b"{}",
            incoming_signature=None, incoming_timestamp=None,
        )
        assert ok is True  # disabled = always pass
    finally:
        os.environ["EMIX_ORIGIN_AUTH_SECRET"] = old_secret
        reload_proxy_config()


def test_upstream_health_records_success_and_failure():
    h = get_upstream_health("route1|http://upstream1", "http://upstream1")
    from reverseproxy.health import UpstreamSample
    h.record(UpstreamSample(timestamp=time.time(), ok=True, latency_ms=50.0))
    h.record(UpstreamSample(timestamp=time.time(), ok=True, latency_ms=60.0))
    assert h.total_checks == 2
    assert h.consecutive_successes == 2
    assert h.avg_latency_ms(300) == 55.0
    assert h.success_rate(300) == 1.0


def test_upstream_health_opens_after_threshold():
    h = get_upstream_health("route2|http://upstream2", "http://upstream2")
    from reverseproxy.health import UpstreamSample
    for _ in range(3):
        h.record(UpstreamSample(timestamp=time.time(), ok=False, error="timeout"))
    assert h.state == "open"
    assert h.is_open() is True  # circuit is open
    assert h.is_open(cooldown_seconds=0) is False  # cooldown elapsed → half_open


def test_load_balancer_round_robin():
    """Round-robin should cycle through healthy upstreams."""
    ups = [
        Upstream(url="http://u1"),
        Upstream(url="http://u2"),
        Upstream(url="http://u3"),
    ]
    lb = LoadBalancer("test-route|/", "round_robin")
    picks = [lb.select(ups).url for _ in range(6)]
    # Should cycle u1, u2, u3, u1, u2, u3
    assert picks == ["http://u1", "http://u2", "http://u3", "http://u1", "http://u2", "http://u3"]


def test_load_balancer_priority_prefers_high_priority():
    ups = [
        Upstream(url="http://low", priority=1),
        Upstream(url="http://high", priority=10),
    ]
    lb = LoadBalancer("priority-route|/", "priority")
    picks = [lb.select(ups).url for _ in range(5)]
    # All picks should be the high-priority one
    assert all(p == "http://high" for p in picks)


def test_load_balancer_skips_open_circuits():
    ups = [
        Upstream(url="http://broken"),
        Upstream(url="http://healthy"),
    ]
    lb = LoadBalancer("skip-route|/", "round_robin")
    # Force broken to OPEN state
    from reverseproxy.health import UpstreamSample, get_upstream_health
    h = get_upstream_health("skip-route|/", "http://broken")
    for _ in range(3):
        h.record(UpstreamSample(timestamp=time.time(), ok=False, error="down"))
    # Selection should skip broken and return healthy
    pick = lb.select(ups)
    assert pick.url == "http://healthy"


def test_load_balancer_returns_none_when_all_unhealthy():
    ups = [
        Upstream(url="http://broken1"),
        Upstream(url="http://broken2"),
    ]
    lb = LoadBalancer("none-route|/", "round_robin")
    from reverseproxy.health import UpstreamSample, get_upstream_health
    for u in ups:
        h = get_upstream_health("none-route|/", u.url)
        for _ in range(3):
            h.record(UpstreamSample(timestamp=time.time(), ok=False, error="down"))
    pick = lb.select(ups)
    assert pick is None
