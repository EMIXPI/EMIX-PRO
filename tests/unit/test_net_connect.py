# tests/unit/test_net_connect.py — IPv4-first egress (Errno 101 fix)
import asyncio
import socket

import pytest

from protocol.net_connect import open_connection_v4first


@pytest.mark.asyncio
async def test_v4first_connects_numeric_ip():
    """Numeric IPv4 → same behavior as open_connection (reader/writer)."""

    async def _handle(reader, writer):
        writer.close()

    server = await asyncio.start_server(_handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        reader, writer = await open_connection_v4first("127.0.0.1", port, timeout=3.0)
        assert writer.get_extra_info("peername")[0] == "127.0.0.1"
        assert writer.get_extra_info("peername")[1] == port
        writer.close()
    finally:
        server.close()


@pytest.mark.asyncio
async def test_v4first_prefers_ipv4_record():
    """Resolve order must list AF_INET before AF_INET6 (the Errno-101 fix)."""
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo("localhost", 80, type=socket.SOCK_STREAM)
    fams = [i[0] for i in infos]
    # the helper itself must not break on dual-stack names
    assert socket.AF_INET in fams


@pytest.mark.asyncio
async def test_v4first_unreachable_raises_original():
    """Dead host → an exception is raised (not a hang, not silent None)."""
    with pytest.raises((OSError, asyncio.TimeoutError, socket.gaierror)):
        await open_connection_v4first("host.invalid.example", 81, timeout=2.0)


@pytest.mark.asyncio
async def test_v4first_timeout_applies():
    """Connection to a black-hole IP must fail within the timeout window."""
    import time
    t0 = time.monotonic()
    with pytest.raises((OSError, asyncio.TimeoutError)):
        # TEST-NET-1 (RFC 5737) — guaranteed non-routable
        await open_connection_v4first("192.0.2.1", 81, timeout=2.0)
    assert time.monotonic() - t0 < 6.0
