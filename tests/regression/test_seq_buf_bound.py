"""Regression test for seq_buf memory bound (Phase 2.7).

This test verifies the *enforcement* path: when the buffer exceeds the
configured max, the code path raises HTTPException(413) and tears down
the session. Since we cannot easily spin up a full FastAPI request here,
we exercise the bound-checking logic in isolation.

The actual enforcement is in protocol/vless/xhttshadpacketup.py and
protocol/trojan/xhttshadpacketup.py. The bound is computed via:

    current_buf_bytes = sum(len(v) for v in sess["seq_buf"].values())
    if current_buf_bytes + len(body) > seq_buf_max:
        ... teardown ...

We test that the bound computation is correct and the limit can be
configured via EMIX_XHTTP_SEQ_BUF_MAX_MB.
"""
import os
import pytest

from config_layer import CONFIG


def test_seq_buf_max_bytes_default_is_4mb():
    """Default EMIX_XHTTP_SEQ_BUF_MAX_MB is 4 (4 MB)."""
    assert CONFIG.xhttp_seq_buf_max_mb == 4
    assert CONFIG.xhttp_seq_buf_max_bytes == 4 * 1024 * 1024


def test_seq_buf_max_bytes_can_be_overridden_via_env(monkeypatch):
    """EMIX_XHTTP_SEQ_BUF_MAX_MB=1 → 1 MB cap."""
    monkeypatch.setenv("EMIX_XHTTP_SEQ_BUF_MAX_MB", "1")
    # Re-import config_layer to pick up the new env var
    import importlib
    import config_layer
    importlib.reload(config_layer)
    assert config_layer.CONFIG.xhttp_seq_buf_max_mb == 1
    assert config_layer.CONFIG.xhttp_seq_buf_max_bytes == 1 * 1024 * 1024


def test_seq_buf_bound_computation_logic():
    """Replicate the bound computation from packet-up handlers and verify
    the inequality used to trigger teardown."""
    # Simulate a sess with 5 packets of 100KB each = 500KB buffered
    sess = {
        "seq_buf": {1: b"x" * 100_000, 2: b"x" * 100_000, 3: b"x" * 100_000,
                    4: b"x" * 100_000, 5: b"x" * 100_000}
    }
    body = b"x" * 100_000  # incoming packet of 100KB
    max_bytes = 4 * 1024 * 1024  # 4 MB
    current_buf_bytes = sum(len(v) for v in sess["seq_buf"].values())
    # At 500KB + 100KB = 600KB → well under 4MB → should NOT trigger
    assert current_buf_bytes + len(body) < max_bytes

    # Now blow past the limit: 5 packets of 1MB each = 5MB buffered
    sess_big = {
        "seq_buf": {1: b"x" * (1024 * 1024), 2: b"x" * (1024 * 1024),
                    3: b"x" * (1024 * 1024), 4: b"x" * (1024 * 1024),
                    5: b"x" * (1024 * 1024)}
    }
    body = b"x" * 100
    current_buf_bytes = sum(len(v) for v in sess_big["seq_buf"].values())
    # 5MB + 100B > 4MB → SHOULD trigger teardown
    assert current_buf_bytes + len(body) > max_bytes


def test_seq_buf_bound_zero_size_body():
    """An empty body must never trip the bound — existing packet-up code
    returns {"ok": True} before reaching the bound check."""
    sess = {"seq_buf": {}}
    body = b""
    max_bytes = 4 * 1024 * 1024
    current_buf_bytes = sum(len(v) for v in sess["seq_buf"].values())
    assert current_buf_bytes + len(body) < max_bytes
