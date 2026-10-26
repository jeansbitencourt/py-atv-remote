"""Tests for app shortcuts dialog and data updates."""

from pathlib import Path

from py_atv_remote.domain.models import AppShortcut
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.infrastructure.paths import AppPaths


def test_shortcuts_roundtrip_in_config(tmp_path: Path) -> None:
    paths = AppPaths(base_dir=tmp_path)
    store = ConfigStore(paths)

    initial = store.get_app_shortcuts()
    assert len(initial) > 0

    custom = [
        AppShortcut(label="YouTube", link="https://www.youtube.com"),
        AppShortcut(label="Twitch", link="tv.twitch.android.app"),
    ]
    store.set_app_shortcuts(custom)

    reloaded = store.get_app_shortcuts()
    assert len(reloaded) == 2
    assert reloaded[0].label == "YouTube"
    assert reloaded[1].label == "Twitch"
    assert reloaded[1].link == "tv.twitch.android.app"
