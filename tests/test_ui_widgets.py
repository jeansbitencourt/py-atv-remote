"""Tests for CustomTkinter UI widgets."""

from __future__ import annotations

import contextlib
from collections.abc import Generator

import customtkinter as ctk
import pytest

from py_atv_remote.domain.keys import RemoteKey
from py_atv_remote.domain.models import ConnectionState, VolumeState
from py_atv_remote.ui.widgets.dpad import DPad
from py_atv_remote.ui.widgets.repeat_button import RepeatButton
from py_atv_remote.ui.widgets.status_bar import StatusBar


@pytest.fixture
def ctk_root() -> Generator[ctk.CTk]:
    root = ctk.CTk()
    root.withdraw()
    yield root
    with contextlib.suppress(Exception):
        root.destroy()


def test_repeat_button_state_and_press(ctk_root: ctk.CTk) -> None:
    actions: list[str] = []
    btn = RepeatButton(ctk_root, text="Test", command=lambda: actions.append("clicked"))
    btn.pack()

    # Initial state
    assert btn.cget("state") == "normal"
    assert btn["state"] == "normal"

    # Press should trigger action once
    btn._on_press(None)  # type: ignore[arg-type]
    assert len(actions) == 1

    # Release cancels repeat
    btn._on_release(None)  # type: ignore[arg-type]
    assert btn._timer_id is None

    # Disable button
    btn.configure(state="disabled")
    assert btn["state"] == "disabled"
    btn._on_press(None)  # type: ignore[arg-type]
    assert len(actions) == 1  # No new click because disabled


def test_dpad_enabling(ctk_root: ctk.CTk) -> None:
    dispatched_keys: list[RemoteKey] = []
    dpad = DPad(ctk_root, on_key=lambda k: dispatched_keys.append(k))
    dpad.pack()

    # Initial state is normal
    assert dpad.btn_up.cget("state") == "normal"
    assert dpad.btn_center.cget("state") == "normal"

    # Trigger action
    dpad._on_key(RemoteKey.DPAD_CENTER)
    assert dispatched_keys == [RemoteKey.DPAD_CENTER]

    # Disable
    dpad.set_enabled(False)
    assert dpad.btn_up.cget("state") == "disabled"
    assert dpad.btn_center.cget("state") == "disabled"

    # Re-enable
    dpad.set_enabled(True)
    assert dpad.btn_up.cget("state") == "normal"
    assert dpad.btn_center.cget("state") == "normal"


def test_status_bar_updates(ctk_root: ctk.CTk) -> None:
    bar = StatusBar(ctk_root)
    bar.pack()

    # Initial status
    assert "Nenhuma TV" in bar._text_var.get()

    # Connect
    bar.update_state(ConnectionState.CONNECTED)
    assert "Conectado" in bar._text_var.get()

    # Volume update
    bar.update_volume(VolumeState(level=15, max_level=25, muted=False))
    assert "Vol 15/25" in bar._text_var.get()

    # Mute update
    bar.update_volume(VolumeState(level=15, max_level=25, muted=True))
    assert "Mudo" in bar._text_var.get()

    # App update
    bar.update_current_app("com.google.android.youtube.tv")
    assert "YouTube" in bar._text_var.get()
