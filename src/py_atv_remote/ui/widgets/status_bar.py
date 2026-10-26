"""Status bar widget displaying connection state, volume, and active app."""

from __future__ import annotations

import tkinter as tk
from typing import Any

import customtkinter as ctk

from py_atv_remote.domain.models import ConnectionState, VolumeState

# Colors for connection dot
STATE_COLORS: dict[ConnectionState, str] = {
    ConnectionState.CONNECTED: "#22c55e",  # Green
    ConnectionState.CONNECTING: "#eab308",  # Yellow
    ConnectionState.RECONNECTING: "#f97316",  # Orange
    ConnectionState.OFFLINE: "#ef4444",  # Red
    ConnectionState.NEEDS_PAIRING: "#3b82f6",  # Blue
    ConnectionState.IDLE: "#71717a",  # Muted Zinc
}

STATE_LABELS: dict[ConnectionState, str] = {
    ConnectionState.CONNECTED: "Conectado",
    ConnectionState.CONNECTING: "Conectando…",
    ConnectionState.RECONNECTING: "Reconectando…",
    ConnectionState.OFFLINE: "Offline",
    ConnectionState.NEEDS_PAIRING: "Requer Pareamento",
    ConnectionState.IDLE: "Nenhuma TV selecionada",
}


class StatusBar(ctk.CTkFrame):
    """Displays connection status indicator, app name, and volume level."""

    def __init__(self, master: tk.Misc, **kwargs: Any) -> None:
        kwargs.setdefault("corner_radius", 10)
        kwargs.setdefault("fg_color", ("#e4e4e7", "#27272a"))
        kwargs.setdefault("height", 32)
        super().__init__(master, **kwargs)

        initial_color = STATE_COLORS[ConnectionState.IDLE]
        self._dot = ctk.CTkLabel(
            self,
            text="●",
            font=("Liberation Sans", 13),
            text_color=initial_color,
            width=18,
        )
        self._dot.pack(side="left", padx=(8, 2), pady=3)

        self._text_var = tk.StringVar(value=STATE_LABELS[ConnectionState.IDLE])
        self._label = ctk.CTkLabel(
            self,
            textvariable=self._text_var,
            font=("Liberation Sans", 11),
            text_color=("#18181b", "#d4d4d8"),
            anchor="w",
        )
        self._label.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=3)

        self._state = ConnectionState.IDLE
        self._current_app: str | None = None
        self._volume: VolumeState | None = None

    def update_state(self, state: ConnectionState) -> None:
        """Update connection state and refresh display."""
        self._state = state
        color = STATE_COLORS.get(state, "#71717a")
        self._dot.configure(text_color=color)
        self._refresh_text()

    def update_current_app(self, app_id: str | None) -> None:
        """Update active app package name."""
        self._current_app = app_id
        self._refresh_text()

    def update_volume(self, volume: VolumeState | None) -> None:
        """Update volume level and mute state."""
        self._volume = volume
        self._refresh_text()

    def _refresh_text(self) -> None:
        parts: list[str] = [STATE_LABELS.get(self._state, "Desconhecido")]

        if self._state == ConnectionState.CONNECTED:
            if self._current_app:
                app_name = self._format_app_name(self._current_app)
                parts.append(app_name)

            if self._volume is not None:
                if self._volume.muted:
                    parts.append("Mudo")
                else:
                    parts.append(f"Vol {self._volume.level}/{self._volume.max_level}")

        self._text_var.set(" · ".join(parts))

    @staticmethod
    def _format_app_name(package: str) -> str:
        common_apps = {
            "com.google.android.youtube.tv": "YouTube",
            "com.netflix.ninja": "Netflix",
            "com.amazon.amazonvideo.livingroom": "Prime Video",
            "com.disney.disneyplus": "Disney+",
            "globo.globotv": "Globoplay",
            "com.google.android.tvlauncher": "Início",
        }
        return common_apps.get(package, package.split(".")[-1].capitalize())
