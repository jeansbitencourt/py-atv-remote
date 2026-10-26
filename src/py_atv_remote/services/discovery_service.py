"""High-level discovery service coordinating mDNS, subnet scanning, and config synchronization."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from py_atv_remote.domain.errors import TvUnreachableError
from py_atv_remote.domain.models import DiscoveredTv, TvProfile
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.infrastructure.mdns_browser import MdnsBrowser
from py_atv_remote.infrastructure.subnet_scanner import SubnetScanner, check_port_open
from py_atv_remote.services.events import EventBus

LOGGER = logging.getLogger(__name__)


class DiscoveryService:
    """Discovers TVs on the local network and synchronizes IP changes with saved profiles."""

    def __init__(
        self,
        config_store: ConfigStore,
        event_bus: EventBus,
        mdns_browser: MdnsBrowser | None = None,
        subnet_scanner: SubnetScanner | None = None,
        on_profile_ip_updated: Callable[[TvProfile], None] | None = None,
    ) -> None:
        self._config_store = config_store
        self._event_bus = event_bus
        self._on_profile_ip_updated = on_profile_ip_updated
        self._discovered: dict[str, DiscoveredTv] = {}  # Key: id or host
        self._lock = asyncio.Lock()

        self._mdns = mdns_browser or MdnsBrowser(
            on_tv_found=self._on_tv_found,
            on_tv_lost=self._on_tv_lost,
        )
        self._scanner = subnet_scanner or SubnetScanner()

    @property
    def discovered_tvs(self) -> list[DiscoveredTv]:
        """Return a snapshot of currently discovered TVs."""
        return list(self._discovered.values())

    async def start(self) -> None:
        """Start background mDNS service browsing."""
        await self._mdns.start()

    async def stop(self) -> None:
        """Stop discovery and cleanup background resources."""
        await self._mdns.close()
        async with self._lock:
            self._discovered.clear()

    def _on_tv_found(self, tv: DiscoveredTv) -> None:
        """Handle a TV discovered via mDNS or subnet scan."""
        key = tv.id or tv.host
        self._discovered[key] = tv

        # Check if this TV corresponds to a saved profile
        if tv.id:
            profile = self._config_store.get_tv(tv.id)
            if profile is not None and profile.host != tv.host:
                LOGGER.info(
                    "Dynamic DHCP update for '%s' (%s): IP changed from %s to %s",
                    profile.name,
                    profile.id,
                    profile.host,
                    tv.host,
                )
                updated_profile = profile.with_host(tv.host)
                self._config_store.save_tv(updated_profile)
                if self._on_profile_ip_updated:
                    self._on_profile_ip_updated(updated_profile)

        self._event_bus.emit_tv_discovered(tv)

    def _on_tv_lost(self, tv_id: str) -> None:
        """Handle a TV disappearing from mDNS."""
        self._discovered.pop(tv_id, None)
        self._event_bus.emit_tv_disappeared(tv_id)

    async def full_scan(self) -> list[DiscoveredTv]:
        """Perform a full network scan (mDNS + subnet scan fallback)."""
        scan_results = await self._scanner.scan_subnets()

        async with self._lock:
            # Merge: If an IP was already discovered via mDNS with name/id, retain the richer info
            existing_ips = {tv.host: tv for tv in self._discovered.values()}

            for item in scan_results:
                if item.host not in existing_ips:
                    self._discovered[item.host] = item
                    self._event_bus.emit_tv_discovered(item)

            return list(self._discovered.values())

    async def probe_manual(self, host: str, port: int = 6466) -> DiscoveredTv:
        """Probe an explicit IP address entered manually by the user."""
        is_open = await check_port_open(host, port, timeout=1.5)
        if not is_open:
            raise TvUnreachableError(f"No Android TV Remote service responding at {host}:{port}")

        tv = DiscoveredTv(
            id=None,
            name=f"Android TV ({host})",
            host=host,
            port=port,
            source="manual",
        )
        self._on_tv_found(tv)
        return tv
