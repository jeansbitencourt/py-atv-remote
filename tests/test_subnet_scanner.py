"""Tests for subnet scanner fallback."""

import asyncio

import pytest

from py_atv_remote.infrastructure.subnet_scanner import SubnetScanner, check_port_open


@pytest.mark.asyncio
async def test_check_port_open_and_scanner() -> None:
    # Start an ephemeral TCP server
    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    try:
        # Check that check_port_open detects it
        assert await check_port_open("127.0.0.1", port, timeout=0.5) is True
        # Check closed port
        assert await check_port_open("127.0.0.1", port + 1, timeout=0.1) is False

        scanner = SubnetScanner(port=port)
        found = await scanner.scan_hosts(["127.0.0.1", "127.0.0.2"], timeout=0.5)
        assert "127.0.0.1" in found
    finally:
        server.close()
        await server.wait_closed()
