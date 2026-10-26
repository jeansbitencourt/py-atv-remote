"""Modal dialog for entering TV pairing PIN built with CustomTkinter."""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from py_atv_remote.domain.errors import InvalidPinError, PairingFailedError
from py_atv_remote.domain.models import TvProfile
from py_atv_remote.services.async_runner import AsyncRunner
from py_atv_remote.services.pairing_service import PairingService, PairingSession

LOGGER = logging.getLogger(__name__)


class PairDialog(ctk.CTkToplevel):
    """Modal dialog prompting the user to type the PIN displayed on the TV."""

    def __init__(
        self,
        parent: tk.Misc,
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
        if isinstance(parent, (tk.Tk, tk.Toplevel)):
            self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_ui(self) -> None:
        frame = ctk.CTkFrame(self, corner_radius=12, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=20)

        header = ctk.CTkLabel(
            frame,
            text=f"Pareando com {self._session.target_name}",
            font=("Liberation Sans", 14, "bold"),
        )
        header.pack(pady=(0, 6))

        info = ctk.CTkLabel(
            frame,
            text=f"IP: {self._session.host}\nDigite o código de pareamento exibido na tela da TV:",
            justify="center",
            font=("Liberation Sans", 11),
            text_color=("#52525b", "#a1a1aa"),
        )
        info.pack(pady=(0, 14))

        self._pin_var = tk.StringVar()
        self._pin_entry = ctk.CTkEntry(
            frame,
            textvariable=self._pin_var,
            font=("monospace", 22, "bold"),
            justify="center",
            width=180,
            height=46,
            corner_radius=10,
        )
        self._pin_entry.pack(pady=(0, 10))
        self._pin_entry.focus_set()
        self._pin_entry.bind("<Return>", lambda _e: self._on_submit())
        self._pin_entry.bind("<Escape>", lambda _e: self._on_cancel())

        self._status_var = tk.StringVar(value="")
        self._status_lbl = ctk.CTkLabel(
            frame,
            textvariable=self._status_var,
            text_color="#ef4444",
            font=("Liberation Sans", 10),
        )
        self._status_lbl.pack(pady=(0, 12))

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x")

        self._btn_cancel = ctk.CTkButton(
            btn_frame,
            text="Cancelar",
            fg_color=("#d4d4d8", "#3f3f46"),
            hover_color=("#a1a1aa", "#52525b"),
            text_color=("#18181b", "#f4f4f5"),
            corner_radius=8,
            height=34,
            command=self._on_cancel,
        )
        self._btn_cancel.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self._btn_submit = ctk.CTkButton(
            btn_frame,
            text="Confirmar PIN",
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            corner_radius=8,
            height=34,
            font=("Liberation Sans", 11, "bold"),
            command=self._on_submit,
        )
        self._btn_submit.pack(side="right", expand=True, fill="x", padx=(6, 0))

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
        state = "disabled" if loading else "normal"
        self._btn_submit.configure(state=state)
        self._btn_cancel.configure(state=state)
        self._pin_entry.configure(state=state)

    def _on_cancel(self) -> None:
        self._pairing_service.cancel_pairing(self._session)
        self.destroy()
