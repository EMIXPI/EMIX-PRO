# backup_validator.py — strict schema validation for backup import (Phase 3.9)
#
# Workflow enforced by callers:
#   VALIDATE → STAGE → BACKUP CURRENT STATE → APPLY → VERIFY
#
# Never: PARSE → OVERWRITE
#
# On validation failure: no state change.
# On apply failure: rollback automatically from the staged backup.
#
# Validation covers:
#   - top-level structure
#   - links, subs, nodes, node_keys, password_hash
#   - required fields per entity
#   - field types
#   - UUID format
#   - protocol names
#   - non-negative limits
#   - ISO timestamps where applicable
#
# Unknown fields are preserved, never silently discarded.

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("EMIX.backup")

# UUID v4-ish format: 8-4-4-4-12 hex chars (case-insensitive, with hyphens)
# We accept any 8-4-4-4-12 hex (not strictly v4 — production UUIDs in EMIX
# are derived from sha256 and may have any version nibble).
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_VALID_PROTOCOLS = {
    "vless-ws",
    "xhttp-packet-up", "xhttp-stream-up",
    "trojan-ws", "trojan-xhttp-packet-up", "trojan-xhttp-stream-up",
    "mtproto", "shadowsocks",
}


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data: Optional[dict] = None  # normalized, validated data

    def __bool__(self):
        return self.ok


def _is_uuid(s: Any) -> bool:
    return isinstance(s, str) and bool(_UUID_RE.match(s))


def _is_iso_timestamp(s: Any) -> bool:
    """Permissive ISO timestamp check. Accepts 'YYYY-MM-DDTHH:MM:SS' prefix."""
    if not isinstance(s, str):
        return False
    if len(s) < 10:
        return False
    # Year-Month-Day at minimum
    try:
        year = int(s[:4])
        month = int(s[5:7])
        day = int(s[8:10])
        return 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31
    except (ValueError, IndexError):
        return False


def _validate_link(uid: str, link: Any) -> list[str]:
    errors = []
    if not _is_uuid(uid):
        errors.append(f"link key is not a valid UUID: {uid!r}")
    if not isinstance(link, dict):
        errors.append(f"link[{uid[:8]}] must be an object")
        return errors

    # Required fields with type checks
    label = link.get("label")
    if not isinstance(label, str):
        errors.append(f"link[{uid[:8]}] missing/invalid 'label' (must be string)")

    proto = link.get("protocol")
    if not isinstance(proto, str):
        errors.append(f"link[{uid[:8]}] missing 'protocol'")
    elif proto not in _VALID_PROTOCOLS:
        errors.append(f"link[{uid[:8]}] has unknown protocol: {proto!r}")

    # Limits must be non-negative integers (or 0 = unlimited)
    for k in ("limit_bytes", "used_bytes"):
        v = link.get(k)
        if v is None:
            continue
        if not isinstance(v, (int, float)):
            errors.append(f"link[{uid[:8]}] {k} must be numeric, got {type(v).__name__}")
        elif v < 0:
            errors.append(f"link[{uid[:8]}] {k} must not be negative, got {v}")
        # bool is a subclass of int — reject explicitly
        elif isinstance(v, bool):
            errors.append(f"link[{uid[:8]}] {k} must not be boolean")

    active = link.get("active", True)
    if not isinstance(active, bool):
        errors.append(f"link[{uid[:8]}] 'active' must be boolean, got {type(active).__name__}")

    exp = link.get("expires_at")
    if exp is not None and not _is_iso_timestamp(exp):
        errors.append(f"link[{uid[:8]}] 'expires_at' must be ISO timestamp or null, got {exp!r}")

    created = link.get("created_at")
    if created is not None and not _is_iso_timestamp(created):
        errors.append(f"link[{uid[:8]}] 'created_at' must be ISO timestamp or null")

    # ── SNI spoofing fields (optional, but if present must be right type) ──
    # spoof_sni: must be a string (or null). Empty string is allowed (treated
    # as "no spoof"). Validation of the domain content is done at runtime by
    # _validate_sni() in main.py — the backup validator only checks types.
    spoof_sni = link.get("spoof_sni")
    if spoof_sni is not None and not isinstance(spoof_sni, str):
        errors.append(f"link[{uid[:8]}] 'spoof_sni' must be a string or null, got {type(spoof_sni).__name__}")
    elif isinstance(spoof_sni, str) and len(spoof_sni) > 253:
        errors.append(f"link[{uid[:8]}] 'spoof_sni' must be ≤ 253 chars (RFC 1123)")

    spoof_enabled = link.get("spoof_sni_enabled", False)
    if not isinstance(spoof_enabled, bool):
        errors.append(f"link[{uid[:8]}] 'spoof_sni_enabled' must be boolean, got {type(spoof_enabled).__name__}")

    return errors


def _validate_sub(sid: str, sub: Any) -> list[str]:
    errors = []
    if not _is_uuid(sid) and not isinstance(sid, str):
        errors.append(f"sub key must be a string: {sid!r}")
    if not isinstance(sub, dict):
        errors.append(f"sub[{sid}] must be an object")
        return errors
    name = sub.get("name")
    if not isinstance(name, str):
        errors.append(f"sub[{sid}] missing/invalid 'name'")
    link_ids = sub.get("link_ids", [])
    if not isinstance(link_ids, list):
        errors.append(f"sub[{sid}] 'link_ids' must be a list")
    elif not all(isinstance(x, str) for x in link_ids):
        errors.append(f"sub[{sid}] all link_ids must be strings")
    return errors


def _validate_node(nid: str, node: Any) -> list[str]:
    errors = []
    if not isinstance(nid, str):
        errors.append(f"node key must be a string: {nid!r}")
    if not isinstance(node, dict):
        errors.append(f"node[{nid}] must be an object")
        return errors
    name = node.get("name")
    if not isinstance(name, str):
        errors.append(f"node[{nid}] missing/invalid 'name'")
    endpoint = node.get("endpoint") or node.get("address")
    if endpoint is not None and not isinstance(endpoint, str):
        errors.append(f"node[{nid}] 'endpoint' must be a string")
    return errors


def validate_backup(data: Any) -> ValidationResult:
    """Top-level entry. Returns ValidationResult with ok=True iff valid."""
    result = ValidationResult(ok=False, data=None)
    if not isinstance(data, dict):
        result.errors.append("backup root must be an object")
        return result

    # Top-level fields
    if "links" in data:
        links = data["links"]
        if not isinstance(links, dict):
            result.errors.append("'links' must be an object")
        else:
            for uid, link in links.items():
                result.errors.extend(_validate_link(uid, link))
    else:
        # Missing 'links' is an error — a backup with no link data is meaningless
        # and almost certainly indicates a malformed export.
        result.errors.append("'links' is missing — backup contains no link configurations")

    if "subs" in data:
        subs = data["subs"]
        if not isinstance(subs, dict):
            result.errors.append("'subs' must be an object")
        else:
            for sid, sub in subs.items():
                result.errors.extend(_validate_sub(sid, sub))

    if "nodes" in data:
        nodes = data["nodes"]
        if not isinstance(nodes, dict):
            result.errors.append("'nodes' must be an object")
        else:
            for nid, node in nodes.items():
                result.errors.extend(_validate_node(nid, node))

    if "node_keys" in data:
        nk = data["node_keys"]
        if not isinstance(nk, dict):
            result.errors.append("'node_keys' must be an object")

    if "password_hash" in data:
        ph = data["password_hash"]
        if ph is not None and not isinstance(ph, str):
            result.errors.append("'password_hash' must be a string or null")
        elif isinstance(ph, str) and len(ph) > 0:
            # Reject anything that's not 64-char sha256 hex (backward compat
            # with load_state's existing guard).
            if not (len(ph) == 64 and all(c in "0123456789abcdef" for c in ph.lower())):
                result.warnings.append(
                    "'password_hash' is not sha256 hex format — will be ignored on import"
                )

    if "schema_version" in data:
        sv = data["schema_version"]
        if not isinstance(sv, int) or sv < 0:
            result.errors.append(f"'schema_version' must be a non-negative integer, got {sv!r}")

    # If any errors, return without setting ok
    if result.errors:
        return result

    result.ok = True
    result.data = data
    return result


def is_valid_backup(data: Any) -> bool:
    """Convenience: returns True iff the backup is valid."""
    return validate_backup(data).ok
