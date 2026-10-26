"""Tests for physical keyboard shortcut routing."""

from unittest.mock import MagicMock

from py_atv_remote.domain.keys import RemoteKey
from py_atv_remote.ui.keybindings import KEY_MAP, register_keybindings


def test_key_map_completeness() -> None:
    assert KEY_MAP["Up"] == RemoteKey.DPAD_UP
    assert KEY_MAP["Down"] == RemoteKey.DPAD_DOWN
    assert KEY_MAP["Return"] == RemoteKey.DPAD_CENTER
    assert KEY_MAP["Escape"] == RemoteKey.BACK
    assert KEY_MAP["space"] == RemoteKey.MEDIA_PLAY_PAUSE
    assert KEY_MAP["plus"] == RemoteKey.VOLUME_UP
    assert KEY_MAP["minus"] == RemoteKey.VOLUME_DOWN


def test_keybinding_dispatch_when_enabled() -> None:
    mock_root = MagicMock()
    mock_root.focus_get.return_value = None  # Not focused on Entry

    sent_keys: list[RemoteKey] = []
    register_keybindings(mock_root, on_key=lambda k: sent_keys.append(k), is_enabled=lambda: True)

    # Retrieve registered handler
    args, _ = mock_root.bind.call_args
    assert args[0] == "<Key>"
    handler = args[1]

    # Simulate pressing Up arrow
    event = MagicMock()
    event.keysym = "Up"
    handler(event)
    assert sent_keys == [RemoteKey.DPAD_UP]

    # Simulate pressing 'h'
    event.keysym = "h"
    handler(event)
    assert sent_keys == [RemoteKey.DPAD_UP, RemoteKey.HOME]

    # Simulate pressing 'm'
    event.keysym = "m"
    handler(event)
    assert sent_keys == [RemoteKey.DPAD_UP, RemoteKey.HOME, RemoteKey.MUTE]
