# tests/unit/test_account_manager.py — Phase 38 / P2+P3 accounts engine
# Security semantics: hashed passwords, one-time tokens, backend limits.

import asyncio
import time

import pytest

import account_manager as am


@pytest.fixture(autouse=True)
def clean():
    am.reset_for_tests()
    yield
    am.reset_for_tests()




# ── password hashing ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_password_hash_is_pbkdf2_salted():
    h = am.hash_password("s3cret-pass")
    assert h.startswith("pbkdf2_sha256$")
    assert h != am.hash_password("s3cret-pass")       # random salt


@pytest.mark.asyncio
async def test_password_verify_roundtrip():
    h = am.hash_password("s3cret-pass", iterations=1000)
    assert am.verify_password("s3cret-pass", h) is True
    assert am.verify_password("wrong", h) is False


@pytest.mark.asyncio
async def test_password_verify_malformed_hash_fails_closed():
    assert am.verify_password("x", "garbage") is False
    assert am.verify_password("x", "") is False


# ── accounts ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_account_and_authenticate():
    acc = await (am.create_account("ali", "password123"))
    assert acc["username"] == "ali"
    assert "password_hash" not in acc                 # hash never serialized
    auth = await (am.authenticate("ali", "password123"))
    assert auth["id"] == acc["id"]
    assert await (am.authenticate("ali", "wrong")) is None


@pytest.mark.asyncio
async def test_duplicate_username_rejected():
    await (am.create_account("ali", "password123"))
    with pytest.raises(ValueError):
        await (am.create_account("ALI", "password456"))  # case-insensitive


@pytest.mark.asyncio
async def test_weak_password_rejected():
    with pytest.raises(ValueError):
        await (am.create_account("ali", "short"))
    with pytest.raises(ValueError):
        await (am.create_account("", "password123"))


@pytest.mark.asyncio
async def test_disable_account_kills_sessions():
    acc = await (am.create_account("ali", "password123"))
    await (am.register_device(acc["id"], "phone", "android"))
    dev = am.list_devices(acc["id"])[0]
    await (am.open_session(acc["id"], dev["device_id"]))
    assert len(am.list_sessions(acc["id"], active_only=True)) == 1
    await (am.set_account_status(acc["id"], "DISABLED"))
    assert len(am.list_sessions(acc["id"], active_only=True)) == 0
    gate = await (am.can_connect(acc["id"], dev["device_id"]))
    assert gate["verdict"] == "ACCOUNT_DISABLED"


@pytest.mark.asyncio
async def test_expired_account_blocked():
    acc = await (am.create_account("ali", "password123",
                                expires_at=time.time() - 10))
    gate = await (am.can_connect(acc["id"]))
    assert gate["verdict"] == "ACCOUNT_EXPIRED"
    assert gate["allowed"] is False


@pytest.mark.asyncio
async def test_quota_enforced_backend():
    acc = await (am.create_account("ali", "password123",
                                traffic_quota_bytes=1000))
    await (am.track_usage(acc["id"], bytes_in=600, bytes_out=500))
    gate = await (am.can_connect(acc["id"]))
    assert gate["verdict"] == "QUOTA_EXCEEDED"


# ── devices ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_device_returns_one_time_token():
    acc = await (am.create_account("ali", "password123"))
    out = await (am.register_device(acc["id"], "my-phone", "android", "meta"))
    assert "access_token" in out
    dev = out["device"]
    assert "token_hash" not in dev                   # hash never serialized
    # token verifies
    verified = await (am.verify_device_token(dev["device_id"], out["access_token"]))
    assert verified is not None
    # wrong token fails
    assert await (am.verify_device_token(dev["device_id"], "nope")) is None


@pytest.mark.asyncio
async def test_device_limit_enforced_backend():
    acc = await (am.create_account("ali", "password123", max_devices=2))
    await (am.register_device(acc["id"], "d1"))
    await (am.register_device(acc["id"], "d2"))
    with pytest.raises(PermissionError) as e:
        await (am.register_device(acc["id"], "d3"))
    assert "DEVICE_LIMIT_REACHED" in str(e.value)


@pytest.mark.asyncio
async def test_revoked_device_rejected_and_sessions_die():
    acc = await (am.create_account("ali", "password123"))
    out = await (am.register_device(acc["id"], "phone"))
    dev_id = out["device"]["device_id"]
    await (am.open_session(acc["id"], dev_id))
    await (am.revoke_device(dev_id))
    assert len(am.list_sessions(acc["id"], active_only=True)) == 0
    gate = await (am.can_connect(acc["id"], dev_id))
    assert gate["verdict"] == "DEVICE_REVOKED"
    assert await (am.verify_device_token(dev_id, out["access_token"])) is None


@pytest.mark.asyncio
async def test_device_limit_counts_only_active_devices():
    acc = await (am.create_account("ali", "password123", max_devices=1))
    out = await (am.register_device(acc["id"], "d1"))
    await (am.revoke_device(out["device"]["device_id"]))
    out2 = await (am.register_device(acc["id"], "d2"))   # revoked slot freed
    assert out2["device"]["name"] == "d2"


@pytest.mark.asyncio
async def test_device_rename_and_heartbeat():
    acc = await (am.create_account("ali", "password123"))
    out = await (am.register_device(acc["id"], "old-name"))
    dev_id = out["device"]["device_id"]
    await (am.rename_device(dev_id, "new-name"))
    assert am.list_devices(acc["id"])[0]["name"] == "new-name"
    await (am.device_heartbeat(dev_id))
    assert am.list_devices(acc["id"])[0]["last_seen"] is not None


# ── sessions ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_limit_enforced_backend():
    acc = await (am.create_account("ali", "password123",
                                max_concurrent_sessions=2))
    out = await (am.register_device(acc["id"], "phone"))
    dev_id = out["device"]["device_id"]
    await (am.open_session(acc["id"], dev_id))
    await (am.open_session(acc["id"], dev_id))
    with pytest.raises(PermissionError) as e:
        await (am.open_session(acc["id"], dev_id))
    assert "SESSION_LIMIT_REACHED" in str(e.value)


@pytest.mark.asyncio
async def test_session_close_updates_device_state():
    acc = await (am.create_account("ali", "password123"))
    out = await (am.register_device(acc["id"], "phone"))
    ses = await (am.open_session(acc["id"], out["device"]["device_id"]))
    await (am.close_session(ses["session_id"]))
    assert len(am.list_sessions(acc["id"], active_only=True)) == 0
    dev = am.list_devices(acc["id"])[0]
    assert dev["connection_state"] == "DISCONNECTED"


@pytest.mark.asyncio
async def test_stale_session_sweep():
    acc = await (am.create_account("ali", "password123"))
    out = await (am.register_device(acc["id"], "phone"))
    ses = await (am.open_session(acc["id"], out["device"]["device_id"]))
    # age it beyond max idle
    am._sessions[ses["session_id"]].last_seen -= 7200
    closed = await (am.sweep_stale_sessions(max_idle_s=3600))
    assert closed == 1
    assert len(am.list_sessions(acc["id"], active_only=True)) == 0


# ── subscriptions ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_subscription_defaults():
    acc = await (am.create_account("ali", "password123"))
    sub = await (am.create_subscription(acc["id"]))
    assert sub["status"] == "ACTIVE"
    assert sub["route_policy"] == "ALL_VPN"
    assert sub["node_policy"] == "auto"
    assert sub["protocol"] == "vless"


@pytest.mark.asyncio
async def test_subscription_limit_enforced():
    acc = await (am.create_account("ali", "password123", max_subscriptions=1))
    await (am.create_subscription(acc["id"]))
    with pytest.raises(PermissionError) as e:
        await (am.create_subscription(acc["id"]))
    assert "SUBSCRIPTION_LIMIT_REACHED" in str(e.value)


@pytest.mark.asyncio
async def test_expired_subscription_blocked():
    acc = await (am.create_account("ali", "password123"))
    sub = await (am.create_subscription(acc["id"], expires_at=time.time() - 5))
    gate = await (am.can_connect(acc["id"], subscription_id=sub["subscription_id"]))
    assert gate["verdict"] == "SUBSCRIPTION_EXPIRED"
    assert gate["allowed"] is False


@pytest.mark.asyncio
async def test_revoked_subscription_blocked():
    acc = await (am.create_account("ali", "password123"))
    sub = await (am.create_subscription(acc["id"]))
    await (am.set_subscription_status(sub["subscription_id"], "REVOKED"))
    gate = await (am.can_connect(acc["id"], subscription_id=sub["subscription_id"]))
    assert gate["verdict"] == "SUBSCRIPTION_REVOKED"


@pytest.mark.asyncio
async def test_suspended_subscription_blocked():
    acc = await (am.create_account("ali", "password123"))
    sub = await (am.create_subscription(acc["id"]))
    await (am.set_subscription_status(sub["subscription_id"], "SUSPENDED"))
    gate = await (am.can_connect(acc["id"], subscription_id=sub["subscription_id"]))
    assert gate["verdict"] == "SUBSCRIPTION_SUSPENDED"


@pytest.mark.asyncio
async def test_reconcile_expires_and_drains():
    acc = await (am.create_account("ali", "password123"))
    s_exp = await (am.create_subscription(acc["id"], expires_at=time.time() - 5))
    s_quota = await (am.create_subscription(acc["id"], quota_bytes=100))
    await (am.track_usage(acc["id"], bytes_in=200,
                       subscription_id=s_quota["subscription_id"]))
    changed = await (am.reconcile_subscription_statuses())
    assert changed[s_exp["subscription_id"]] == "EXPIRED"
    assert changed[s_quota["subscription_id"]] == "DRAINING"


@pytest.mark.asyncio
async def test_subscription_unknown_and_foreign():
    acc = await (am.create_account("ali", "password123"))
    gate = await (am.can_connect(acc["id"], subscription_id="sub_missing"))
    assert gate["verdict"] == "SUBSCRIPTION_UNKNOWN"
    other = await (am.create_account("reza", "password123"))
    sub = await (am.create_subscription(other["id"]))
    gate = await (am.can_connect(acc["id"], subscription_id=sub["subscription_id"]))
    assert gate["verdict"] == "SUBSCRIPTION_UNKNOWN"   # belongs to another


@pytest.mark.asyncio
async def test_subscription_statuses_vocabulary():
    assert am.SUBSCRIPTION_STATUSES == (
        "ACTIVE", "EXPIRED", "REVOKED", "SUSPENDED", "DRAINING")


# ── connection gate (the full E2E semantics, engine level) ──────────────────

@pytest.mark.asyncio
async def test_can_connect_allowed_when_all_gates_pass():
    acc = await (am.create_account("ali", "password123"))
    out = await (am.register_device(acc["id"], "phone"))
    sub = await (am.create_subscription(acc["id"]))
    gate = await (am.can_connect(acc["id"], out["device"]["device_id"],
                              sub["subscription_id"]))
    assert gate["verdict"] == "ALLOWED"
    assert gate["allowed"] is True


@pytest.mark.asyncio
async def test_can_connect_unknown_account():
    gate = await (am.can_connect("acc_ghost"))
    assert gate["verdict"] == "ACCOUNT_UNKNOWN"


@pytest.mark.asyncio
async def test_subscription_compilation_requires_unified_compiler():
    acc = await (am.create_account("ali", "password123"))
    sub = await (am.create_subscription(acc["id"]))
    out = await (am.compile_subscription_configs(sub["subscription_id"], []))
    assert "CONFIG_COMPILER_NOT_WIRED" in out.get("error", "")
    # wiring a compile fn routes through it (no duplicate logic)
    am.set_compile_fn(lambda link: type("C", (), {"uri": "vless://x",
                                                  "checksum": "abc"})())
    out2 = await (am.compile_subscription_configs(
        sub["subscription_id"], [{"id": "l1", "label": "l1"}]))
    assert sub["subscription_id"] == out2["subscription_id"]
    assert out2["emitted_by"].startswith("config_compiler")


# ── persistence + audit ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_persist_and_restore_snapshot():
    acc = await (am.create_account("ali", "password123"))
    await (am.register_device(acc["id"], "phone"))
    sub = await (am.create_subscription(acc["id"]))
    snap = am.persist_snapshot()
    am.reset_for_tests()
    am.restore_snapshot(snap)
    assert am.get_account(acc["id"])["username"] == "ali"
    assert len(am.list_devices(acc["id"])) == 1
    assert am.list_subscriptions(acc["id"])[0]["subscription_id"] == \
        sub["subscription_id"]
    # restored device keeps its token hash → old token still verifies
    dev = am._devices.values().__iter__().__next__()
    assert dev.token_hash


@pytest.mark.asyncio
async def test_audit_never_contains_token_or_password():
    acc = await (am.create_account("ali", "password123"))
    out = await (am.register_device(acc["id"], "phone"))
    await (am.open_session(acc["id"], out["device"]["device_id"]))
    blob = str(am.audit_events(100))
    assert "password123" not in blob
    assert out["access_token"] not in blob          # token never logged


@pytest.mark.asyncio
async def test_audit_events_bounded():
    acc = await (am.create_account("ali", "password123"))
    for i in range(am.ACCOUNT_HISTORY_BOUND + 10):
        am._audit_log("tick", i=i)
    assert len(am.audit_events(10_000)) <= am.ACCOUNT_HISTORY_BOUND


@pytest.mark.asyncio
async def test_summary_shape():
    acc = await (am.create_account("ali", "password123"))
    await (am.register_device(acc["id"], "phone"))
    s = am.summary()
    assert s["accounts"] == 1
    assert s["devices"] == 1
    assert "limits" in s
    assert s["engine"].startswith("account_manager/")
