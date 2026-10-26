"""Visual D-Pad navigation control widget built with PyQt6."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6 import QtCore, QtWidgets

from py_atv_remote.domain.keys import RemoteKey
from py_atv_remote.ui.widgets.repeat_button import RepeatButton


class DPad(QtWidgets.QWidget):
    """Directional pad (▲, ◄, OK, ►, ▼) with repeat-on-hold for arrows."""

    def __init__(
        self,
        on_key: Callable[[RemoteKey], None],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_key = on_key

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        btn_size = QtCore.QSize(54, 42)

        # Row 0: Up
        self.btn_up = RepeatButton("▲", self, command=lambda: self._on_key(RemoteKey.DPAD_UP))
        self.btn_up.setObjectName("dpadArrow")
        self.btn_up.setFixedSize(btn_size)
        layout.addWidget(self.btn_up, 0, 1)

        # Row 1: Left, OK, Right
        self.btn_left = RepeatButton("◄", self, command=lambda: self._on_key(RemoteKey.DPAD_LEFT))
        self.btn_left.setObjectName("dpadArrow")
        self.btn_left.setFixedSize(btn_size)
        layout.addWidget(self.btn_left, 1, 0)

        self.btn_center = QtWidgets.QPushButton("OK", self)
        self.btn_center.setObjectName("dpadCenter")
        self.btn_center.setFixedSize(btn_size)
        self.btn_center.clicked.connect(lambda: self._on_key(RemoteKey.DPAD_CENTER))
        layout.addWidget(self.btn_center, 1, 1)

        self.btn_right = RepeatButton("►", self, command=lambda: self._on_key(RemoteKey.DPAD_RIGHT))
        self.btn_right.setObjectName("dpadArrow")
        self.btn_right.setFixedSize(btn_size)
        layout.addWidget(self.btn_right, 1, 2)

        # Row 2: Down
        self.btn_down = RepeatButton("▼", self, command=lambda: self._on_key(RemoteKey.DPAD_DOWN))
        self.btn_down.setObjectName("dpadArrow")
        self.btn_down.setFixedSize(btn_size)
        layout.addWidget(self.btn_down, 2, 1)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable all DPad buttons."""
        for btn in (self.btn_up, self.btn_left, self.btn_center, self.btn_right, self.btn_down):
            btn.setEnabled(enabled)
