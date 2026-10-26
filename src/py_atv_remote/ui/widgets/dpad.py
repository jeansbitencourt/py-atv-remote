"""Visual D-Pad navigation control widget."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from py_atv_remote.domain.keys import RemoteKey
from py_atv_remote.ui.widgets.repeat_button import RepeatButton


class DPad(ttk.Frame):
    """Directional pad (▲, ◄, OK, ►, ▼) with repeat-on-hold for arrows."""

    def __init__(
        self,
        master: tk.Misc,
        on_key: Callable[[RemoteKey], None],
    ) -> None:
        super().__init__(master)
        self._on_key = on_key

        # Grid layout
        self.columnconfigure((0, 1, 2), weight=1, uniform="dpad")
        self.rowconfigure((0, 1, 2), weight=1, uniform="dpad")

        # Row 0: Up
        self.btn_up = RepeatButton(
            self,
            text="▲",
            command=lambda: self._on_key(RemoteKey.DPAD_UP),
            width=5,
            style="DPad.TButton",
        )
        self.btn_up.grid(row=0, column=1, padx=4, pady=4, sticky="nsew")

        # Row 1: Left, OK, Right
        self.btn_left = RepeatButton(
            self,
            text="◄",
            command=lambda: self._on_key(RemoteKey.DPAD_LEFT),
            width=5,
            style="DPad.TButton",
        )
        self.btn_left.grid(row=1, column=0, padx=4, pady=4, sticky="nsew")

        self.btn_center = ttk.Button(
            self,
            text="OK",
            command=lambda: self._on_key(RemoteKey.DPAD_CENTER),
            width=5,
            style="DPad.TButton",
        )
        self.btn_center.grid(row=1, column=1, padx=4, pady=4, sticky="nsew")

        self.btn_right = RepeatButton(
            self,
            text="►",
            command=lambda: self._on_key(RemoteKey.DPAD_RIGHT),
            width=5,
            style="DPad.TButton",
        )
        self.btn_right.grid(row=1, column=2, padx=4, pady=4, sticky="nsew")

        # Row 2: Down
        self.btn_down = RepeatButton(
            self,
            text="▼",
            command=lambda: self._on_key(RemoteKey.DPAD_DOWN),
            width=5,
            style="DPad.TButton",
        )
        self.btn_down.grid(row=2, column=1, padx=4, pady=4, sticky="nsew")

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable all DPad buttons."""
        state = tk.NORMAL if enabled else tk.DISABLED
        for btn in (self.btn_up, self.btn_left, self.btn_center, self.btn_right, self.btn_down):
            btn["state"] = state
