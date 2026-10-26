"""Thread-safe, atomic configuration persistence."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import socket
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from py_atv_remote.domain.models import AppShortcut, TvProfile
from py_atv_remote.infrastructure.paths import AppPaths

LOGGER = logging.getLogger(__name__)

DEFAULT_APP_SHORTCUTS: list[AppShortcut] = [
    AppShortcut(label="YouTube", link="https://www.youtube.com"),
    AppShortcut(label="Netflix", link="https://www.netflix.com/title"),
    AppShortcut(label="Prime Video", link="https://app.primevideo.com"),
    AppShortcut(label="Disney+", link="https://www.disneyplus.com"),
    AppShortcut(label="Crunchyroll", link="https://www.crunchyroll.com"),
    AppShortcut(label="HBO Max", link="https://play.max.com"),
]


class ConfigStore:
    """Manages reading, modifying, and atomically persisting application configuration."""

    CURRENT_SCHEMA_VERSION = 2

    def __init__(self, paths: AppPaths) -> None:
        self._paths = paths
        self._lock = threading.Lock()
        self._data: dict[str, Any] = self._load_or_create()

    def _default_client_name(self) -> str:
        try:
            hostname = socket.gethostname()
        except OSError:
            hostname = "desktop"
        return f"py-atv-remote ({hostname})"

    def _default_config(self) -> dict[str, Any]:
        return {
            "schema_version": self.CURRENT_SCHEMA_VERSION,
            "client_name": self._default_client_name(),
            "last_selected_id": None,
            "tvs": {},
            "app_shortcuts": [
                {"label": item.label, "link": item.link} for item in DEFAULT_APP_SHORTCUTS
            ],
            "ui": {
                "always_on_top": False,
            },
        }

    def _load_or_create(self) -> dict[str, Any]:
        config_file = self._paths.config_file
        if not config_file.exists():
            default_data = self._default_config()
            self._save_to_disk(default_data)
            return default_data

        try:
            content = config_file.read_text(encoding="utf-8")
            data = json.loads(content)
            if not isinstance(data, dict):
                raise ValueError("Config root is not a dictionary")
            return self._migrate(data)
        except Exception as exc:
            backup_path = config_file.with_name(f"config.json.bak-{int(time.time())}")
            LOGGER.error(
                "Failed to parse config %s (%s). Backing up to %s",
                config_file,
                exc,
                backup_path,
            )
            with contextlib.suppress(OSError):
                config_file.rename(backup_path)
            fallback = self._default_config()
            self._save_to_disk(fallback)
            return fallback

    def _migrate(self, data: dict[str, Any]) -> dict[str, Any]:
        version = int(data.get("schema_version", 1))
        if version < 2:
            data.setdefault("ui", {"always_on_top": False})
            data.setdefault("tvs", {})
            existing = data.get("app_shortcuts")
            if not existing or not isinstance(existing, list):
                data["app_shortcuts"] = [
                    {"label": item.label, "link": item.link} for item in DEFAULT_APP_SHORTCUTS
                ]
            else:
                old_labels = [
                    s.get("label") for s in existing if isinstance(s, dict) and "label" in s
                ]
                if old_labels == ["YouTube", "Netflix", "Prime Video", "Disney+", "Globoplay"]:
                    data["app_shortcuts"] = [
                        {"label": item.label, "link": item.link} for item in DEFAULT_APP_SHORTCUTS
                    ]
            data["schema_version"] = 2
            self._save_to_disk(data)
        return data

    def _save_to_disk(self, data: dict[str, Any]) -> None:
        """Atomically persist dictionary to config.json."""
        self._paths.ensure_dirs()
        target_file = self._paths.config_file
        content = json.dumps(data, indent=2, ensure_ascii=False)

        # Write to temporary file in the same filesystem directory to allow atomic replace
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self._paths.config_dir,
            delete=False,
            prefix="config-",
            suffix=".tmp",
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())

        try:
            tmp_path.chmod(0o600)
            tmp_path.replace(target_file)
        finally:
            if tmp_path.exists():
                with contextlib.suppress(OSError):
                    tmp_path.unlink()

    # Public Accessors

    def get_client_name(self) -> str:
        with self._lock:
            return str(self._data.get("client_name") or self._default_client_name())

    def get_last_selected_id(self) -> str | None:
        with self._lock:
            val = self._data.get("last_selected_id")
            return str(val) if val else None

    def set_last_selected_id(self, tv_id: str | None) -> None:
        with self._lock:
            self._data["last_selected_id"] = tv_id
            self._save_to_disk(self._data)

    def get_always_on_top(self) -> bool:
        with self._lock:
            ui = self._data.get("ui", {})
            return bool(ui.get("always_on_top", False))

    def set_always_on_top(self, value: bool) -> None:
        with self._lock:
            ui = self._data.setdefault("ui", {})
            ui["always_on_top"] = bool(value)
            self._save_to_disk(self._data)

    def get_tv(self, tv_id: str) -> TvProfile | None:
        with self._lock:
            raw = self._data.get("tvs", {}).get(tv_id)
            if not raw or not isinstance(raw, dict):
                return None
            return self._profile_from_dict(raw)

    def list_tvs(self) -> list[TvProfile]:
        with self._lock:
            tvs_dict = self._data.get("tvs", {})
            result: list[TvProfile] = []
            for raw in tvs_dict.values():
                if isinstance(raw, dict):
                    result.append(self._profile_from_dict(raw))
            return sorted(result, key=lambda tv: tv.name.lower())

    def save_tv(self, profile: TvProfile) -> None:
        with self._lock:
            tvs = self._data.setdefault("tvs", {})
            tvs[profile.id] = self._profile_to_dict(profile)
            self._save_to_disk(self._data)

    def delete_tv(self, tv_id: str) -> bool:
        with self._lock:
            tvs = self._data.get("tvs", {})
            if tv_id in tvs:
                del tvs[tv_id]
                if self._data.get("last_selected_id") == tv_id:
                    self._data["last_selected_id"] = None
                self._save_to_disk(self._data)
                return True
            return False

    def get_app_shortcuts(self) -> list[AppShortcut]:
        with self._lock:
            raw_list = self._data.get("app_shortcuts", [])
            shortcuts: list[AppShortcut] = []
            for item in raw_list:
                if isinstance(item, dict) and "label" in item and "link" in item:
                    shortcuts.append(AppShortcut(label=str(item["label"]), link=str(item["link"])))
            return shortcuts

    def set_app_shortcuts(self, shortcuts: list[AppShortcut]) -> None:
        with self._lock:
            self._data["app_shortcuts"] = [
                {"label": item.label, "link": item.link} for item in shortcuts
            ]
            self._save_to_disk(self._data)

    # Serialization Helpers

    @staticmethod
    def _profile_to_dict(profile: TvProfile) -> dict[str, Any]:
        return {
            "id": profile.id,
            "name": profile.name,
            "host": profile.host,
            "api_port": profile.api_port,
            "pair_port": profile.pair_port,
            "model": profile.model,
            "wol_mac": profile.wol_mac,
            "paired_at": profile.paired_at.isoformat() if profile.paired_at else None,
        }

    @staticmethod
    def _profile_from_dict(raw: dict[str, Any]) -> TvProfile:
        paired_at: datetime | None = None
        raw_paired = raw.get("paired_at")
        if raw_paired and isinstance(raw_paired, str):
            try:
                paired_at = datetime.fromisoformat(raw_paired)
            except ValueError:
                paired_at = None

        return TvProfile(
            id=str(raw["id"]),
            name=str(raw.get("name", "Android TV")),
            host=str(raw["host"]),
            api_port=int(raw.get("api_port", 6466)),
            pair_port=int(raw.get("pair_port", 6467)),
            model=str(raw["model"]) if raw.get("model") else None,
            wol_mac=str(raw["wol_mac"]) if raw.get("wol_mac") else None,
            paired_at=paired_at,
        )
