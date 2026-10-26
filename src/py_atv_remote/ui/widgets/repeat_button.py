"""Button widget supporting repeated firing while held down, built with CustomTkinter."""

from __future__ import annotations

import contextlib
import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk


class RepeatButton(ctk.CTkButton):
    """customtkinter.CTkButton subclass that fires repeatedly while held down."""

    def __init__(
        self,
        master: tk.Misc,
        text: str = "",
        command: Callable[[], None] | None = None,
        initial_delay_ms: int = 400,
        repeat_interval_ms: int = 110,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("corner_radius", 8)
        kwargs.setdefault("font", ("Liberation Sans", 11, "bold"))
        super().__init__(master, text=text, command=None, **kwargs)
        self._action = command
        self._initial_delay_ms = initial_delay_ms
        self._repeat_interval_ms = repeat_interval_ms
        self._timer_id: str | None = None

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Leave>", self._on_release)

    def _on_press(self, _event: tk.Event[tk.Misc]) -> None:
        self._cancel_timer()
        if self.cget("state") == "disabled":
            return

        if self._action:
            self._action()

        self._timer_id = self.after(self._initial_delay_ms, self._on_repeat)

    def _on_repeat(self) -> None:
        if self.cget("state") == "disabled":
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

    def __setitem__(self, key: str, value: Any) -> None:
        if key == "state":
            self.configure(state=value)
        else:
            super().__setitem__(key, value)

    def __getitem__(self, key: str) -> Any:
        if key == "state":
            return self.cget("state")
        return super().__getitem__(key)
