"""Domain models, keys, and exceptions for py-atv-remote."""

from py_atv_remote.domain.errors import (
    DomainError,
    InvalidPinError,
    PairingFailedError,
    PairingRequiredError,
    TvNotFoundError,
    TvUnreachableError,
)
from py_atv_remote.domain.keys import RemoteKey
from py_atv_remote.domain.models import (
    AppShortcut,
    ConnectionState,
    DiscoveredTv,
    TvProfile,
    VolumeState,
)

__all__ = [
    "AppShortcut",
    "ConnectionState",
    "DiscoveredTv",
    "DomainError",
    "InvalidPinError",
    "PairingFailedError",
    "PairingRequiredError",
    "RemoteKey",
    "TvNotFoundError",
    "TvProfile",
    "TvUnreachableError",
    "VolumeState",
]
