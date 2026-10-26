"""Tests for configuration persistence and schema management."""

from datetime import UTC, datetime
from pathlib import Path

from py_atv_remote.domain.models import AppShortcut, TvProfile
from py_atv_remote.infrastructure.config_store import DEFAULT_APP_SHORTCUTS, ConfigStore
from py_atv_remote.infrastructure.paths import AppPaths


def test_default_config_created(tmp_path: Path) -> None:
    paths = AppPaths(base_dir=tmp_path)
    store = ConfigStore(paths)

    assert paths.config_file.exists()
    assert (paths.config_file.stat().st_mode & 0o777) == 0o600

    assert store.get_last_selected_id() is None
    assert len(store.list_tvs()) == 0
    assert len(store.get_app_shortcuts()) == len(DEFAULT_APP_SHORTCUTS)
    assert store.get_always_on_top() is False


def test_save_and_retrieve_tv_profile(tmp_path: Path) -> None:
    paths = AppPaths(base_dir=tmp_path)
    store = ConfigStore(paths)

    profile = TvProfile(
        id="84c8a02b914c",
        name="TV da sala",
        host="192.168.2.104",
        api_port=6466,
        pair_port=6467,
        model="Philips Google TV TA7",
        wol_mac="6a:5d:ac:20:7c:23",
        paired_at=datetime.now(UTC),
    )
    store.save_tv(profile)
    store.set_last_selected_id("84c8a02b914c")

    retrieved = store.get_tv("84c8a02b914c")
    assert retrieved is not None
    assert retrieved.name == "TV da sala"
    assert retrieved.host == "192.168.2.104"
    assert retrieved.wol_mac == "6a:5d:ac:20:7c:23"
    assert retrieved.model == "Philips Google TV TA7"
    assert retrieved.paired_at is not None

    assert store.get_last_selected_id() == "84c8a02b914c"

    # Reload store from disk
    new_store = ConfigStore(paths)
    reloaded = new_store.get_tv("84c8a02b914c")
    assert reloaded is not None
    assert reloaded.name == "TV da sala"

    # Deleting TV also clears last_selected_id if matching
    assert new_store.delete_tv("84c8a02b914c")
    assert new_store.get_tv("84c8a02b914c") is None
    assert new_store.get_last_selected_id() is None


def test_corrupted_config_recovery(tmp_path: Path) -> None:
    paths = AppPaths(base_dir=tmp_path)
    # Write invalid JSON
    paths.config_file.write_text("{ broken json, not valid ...", encoding="utf-8")

    store = ConfigStore(paths)
    # Should not crash, and should start with fresh default config
    assert store.get_last_selected_id() is None
    # Check that backup was created
    backups = list(tmp_path.glob("config.json.bak-*"))
    assert len(backups) == 1


def test_app_shortcuts_and_ui_settings(tmp_path: Path) -> None:
    paths = AppPaths(base_dir=tmp_path)
    store = ConfigStore(paths)

    custom_shortcuts = [
        AppShortcut(label="YouTube", link="https://www.youtube.com"),
        AppShortcut(label="Custom App", link="https://example.com/app"),
    ]
    store.set_app_shortcuts(custom_shortcuts)
    assert store.get_app_shortcuts() == custom_shortcuts

    store.set_always_on_top(True)
    assert store.get_always_on_top() is True
