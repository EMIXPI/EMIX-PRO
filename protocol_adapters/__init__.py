# protocol_adapters/__init__.py — adapter registration
#
# Adapter modules under protocol_adapters/existing/ wrap the CURRENT production
# protocol implementations. They expose the ProtocolAdapter interface but
# delegate to the existing code paths — NO wire-level changes.
#
# Adapter modules under protocol_adapters/ for new protocols (vmess, reality,
# hysteria2, etc.) are either real (link-emission only) or DEFERRED with
# documentation explaining what's missing.

from . import existing  # noqa: F401 — registers all existing-protocol adapters

# Optional/new protocol adapters are imported individually to keep
# startup failures isolated. A broken optional adapter must NOT prevent
# EMIX from starting.

import logging
_logger = logging.getLogger("EMIX.protocol_adapters")

def _safe_import(modname: str) -> bool:
    """Import an adapter module, swallow errors."""
    try:
        __import__(f"protocol_adapters.{modname}", globals(), locals(), [], 0)
        return True
    except Exception as exc:
        _logger.warning(f"[adapters] failed to load {modname}: {type(exc).__name__}: {exc}")
        return False

# Link-emission-only adapters (safe — they use existing link_emit.py)
_safe_import("vmess")
_safe_import("vless_reality")
_safe_import("ss2022")

# DEFERRED adapters (placeholder + documentation, no real implementation)
_safe_import("hysteria2")
_safe_import("tuic")
_safe_import("wireguard")
_safe_import("naiveproxy")
_safe_import("openvpn")

# EXPERIMENTAL adapters (capability detection + safe stubs)
_safe_import("ssh")
_safe_import("grpc_transport")
_safe_import("httpupgrade")
