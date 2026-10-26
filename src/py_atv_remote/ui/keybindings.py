"""Keyboard shortcut mappings for the remote control."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from py_atv_remote.domain.keys import RemoteKey

# Key symbols mapped to RemoteKey
KEY_MAP: dict[str, RemoteKey] = {
    # Navigation
    "Up": RemoteKey.DPAD_UP,
    "Down": RemoteKey.DPAD_DOWN,
    "Left": RemoteKey.DPAD_LEFT,
    "Right": RemoteKey.DPAD_RIGHT,
    "Return": RemoteKey.DPAD_CENTER,
    "KP_Enter": RemoteKey.DPAD_CENTER,
    # Navigation / System
    "Escape": RemoteKey.BACK,
    "BackSpace": RemoteKey.BACK,
    "Home": RemoteKey.HOME,
    # Volume
    "plus": RemoteKey.VOLUME_UP,
    "equal": RemoteKey.VOLUME_UP,
    "KP_Add": RemoteKey.VOLUME_UP,
    "minus": RemoteKey.VOLUME_DOWN,
    "KP_Subtract": RemoteKey.VOLUME_DOWN,
    # Media
    "space": RemoteKey.MEDIA_PLAY_PAUSE,
}


def register_keybindings(
    root: tk.Misc,
    on_key: Callable[[RemoteKey], None],
    is_enabled: Callable[[], bool],
) -> None:
    """Attach keyboard event listeners to the window root."""

    def _on_key_press(event: tk.Event[tk.Misc]) -> None:
        if not is_enabled():
            return

        # If user is focused on an Entry, Text or Combobox, do not intercept normal typing!
        focused = root.focus_get()
        if isinstance(focused, (tk.Entry, ttk.Entry, tk.Text)):
            # Allow Escape in text input to unfocus
            if event.keysym == "Escape":
                root.focus_set()
            return

        keysym = event.keysym

        # Case-insensitive letter shortcuts when not typing
        if keysym in ("h", "H"):
            on_key(RemoteKey.HOME)
            return
        if keysym in ("m", "M"):
            on_key(RemoteKey.MUTE)
            return

        remote_key = KEY_MAP.get(keysym)
        if remote_key:
            on_key(remote_key)

    root.bind("<Key>", _on_key_press)
