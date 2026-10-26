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
    # Volume
    QtCore.Qt.Key.Key_Plus.value: RemoteKey.VOLUME_UP,
    QtCore.Qt.Key.Key_Equal.value: RemoteKey.VOLUME_UP,
    QtCore.Qt.Key.Key_Minus.value: RemoteKey.VOLUME_DOWN,
    # Media
    QtCore.Qt.Key.Key_Space.value: RemoteKey.MEDIA_PLAY_PAUSE,
}


def handle_key_event(
    event: QtGui.QKeyEvent,
    window: QtWidgets.QWidget,
    on_key: Callable[[RemoteKey], None],
    is_enabled: Callable[[], bool],
) -> bool:
    """Handle physical key press and dispatch matching RemoteKey."""
    if not is_enabled():
        return False

    focused = window.focusWidget()
    if isinstance(focused, QtWidgets.QLineEdit):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            focused.clearFocus()
            return True
        return False

    key = event.key()
    if key in (QtCore.Qt.Key.Key_H,):
        on_key(RemoteKey.HOME)
        return True
    if key in (QtCore.Qt.Key.Key_M,):
        on_key(RemoteKey.MUTE)
        return True

    remote_key = KEY_MAP.get(key)
    if remote_key:
        on_key(remote_key)
        return True

    return False
