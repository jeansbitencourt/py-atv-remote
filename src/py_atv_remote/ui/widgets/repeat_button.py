"""Button widget supporting repeated firing while held down using Qt auto-repeat."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6 import QtWidgets


class RepeatButton(QtWidgets.QPushButton):
    """QPushButton subclass that fires repeatedly while pressed down."""

    def __init__(
        self,
        text: str = "",
        parent: QtWidgets.QWidget | None = None,
        command: Callable[[], None] | None = None,
        initial_delay_ms: int = 400,
        repeat_interval_ms: int = 110,
    ) -> None:
        super().__init__(text, parent)
        self.setAutoRepeat(True)
        self.setAutoRepeatDelay(initial_delay_ms)
        self.setAutoRepeatInterval(repeat_interval_ms)

        if command:
            self.clicked.connect(command)
