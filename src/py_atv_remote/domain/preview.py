"""Values and errors for optional ADB screen preview."""

from dataclasses import dataclass
from enum import StrEnum

from py_atv_remote.domain.errors import DomainError


class PreviewError(DomainError):
    """An actionable preview failure."""


class PreviewState(StrEnum):
    CLOSED = "closed"
    PREPARING = "preparing"
    RUNNING = "running"
    ERROR = "error"


QUALITY_PRESETS: dict[str, tuple[int, int, str]] = {
    "economic": (640, 10, "1M"),
    "balanced": (960, 15, "2M"),
    "high": (1280, 30, "4M"),
}


@dataclass(frozen=True, slots=True)
class AdbIdentity:
    serial: str
    model: str


@dataclass(frozen=True, slots=True)
class PreviewSettings:
    enabled: bool = False
    endpoint: str = ""
    mode: str = "wireless_tls"
    identity: str = ""
    quality: str = "balanced"


@dataclass(frozen=True, slots=True)
class PreviewEvent:
    tv_id: str
    state: PreviewState
    message: str = ""
