"""Integration tests for keyboard shortcuts across the main window focus tree."""

from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtTest import QTest

from py_atv_remote.domain.keys import RemoteKey
from py_atv_remote.domain.models import ConnectionState
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.infrastructure.paths import AppPaths
from py_atv_remote.services.events import EventBus
from py_atv_remote.ui.main_window import MainWindow


@pytest.fixture
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if isinstance(app, QtWidgets.QApplication):
        return app
    return QtWidgets.QApplication(sys.argv)


@pytest.fixture
def main_window(
    tmp_path: Path, qapp: QtWidgets.QApplication
) -> Generator[tuple[MainWindow, MagicMock, list[RemoteKey]], None, None]:
    config_store = ConfigStore(AppPaths(base_dir=tmp_path))
    session = MagicMock()
    session.state = ConnectionState.CONNECTED
    sent_keys: list[RemoteKey] = []
    window = MainWindow(
        config_store=config_store,
        remote_session=session,
        event_bus=EventBus(),
        async_runner=MagicMock(),
        open_device_manager=lambda: None,
        open_shortcuts_dialog=lambda: None,
    )
    window._send_key = sent_keys.append  # type: ignore[method-assign]
    window.show()
    qapp.processEvents()
    yield window, session, sent_keys
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_shortcuts_precede_focused_button_and_skip_dialog(
    main_window: tuple[MainWindow, MagicMock, list[RemoteKey]], qapp: QtWidgets.QApplication
) -> None:
    window, session, sent_keys = main_window
    window._btn_power.setFocus()
    qapp.processEvents()

    QTest.keyClick(window._btn_power, QtCore.Qt.Key.Key_Up)
    QTest.keyClick(window._btn_power, QtCore.Qt.Key.Key_Return)

    assert sent_keys == [RemoteKey.DPAD_UP, RemoteKey.DPAD_CENTER]
    session.power.assert_not_called()

    dialog = QtWidgets.QDialog(window)
    dialog_button = QtWidgets.QPushButton("Dialog", dialog)
    dialog.show()
    dialog_button.setFocus()
    qapp.processEvents()
    QTest.keyClick(dialog_button, QtCore.Qt.Key.Key_Down)

    assert sent_keys == [RemoteKey.DPAD_UP, RemoteKey.DPAD_CENTER]
    dialog.close()


def test_text_input_keeps_native_keys_and_power_works_offline(
    main_window: tuple[MainWindow, MagicMock, list[RemoteKey]], qapp: QtWidgets.QApplication
) -> None:
    window, session, sent_keys = main_window
    window._txt_input.setText("texto")
    window._txt_input.setFocus()
    qapp.processEvents()

    QTest.keyClick(window._txt_input, QtCore.Qt.Key.Key_Backspace)
    assert window._txt_input.text() == "text"

    QTest.keyClick(window._txt_input, QtCore.Qt.Key.Key_Return)
    session.send_text.assert_called_once_with("text")
    assert sent_keys == []

    window._btn_power.setFocus()
    session.state = ConnectionState.OFFLINE
    QTest.keyClick(window._btn_power, QtCore.Qt.Key.Key_P)

    session.power.assert_called_once_with()
    assert sent_keys == []
