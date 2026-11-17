"""Tests for physical keyboard shortcut routing in PyQt6."""

from __future__ import annotations

import sys

from PyQt6 import QtCore, QtGui, QtWidgets

from py_atv_remote.domain.keys import RemoteKey
from py_atv_remote.ui.keybindings import KEY_MAP, handle_key_event


def test_key_map_completeness() -> None:
    assert KEY_MAP[QtCore.Qt.Key.Key_Up.value] == RemoteKey.DPAD_UP
    assert KEY_MAP[QtCore.Qt.Key.Key_Down.value] == RemoteKey.DPAD_DOWN
    assert KEY_MAP[QtCore.Qt.Key.Key_Left.value] == RemoteKey.DPAD_LEFT
    assert KEY_MAP[QtCore.Qt.Key.Key_Right.value] == RemoteKey.DPAD_RIGHT
    assert KEY_MAP[QtCore.Qt.Key.Key_Return.value] == RemoteKey.DPAD_CENTER
    assert KEY_MAP[QtCore.Qt.Key.Key_Enter.value] == RemoteKey.DPAD_CENTER
    assert KEY_MAP[QtCore.Qt.Key.Key_Escape.value] == RemoteKey.BACK
    assert KEY_MAP[QtCore.Qt.Key.Key_Backspace.value] == RemoteKey.BACK
    assert KEY_MAP[QtCore.Qt.Key.Key_Home.value] == RemoteKey.HOME
    assert KEY_MAP[QtCore.Qt.Key.Key_H.value] == RemoteKey.HOME
    assert KEY_MAP[QtCore.Qt.Key.Key_I.value] == RemoteKey.TV_INPUT
    assert KEY_MAP[QtCore.Qt.Key.Key_M.value] == RemoteKey.MUTE
    assert KEY_MAP[QtCore.Qt.Key.Key_Space.value] == RemoteKey.MEDIA_PLAY_PAUSE
    assert KEY_MAP[QtCore.Qt.Key.Key_J.value] == RemoteKey.MEDIA_REWIND
    assert KEY_MAP[QtCore.Qt.Key.Key_L.value] == RemoteKey.MEDIA_FAST_FORWARD
    assert KEY_MAP[QtCore.Qt.Key.Key_Plus.value] == RemoteKey.VOLUME_UP
    assert KEY_MAP[QtCore.Qt.Key.Key_Equal.value] == RemoteKey.VOLUME_UP
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


def test_keybinding_modifiers_and_repeat_behavior() -> None:
    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QWidget()
    sent_keys: list[RemoteKey] = []

    ctrl_h = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_H.value,
        QtCore.Qt.KeyboardModifier.ControlModifier,
    )
    assert handle_key_event(ctrl_h, window, sent_keys.append, is_enabled=lambda: True) is False
    assert sent_keys == []

    repeated_play = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_Space.value,
        QtCore.Qt.KeyboardModifier.NoModifier,
        " ",
        True,
        1,
    )
    assert (
        handle_key_event(repeated_play, window, sent_keys.append, is_enabled=lambda: True) is True
    )
    assert sent_keys == []

    repeated_volume = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_Plus.value,
        QtCore.Qt.KeyboardModifier.KeypadModifier,
        "+",
        True,
        1,
    )
    assert (
        handle_key_event(repeated_volume, window, sent_keys.append, is_enabled=lambda: True) is True
    )
    assert sent_keys == [RemoteKey.VOLUME_UP]


def test_power_shortcut_uses_power_handler_while_disconnected() -> None:
    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QWidget()
    power_calls: list[str] = []
    sent_keys: list[RemoteKey] = []

    event = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_P.value,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    handled = handle_key_event(
        event,
        window,
        sent_keys.append,
        is_enabled=lambda: False,
        on_power=lambda: power_calls.append("power"),
    )

    assert handled is True
    assert power_calls == ["power"]
    assert sent_keys == []


def test_line_edit_keeps_text_keys_and_escape_clears_focus() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QWidget()
    line_edit = QtWidgets.QLineEdit(window)
    window.show()
    line_edit.setFocus()
    app.processEvents()

    sent_keys: list[RemoteKey] = []
    backspace = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_Backspace.value,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    enter = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_Return.value,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    power = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_P.value,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    escape = QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_Escape.value,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )

    assert window.focusWidget() is line_edit
    assert handle_key_event(backspace, window, sent_keys.append, lambda: True) is False
    assert handle_key_event(enter, window, sent_keys.append, lambda: True) is False
    assert handle_key_event(power, window, sent_keys.append, lambda: True) is False
    assert handle_key_event(escape, window, sent_keys.append, lambda: True) is True
    assert window.focusWidget() is not line_edit
    assert sent_keys == []
    window.close()
