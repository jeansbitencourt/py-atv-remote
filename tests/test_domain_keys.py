"""Tests for remote keys."""

from py_atv_remote.domain.keys import RemoteKey


def test_remote_keys_values() -> None:
    assert RemoteKey.DPAD_CENTER.value == "KEYCODE_DPAD_CENTER"
    assert RemoteKey.POWER.value == "KEYCODE_POWER"
    assert RemoteKey.VOLUME_UP.value == "KEYCODE_VOLUME_UP"
    assert RemoteKey.BACK.value == "KEYCODE_BACK"
    assert RemoteKey.TV_INPUT.value == "KEYCODE_TV_INPUT"


def test_remote_keys_repeatable() -> None:
    assert RemoteKey.DPAD_UP.is_repeatable is True
    assert RemoteKey.DPAD_DOWN.is_repeatable is True
    assert RemoteKey.VOLUME_UP.is_repeatable is True
    assert RemoteKey.VOLUME_DOWN.is_repeatable is True
    assert RemoteKey.DPAD_CENTER.is_repeatable is False
    assert RemoteKey.POWER.is_repeatable is False
    assert RemoteKey.BACK.is_repeatable is False
