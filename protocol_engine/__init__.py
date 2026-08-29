# protocol_engine/__init__.py — public API for the EMIX protocol engine
#
# Public API:
#   from protocol_engine import (
#       ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
#       register_protocol, get_protocol, list_protocols,
#       get_enabled_protocols, get_protocol_capabilities,
#       select_best, rank_protocols, run_with_fallback,
#       get_metrics, get_health, all_health,
#       list_profiles, get_profile,
#   )

from .base import (
    ProtocolAdapter,
    HealthResult,
    LinkResult,
    AdapterStatus,
)
from .capabilities import Capabilities, Transport, ProtocolStatus
from .registry import (
    ProtocolRegistry,
    get_registry,
    register_protocol,
    unregister_protocol,
    get_protocol,
    list_protocols,
    list_protocol_names,
    get_enabled_protocols,
    get_protocol_capabilities,
)
from .health import RollingHealth, get_health, all_health
from .metrics import MetricsCollector, get_metrics
from .selector import (
    SelectorWeights,
    score_protocol,
    select_best,
    rank_protocols,
    get_profile,
    list_profiles,
)
from .fallback import run_with_fallback, FallbackResult

__all__ = [
    "ProtocolAdapter", "HealthResult", "LinkResult", "AdapterStatus",
    "Capabilities", "Transport", "ProtocolStatus",
    "ProtocolRegistry", "get_registry",
    "register_protocol", "unregister_protocol",
    "get_protocol", "list_protocols", "list_protocol_names",
    "get_enabled_protocols", "get_protocol_capabilities",
    "RollingHealth", "get_health", "all_health",
    "MetricsCollector", "get_metrics",
    "SelectorWeights", "score_protocol", "select_best", "rank_protocols",
    "get_profile", "list_profiles",
    "run_with_fallback", "FallbackResult",
]
