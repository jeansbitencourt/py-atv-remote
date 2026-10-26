"""mDNS discovery for Android TV Remote V2 services using zeroconf."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

from py_atv_remote.domain.models import DiscoveredTv

LOGGER = logging.getLogger(__name__)

SERVICE_TYPE = "_androidtvremote2._tcp.local."


def normalize_mac_or_id(raw_id: str | bytes | None) -> str | None:
    """Normalize a MAC or ID string to lower-case alphanumeric without separators."""
    if raw_id is None:
        return None
    if isinstance(raw_id, bytes):
        try:
            val = raw_id.decode("utf-8")
        except UnicodeDecodeError:
            val = raw_id.hex()
    else:
        val = raw_id
    clean = "".join(c for c in val.lower() if c.isalnum())
    return clean if clean else None


def parse_service_info(name: str, info: AsyncServiceInfo) -> DiscoveredTv | None:
    """Parse an AsyncServiceInfo into a DiscoveredTv domain model."""
    addresses = info.parsed_addresses()
    if not addresses:
        return None

    # Prefer IPv4 address
    ipv4_addrs = [addr for addr in addresses if ":" not in addr]
    host = ipv4_addrs[0] if ipv4_addrs else addresses[0]

    # Clean display name from service record
    display_name = name
    if display_name.endswith(f".{SERVICE_TYPE}"):
        display_name = display_name[: -len(f".{SERVICE_TYPE}")]
    display_name = display_name.replace(r"\.", ".")

    # Parse properties (bt mac and standby mode)
    props = info.properties or {}
    raw_bt = props.get(b"bt")
    tv_id = normalize_mac_or_id(raw_bt)

    raw_standby = props.get(b"isDeviceInStandbyMode")
    in_standby: bool | None = None
    if raw_standby is not None:
        val_str = (
            raw_standby.decode("utf-8", errors="ignore").strip().lower()
            if isinstance(raw_standby, bytes)
            else str(raw_standby).strip().lower()
        )
        in_standby = val_str == "true"

    return DiscoveredTv(
        id=tv_id,
        name=display_name,
        host=host,
        port=info.port or 6466,
        in_standby=in_standby,
        source="mdns",
    )


class MdnsBrowser:
    """Asynchronously browses local mDNS for Android TV Remote V2 services."""

    def __init__(
        self,
        on_tv_found: Callable[[DiscoveredTv], None],
        on_tv_lost: Callable[[str], None],
    ) -> None:
        self._on_tv_found = on_tv_found
        self._on_tv_lost = on_tv_lost
        self._zeroconf: AsyncZeroconf | None = None
        self._browser: AsyncServiceBrowser | None = None
        self._owns_zeroconf = False
        self._lock = asyncio.Lock()
        self._known_services: dict[str, DiscoveredTv] = {}
        self._background_tasks: set[asyncio.Task[None]] = set()

    @property
    def zeroconf(self) -> AsyncZeroconf | None:
        """Return the active AsyncZeroconf instance if running."""
        return self._zeroconf

    async def start(self, zeroconf: AsyncZeroconf | None = None) -> None:
        """Start browsing for mDNS services."""
        async with self._lock:
            if self._browser is not None:
                return

            if zeroconf is not None:
                self._zeroconf = zeroconf
                self._owns_zeroconf = False
            else:
                self._zeroconf = AsyncZeroconf()
                self._owns_zeroconf = True

            self._browser = AsyncServiceBrowser(
                self._zeroconf.zeroconf,
                SERVICE_TYPE,
                handlers=[self._on_service_state_change],
            )
            LOGGER.info("Started mDNS service browser for %s", SERVICE_TYPE)

    def _on_service_state_change(
        self,
        zeroconf: Any,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        """Callback from zeroconf ServiceBrowser."""
        if self._zeroconf is None:
            return

        task = asyncio.create_task(self._handle_service_change(service_type, name, state_change))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _handle_service_change(
        self,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        if self._zeroconf is None:
            return

        if state_change in (ServiceStateChange.Added, ServiceStateChange.Updated):
            info = AsyncServiceInfo(service_type, name)
            if await info.async_request(self._zeroconf.zeroconf, 3000):
                tv = parse_service_info(name, info)
                if tv is not None:
                    self._known_services[name] = tv
                    LOGGER.info("Discovered TV via mDNS: %s (%s at %s)", tv.name, tv.id, tv.host)
                    self._on_tv_found(tv)
        elif state_change == ServiceStateChange.Removed:
            removed = self._known_services.pop(name, None)
            if removed and removed.id:
                LOGGER.info("Lost TV via mDNS: %s (%s)", removed.name, removed.id)
                self._on_tv_lost(removed.id)

    async def close(self) -> None:
        """Stop browser and release resources."""
        async with self._lock:
            if self._background_tasks:
                for task in self._background_tasks:
                    task.cancel()
                self._background_tasks.clear()

            if self._browser is not None:
                await self._browser.async_cancel()
                self._browser = None

            if self._zeroconf is not None and self._owns_zeroconf:
                await self._zeroconf.async_close()
                self._zeroconf = None

            self._known_services.clear()
            LOGGER.info("Closed mDNS service browser.")
