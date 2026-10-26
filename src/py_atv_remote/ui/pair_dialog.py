"""Modal dialog for entering TV pairing PIN."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from py_atv_remote.domain.errors import InvalidPinError, PairingFailedError
from py_atv_remote.domain.models import TvProfile
from py_atv_remote.services.async_runner import AsyncRunner
from py_atv_remote.services.pairing_service import PairingService, PairingSession

LOGGER = logging.getLogger(__name__)


class PairDialog(tk.Toplevel):
    """Modal dialog prompting the user to type the PIN displayed on the TV."""

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
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

        self.title("Pareamento de TV")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Label(
            frame,
            text=f"Pareando com {self._session.target_name}",
            font=("sans-serif", 12, "bold"),
        )
        header.pack(pady=(0, 6))

        info = ttk.Label(
            frame,
            text=f"IP: {self._session.host}\nDigite o código de pareamento exibido na tela da TV:",
            justify=tk.CENTER,
        )
        info.pack(pady=(0, 12))

        self._pin_var = tk.StringVar()
        self._pin_entry = ttk.Entry(
            frame,
            textvariable=self._pin_var,
            font=("monospace", 18, "bold"),
            justify=tk.CENTER,
            width=10,
        )
        self._pin_entry.pack(pady=(0, 10))
        self._pin_entry.focus_set()
        self._pin_entry.bind("<Return>", lambda _e: self._on_submit())
        self._pin_entry.bind("<Escape>", lambda _e: self._on_cancel())

        self._status_var = tk.StringVar(value="")
        self._status_lbl = ttk.Label(
            frame,
            textvariable=self._status_var,
            foreground="#c0392b",
            font=("sans-serif", 9),
        )
        self._status_lbl.pack(pady=(0, 12))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)

        self._btn_cancel = ttk.Button(btn_frame, text="Cancelar", command=self._on_cancel)
        self._btn_cancel.pack(side=tk.LEFT, expand=True, padx=4)

        self._btn_submit = ttk.Button(btn_frame, text="Confirmar PIN", command=self._on_submit)
        self._btn_submit.pack(side=tk.RIGHT, expand=True, padx=4)

    def _on_submit(self) -> None:
        pin = self._pin_var.get().strip().upper()
        if not pin:
            self._status_var.set("Digite o PIN exibido na TV.")
            return

        self._set_loading(True)
        self._status_var.set("Verificando PIN…")

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
        self.destroy()

    def _show_error(self, message: str) -> None:
        self._set_loading(False)
        self._status_var.set(message)
        self._pin_entry.focus_set()

    def _set_loading(self, loading: bool) -> None:
        state = tk.DISABLED if loading else tk.NORMAL
        self._btn_submit["state"] = state
        self._btn_cancel["state"] = state
        self._pin_entry["state"] = state

    def _on_cancel(self) -> None:
        self._pairing_service.cancel_pairing(self._session)
        self.destroy()
