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
async def test_v4first_timeout_applies(monkeypatch):
    """Connection to a black-hole target must fail within the timeout window.

    FIX v12: قبلاً به TEST-NET-1 (192.0.2.1) وصل می‌شد که رفتارش وابسته به
    شبکه‌ی محیط اجراست (بعضی sandbox ها/VPN ها بلافاصله accept می‌کنند).
    الان بخش شبکه‌ی واقعی mock می‌شود: open_connection تا ابد hang می‌کند —
    فقط و فقط if wait_for(timeout) کار کند، TimeoutError برمی‌گردد."""
    import time as _time
    from protocol import net_connect

    async def _hang(*a, **kw):
        await asyncio.sleep(3600)

    async def _no_resolve(*a, **kw):
        # getaddrinfo واقعی صدا زده نشود؛ مسیر numeric-IP شبیه‌سازی می‌شود
        raise OSError("resolve disabled in test")

    monkeypatch.setattr(net_connect.asyncio, "open_connection", _hang)
    monkeypatch.setattr(net_connect.asyncio, "get_running_loop",
                        lambda: type("L", (), {"getaddrinfo": staticmethod(_no_resolve)})())
    t0 = _time.monotonic()
    with pytest.raises((OSError, asyncio.TimeoutError)):
        await net_connect.open_connection_v4first("203.0.113.7", 81, timeout=2.0)
    assert _time.monotonic() - t0 < 6.0
