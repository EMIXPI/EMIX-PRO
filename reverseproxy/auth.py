# reverseproxy/auth.py — HMAC origin authentication (Phase 39)
#
# Verifies that requests reaching EMIX came through a trusted edge (Cloudflare
# Worker, ArvanCloud) by checking an HMAC-SHA256 signature.
#
# Flow:
#   1. Edge (worker) computes:  HMAC(secret, body + timestamp + path + method)
#   2. Edge sends headers: X-EMIX-Origin-Signature=<hex> + X-EMIX-Origin-Timestamp=<epoch>
#   3. EMIX recomputes HMAC and compares with hmac.compare_digest (constant time)
#   4. EMIX checks timestamp is within EMIX_ORIGIN_AUTH_REPLAY_WINDOW seconds (replay protection)
#
# If verification fails: 401 + log (no information leakage in the error message).
#
# NEVER log the secret. NEVER expose the secret to frontend code.

import hmac
import hashlib
import time
import logging
from typing import Optional
from .config import get_proxy_config

logger = logging.getLogger("EMIX.reverseproxy.auth")

HMAC_ORIGIN_HEADER = "X-EMIX-Origin-Signature"
HMAC_TIMESTAMP_HEADER = "X-EMIX-Origin-Timestamp"
DEFAULT_REPLAY_WINDOW_SECONDS = 60  # ±60s


def _compute_signature(secret: str, method: str, path: str, body: bytes, timestamp: int) -> str:
    """Compute HMAC-SHA256(secret, method + path + timestamp + body)."""
    msg = f"{method.upper()}|{path}|{timestamp}|".encode() + (body or b"")
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def build_origin_signature(secret: str, method: str, path: str, body: bytes) -> tuple[str, int]:
    """Build a signature + timestamp pair (for the edge side to call).
    Returns (signature_hex, timestamp_epoch)."""
    ts = int(time.time())
    sig = _compute_signature(secret, method, path, body, ts)
    return sig, ts


def verify_origin_signature(
    method: str,
    path: str,
    body: bytes,
    incoming_signature: Optional[str],
    incoming_timestamp: Optional[str],
    replay_window_seconds: int = DEFAULT_REPLAY_WINDOW_SECONDS,
) -> tuple[bool, Optional[str]]:
    """Verify an incoming edge signature.
    Returns (ok, error_message). error_message is None on success.
    """
    cfg = get_proxy_config()
    if not cfg.origin_auth_enabled:
        # Origin auth not configured — feature is off. Return ok=True so the panel works.
        return True, None
    if not incoming_signature or not incoming_timestamp:
        return False, "missing origin signature headers"
    secret = cfg.origin_auth_secret
    if not secret:
        return False, "no secret configured (cannot verify)"
    # Parse timestamp (epoch seconds, integer)
    try:
        ts = int(incoming_timestamp)
    except (TypeError, ValueError):
        return False, "invalid timestamp format"
    # Replay window check
    now = int(time.time())
    if abs(now - ts) > replay_window_seconds:
        return False, "timestamp outside replay window"
    # Compute expected signature
    expected = _compute_signature(secret, method, path, body, ts)
    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(expected, incoming_signature):
        return False, "signature mismatch"
    return True, None
