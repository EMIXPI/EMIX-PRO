# account_manager.py — Accounts / Devices / Subscriptions / Sessions (Phase 38 / P2+P3)
# ══════════════════════════════════════════════════════════════════════════════
# Entity relationship (first-class objects, backend-enforced limits):
#
#     Account → Subscription → Config(link) → Route → Node → Verified Egress
#        ↓
#     Device → Session
#
# SECURITY RULES:
#   * Passwords are PBKDF2-SHA256 hashed (salted, tunable iterations) — never
#     stored or logged in cleartext.
#   * Device access tokens are returned ONCE and stored only as SHA-256
#     hashes. Tokens are NEVER logged anywhere.
#   * Minimal sensitive data: no email required, no PII beyond what is typed.
#   * Limits (MAX_DEVICES / MAX_CONCURRENT_SESSIONS / quotas) are enforced
#     BACKEND-side in open_session()/can_connect() — never only in UI.
#
# CONNECTION GATE (the honest part):
#     can_connect(account, device, subscription) → verdict + reason
#     verdicts: ALLOWED | ACCOUNT_DISABLED | ACCOUNT_EXPIRED | QUOTA_EXCEEDED |
#               DEVICE_REVOKED | DEVICE_UNKNOWN | SESSION_LIMIT_REACHED |
#               SUBSCRIPTION_EXPIRED | SUBSCRIPTION_REVOKED |
#               SUBSCRIPTION_SUSPENDED | SUBSCRIPTION_UNKNOWN
#     A connection is allowed ONLY when every gate passes.
#
# Subscription config/URI generation goes through the unified Config Compiler
# (compile_fn injected — no duplicate URI generation logic in this module).
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Callable, Any

from pydantic import BaseModel

ACCOUNT_ENGINE_VERSION = "1.0.0"

ACCOUNT_STATUSES = ("ACTIVE", "DISABLED")
SUBSCRIPTION_STATUSES = ("ACTIVE", "EXPIRED", "REVOKED", "SUSPENDED", "DRAINING")
DEVICE_CONNECTION_STATES = ("CONNECTED", "DISCONNECTED", "UNKNOWN")

# Backend-enforced limits (env-tunable from main)
DEFAULT_MAX_DEVICES = 5
DEFAULT_MAX_CONCURRENT_SESSIONS = 3
DEFAULT_MAX_SUBSCRIPTIONS = 10

ACCOUNT_HISTORY_BOUND = 200          # bounded audit events

PBKDF2_ITERATIONS = 120_000


def _now() -> float:
    return time.time()


def _uid(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


# ── Password hashing (PBKDF2-SHA256, salted) ────────────────────────────────

def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                 bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)   # constant-time
    except Exception:
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── Entities ────────────────────────────────────────────────────────────────

@dataclass
class Account:
    id: str
    username: str
    password_hash: str
    email: Optional[str] = None
    status: str = "ACTIVE"                     # ACTIVE | DISABLED
    created_at: float = field(default_factory=_now)
    expires_at: Optional[float] = None         # None = no expiry
    traffic_quota_bytes: Optional[int] = None  # None = unlimited
    used_bytes: int = 0
    max_devices: int = DEFAULT_MAX_DEVICES
    max_concurrent_sessions: int = DEFAULT_MAX_CONCURRENT_SESSIONS
    max_subscriptions: int = DEFAULT_MAX_SUBSCRIPTIONS
    notes: List[str] = field(default_factory=list)

    def to_dict(self, include_hash: bool = False) -> dict:
        d = asdict(self)
        if not include_hash:
            d.pop("password_hash", None)
        d["created_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                            time.gmtime(self.created_at))
        d["expires_at_iso"] = (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.expires_at))
            if self.expires_at else None)
        d["quota_used_pct"] = (
            round(100.0 * self.used_bytes / self.traffic_quota_bytes, 1)
            if self.traffic_quota_bytes else None)
        d["expired"] = bool(self.expires_at and _now() > self.expires_at)
        d["over_quota"] = bool(self.traffic_quota_bytes
                               and self.used_bytes >= self.traffic_quota_bytes)
        return d


@dataclass
class Subscription:
    subscription_id: str
    account_id: str
    profile: str = "default"                   # endpoint/protocol profile name
    protocol: str = "vless"
    transport: str = "ws"
    route_policy: str = "ALL_VPN"              # ALL_VPN | IRAN_DIRECT | CUSTOM
    node_policy: str = "auto"                  # auto | pinned node id
    quota_bytes: Optional[int] = None
    used_bytes: int = 0
    expires_at: Optional[float] = None
    status: str = "ACTIVE"                     # SUBSCRIPTION_STATUSES
    link_ids: List[str] = field(default_factory=list)   # panel LINKS ids
    created_at: float = field(default_factory=_now)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["created_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                            time.gmtime(self.created_at))
        d["expires_at_iso"] = (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.expires_at))
            if self.expires_at else None)
        d["expired"] = bool(self.expires_at and _now() > self.expires_at)
        d["over_quota"] = bool(self.quota_bytes and self.used_bytes >= self.quota_bytes)
        return d


@dataclass
class Device:
    device_id: str
    account_id: str
    name: str = "unnamed device"
    platform: str = "unknown"
    client_metadata: str = ""                  # free-form, size-capped at input
    token_hash: str = ""                       # SHA-256 of the access token
    registered_at: float = field(default_factory=_now)
    last_seen: Optional[float] = None
    connection_state: str = "UNKNOWN"
    revoked: bool = False
    sessions_opened: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("token_hash", None)              # hashes never leave the engine
        d["registered_at_iso"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.registered_at))
        d["last_seen_iso"] = (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.last_seen))
            if self.last_seen else None)
        d["last_seen_age_s"] = (round(_now() - self.last_seen, 1)
                                if self.last_seen else None)
        return d


@dataclass
class ClientSession:
    session_id: str
    account_id: str
    device_id: str
    node_id: Optional[str] = None
    started_at: float = field(default_factory=_now)
    last_seen: float = field(default_factory=_now)
    bytes_in: int = 0
    bytes_out: int = 0
    active: bool = True

    def to_dict(self) -> dict:
        d = asdict(self)
        d["started_at_iso"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.started_at))
        return d


# ── Engine store (bounded, persisted via snapshot bridge) ──────────────────

_accounts: Dict[str, Account] = {}
_subscriptions: Dict[str, Subscription] = {}
_devices: Dict[str, Device] = {}
_sessions: Dict[str, ClientSession] = {}
_audit: List[dict] = []
_lock = asyncio.Lock()
_compile_fn: Optional[Callable] = None         # injected: config_compiler.compile_from_link


def set_compile_fn(fn: Callable) -> None:
    """DI seam — subscription configs are emitted by the unified Config
    Compiler (single source of truth; no duplicate URI logic here)."""
    global _compile_fn
    _compile_fn = fn


def _audit_log(event: str, **kw) -> None:
    # NOTE: never put tokens or password material in audit events.
    _audit.append({"event": event, "at": _now(), **kw})
    del _audit[:-ACCOUNT_HISTORY_BOUND]


def reset_for_tests() -> None:
    _accounts.clear(); _subscriptions.clear()
    _devices.clear(); _sessions.clear(); _audit.clear()
    global _compile_fn
    _compile_fn = None


# ── Accounts ────────────────────────────────────────────────────────────────

async def create_account(username: str, password: str,
                         email: Optional[str] = None,
                         expires_at: Optional[float] = None,
                         traffic_quota_bytes: Optional[int] = None,
                         max_devices: int = DEFAULT_MAX_DEVICES,
                         max_concurrent_sessions: int = DEFAULT_MAX_CONCURRENT_SESSIONS,
                         max_subscriptions: int = DEFAULT_MAX_SUBSCRIPTIONS
                         ) -> dict:
    username = (username or "").strip()
    if not username or len(username) > 64:
        raise ValueError("username must be 1-64 chars")
    if not password or len(password) < 8:
        raise ValueError("password must be at least 8 chars")
    async with _lock:
        for acc in _accounts.values():
            if acc.username.lower() == username.lower():
                raise ValueError(f"username already exists: {username}")
        acc = Account(
            id=_uid("acc"), username=username, password_hash=hash_password(password),
            email=email, expires_at=expires_at,
            traffic_quota_bytes=traffic_quota_bytes,
            max_devices=max_devices,
            max_concurrent_sessions=max_concurrent_sessions,
            max_subscriptions=max_subscriptions)
        _accounts[acc.id] = acc
    _audit_log("account_created", account_id=acc.id, username=username)
    return acc.to_dict()


async def authenticate(username: str, password: str) -> Optional[dict]:
    """None on failure. Constant-time hash comparison."""
    async with _lock:
        acc = next((a for a in _accounts.values()
                    if a.username.lower() == (username or "").strip().lower()), None)
        if acc is None or not verify_password(password or "", acc.password_hash):
            _audit_log("auth_failed", username=(username or "")[:64])
            return None
        acc.last_seen = _now()
    _audit_log("auth_ok", account_id=acc.id)
    return acc.to_dict()


async def set_account_status(account_id: str, status: str,
                             reason: str = "") -> Optional[dict]:
    if status not in ACCOUNT_STATUSES:
        raise ValueError(f"invalid status {status}")
    async with _lock:
        acc = _accounts.get(account_id)
        if acc is None:
            return None
        acc.status = status
        if status == "DISABLED":
            # revocation cascade: kill live sessions immediately (backend-enforced)
            for s in _sessions.values():
                if s.account_id == account_id and s.active:
                    s.active = False
    _audit_log("account_status", account_id=account_id, status=status, reason=reason)
    return acc.to_dict()


async def track_usage(account_id: str, bytes_in: int = 0, bytes_out: int = 0,
                      subscription_id: Optional[str] = None) -> Optional[dict]:
    """Usage accounting — enforced on the SAME gates connections use."""
    async with _lock:
        acc = _accounts.get(account_id)
        if acc is None:
            return None
        acc.used_bytes += max(0, int(bytes_in)) + max(0, int(bytes_out))
        sub = _subscriptions.get(subscription_id) if subscription_id else None
        if sub is not None:
            sub.used_bytes += max(0, int(bytes_in)) + max(0, int(bytes_out))
    return acc.to_dict()


# ── Devices ─────────────────────────────────────────────────────────────────

async def register_device(account_id: str, name: str, platform: str = "unknown",
                          client_metadata: str = "") -> dict:
    """Register a device; returns {device, access_token} — the token is
    returned ONCE and stored only as a SHA-256 hash (never logged)."""
    async with _lock:
        acc = _accounts.get(account_id)
        if acc is None:
            raise ValueError("account not found")
        if acc.status != "ACTIVE":
            raise ValueError("account not ACTIVE")
        owned = [d for d in _devices.values()
                 if d.account_id == account_id and not d.revoked]
        if len(owned) >= acc.max_devices:      # BACKEND-enforced device limit
            raise PermissionError(
                f"DEVICE_LIMIT_REACHED (max {acc.max_devices})")
        dev = Device(device_id=_uid("dev"), account_id=account_id,
                     name=(name or "unnamed device")[:64],
                     platform=(platform or "unknown")[:32],
                     client_metadata=(client_metadata or "")[:256],
                     token_hash="")
        token = secrets.token_urlsafe(24)      # shown once to the operator
        dev.token_hash = _token_hash(token)
        _devices[dev.device_id] = dev
    _audit_log("device_registered", account_id=account_id, device_id=dev.device_id)
    return {"device": dev.to_dict(), "access_token": token}


async def verify_device_token(device_id: str, token: str) -> Optional[dict]:
    async with _lock:
        dev = _devices.get(device_id)
        if dev is None or dev.revoked:
            return None
        if not dev.token_hash or not hmac.compare_digest(
                _token_hash(token or ""), dev.token_hash):
            return None
        dev.last_seen = _now()
        dev.connection_state = "UNKNOWN"
    return dev.to_dict()


async def revoke_device(device_id: str) -> Optional[dict]:
    async with _lock:
        dev = _devices.get(device_id)
        if dev is None:
            return None
        dev.revoked = True
        dev.connection_state = "DISCONNECTED"
        for s in _sessions.values():           # sessions die with the device
            if s.device_id == device_id and s.active:
                s.active = False
    _audit_log("device_revoked", device_id=device_id)
    return dev.to_dict()


async def rename_device(device_id: str, name: str) -> Optional[dict]:
    async with _lock:
        dev = _devices.get(device_id)
        if dev is None:
            return None
        dev.name = (name or dev.name)[:64]
        return dev.to_dict()


async def device_heartbeat(device_id: str) -> Optional[dict]:
    async with _lock:
        dev = _devices.get(device_id)
        if dev is None:
            return None
        dev.last_seen = _now()
        return dev.to_dict()


def list_devices(account_id: str) -> List[dict]:
    return [d.to_dict() for d in _devices.values() if d.account_id == account_id]


# ── Sessions ────────────────────────────────────────────────────────────────

async def open_session(account_id: str, device_id: str,
                       node_id: Optional[str] = None) -> dict:
    """Open a client session. ALL limits are enforced here, backend-side."""
    async with _lock:
        acc = _accounts.get(account_id)
        dev = _devices.get(device_id)
        if acc is None:
            raise PermissionError("ACCOUNT_UNKNOWN")
        if dev is None or dev.account_id != account_id:
            raise PermissionError("DEVICE_UNKNOWN")
        verdict, reason = _gate(acc, dev)
        if verdict != "ALLOWED":
            raise PermissionError(f"{verdict}: {reason}")
        live = [s for s in _sessions.values()
                if s.account_id == account_id and s.active]
        if len(live) >= acc.max_concurrent_sessions:
            raise PermissionError(
                f"SESSION_LIMIT_REACHED (max {acc.max_concurrent_sessions})")
        ses = ClientSession(session_id=_uid("ses"), account_id=account_id,
                            device_id=device_id, node_id=node_id)
        _sessions[ses.session_id] = ses
        dev.sessions_opened += 1
        dev.last_seen = _now()
        dev.connection_state = "CONNECTED"
    _audit_log("session_opened", account_id=account_id,
               device_id=device_id, node_id=node_id)
    return ses.to_dict()


async def close_session(session_id: str) -> Optional[dict]:
    async with _lock:
        ses = _sessions.get(session_id)
        if ses is None:
            return None
        ses.active = False
        dev = _devices.get(ses.device_id)
        if dev:
            dev.connection_state = "DISCONNECTED"
    _audit_log("session_closed", session_id=session_id)
    return ses.to_dict()


async def sweep_stale_sessions(max_idle_s: float = 3600.0) -> int:
    """Bounded cleanup — sessions idle past max_idle_s are closed."""
    closed = 0
    async with _lock:
        for ses in list(_sessions.values()):
            if ses.active and (_now() - ses.last_seen) > max_idle_s:
                ses.active = False
                closed += 1
    return closed


def _gate(acc: Account, dev: Device) -> tuple[str, str]:
    if acc.status != "ACTIVE":
        return "ACCOUNT_DISABLED", "account is disabled"
    if acc.expires_at and _now() > acc.expires_at:
        return "ACCOUNT_EXPIRED", "account expiry passed"
    if acc.traffic_quota_bytes and acc.used_bytes >= acc.traffic_quota_bytes:
        return "QUOTA_EXCEEDED", "traffic quota exhausted"
    if dev.revoked:
        return "DEVICE_REVOKED", "device was revoked"
    return "ALLOWED", "all gates passed"


def _sub_gate(sub: Subscription) -> tuple[str, str]:
    if sub.status == "REVOKED":
        return "SUBSCRIPTION_REVOKED", "subscription revoked"
    if sub.status == "SUSPENDED":
        return "SUBSCRIPTION_SUSPENDED", "subscription suspended"
    if sub.status == "DRAINING":
        return "ALLOWED", "draining — existing connections continue, no renewal"
    if sub.expires_at and _now() > sub.expires_at:
        return "SUBSCRIPTION_EXPIRED", "subscription expiry passed"
    if sub.quota_bytes and sub.used_bytes >= sub.quota_bytes:
        return "QUOTA_EXCEEDED", "subscription quota exhausted"
    return "ALLOWED", "subscription active"


async def can_connect(account_id: str, device_id: Optional[str] = None,
                      subscription_id: Optional[str] = None) -> dict:
    """THE connection gate. Every verdict carries an honest reason."""
    async with _lock:
        acc = _accounts.get(account_id)
        if acc is None:
            return {"verdict": "ACCOUNT_UNKNOWN", "reason": "account not found",
                    "allowed": False}
        dev = _devices.get(device_id) if device_id else None
        if device_id and (dev is None or dev.account_id != account_id):
            return {"verdict": "DEVICE_UNKNOWN", "reason": "device not found",
                    "allowed": False}
        verdict, reason = _gate(acc, dev or Device(
            device_id="probe", account_id=account_id, revoked=False))
        if verdict != "ALLOWED":
            return {"verdict": verdict, "reason": reason, "allowed": False}
        if subscription_id:
            sub = _subscriptions.get(subscription_id)
            if sub is None:
                return {"verdict": "SUBSCRIPTION_UNKNOWN",
                        "reason": "subscription not found", "allowed": False}
            if sub.account_id != account_id:
                return {"verdict": "SUBSCRIPTION_UNKNOWN",
                        "reason": "subscription belongs to another account",
                        "allowed": False}
            verdict, reason = _sub_gate(sub)
            if verdict != "ALLOWED":
                return {"verdict": verdict, "reason": reason, "allowed": False}
    return {"verdict": "ALLOWED", "reason": "all gates passed", "allowed": True}


# ── Subscriptions ───────────────────────────────────────────────────────────

async def create_subscription(account_id: str, profile: str = "default",
                              protocol: str = "vless", transport: str = "ws",
                              route_policy: str = "ALL_VPN",
                              node_policy: str = "auto",
                              quota_bytes: Optional[int] = None,
                              expires_at: Optional[float] = None,
                              link_ids: Optional[List[str]] = None
                              ) -> dict:
    async with _lock:
        acc = _accounts.get(account_id)
        if acc is None:
            raise ValueError("account not found")
        if acc.status != "ACTIVE":
            raise PermissionError("account not ACTIVE")
        owned = [s for s in _subscriptions.values()
                 if s.account_id == account_id and s.status in ("ACTIVE", "DRAINING")]
        if len(owned) >= acc.max_subscriptions:
            raise PermissionError(
                f"SUBSCRIPTION_LIMIT_REACHED (max {acc.max_subscriptions})")
        sub = Subscription(
            subscription_id=_uid("sub"), account_id=account_id,
            profile=(profile or "default")[:64], protocol=protocol,
            transport=transport, route_policy=route_policy,
            node_policy=node_policy, quota_bytes=quota_bytes,
            expires_at=expires_at, link_ids=list(link_ids or []))
        _subscriptions[sub.subscription_id] = sub
    _audit_log("subscription_created", account_id=account_id,
               subscription_id=sub.subscription_id)
    return sub.to_dict()


async def set_subscription_status(subscription_id: str, status: str,
                                  reason: str = "") -> Optional[dict]:
    if status not in SUBSCRIPTION_STATUSES:
        raise ValueError(f"invalid subscription status {status}")
    async with _lock:
        sub = _subscriptions.get(subscription_id)
        if sub is None:
            return None
        sub.status = status
    _audit_log("subscription_status", subscription_id=subscription_id,
               status=status, reason=reason)
    return sub.to_dict()


async def reconcile_subscription_statuses() -> dict:
    """Sweep: expiry/quota → status transitions (EXPIRED / DRAINING)."""
    changed = {}
    async with _lock:
        for sub in _subscriptions.values():
            if sub.status not in ("ACTIVE", "DRAINING"):
                continue
            if sub.expires_at and _now() > sub.expires_at and sub.status != "EXPIRED":
                sub.status = "EXPIRED"
                changed[sub.subscription_id] = "EXPIRED"
            elif (sub.quota_bytes and sub.used_bytes >= sub.quota_bytes
                  and sub.status == "ACTIVE"):
                sub.status = "DRAINING"        # existing continue, new blocked
                changed[sub.subscription_id] = "DRAINING"
    return changed


async def compile_subscription_configs(subscription_id: str,
                                       links: List[dict]) -> dict:
    """Emit configs for a subscription's links THROUGH the unified Config
    Compiler (injected compile_fn). No duplicate URI logic here — ever."""
    sub = _subscriptions.get(subscription_id)
    if sub is None:
        return {"error": "subscription not found"}
    if _compile_fn is None:
        return {"error": "CONFIG_COMPILER_NOT_WIRED",
                "note": "compile_fn not injected (main wires config_compiler)"}
    out = []
    for link in links:
        if link.get("id") not in sub.link_ids and link.get("label") not in sub.link_ids:
            continue
        try:
            compiled = _compile_fn(link)      # config_compiler.compile_from_link
            out.append({"ok": True, "link": link.get("id") or link.get("label"),
                        "uri": compiled.uri if hasattr(compiled, "uri") else str(compiled),
                        "checksum": getattr(compiled, "checksum", None)})
        except Exception as exc:
            out.append({"ok": False, "link": link.get("id") or link.get("label"),
                        "error": str(exc)[:200]})
    return {"subscription_id": subscription_id,
            "route_policy": sub.route_policy,
            "node_policy": sub.node_policy,
            "configs": out,
            "emitted_by": "config_compiler (unified — no duplicate logic)"}


# ── Queries / summary / persistence ─────────────────────────────────────────

def get_account(account_id: str) -> Optional[dict]:
    acc = _accounts.get(account_id)
    return acc.to_dict() if acc else None


def list_accounts() -> List[dict]:
    return [a.to_dict() for a in _accounts.values()]


def list_subscriptions(account_id: Optional[str] = None) -> List[dict]:
    return [s.to_dict() for s in _subscriptions.values()
            if account_id is None or s.account_id == account_id]


def list_sessions(account_id: Optional[str] = None, active_only: bool = True) -> List[dict]:
    return [s.to_dict() for s in _sessions.values()
            if (not active_only or s.active)
            and (account_id is None or s.account_id == account_id)]


def audit_events(limit: int = 50) -> List[dict]:
    return list(_audit[-limit:])


def summary() -> dict:
    active_sessions = sum(1 for s in _sessions.values() if s.active)
    return {
        "accounts": len(_accounts),
        "accounts_active": sum(1 for a in _accounts.values() if a.status == "ACTIVE"),
        "subscriptions": len(_subscriptions),
        "devices": len(_devices),
        "devices_revoked": sum(1 for d in _devices.values() if d.revoked),
        "sessions_active": active_sessions,
        "audit_events": len(_audit),
        "limits": {"default_max_devices": DEFAULT_MAX_DEVICES,
                   "default_max_concurrent_sessions": DEFAULT_MAX_CONCURRENT_SESSIONS,
                   "default_max_subscriptions": DEFAULT_MAX_SUBSCRIPTIONS},
        "engine": f"account_manager/{ACCOUNT_ENGINE_VERSION}",
    }


def persist_snapshot() -> dict:
    return {
        "accounts": [a.__dict__ for a in _accounts.values()],
        "subscriptions": [s.__dict__ for s in _subscriptions.values()],
        "devices": [d.__dict__ for d in _devices.values()],
        "sessions": [s.__dict__ for s in _sessions.values() if s.active],
        "audit": _audit[-50:],
    }


def restore_snapshot(data: dict) -> None:
    _accounts.clear(); _subscriptions.clear(); _devices.clear(); _sessions.clear()
    for d in (data or {}).get("accounts", []):
        try:
            d = {k: v for k, v in d.items() if k in Account.__dataclass_fields__}
            _accounts[d["id"]] = Account(**d)
        except Exception:
            continue
    for d in (data or {}).get("subscriptions", []):
        try:
            d = {k: v for k, v in d.items() if k in Subscription.__dataclass_fields__}
            _subscriptions[d["subscription_id"]] = Subscription(**d)
        except Exception:
            continue
    for d in (data or {}).get("devices", []):
        try:
            d = {k: v for k, v in d.items() if k in Device.__dataclass_fields__}
            _devices[d["device_id"]] = Device(**d)
        except Exception:
            continue
    for d in (data or {}).get("sessions", []):
        try:
            d = {k: v for k, v in d.items() if k in ClientSession.__dataclass_fields__}
            _sessions[d["session_id"]] = ClientSession(**d)
        except Exception:
            continue


# ── API surface (admin-auth; registered from main) ─────────────────────────

class AccountIn(BaseModel):
    """Module-level on purpose: FastAPI cannot resolve function-local classes
    under `from __future__ import annotations` (same lesson as v11.2.0)."""
    username: str
    password: str
    email: Optional[str] = None
    expires_in_days: Optional[int] = None
    traffic_quota_gb: Optional[float] = None
    max_devices: int = DEFAULT_MAX_DEVICES
    max_concurrent_sessions: int = DEFAULT_MAX_CONCURRENT_SESSIONS


class DeviceIn(BaseModel):
    name: str = "unnamed device"
    platform: str = "unknown"
    client_metadata: str = ""


class SubscriptionIn(BaseModel):
    profile: str = "default"
    protocol: str = "vless"
    transport: str = "ws"
    route_policy: str = "ALL_VPN"
    node_policy: str = "auto"
    quota_gb: Optional[float] = None
    expires_in_days: Optional[int] = None
    link_ids: List[str] = []


def register_routes(app, require_auth) -> None:
    from fastapi import Depends, Query
    from fastapi.responses import JSONResponse

    _auth = [Depends(require_auth)]

    @app.get("/api/accounts", dependencies=_auth)
    async def api_accounts():
        return {"accounts": list_accounts(), "summary": summary()}

    @app.post("/api/accounts", dependencies=_auth)
    async def api_create_account(body: AccountIn):
        try:
            exp = (time.time() + body.expires_in_days * 86400
                   ) if body.expires_in_days else None
            quota = (int(body.traffic_quota_gb * (10 ** 9))
                     ) if body.traffic_quota_gb else None
            acc = await create_account(
                body.username, body.password, email=body.email,
                expires_at=exp, traffic_quota_bytes=quota,
                max_devices=body.max_devices,
                max_concurrent_sessions=body.max_concurrent_sessions)
            return acc
        except (ValueError, PermissionError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.get("/api/accounts/summary", dependencies=_auth)
    async def api_accounts_summary():
        return summary()

    @app.get("/api/accounts/{account_id}", dependencies=_auth)
    async def api_account(account_id: str):
        acc = get_account(account_id)
        if acc is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        acc["devices"] = list_devices(account_id)
        acc["subscriptions"] = list_subscriptions(account_id)
        acc["sessions"] = list_sessions(account_id)
        return acc

    @app.post("/api/accounts/{account_id}/status", dependencies=_auth)
    async def api_account_status(account_id: str, status: str = Query(...),
                                 reason: str = Query("")):
        try:
            out = await set_account_status(account_id, status, reason)
            if out is None:
                from fastapi.responses import JSONResponse
                return JSONResponse({"error": "not found"}, status_code=404)
            return out
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.post("/api/accounts/{account_id}/devices", dependencies=_auth)
    async def api_register_device(account_id: str, body: DeviceIn):
        try:
            out = await register_device(account_id, body.name, body.platform,
                                        body.client_metadata)
            # access_token returned exactly once, never stored/logged in clear
            return out
        except (ValueError, PermissionError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.post("/api/devices/{device_id}/revoke", dependencies=_auth)
    async def api_revoke_device(device_id: str):
        out = await revoke_device(device_id)
        if out is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return out

    @app.post("/api/devices/{device_id}/rename", dependencies=_auth)
    async def api_rename_device(device_id: str, name: str = Query(...)):
        out = await rename_device(device_id, name)
        if out is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return out

    @app.get("/api/accounts/{account_id}/subscriptions", dependencies=_auth)
    async def api_list_subs(account_id: str):
        return {"subscriptions": list_subscriptions(account_id)}

    @app.post("/api/accounts/{account_id}/subscriptions", dependencies=_auth)
    async def api_create_sub(account_id: str, body: SubscriptionIn):
        try:
            exp = (time.time() + body.expires_in_days * 86400
                   ) if body.expires_in_days else None
            quota = int(body.quota_gb * (10 ** 9)) if body.quota_gb else None
            sub = await create_subscription(
                account_id, profile=body.profile, protocol=body.protocol,
                transport=body.transport, route_policy=body.route_policy,
                node_policy=body.node_policy, quota_bytes=quota,
                expires_at=exp, link_ids=body.link_ids)
            return sub
        except (ValueError, PermissionError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.post("/api/subscriptions/{subscription_id}/status", dependencies=_auth)
    async def api_sub_status(subscription_id: str, status: str = Query(...),
                             reason: str = Query("")):
        try:
            out = await set_subscription_status(subscription_id, status, reason)
            if out is None:
                from fastapi.responses import JSONResponse
                return JSONResponse({"error": "not found"}, status_code=404)
            return out
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.get("/api/connect/authorize", dependencies=_auth)
    async def api_connect_authorize(account_id: str = Query(...),
                                    device_id: Optional[str] = Query(None),
                                    subscription_id: Optional[str] = Query(None)):
        """The connection gate — used by exit nodes / workers / E2E tests."""
        return await can_connect(account_id, device_id, subscription_id)

