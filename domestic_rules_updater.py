# domestic_rules_updater.py — Atomic Domestic Ruleset Updates (Phase 38 / P17)
# ══════════════════════════════════════════════════════════════════════════════
# Updates the Iranian prefix dataset from a configurable trusted source.
#
# GUARANTEES (tested):
#   * atomic updates  — a new dataset is fully validated BEFORE it replaces
#                       the live one
#   * versioning      — every applied dataset carries a version + source
#   * rollback        — failed update ⇒ previous known-good dataset retained
#   * checksum        — SHA-256 over the prefix list, verified when present
#   * metadata        — source, fetched_at, last successful update stored
#   * TTL             — datasets older than TTL are flagged STALE (still used
#                       until a successful update lands — never dropped)
#   * failure fallback— an EMPTY or MALFORMED dataset NEVER replaces a
#                       working one
#
# Default source: RIPEstat country-resource-list (the RIR that actually
# allocates Iranian address space). Override with EMIX_IRAN_PREFIX_SOURCE.
# Formats auto-detected: RIPEstat JSON  |  plain text (CIDR per line).
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import json
import time
from typing import Optional, List

import domestic_route_engine as dre

RULES_UPDATER_VERSION = "1.0.0"

DEFAULT_SOURCE = ("https://stat.ripe.net/data/country-resource-list/"
                  "data.json?resource=IR&v4=1&v6=1")
DEFAULT_TTL_S = 86400.0            # 24h — datasets older than this = STALE
DEFAULT_TIMEOUT_S = 20.0
UPDATE_HISTORY_BOUND = 20

_status = {
    "last_attempt": None,
    "last_attempt_iso": None,
    "last_successful_update": None,
    "last_successful_update_iso": None,
    "last_error": None,
    "last_error_iso": None,
    "source": None,
    "applied_version": None,
    "attempts": 0,
    "failures": 0,
    "successes": 0,
}
_history: List[dict] = []


def _iso(ts: Optional[float]) -> Optional[str]:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)) if ts else None


# ── Fetch (injectable for tests; httpx used in production) ─────────────────

async def _fetch_http(url: str, timeout: float) -> str:
    import httpx
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.text


_fetch_fn = _fetch_http


def set_fetch_fn(fn) -> None:
    """DI seam — tests inject a fake fetcher (no real network)."""
    global _fetch_fn
    _fetch_fn = fn


def _parse(text: str, source_url: str) -> dict:
    """Parse RIPEstat JSON or plain CIDR text into a dataset document."""
    prefixes: List[str] = []
    version = None
    fetched_at = None
    source_name = "unknown"
    try:
        doc = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # plain text: one CIDR per line
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                prefixes.append(line)
        source_name = f"text:{source_url}"
        fetched_at = time.time()
    else:
        if isinstance(doc, dict) and "data" in doc and "resources" in doc.get("data", {}):
            res = doc["data"]["resources"]
            prefixes = list(res.get("ipv4", [])) + list(res.get("ipv6", []))
            version = int(time.time())
            fetched_at = time.time()
            source_name = "RIPEstat country-resource-list (IR)"
            try:
                fetched_at = time.mktime(time.strptime(
                    doc["data"].get("query_time", ""),
                    "%Y-%m-%dT%H:%M:%S"))
            except (ValueError, TypeError):
                pass
        elif isinstance(doc, dict):
            prefixes = [str(p) for p in doc.get("prefixes", [])]
            version = doc.get("version")
            fetched_at = doc.get("fetched_at") or time.time()
            source_name = doc.get("source_name") or source_url
        else:
            raise ValueError("unrecognized dataset format")
    if not prefixes:
        raise ValueError("dataset is empty")
    # NOTE: no checksum is declared here — apply_dataset computes and verifies
    # the checksum over the NORMALIZED prefix list (single source of truth).
    return {
        "prefixes": prefixes,
        "version": version or int(time.time()),
        "source": source_url,
        "source_name": source_name,
        "fetched_at": fetched_at,
    }


# ── The update (atomic, with rollback-by-retention) ────────────────────────

async def update_rules(source_url: Optional[str] = None,
                       timeout: float = DEFAULT_TIMEOUT_S,
                       require_min: int = dre.MIN_DATASET_PREFIXES) -> dict:
    """Fetch → parse → validate → atomically apply. ANY failure keeps the
    previous known-good dataset and returns an error report (never raises)."""
    url = source_url or DEFAULT_SOURCE
    _status["last_attempt"] = time.time()
    _status["last_attempt_iso"] = _iso(_status["last_attempt"])
    _status["attempts"] += 1
    _status["source"] = url
    try:
        text = await _fetch_fn(url, timeout)
        doc = _parse(text, url)
        applied = dre.apply_dataset(doc,      # validates + atomic swap
                                  require_min=require_min)
    except Exception as exc:
        _status["failures"] += 1
        _status["last_error"] = str(exc)[:300]
        _status["last_error_iso"] = _iso(time.time())
        report = {
            "ok": False,
            "error": _status["last_error"],
            "fallback": "previous known-good dataset retained",
            "dataset": dre.dataset_status(),
        }
        _history.append(report)
        del _history[:-UPDATE_HISTORY_BOUND]
        return report
    _status["successes"] += 1
    _status["last_successful_update"] = time.time()
    _status["last_successful_update_iso"] = _iso(_status["last_successful_update"])
    _status["last_error"] = None
    _status["applied_version"] = applied.get("version")
    report = {"ok": True, **applied,
              "last_successful_update_iso": _status["last_successful_update_iso"]}
    _history.append(report)
    del _history[:-UPDATE_HISTORY_BOUND]
    return report


def status() -> dict:
    ds = dre.dataset_status()
    stale = (ds.get("fetched_at") is not None
             and (time.time() - ds["fetched_at"]) > DEFAULT_TTL_S)
    return {
        **_status,
        "ttl_s": DEFAULT_TTL_S,
        "dataset_stale": stale,
        "dataset": ds,
        "engine": f"domestic_rules_updater/{RULES_UPDATER_VERSION}",
    }


def history() -> List[dict]:
    return list(_history)


def reset_for_tests() -> None:
    global _fetch_fn
    _history.clear()
    for k in ("last_attempt", "last_attempt_iso", "last_successful_update",
              "last_successful_update_iso", "last_error", "last_error_iso",
              "source", "applied_version"):
        _status[k] = None
    _status["attempts"] = _status["failures"] = _status["successes"] = 0
    _fetch_fn = _fetch_http
