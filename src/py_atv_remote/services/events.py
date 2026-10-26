"""Typed event bus and dispatcher protocol for cross-thread event delivery."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

from py_atv_remote.domain.models import (
    ConnectionState,
    DiscoveredTv,
    TvProfile,
    VolumeState,
)

LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class Dispatcher(Protocol):
    """Protocol for posting callbacks to the main/UI thread."""

    def post(self, fn: Callable[[], None]) -> None:
        """Post a function to be executed on the UI thread."""
        ...


class DirectDispatcher:
    """Direct dispatcher executing callbacks synchronously (for headless use and unit tests)."""

    def post(self, fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception:
            LOGGER.exception("Unhandled error executing dispatched callback directly")


# Listener Signatures
StateListener = Callable[[ConnectionState, TvProfile | None], None]
VolumeListener = Callable[[VolumeState], None]
CurrentAppListener = Callable[[str], None]
IsOnListener = Callable[[bool], None]
TvDiscoveredListener = Callable[[DiscoveredTv], None]
TvDisappearedListener = Callable[[str], None]
ErrorListener = Callable[[str, Exception | None], None]


class EventBus:
    """Publishes domain events and dispatches notifications to listeners via a Dispatcher."""

    def __init__(self, dispatcher: Dispatcher | None = None) -> None:
        self._dispatcher = dispatcher or DirectDispatcher()
        self._state_listeners: list[StateListener] = []
        self._volume_listeners: list[VolumeListener] = []
        self._app_listeners: list[CurrentAppListener] = []
        self._is_on_listeners: list[IsOnListener] = []
        self._tv_discovered_listeners: list[TvDiscoveredListener] = []
        self._tv_disappeared_listeners: list[TvDisappearedListener] = []
        self._error_listeners: list[ErrorListener] = []

    def set_dispatcher(self, dispatcher: Dispatcher) -> None:
        """Update or set the UI thread dispatcher."""
        self._dispatcher = dispatcher

    # Subscription methods

    def on_state(self, listener: StateListener) -> Callable[[], None]:
        """Subscribe to connection state changes."""
        self._state_listeners.append(listener)
        return lambda: self._remove(self._state_listeners, listener)

    def on_volume(self, listener: VolumeListener) -> Callable[[], None]:
        """Subscribe to volume changes."""
        self._volume_listeners.append(listener)
        return lambda: self._remove(self._volume_listeners, listener)

    def on_current_app(self, listener: CurrentAppListener) -> Callable[[], None]:
        """Subscribe to foreground app changes."""
        self._app_listeners.append(listener)
        return lambda: self._remove(self._app_listeners, listener)

    def on_is_on(self, listener: IsOnListener) -> Callable[[], None]:
        """Subscribe to TV power status updates."""
        self._is_on_listeners.append(listener)
        return lambda: self._remove(self._is_on_listeners, listener)

    def on_tv_discovered(self, listener: TvDiscoveredListener) -> Callable[[], None]:
        """Subscribe to discovered TV events."""
        self._tv_discovered_listeners.append(listener)
        return lambda: self._remove(self._tv_discovered_listeners, listener)

    def on_tv_disappeared(self, listener: TvDisappearedListener) -> Callable[[], None]:
        """Subscribe to disappeared TV events."""
        self._tv_disappeared_listeners.append(listener)
        return lambda: self._remove(self._tv_disappeared_listeners, listener)

    def on_error(self, listener: ErrorListener) -> Callable[[], None]:
        """Subscribe to application error notifications."""
        self._error_listeners.append(listener)
        return lambda: self._remove(self._error_listeners, listener)

    # Publishing methods (invoked from any thread, dispatched to UI thread)

    def emit_state(self, state: ConnectionState, profile: TvProfile | None) -> None:
        listeners = list(self._state_listeners)
        self._dispatcher.post(lambda: self._invoke_all(listeners, state, profile))

    def emit_volume(self, volume: VolumeState) -> None:
        listeners = list(self._volume_listeners)
        self._dispatcher.post(lambda: self._invoke_all(listeners, volume))

    def emit_current_app(self, app_id: str) -> None:
        listeners = list(self._app_listeners)
        self._dispatcher.post(lambda: self._invoke_all(listeners, app_id))

    def emit_is_on(self, is_on: bool) -> None:
        listeners = list(self._is_on_listeners)
        self._dispatcher.post(lambda: self._invoke_all(listeners, is_on))

    def emit_tv_discovered(self, tv: DiscoveredTv) -> None:
        listeners = list(self._tv_discovered_listeners)
        self._dispatcher.post(lambda: self._invoke_all(listeners, tv))

    def emit_tv_disappeared(self, tv_id: str) -> None:
        listeners = list(self._tv_disappeared_listeners)
        self._dispatcher.post(lambda: self._invoke_all(listeners, tv_id))

    def emit_error(self, message: str, exc: Exception | None = None) -> None:
        listeners = list(self._error_listeners)
        self._dispatcher.post(lambda: self._invoke_all(listeners, message, exc))

    @staticmethod
    def _invoke_all(listeners: list[Callable[..., None]], *args: Any) -> None:
        for listener in listeners:
            try:
                listener(*args)
            except Exception:
                LOGGER.exception("Error executing event listener callback")

    @staticmethod
    def _remove(listeners: list[Any], target: Any) -> None:
        if target in listeners:
            listeners.remove(target)
