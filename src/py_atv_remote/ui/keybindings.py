"""Keyboard shortcut mappings for the remote control built with PyQt6."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6 import QtCore, QtGui, QtWidgets

from py_atv_remote.domain.keys import RemoteKey

KEY_MAP: dict[int, RemoteKey] = {
    # Navigation
    QtCore.Qt.Key.Key_Up.value: RemoteKey.DPAD_UP,
    QtCore.Qt.Key.Key_Down.value: RemoteKey.DPAD_DOWN,
    QtCore.Qt.Key.Key_Left.value: RemoteKey.DPAD_LEFT,
    QtCore.Qt.Key.Key_Right.value: RemoteKey.DPAD_RIGHT,
    QtCore.Qt.Key.Key_Return.value: RemoteKey.DPAD_CENTER,
    QtCore.Qt.Key.Key_Enter.value: RemoteKey.DPAD_CENTER,
    # System
    QtCore.Qt.Key.Key_Escape.value: RemoteKey.BACK,
    QtCore.Qt.Key.Key_Backspace.value: RemoteKey.BACK,
    QtCore.Qt.Key.Key_Home.value: RemoteKey.HOME,
    QtCore.Qt.Key.Key_H.value: RemoteKey.HOME,
    QtCore.Qt.Key.Key_I.value: RemoteKey.TV_INPUT,
    QtCore.Qt.Key.Key_M.value: RemoteKey.MUTE,
    # Volume
    QtCore.Qt.Key.Key_Plus.value: RemoteKey.VOLUME_UP,
    QtCore.Qt.Key.Key_Equal.value: RemoteKey.VOLUME_UP,
    QtCore.Qt.Key.Key_Minus.value: RemoteKey.VOLUME_DOWN,
    # Media
    QtCore.Qt.Key.Key_Space.value: RemoteKey.MEDIA_PLAY_PAUSE,
    QtCore.Qt.Key.Key_J.value: RemoteKey.MEDIA_REWIND,
    QtCore.Qt.Key.Key_L.value: RemoteKey.MEDIA_FAST_FORWARD,
}

_MODIFIER_KEYS = (
    QtCore.Qt.KeyboardModifier.ControlModifier
    | QtCore.Qt.KeyboardModifier.AltModifier
    | QtCore.Qt.KeyboardModifier.MetaModifier
    | QtCore.Qt.KeyboardModifier.GroupSwitchModifier
)
_SHIFTABLE_KEYS = {
    QtCore.Qt.Key.Key_Plus.value,
    QtCore.Qt.Key.Key_Equal.value,
}


def handle_key_event(
    event: QtGui.QKeyEvent,
    window: QtWidgets.QWidget,
    on_key: Callable[[RemoteKey], None],
    is_enabled: Callable[[], bool],
    on_power: Callable[[], None] | None = None,
) -> bool:
    """Handle physical key press and dispatch matching RemoteKey."""
    focused = window.focusWidget()
    if isinstance(focused, QtWidgets.QLineEdit):
        if (
            event.key() == QtCore.Qt.Key.Key_Escape
            and not event.modifiers()
            and not event.isAutoRepeat()
        ):
            focused.clearFocus()
            return True
        return False

    key = event.key()
    modifiers = event.modifiers()
    if modifiers & _MODIFIER_KEYS:
        return False
    if modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier and key not in _SHIFTABLE_KEYS:
        return False

    # Power has its own async/Wake-on-LAN path and remains available while offline.
    if key == QtCore.Qt.Key.Key_P and on_power is not None:
        if not event.isAutoRepeat():
            on_power()
        return True

    if not is_enabled():
        return False

    remote_key = KEY_MAP.get(key)
    if remote_key:
        # Repeating navigation and volume is useful; repeated toggle commands are not.
        if not event.isAutoRepeat() or remote_key.is_repeatable:
            on_key(remote_key)
        return True

    return False
