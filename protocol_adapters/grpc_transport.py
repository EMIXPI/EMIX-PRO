# protocol_adapters/grpc_transport.py — EXPERIMENTAL adapter for gRPC transport
#
# STATUS: EXPERIMENTAL
#
# What this adapter does today:
#   - Reports capabilities (gRPC transport via HTTP/2)
#   - Honest note: existing XHTTP transport already mimics gRPC by setting
#     `Content-Type: application/grpc` for HTTP/2 framing. This is NOT real
#     gRPC (which uses Protocol Buffers + grpc-go/grpc-python on both sides).
#   - Real gRPC transport would require a separate inbound server that
#     speaks the actual gRPC protocol — currently out of scope.
#
# Path to enable: add grpcio + grpcio-tools to requirements.txt, implement
# a gRPC server that wraps the existing relay logic.
#
# This adapter does NOT claim to be production gRPC. It is EXPERIMENTAL.

import logging
from protocol_engine import (
    ProtocolAdapter, Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult

logger = logging.getLogger("EMIX.adapter.grpc_transport")


def _grpc_available() -> bool:
    try:
        import grpc  # noqa: F401
        return True
    except ImportError:
        return False


class GrpcTransportAdapter(ProtocolAdapter):
    name = "grpc"
    version = "0.1.0"
    description = (
        "gRPC transport. EXPERIMENTAL — existing XHTTP already mimics gRPC "
        "wire envelope (Content-Type: application/grpc) but is not real gRPC. "
        "Real gRPC needs grpcio + grpcio-tools."
    )

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.GRPC,),
            supports_tcp=True,
            supports_tls=True,
            supports_http2=True,
            supports_grpc=True,  # advertised; real implementation is EXPERIMENTAL
            supports_multiplexing=True,
            supports_ipv4=True,
            supports_ipv6=False,
            supports_link_generation=False,  # gRPC has no standard share-link
            supports_health_check=False,
            supports_inbound=False,  # XHTTP already covers the inbound path
            supports_outbound=False,
            status=ProtocolStatus.EXPERIMENTAL,
            maturity="experimental",
        )

    def validate_config(self, config: dict) -> tuple[bool, list[str]]:
        errors = []
        if not config.get("service_name"):
            errors.append("service_name is required (e.g. 'vless.Service')")
        if not config.get("authority"):
            errors.append("authority (SNI) is required")
        return (len(errors) == 0), errors

    def configure(self, config: dict) -> None:
        pass

    def generate_link(self, params: dict) -> LinkResult:
        return LinkResult(
            ok=False,
            error="gRPC has no standard share-link format; use VLESS+gRPC transport params",
        )

    async def health_check(self) -> HealthResult:
        # Phase 37 honest-gap fix: this adapter has NO runtime to probe — the
        # previous `ok=True` was a fake-healthy result (the only one in the
        # codebase). Envelope mimicry inside XHTTP is not gRPC health.
        return HealthResult(
            ok=False,
            detail="NOT_TESTABLE — no gRPC server runtime; XHTTP only mimics "
                   "the gRPC envelope (content-type), which is not probeable "
                   "as a transport",
        )

    async def start(self) -> bool:
        return False

    async def stop(self) -> bool:
        return False


register_protocol(GrpcTransportAdapter())
