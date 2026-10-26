"""Dialog for configuring TV application shortcuts built with CustomTkinter."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, simpledialog, ttk
from typing import Any

import customtkinter as ctk

from py_atv_remote.domain.models import AppShortcut
from py_atv_remote.infrastructure.config_store import DEFAULT_APP_SHORTCUTS, ConfigStore


class ShortcutsDialog(ctk.CTkToplevel):
    """Dialog allowing users to customize app launcher shortcuts."""

    def __init__(
        self,
        parent: tk.Misc,
        config_store: ConfigStore,
        on_saved: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._config_store = config_store
        self._on_saved = on_saved

        self.title("Editar Atalhos de Apps")
        if isinstance(parent, (tk.Tk, tk.Toplevel)):
            self.transient(parent)
        self.minsize(480, 320)

        self._shortcuts: list[AppShortcut] = list(self._config_store.get_app_shortcuts())

        self._build_ui()
        self._refresh_tree()

    def _build_ui(self) -> None:
        btn_common: dict[str, Any] = {
            "fg_color": ("#d4d4d8", "#3f3f46"),
            "hover_color": ("#a1a1aa", "#52525b"),
            "text_color": ("#18181b", "#f4f4f5"),
            "corner_radius": 8,
            "height": 32,
            "font": ("Liberation Sans", 11),
        }

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        info = ctk.CTkLabel(
            frame,
            text="Atalhos rápidos para abrir aplicativos na TV:",
            font=("Liberation Sans", 12, "bold"),
            anchor="w",
        )
        info.pack(fill="x", pady=(0, 8))

        content_row = ctk.CTkFrame(frame, fg_color="transparent")
        content_row.pack(fill="both", expand=True)

        columns = ("label", "link")
        self._tree = ttk.Treeview(
            content_row,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=8,
        )
        self._tree.heading("label", text="Nome do App")
        self._tree.heading("link", text="Link / ID do Pacote")
        self._tree.column("label", width=130)
        self._tree.column("link", width=230)

        tree_scroll = ttk.Scrollbar(content_row, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=tree_scroll.set)

        self._tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="left", fill="y", padx=(0, 10))

        btn_panel = ctk.CTkFrame(content_row, fg_color="transparent")
        btn_panel.pack(side="right", fill="y")

        self._btn_add = ctk.CTkButton(
            btn_panel,
            text="Adicionar…",
            command=self._on_add,
            **btn_common,
        )
        self._btn_add.pack(fill="x", pady=(0, 6))

        self._btn_edit = ctk.CTkButton(
            btn_panel,
            text="Editar…",
            command=self._on_edit,
            **btn_common,
        )
        self._btn_edit.pack(fill="x", pady=(0, 6))

        self._btn_remove = ctk.CTkButton(
            btn_panel,
            text="Remover",
            command=self._on_remove,
            **btn_common,
        )
        self._btn_remove.pack(fill="x", pady=(0, 12))

        self._btn_reset = ctk.CTkButton(
            btn_panel,
            text="Padrões",
            command=self._on_reset,
            **btn_common,
        )
        self._btn_reset.pack(fill="x", pady=(0, 6))

        self._btn_save = ctk.CTkButton(
            btn_panel,
            text="Salvar",
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            corner_radius=8,
            height=32,
            font=("Liberation Sans", 11, "bold"),
            command=self._on_save,
        )
        self._btn_save.pack(fill="x", side="bottom")

    def _refresh_tree(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for idx, item in enumerate(self._shortcuts):
            self._tree.insert("", tk.END, iid=str(idx), values=(item.label, item.link))

    def _on_add(self) -> None:
        label = simpledialog.askstring(
            "Novo Atalho",
            "Nome do App (ex: YouTube, Spotify):",
            parent=self,
        )
        if not label or not label.strip():
            return
        msg = (
            "Link web ou ID do pacote Android:\n"
            "(Ex: https://www.youtube.com ou com.spotify.tv.android):"
        )
        link = simpledialog.askstring("Link ou Pacote", msg, parent=self)
        if not link or not link.strip():
            return

        self._shortcuts.append(AppShortcut(label=label.strip(), link=link.strip()))
        self._refresh_tree()

    def _on_edit(self) -> None:
        selection = self._tree.selection()
        if not selection:
            messagebox.showinfo("Seleção", "Selecione um atalho para editar.", parent=self)
            return

        idx = int(selection[0])
        current = self._shortcuts[idx]

        new_label = simpledialog.askstring(
            "Editar Atalho",
            "Nome do App:",
            initialvalue=current.label,
            parent=self,
        )
        if not new_label or not new_label.strip():
            return

        new_link = simpledialog.askstring(
            "Editar Link",
            "Link ou ID do pacote:",
            initialvalue=current.link,
            parent=self,
        )
        if not new_link or not new_link.strip():
            return

        self._shortcuts[idx] = AppShortcut(label=new_label.strip(), link=new_link.strip())
        self._refresh_tree()

    def _on_remove(self) -> None:
        selection = self._tree.selection()
        if not selection:
            messagebox.showinfo("Seleção", "Selecione um atalho para remover.", parent=self)
            return

        idx = int(selection[0])
        del self._shortcuts[idx]
        self._refresh_tree()

    def _on_reset(self) -> None:
        self._shortcuts = list(DEFAULT_APP_SHORTCUTS)
        self._refresh_tree()

    def _on_save(self) -> None:
        self._config_store.set_app_shortcuts(self._shortcuts)
        self._on_saved()
        self.destroy()
