"""Tests for domain models."""

from datetime import UTC, datetime

from py_atv_remote.domain.models import (
    AppShortcut,
    ConnectionState,
    DiscoveredTv,
    TvProfile,
    VolumeState,
)


def test_tv_profile_creation_and_mutations() -> None:
    now = datetime.now(UTC)
    profile = TvProfile(
        id="84c8a02b914c",
        name="TV da sala",
        host="192.168.2.104",
        paired_at=now,
    )
    assert profile.id == "84c8a02b914c"
    assert profile.name == "TV da sala"
    assert profile.host == "192.168.2.104"
    assert profile.api_port == 6466
    assert profile.pair_port == 6467
    assert profile.wol_mac is None

    updated_host = profile.with_host("192.168.2.150")
    assert updated_host.host == "192.168.2.150"
    assert updated_host.id == profile.id

    with_wol = profile.with_wol_mac("6a:5d:ac:20:7c:23")
    assert with_wol.wol_mac == "6a:5d:ac:20:7c:23"

    renamed = profile.with_name("Sala de Estar")
    assert renamed.name == "Sala de Estar"


def test_discovered_tv_model() -> None:
    discovered = DiscoveredTv(
        id="843e1d6b5e7d",
        name="TV do quarto",
        host="192.168.2.109",
        in_standby=False,
        source="mdns",
    )
    assert discovered.id == "843e1d6b5e7d"
    assert discovered.source == "mdns"
    assert discovered.in_standby is False


def test_volume_and_app_models() -> None:
    vol = VolumeState(level=15, max_level=60, muted=False)
    assert vol.level == 15
    assert not vol.muted

    shortcut = AppShortcut(label="YouTube", link="https://www.youtube.com")
    assert shortcut.label == "YouTube"

    assert ConnectionState.CONNECTED == "connected"
