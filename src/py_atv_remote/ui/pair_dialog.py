"""Modal dialog for entering TV pairing PIN built with PyQt6."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PyQt6 import QtCore, QtGui, QtWidgets

from py_atv_remote.domain.errors import InvalidPinError, PairingFailedError
from py_atv_remote.domain.models import TvProfile
from py_atv_remote.services.async_runner import AsyncRunner
from py_atv_remote.services.pairing_service import PairingService, PairingSession

LOGGER = logging.getLogger(__name__)


class PairDialog(QtWidgets.QDialog):
    """Modal dialog prompting the user to type the PIN displayed on the TV."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        pairing_service: PairingService,
        pairing_session: PairingSession,
        async_runner: AsyncRunner,
        on_success: Callable[[TvProfile], None],
    ) -> None:
        super().__init__(parent)
        self._pairing_service = pairing_service
        self._session = pairing_session
        self._runner = async_runner
        self._on_success = on_success

        self.setWindowTitle("Pareamento de TV")
        self.setModal(True)
        self.setFixedSize(360, 240)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        header = QtWidgets.QLabel(f"Pareando com {self._session.target_name}", self)
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        info = QtWidgets.QLabel(
            f"IP: {self._session.host}\nDigite o código de pareamento exibido na tela da TV:",
            self,
        )
        info.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        info.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        self._pin_entry = QtWidgets.QLineEdit(self)
        self._pin_entry.setMaxLength(8)
        self._pin_entry.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._pin_entry.setStyleSheet(
            "font-family: monospace; font-size: 22px; font-weight: bold; "
            "padding: 6px; letter-spacing: 4px;"
        )
        self._pin_entry.returnPressed.connect(self._on_submit)
        layout.addWidget(self._pin_entry)

        self._status_lbl = QtWidgets.QLabel("", self)
        self._status_lbl.setStyleSheet("color: #ef4444; font-size: 10px;")
        self._status_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_lbl)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(10)

        self._btn_cancel = QtWidgets.QPushButton("Cancelar", self)
        self._btn_cancel.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self._btn_cancel)

        self._btn_submit = QtWidgets.QPushButton("Confirmar PIN", self)
        self._btn_submit.setObjectName("primaryButton")
        self._btn_submit.clicked.connect(self._on_submit)
        btn_layout.addWidget(self._btn_submit)

        layout.addLayout(btn_layout)
        self._pin_entry.setFocus()

    def _on_submit(self) -> None:
        pin = self._pin_entry.text().strip().upper()
        if not pin:
            self._status_lbl.setText("Digite o PIN exibido na TV.")
            return

        self._set_loading(True)
        self._status_lbl.setText("Verificando PIN…")

        async def _do_finish() -> None:
            try:
                profile = await self._pairing_service.finish_pairing(self._session, pin)
                self._runner.call_soon(lambda: self._finish_success(profile))
            except InvalidPinError:
                self._runner.call_soon(
                    lambda: self._show_error("PIN incorreto. Verifique e tente novamente.")
                )
            except PairingFailedError as exc:
                err_text = f"Falha no pareamento: {exc}"
                self._runner.call_soon(lambda: self._show_error(err_text))
            except Exception as exc:
                err_text = f"Erro inesperado: {exc}"
                self._runner.call_soon(lambda: self._show_error(err_text))

        self._runner.submit(_do_finish())

    def _finish_success(self, profile: TvProfile) -> None:
        self._on_success(profile)
        self.accept()

    def _show_error(self, message: str) -> None:
        self._set_loading(False)
        self._status_lbl.setText(message)
        self._pin_entry.setFocus()

    def _set_loading(self, loading: bool) -> None:
        self._btn_submit.setEnabled(not loading)
        self._btn_cancel.setEnabled(not loading)
        self._pin_entry.setEnabled(not loading)

    def _on_cancel(self) -> None:
        self._pairing_service.cancel_pairing(self._session)
        self.reject()

    def reject(self) -> None:
        self._on_cancel()

    def keyPressEvent(self, event: QtGui.QKeyEvent | None) -> None:
        if event is not None and event.key() == QtCore.Qt.Key.Key_Escape.value:
            self._on_cancel()
        elif event is not None:
            super().keyPressEvent(event)
