"""Unit tests for parse_size_to_bytes (Phase 2.8).

Verifies:
  - valid B/KB/MB/GB
  - decimal values (already supported)
  - negative → ValueError
  - NaN → ValueError
  - infinity → ValueError
  - non-numeric → TypeError
  - invalid unit → ValueError
  - existing valid MB/GB behavior preserved
"""
import math
import pytest

from main import parse_size_to_bytes


def test_valid_bytes():
    assert parse_size_to_bytes(1, "B") == 1
    assert parse_size_to_bytes(100, "B") == 100


def test_valid_kb():
    assert parse_size_to_bytes(1, "KB") == 1024
    assert parse_size_to_bytes(2, "kb") == 2048  # case-insensitive
    assert parse_size_to_bytes(0.5, " KB ") == 512  # whitespace tolerated


def test_valid_mb():
    assert parse_size_to_bytes(1, "MB") == 1024 ** 2
    assert parse_size_to_bytes(1.5, "mb") == int(1.5 * 1024 ** 2)


def test_valid_gb():
    assert parse_size_to_bytes(1, "GB") == 1024 ** 3
    assert parse_size_to_bytes(2, "gb") == 2 * 1024 ** 3


def test_decimal_values_supported():
    assert parse_size_to_bytes(0.5, "MB") == int(0.5 * 1024 ** 2)
    assert parse_size_to_bytes(1.25, "GB") == int(1.25 * 1024 ** 3)


def test_negative_rejected():
    with pytest.raises(ValueError):
        parse_size_to_bytes(-1, "MB")
    with pytest.raises(ValueError):
        parse_size_to_bytes(-0.5, "GB")


def test_nan_rejected():
    with pytest.raises(ValueError):
        parse_size_to_bytes(float("nan"), "MB")


def test_infinity_rejected():
    with pytest.raises(ValueError):
        parse_size_to_bytes(float("inf"), "MB")
    with pytest.raises(ValueError):
        parse_size_to_bytes(float("-inf"), "GB")


def test_non_numeric_rejected():
    with pytest.raises(TypeError):
        parse_size_to_bytes("abc", "MB")
    with pytest.raises(TypeError):
        parse_size_to_bytes(None, "MB")


def test_invalid_unit_rejected():
    with pytest.raises(ValueError):
        parse_size_to_bytes(1, "TB")  # unsupported
    with pytest.raises(ValueError):
        parse_size_to_bytes(1, "PB")
    with pytest.raises(ValueError):
        parse_size_to_bytes(1, "bytes")  # not B/KB/MB/GB


def test_empty_unit_treated_as_bytes():
    """For backward compat, an empty unit falls back to bytes."""
    assert parse_size_to_bytes(100, "") == 100
    assert parse_size_to_bytes(100, None) == 100
