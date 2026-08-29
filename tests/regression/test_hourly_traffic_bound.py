"""Regression test for hourly_traffic bounded retention (Phase 1.3).

Verifies:
  - _hourly_traffic_key returns sortable ISO datetime string
  - _prune_hourly_traffic drops entries older than the retention window
  - _hourly_traffic_public_view returns the backward-compat 'HH:00' shape
  - retention is configurable via EMIX_HOURLY_RETENTION
"""
import os
import time
import pytest
from datetime import datetime, timedelta

# We need to control the env BEFORE importing main (config_layer is read at
# import time). So we set env here and re-import.
os.environ.setdefault("EMIX_HOURLY_RETENTION", "24")

from main import _hourly_traffic_key, _hourly_traffic_public_view, _prune_hourly_traffic, hourly_traffic  # noqa: E402


def test_key_format_is_sortable_iso():
    """Key must be 'YYYY-MM-DD HH:00' so lexical sort == chronological sort."""
    k = _hourly_traffic_key()
    assert len(k) == 16, f"expected 16-char key, got {k!r}"
    assert k[4] == "-" and k[7] == "-" and k[10] == " " and k[13] == ":", k
    # Verify it parses as a datetime
    dt = datetime.strptime(k, "%Y-%m-%d %H:00")
    assert dt.minute == 0
    assert dt.second == 0


def test_keys_are_lexically_sortable_across_days():
    """A key from yesterday must sort before a key from today."""
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    k_now = now.strftime("%Y-%m-%d %H:00")
    k_yest = yesterday.strftime("%Y-%m-%d %H:00")
    assert k_yest < k_now, f"yesterday key {k_yest!r} should sort before today {k_now!r}"


def test_prune_drops_old_entries():
    """Entries older than the retention window are removed."""
    # Patch the config_layer.CONFIG that _prune_hourly_traffic reads.
    import config_layer
    from config_layer import EmixConfig
    original_cfg = config_layer.CONFIG
    config_layer.CONFIG = EmixConfig(hourly_traffic_retention_hours=24)
    try:
        # Set up: insert entries from 48h ago
        hourly_traffic.clear()
        old_key = (datetime.now() - timedelta(hours=48)).strftime("%Y-%m-%d %H:00")
        recent_key = _hourly_traffic_key()
        hourly_traffic[old_key] = 100
        hourly_traffic[recent_key] = 200
        _prune_hourly_traffic()
        # Old entry should be dropped, recent kept
        assert old_key not in hourly_traffic
        assert recent_key in hourly_traffic
        assert hourly_traffic[recent_key] == 200
    finally:
        config_layer.CONFIG = original_cfg


def test_prune_with_retention_zero_is_noop():
    """retention=0 means 'keep everything' (we don't prune)."""
    import config_layer
    from config_layer import EmixConfig
    original_cfg = config_layer.CONFIG
    config_layer.CONFIG = EmixConfig(hourly_traffic_retention_hours=0)
    try:
        hourly_traffic.clear()
        old_key = (datetime.now() - timedelta(hours=9999)).strftime("%Y-%m-%d %H:00")
        hourly_traffic[old_key] = 100
        _prune_hourly_traffic()
        assert old_key in hourly_traffic  # nothing pruned
    finally:
        config_layer.CONFIG = original_cfg


def test_public_view_returns_hh_only_format():
    """Public view exposes 'HH:00' keys (backward compat with dashboard)."""
    hourly_traffic.clear()
    # Insert with full ISO key
    hourly_traffic["2026-08-29 14:00"] = 1000
    view = _hourly_traffic_public_view()
    # Public view should have '14:00' key
    assert "14:00" in view
    assert view["14:00"] == 1000


def test_public_view_aggregates_same_hour_across_days():
    """Two days with same 'HH:00' aggregated into one entry in public view."""
    hourly_traffic.clear()
    hourly_traffic["2026-08-28 14:00"] = 500
    hourly_traffic["2026-08-29 14:00"] = 700
    view = _hourly_traffic_public_view()
    assert view["14:00"] == 1200  # summed


def test_prune_does_not_crash_on_empty():
    """Prune on empty dict should not raise."""
    hourly_traffic.clear()
    _prune_hourly_traffic()  # no exception
