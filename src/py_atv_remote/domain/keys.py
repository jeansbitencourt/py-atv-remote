"""Remote control key definitions and metadata."""

from enum import StrEnum


class RemoteKey(StrEnum):
    """Supported keys mapped to Google Remote V2 keycode names."""

    # Navigation / D-Pad
    DPAD_UP = "KEYCODE_DPAD_UP"
    DPAD_DOWN = "KEYCODE_DPAD_DOWN"
    DPAD_LEFT = "KEYCODE_DPAD_LEFT"
    DPAD_RIGHT = "KEYCODE_DPAD_RIGHT"
    DPAD_CENTER = "KEYCODE_DPAD_CENTER"  # OK / Select

    # System actions
    BACK = "KEYCODE_BACK"
    HOME = "KEYCODE_HOME"
    POWER = "KEYCODE_POWER"
    MENU = "KEYCODE_MENU"
    SETTINGS = "KEYCODE_SETTINGS"
    TV_INPUT = "KEYCODE_TV_INPUT"

    # Volume
    VOLUME_UP = "KEYCODE_VOLUME_UP"
    VOLUME_DOWN = "KEYCODE_VOLUME_DOWN"
    MUTE = "KEYCODE_VOLUME_MUTE"

    # Media controls
    MEDIA_PLAY_PAUSE = "KEYCODE_MEDIA_PLAY_PAUSE"
    MEDIA_REWIND = "KEYCODE_MEDIA_REWIND"
    MEDIA_FAST_FORWARD = "KEYCODE_MEDIA_FAST_FORWARD"

    @property
    def is_repeatable(self) -> bool:
        """Whether holding down this button should trigger periodic key repeats."""
        return self in (
            RemoteKey.DPAD_UP,
            RemoteKey.DPAD_DOWN,
            RemoteKey.DPAD_LEFT,
            RemoteKey.DPAD_RIGHT,
            RemoteKey.VOLUME_UP,
            RemoteKey.VOLUME_DOWN,
        )
