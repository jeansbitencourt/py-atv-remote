"""Tests for QtDispatcher thread-safe dispatching."""

from __future__ import annotations

import sys

from PyQt6 import QtWidgets

from py_atv_remote.ui.qt_dispatcher import QtDispatcher


def test_qt_dispatcher_post() -> None:
    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    dispatcher = QtDispatcher()

    executed: list[int] = []
    dispatcher.post(lambda: executed.append(42))

    # Process events to allow queued signal delivery
    QtWidgets.QApplication.processEvents()

    assert executed == [42]
