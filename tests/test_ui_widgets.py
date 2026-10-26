"""Tests for PyQt6 UI widgets."""

from __future__ import annotations

import sys
from collections.abc import Generator

import pytest
from PyQt6 import QtWidgets

from py_atv_remote.domain.keys import RemoteKey
from py_atv_remote.domain.models import ConnectionState, VolumeState
from py_atv_remote.ui.widgets.dpad import DPad
from py_atv_remote.ui.widgets.repeat_button import RepeatButton
from py_atv_remote.ui.widgets.status_bar import StatusBar


@pytest.fixture(scope="session")
def qapp() -> Generator[QtWidgets.QApplication]:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    yield app  # type: ignore[misc]


def test_repeat_button(qapp: QtWidgets.QApplication) -> None:
    clicks: list[str] = []
    btn = RepeatButton("Test", command=lambda: clicks.append("clicked"))

    assert btn.autoRepeat() is True
    assert btn.autoRepeatDelay() == 400
    assert btn.autoRepeatInterval() == 110

    btn.click()
    assert clicks == ["clicked"]


def test_dpad_dispatch_and_enabling(qapp: QtWidgets.QApplication) -> None:
    keys: list[RemoteKey] = []
    dpad = DPad(on_key=lambda k: keys.append(k))

    assert dpad.btn_up.isEnabled() is True
    assert dpad.btn_center.isEnabled() is True

    dpad.btn_center.click()
    assert keys == [RemoteKey.DPAD_CENTER]

    dpad.set_enabled(False)
    assert dpad.btn_up.isEnabled() is False
    assert dpad.btn_center.isEnabled() is False

    dpad.set_enabled(True)
    assert dpad.btn_up.isEnabled() is True
    assert dpad.btn_center.isEnabled() is True


def test_status_bar_updates(qapp: QtWidgets.QApplication) -> None:
    bar = StatusBar()

    assert "Nenhuma TV" in bar._label.text()

    bar.update_state(ConnectionState.CONNECTED)
    assert "Conectado" in bar._label.text()

    bar.update_volume(VolumeState(level=18, max_level=100, muted=False))
    assert "Vol 18/100" in bar._label.text()

    bar.update_volume(VolumeState(level=18, max_level=100, muted=True))
    assert "Mudo" in bar._label.text()

    bar.update_current_app("com.google.android.youtube.tv")
    assert "YouTube" in bar._label.text()
