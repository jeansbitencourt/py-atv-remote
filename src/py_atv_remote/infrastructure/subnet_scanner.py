"""Fallback subnet scanner for environments where mDNS multicast is blocked."""

from __future__ import annotations

import asyncio
import ipaddress
import logging

import ifaddr

from py_atv_remote.domain.models import DiscoveredTv

LOGGER = logging.getLogger(__name__)

DEFAULT_API_PORT = 6466
CONNECT_TIMEOUT = 0.4
MAX_CONCURRENT_PROBES = 100


def get_local_ipv4_networks() -> list[ipaddress.IPv4Network]:
    """Inspect system network adapters and return non-loopback IPv4 networks."""
    networks: list[ipaddress.IPv4Network] = []
    try:
        adapters = ifaddr.get_adapters()
    except Exception as exc:
        LOGGER.warning("Could not enumerate network adapters: %s", exc)
        return networks

    for adapter in adapters:
        for if_ip in adapter.ips:
            if not isinstance(if_ip.ip, str):
                continue
            try:
                ip_obj = ipaddress.IPv4Address(if_ip.ip)
                if ip_obj.is_loopback or ip_obj.is_link_local:
                    continue
                prefix = if_ip.network_prefix
                if prefix is None or prefix < 22 or prefix > 30:
                    # Avoid scanning networks larger than /22 to prevent performance issues
                    continue
                net = ipaddress.IPv4Network(f"{if_ip.ip}/{prefix}", strict=False)
                if net not in networks:
                    networks.append(net)
            except (ValueError, ipaddress.AddressValueError):
                continue

    return networks


async def check_port_open(host: str, port: int, timeout: float = CONNECT_TIMEOUT) -> bool:
    """Check if a TCP port is open at the specified host."""
    try:
        conn = asyncio.open_connection(host, port)
        _reader, writer = await asyncio.wait_for(conn, timeout=timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, TimeoutError):
        return False


class SubnetScanner:
    """Scans local subnets for devices listening on Google TV Remote V2 port (6466)."""

    def __init__(
        self,
        port: int = DEFAULT_API_PORT,
        concurrency: int = MAX_CONCURRENT_PROBES,
    ) -> None:
        self._port = port
        self._semaphore = asyncio.Semaphore(concurrency)

    async def scan_hosts(
        self,
        hosts: list[str],
        timeout: float = CONNECT_TIMEOUT,
    ) -> list[str]:
        """Scan a list of IP addresses concurrently for an open port."""
        results: list[str] = []

        async def _probe(host: str) -> None:
            async with self._semaphore:
                if await check_port_open(host, self._port, timeout=timeout):
                    results.append(host)

        tasks = [asyncio.create_task(_probe(h)) for h in hosts]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return sorted(results)

    async def scan_subnets(
        self,
        networks: list[ipaddress.IPv4Network] | None = None,
        timeout: float = CONNECT_TIMEOUT,
    ) -> list[DiscoveredTv]:
        """Scan all local subnets or provided networks and return discovered TVs."""
        target_networks = networks if networks is not None else get_local_ipv4_networks()
        all_hosts: list[str] = []
        for net in target_networks:
            all_hosts.extend(str(h) for h in net.hosts())

        LOGGER.info(
            "Scanning %d hosts across %d subnets for port %d...",
            len(all_hosts),
            len(target_networks),
            self._port,
        )
        open_ips = await self.scan_hosts(all_hosts, timeout=timeout)
        LOGGER.info(
            "Subnet scan finished. Found %d hosts with port %d open.",
            len(open_ips),
            self._port,
        )

        discovered = [
            DiscoveredTv(
                id=None,
                name=f"Android TV ({ip})",
                host=ip,
                port=self._port,
                in_standby=None,
                source="scan",
            )
            for ip in open_ips
        ]
        return discovered
