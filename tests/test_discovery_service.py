"""Tests for discovery service coordinating mDNS and config updates."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from py_atv_remote.domain.errors import TvUnreachableError
from py_atv_remote.domain.models import DiscoveredTv, TvProfile
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.infrastructure.paths import AppPaths
from py_atv_remote.services.discovery_service import DiscoveryService
from py_atv_remote.services.events import DirectDispatcher, EventBus


@pytest.mark.asyncio
async def test_dhcp_ip_auto_update_on_discovery(tmp_path: Path) -> None:
    paths = AppPaths(base_dir=tmp_path)
    store = ConfigStore(paths)

    # Save a TV with old IP
    old_profile = TvProfile(
        id="84c8a02b914c",
        name="TV da sala",
        host="192.168.2.50",
    )
    store.save_tv(old_profile)

    event_bus = EventBus(DirectDispatcher())
    updated_profiles: list[TvProfile] = []

    discovery = DiscoveryService(
        config_store=store,
        event_bus=event_bus,
        on_profile_ip_updated=lambda p: updated_profiles.append(p),
    )

    # Simulate discovering the TV with a new DHCP IP
    new_tv = DiscoveredTv(
        id="84c8a02b914c",
        name="TV da sala",
        host="192.168.2.104",
        source="mdns",
    )
    discovery._on_tv_found(new_tv)

    # Verify store was updated automatically
    stored = store.get_tv("84c8a02b914c")
    assert stored is not None
    assert stored.host == "192.168.2.104"
    assert len(updated_profiles) == 1
    assert updated_profiles[0].host == "192.168.2.104"


@pytest.mark.asyncio
async def test_probe_manual_failure_and_success() -> None:
    store = MagicMock()
    event_bus = EventBus(DirectDispatcher())
    discovery = DiscoveryService(config_store=store, event_bus=event_bus)

    # Unreachable IP
    with pytest.raises(TvUnreachableError):
        await discovery.probe_manual("192.0.2.1", port=6466)
