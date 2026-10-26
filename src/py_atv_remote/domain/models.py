"""Domain models for py-atv-remote."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal


class ConnectionState(StrEnum):
    """Connection states for the active remote session."""

    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    OFFLINE = "offline"
    NEEDS_PAIRING = "needs_pairing"


@dataclass(frozen=True, slots=True)
class VolumeState:
    """Volume information for a connected TV."""

    level: int
    max_level: int
    muted: bool


@dataclass(frozen=True, slots=True)
class AppShortcut:
    """A user-configurable shortcut to launch an application on the TV."""

    label: str
    link: str


@dataclass(frozen=True, slots=True)
class TvProfile:
    """Persistent profile for a configured and paired Android TV."""

    id: str  # Normalized hex identifier (e.g. from cert MAC or bt property)
    name: str  # User-friendly name
    host: str  # Current IPv4 address or hostname
    api_port: int = 6466
    pair_port: int = 6467
    model: str | None = None
    wol_mac: str | None = None  # Learned network MAC address for Wake-on-LAN
    paired_at: datetime | None = None

    def with_host(self, new_host: str) -> TvProfile:
        """Return a copy of the profile with an updated IP address."""
        return TvProfile(
            id=self.id,
            name=self.name,
            host=new_host,
            api_port=self.api_port,
            pair_port=self.pair_port,
            model=self.model,
            wol_mac=self.wol_mac,
            paired_at=self.paired_at,
        )

    def with_wol_mac(self, wol_mac: str) -> TvProfile:
        """Return a copy of the profile with an updated WoL MAC address."""
        return TvProfile(
            id=self.id,
            name=self.name,
            host=self.host,
            api_port=self.api_port,
            pair_port=self.pair_port,
            model=self.model,
            wol_mac=wol_mac,
            paired_at=self.paired_at,
        )

    def with_name(self, new_name: str) -> TvProfile:
        """Return a copy of the profile with an updated name."""
        return TvProfile(
            id=self.id,
            name=new_name,
            host=self.host,
            api_port=self.api_port,
            pair_port=self.pair_port,
            model=self.model,
            wol_mac=self.wol_mac,
            paired_at=self.paired_at,
        )


@dataclass(frozen=True, slots=True)
class DiscoveredTv:
    """A TV found during mDNS discovery or TCP subnet scan."""

    id: str | None  # Hex identifier if known (from mDNS 'bt' or TLS handshake)
    name: str  # Reported name or fallback label
    host: str  # IP address
    port: int = 6466
    in_standby: bool | None = None
    source: Literal["mdns", "scan", "manual"] = "mdns"
