# protocol_adapters/existing/__init__.py — register all existing-protocol adapters
#
# Each adapter module wraps the corresponding production implementation in
# protocol/* (or main.py). The adapter exposes the ProtocolAdapter interface
# but delegates to the existing code — NO wire-level changes.

from protocol_engine import get_registry

from . import vless_ws       # noqa: F401
from . import vless_xhttp   # noqa: F401
from . import trojan_ws     # noqa: F401
from . import trojan_xhttp  # noqa: F401
from . import shadowsocks   # noqa: F401
from . import mtproto       # noqa: F401
from . import http_proxy    # noqa: F401
from . import zeus_socks5   # noqa: F401

_logger = __import__("logging").getLogger("EMIX.protocol_adapters.existing")
_logger.info(
    f"[existing-adapters] registered {len(get_registry().list_protocol_names())} protocols"
)
