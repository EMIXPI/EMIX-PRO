# protocol_adapters/existing/mtproto.py — wraps protocol/mtproto/

import logging
from protocol_engine import (
    Capabilities, Transport, ProtocolStatus,
    register_protocol,
)
from protocol_engine.base import HealthResult, LinkResult
from ._base import ExistingAdapterBase

logger = logging.getLogger("EMIX.adapter.mtproto")


class MtprotoAdapter(ExistingAdapterBase):
    name = "mtproto"
    version = "1.0.0"
    description = "MTProto proxy via official Telegram mtg binary (per-instance)"

    def capabilities(self) -> Capabilities:
        return Capabilities(
            transports=(Transport.TCP,),
            supports_tcp=True, supports_tls=True,  # FakeTLS domain fronting
            supports_ipv4=True, supports_ipv6=False,
            supports_link_generation=True, supports_subscription=True,
            supports_health_check=True,
            supports_inbound=True, supports_outbound=True,
            supports_token_auth=True,  # MTProto secret-based auth
            status=ProtocolStatus.STABLE, maturity="stable",
        )

    def generate_link(self, params: dict) -> LinkResult:
        try:
            from main import generate_share_link, get_host
            uid = params.get("uuid") or params.get("uid")
            if not uid:
                return LinkResult(ok=False, error="uuid required")
            host = params.get("host") or get_host()
            remark = params.get("remark") or "EMIX-MTProto"
            link = generate_share_link(uid, host, remark=remark, protocol="mtproto")
            return LinkResult(ok=True, link=link, protocol="mtproto", qr_text=link)
        except Exception as exc:
            return LinkResult(ok=False, error=str(exc))

    async def health_check(self) -> HealthResult:
        """MTProto health = instance is running + public TCP proxy attached."""
        try:
            from main import LINKS, LINKS_LOCK
            async with LINKS_LOCK:
                candidates = [
                    (uid, d) for uid, d in LINKS.items()
                    if d.get("protocol") == "mtproto" and d.get("active", True)
                ]
            if not candidates:
                return HealthResult(ok=True, detail="no mtproto links")
            uid, link = candidates[0]
            # Check if instance is running
            from protocol.mtproto import mtproto_native as mtproto_mod
            instances = getattr(mtproto_mod, "_instances", {}) or {}
            running = uid in instances
            has_public = bool(link.get("mtproto_public_host") and link.get("mtproto_public_port"))
            ok = running and has_public
            return HealthResult(
                ok=ok,
                error=None if ok else ("instance not running" if not running else "no public TCP proxy"),
                detail=f"running={running} public_proxy={has_public}",
            )
        except Exception as exc:
            return HealthResult(ok=False, error=f"{type(exc).__name__}: {exc}")


register_protocol(MtprotoAdapter())
