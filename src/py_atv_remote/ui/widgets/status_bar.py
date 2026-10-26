"""Status bar widget displaying connection state, volume, and active app."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from py_atv_remote.domain.models import ConnectionState, VolumeState

# Colors for connection dot
STATE_COLORS: dict[ConnectionState, str] = {
    ConnectionState.CONNECTED: "#2ecc71",  # Green
    ConnectionState.CONNECTING: "#f1c40f",  # Yellow
    ConnectionState.RECONNECTING: "#f39c12",  # Orange
    ConnectionState.OFFLINE: "#e74c3c",  # Red
    ConnectionState.NEEDS_PAIRING: "#3498db",  # Blue
    ConnectionState.IDLE: "#95a5a6",  # Grey
}

STATE_LABELS: dict[ConnectionState, str] = {
    ConnectionState.CONNECTED: "Conectado",
    ConnectionState.CONNECTING: "Conectando…",
    ConnectionState.RECONNECTING: "Reconectando…",
    ConnectionState.OFFLINE: "Offline",
    ConnectionState.NEEDS_PAIRING: "Requer Pareamento",
    ConnectionState.IDLE: "Nenhuma TV selecionada",
}


class StatusBar(ttk.Frame):
    """Displays connection dot, status text, current app, and volume level."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)

        self._canvas = tk.Canvas(self, width=12, height=12, highlightthickness=0)
        self._canvas.pack(side=tk.LEFT, padx=(4, 6), pady=2)
        initial_color = STATE_COLORS[ConnectionState.IDLE]
        self._dot = self._canvas.create_oval(2, 2, 10, 10, fill=initial_color, outline="")

        self._text_var = tk.StringVar(value=STATE_LABELS[ConnectionState.IDLE])
        self._label = ttk.Label(self, textvariable=self._text_var, font=("sans-serif", 9))
        self._label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._state = ConnectionState.IDLE
        self._current_app: str | None = None
        self._volume: VolumeState | None = None

    def update_state(self, state: ConnectionState) -> None:
        """Update connection state and refresh display."""
        self._state = state
        color = STATE_COLORS.get(state, "#95a5a6")
        self._canvas.itemconfig(self._dot, fill=color)
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
                # Format friendly app name if common or shorten package
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
