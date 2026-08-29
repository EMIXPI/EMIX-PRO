"""Regression test for _TrojanHashCache invalidation (Phase 6.12).

Verifies the cache is invalidated when the SET of UUIDs changes — not just
when the count changes. This catches the previously-reported bug:
  delete link A + add link B (same len) → stale cache → wrong UUID returned.

Direct approach: we patch protocol.trojan.trojan's LINKS and LINKS_LOCK
globals (the cache reads them by name at call time, not via the import-time
bound name).
"""
import asyncio
import hashlib
import pytest

import protocol.trojan.trojan as trojan_mod

# Use a fresh asyncio.Lock and a fresh dict — both writable by the test.
_TEST_LINKS: dict = {}
_TEST_LOCK = asyncio.Lock()


@pytest.fixture(autouse=True)
def _patch_trojan_globals():
    """Replace LINKS and LINKS_LOCK in the trojan module namespace."""
    orig_links = trojan_mod.LINKS
    orig_lock = trojan_mod.LINKS_LOCK
    trojan_mod.LINKS = _TEST_LINKS
    trojan_mod.LINKS_LOCK = _TEST_LOCK
    _TEST_LINKS.clear()
    yield
    trojan_mod.LINKS = orig_links
    trojan_mod.LINKS_LOCK = orig_lock
    _TEST_LINKS.clear()


def _hash_uuid(uid: str) -> str:
    return hashlib.sha224(uid.encode()).hexdigest()


def test_cache_returns_correct_uuid_after_rebuild():
    async def run():
        cache = trojan_mod._TrojanHashCache()
        uid = "aaaa1111-2222-3333-4444-555566667777"
        _TEST_LINKS[uid] = {"label": "A"}
        h = _hash_uuid(uid)
        result = await cache.find_uuid(h)
        assert result == uid
    asyncio.run(run())


def test_cache_invalidates_when_uuid_set_changes_same_len():
    """The Phase 6.12 bug: delete A + add B (same len) → stale cache."""
    async def run():
        cache = trojan_mod._TrojanHashCache()
        uid_a = "aaaa1111-2222-3333-4444-555566667777"
        uid_b = "bbbb2222-3333-4444-5555-666677778888"
        # Setup: only A exists
        _TEST_LINKS.clear()
        _TEST_LINKS[uid_a] = {"label": "A"}
        # Build the cache
        result_a = await cache.find_uuid(_hash_uuid(uid_a))
        assert result_a == uid_a
        # Now: delete A, add B — len(LINKS) unchanged!
        _TEST_LINKS.clear()
        _TEST_LINKS[uid_b] = {"label": "B"}
        # OLD behavior: cache returns stale uid_a for hash of uid_a.
        # NEW behavior: cache invalidates because the key SET changed.
        result_a_after = await cache.find_uuid(_hash_uuid(uid_a))
        assert result_a_after is None, (
            f"cache returned stale UUID {result_a_after!r} — "
            "Phase 6.12 fix not working"
        )
        result_b_after = await cache.find_uuid(_hash_uuid(uid_b))
        assert result_b_after == uid_b
    asyncio.run(run())


def test_cache_survives_when_nothing_changes():
    async def run():
        cache = trojan_mod._TrojanHashCache()
        uid = "cccc3333-4444-5555-6666-777788889999"
        _TEST_LINKS.clear()
        _TEST_LINKS[uid] = {"label": "C"}
        # First call builds the cache
        r1 = await cache.find_uuid(_hash_uuid(uid))
        assert r1 == uid
        # Second call should use the cache (no rebuild needed)
        r2 = await cache.find_uuid(_hash_uuid(uid))
        assert r2 == uid
    asyncio.run(run())


def test_cache_returns_none_for_unknown_hash():
    async def run():
        cache = trojan_mod._TrojanHashCache()
        _TEST_LINKS.clear()
        _TEST_LINKS["dddd4444-5555-6666-7777-888899990000"] = {"label": "D"}
        unknown = "0" * 56  # 56-char sha224 that won't match
        result = await cache.find_uuid(unknown)
        assert result is None
    asyncio.run(run())


def test_cache_handles_empty_links():
    async def run():
        cache = trojan_mod._TrojanHashCache()
        _TEST_LINKS.clear()
        result = await cache.find_uuid(_hash_uuid("any-uuid"))
        assert result is None
    asyncio.run(run())
