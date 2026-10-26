"""Tests for physical keyboard shortcut routing in PyQt6."""

from __future__ import annotations

import sys

from PyQt6 import QtCore, QtGui, QtWidgets

from py_atv_remote.domain.keys import RemoteKey
from py_atv_remote.ui.keybindings import KEY_MAP, handle_key_event


def test_key_map_completeness() -> None:
    assert KEY_MAP[QtCore.Qt.Key.Key_Up.value] == RemoteKey.DPAD_UP
    assert KEY_MAP[QtCore.Qt.Key.Key_Down.value] == RemoteKey.DPAD_DOWN
    assert KEY_MAP[QtCore.Qt.Key.Key_Return.value] == RemoteKey.DPAD_CENTER
    assert KEY_MAP[QtCore.Qt.Key.Key_Escape.value] == RemoteKey.BACK
    assert KEY_MAP[QtCore.Qt.Key.Key_Space.value] == RemoteKey.MEDIA_PLAY_PAUSE
    assert KEY_MAP[QtCore.Qt.Key.Key_Plus.value] == RemoteKey.VOLUME_UP
    assert KEY_MAP[QtCore.Qt.Key.Key_Minus.value] == RemoteKey.VOLUME_DOWN


def test_keybinding_dispatch_when_enabled() -> None:
    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QWidget()

    sent_keys: list[RemoteKey] = []

    # Simulate pressing Up arrow
    event = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_Up.value,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    handled = handle_key_event(
        event, window, on_key=lambda k: sent_keys.append(k), is_enabled=lambda: True
    )
    assert handled is True
    assert sent_keys == [RemoteKey.DPAD_UP]

    # Simulate pressing 'h'
    event_h = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_H.value,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    handled_h = handle_key_event(
        event_h, window, on_key=lambda k: sent_keys.append(k), is_enabled=lambda: True
    )
    assert handled_h is True
    assert sent_keys == [RemoteKey.DPAD_UP, RemoteKey.HOME]

    # Simulate pressing 'i' (TV_INPUT)
    event_i = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_I.value,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    handled_i = handle_key_event(
        event_i, window, on_key=lambda k: sent_keys.append(k), is_enabled=lambda: True
    )
    assert handled_i is True
    assert sent_keys == [RemoteKey.DPAD_UP, RemoteKey.HOME, RemoteKey.TV_INPUT]

    # When disabled, should return False and not dispatch
    sent_keys.clear()
    handled_dis = handle_key_event(
        event, window, on_key=lambda k: sent_keys.append(k), is_enabled=lambda: False
    )
    assert handled_dis is False
    assert sent_keys == []
