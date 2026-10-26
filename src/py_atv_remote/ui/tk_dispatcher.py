"""Thread-safe UI dispatcher bridging background threads with Tkinter event loop."""

from __future__ import annotations

import contextlib
import logging
import queue
import tkinter as tk
from collections.abc import Callable

LOGGER = logging.getLogger(__name__)


class TkDispatcher:
    """Dispatches callbacks to the Tkinter UI thread using a thread-safe queue and root.after()."""

    def __init__(self, root: tk.Misc, poll_interval_ms: int = 16) -> None:
        self._root = root
        self._poll_interval_ms = poll_interval_ms
        self._queue: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()
        self._running = False
        self._timer_id: str | None = None

    def start(self) -> None:
        """Start polling the queue in the Tkinter main thread."""
        if not self._running:
            self._running = True
            self._schedule_poll()

    def stop(self) -> None:
        """Stop polling the queue."""
        self._running = False
        if self._timer_id is not None:
            with contextlib.suppress(Exception):
                self._root.after_cancel(self._timer_id)
            self._timer_id = None

    def post(self, fn: Callable[[], None]) -> None:
        """Post a callback to be executed on the Tkinter thread."""
        self._queue.put(fn)

    def _schedule_poll(self) -> None:
        if self._running:
            try:
                self._timer_id = self._root.after(self._poll_interval_ms, self._drain)
            except Exception:
                self._running = False

    def _drain(self) -> None:
        """Drain up to 50 callbacks per tick to prevent UI starvation."""
        count = 0
        while not self._queue.empty() and count < 50:
            try:
                callback = self._queue.get_nowait()
                count += 1
                try:
                    callback()
                except Exception:
                    LOGGER.exception("Unhandled error inside UI dispatched callback")
            except queue.Empty:
                break
        self._schedule_poll()
