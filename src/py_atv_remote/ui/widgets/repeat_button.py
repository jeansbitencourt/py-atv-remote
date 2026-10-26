"""Button widget supporting repeated firing while held down."""

from __future__ import annotations

import contextlib
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk


class RepeatButton(ttk.Button):
    """ttk.Button subclass that fires repeatedly while pressed down."""

    def __init__(
        self,
        master: tk.Misc,
        text: str = "",
        command: Callable[[], None] | None = None,
        initial_delay_ms: int = 400,
        repeat_interval_ms: int = 110,
        **kwargs: object,
    ) -> None:
        super().__init__(master, text=text, command=None, **kwargs)  # type: ignore[arg-type]
        self._action = command
        self._initial_delay_ms = initial_delay_ms
        self._repeat_interval_ms = repeat_interval_ms
        self._timer_id: str | None = None

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Leave>", self._on_release)

    def _on_press(self, _event: tk.Event[tk.Misc]) -> None:
        self._cancel_timer()
        if self["state"] == tk.DISABLED:
            return

        if self._action:
            self._action()

        self._timer_id = self.after(self._initial_delay_ms, self._on_repeat)

    def _on_repeat(self) -> None:
        if self["state"] == tk.DISABLED:
            self._cancel_timer()
            return

        if self._action:
            self._action()

        self._timer_id = self.after(self._repeat_interval_ms, self._on_repeat)

    def _on_release(self, _event: tk.Event[tk.Misc]) -> None:
        self._cancel_timer()

    def _cancel_timer(self) -> None:
        if self._timer_id is not None:
            with contextlib.suppress(Exception):
                self.after_cancel(self._timer_id)
            self._timer_id = None
