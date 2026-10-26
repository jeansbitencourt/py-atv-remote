"""Status bar widget displaying connection state, volume, and active app."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

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


class StatusBar(QtWidgets.QFrame):
    """Displays connection status indicator, app name, and volume level."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setFixedHeight(30)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(6)

        self._dot = QtWidgets.QLabel("●", self)
        self._dot.setFixedWidth(14)
        self._dot.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self._label = QtWidgets.QLabel(STATE_LABELS[ConnectionState.IDLE], self)
        self._label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )

        layout.addWidget(self._dot)
        layout.addWidget(self._label, stretch=1)

        self._state = ConnectionState.IDLE
        self._current_app: str | None = None
        self._volume: VolumeState | None = None

        self._update_dot_color(STATE_COLORS[ConnectionState.IDLE])

    def update_state(self, state: ConnectionState) -> None:
        """Update connection state and refresh display."""
        self._state = state
        color = STATE_COLORS.get(state, "#71717a")
        self._update_dot_color(color)
        self._refresh_text()

    def update_current_app(self, app_id: str | None) -> None:
        """Update active app package name."""
        self._current_app = app_id
        self._refresh_text()

    def update_volume(self, volume: VolumeState | None) -> None:
        """Update volume level and mute state."""
        self._volume = volume
        self._refresh_text()

    def _update_dot_color(self, hex_color: str) -> None:
        self._dot.setStyleSheet(f"color: {hex_color}; font-size: 13px;")

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

        self._label.setText(" · ".join(parts))

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
