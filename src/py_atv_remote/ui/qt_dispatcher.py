"""Thread-safe UI dispatcher bridging background threads with the Qt event loop."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PyQt6 import QtCore

LOGGER = logging.getLogger(__name__)


class QtDispatcher(QtCore.QObject):
    """Dispatches callbacks to the Qt GUI thread using a queued signal."""

    _callback_signal = QtCore.pyqtSignal(object)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._callback_signal.connect(self._run_callback)

    def start(self) -> None:
        """Start dispatcher (no-op in Qt as signals are event-driven)."""
        pass

    def stop(self) -> None:
        """Stop dispatcher (no-op in Qt)."""
        pass

    def post(self, fn: Callable[[], None]) -> None:
        """Post a callback to be safely executed on the Qt GUI thread."""
        self._callback_signal.emit(fn)

    @QtCore.pyqtSlot(object)
    def _run_callback(self, fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception:
            LOGGER.exception("Unhandled error inside UI dispatched callback")
