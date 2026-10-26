"""Visual D-Pad navigation control widget built with CustomTkinter."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from py_atv_remote.domain.keys import RemoteKey
from py_atv_remote.ui.widgets.repeat_button import RepeatButton


class DPad(ctk.CTkFrame):
    """Directional pad (▲, ◄, OK, ►, ▼) with repeat-on-hold for arrows."""

    def __init__(
        self,
        master: tk.Misc,
        on_key: Callable[[RemoteKey], None],
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self._on_key = on_key

        # Grid layout
        self.columnconfigure((0, 1, 2), weight=1, uniform="dpad")
        self.rowconfigure((0, 1, 2), weight=1, uniform="dpad")

        btn_font = ("Liberation Sans", 14, "bold")
        btn_kwargs: dict[str, Any] = {
            "width": 58,
            "height": 48,
            "corner_radius": 12,
            "fg_color": ("#d4d4d8", "#3f3f46"),
            "hover_color": ("#a1a1aa", "#52525b"),
            "text_color": ("#18181b", "#f4f4f5"),
            "font": btn_font,
        }

        # Row 0: Up
        self.btn_up = RepeatButton(
            self,
            text="▲",
            command=lambda: self._on_key(RemoteKey.DPAD_UP),
            **btn_kwargs,
        )
        self.btn_up.grid(row=0, column=1, padx=4, pady=4, sticky="nsew")

        # Row 1: Left, OK, Right
        self.btn_left = RepeatButton(
            self,
            text="◄",
            command=lambda: self._on_key(RemoteKey.DPAD_LEFT),
            **btn_kwargs,
        )
        self.btn_left.grid(row=1, column=0, padx=4, pady=4, sticky="nsew")

        self.btn_center = ctk.CTkButton(
            self,
            text="OK",
            command=lambda: self._on_key(RemoteKey.DPAD_CENTER),
            width=58,
            height=48,
            corner_radius=14,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            font=("Liberation Sans", 13, "bold"),
        )
        self.btn_center.grid(row=1, column=1, padx=4, pady=4, sticky="nsew")

        self.btn_right = RepeatButton(
            self,
            text="►",
            command=lambda: self._on_key(RemoteKey.DPAD_RIGHT),
            **btn_kwargs,
        )
        self.btn_right.grid(row=1, column=2, padx=4, pady=4, sticky="nsew")

        # Row 2: Down
        self.btn_down = RepeatButton(
            self,
            text="▼",
            command=lambda: self._on_key(RemoteKey.DPAD_DOWN),
            **btn_kwargs,
        )
        self.btn_down.grid(row=2, column=1, padx=4, pady=4, sticky="nsew")

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable all DPad buttons."""
        state = "normal" if enabled else "disabled"
        for btn in (self.btn_up, self.btn_left, self.btn_center, self.btn_right, self.btn_down):
            btn.configure(state=state)
