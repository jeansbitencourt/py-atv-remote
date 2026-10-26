"""Dialog for configuring TV application shortcuts."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, simpledialog, ttk

from py_atv_remote.domain.models import AppShortcut
from py_atv_remote.infrastructure.config_store import DEFAULT_APP_SHORTCUTS, ConfigStore


class ShortcutsDialog(tk.Toplevel):
    """Dialog allowing users to customize app launcher shortcuts."""

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
        config_store: ConfigStore,
        on_saved: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._config_store = config_store
        self._on_saved = on_saved

        self.title("Editar Atalhos de Apps")
        self.transient(parent)
        self.minsize(450, 300)

        self._shortcuts: list[AppShortcut] = list(self._config_store.get_app_shortcuts())

        self._build_ui()
        self._refresh_tree()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        info = ttk.Label(
            frame,
            text="Atalhos rápidos para abrir aplicativos na TV:",
            font=("sans-serif", 10, "bold"),
        )
        info.pack(anchor=tk.W, pady=(0, 6))

        columns = ("label", "link")
        self._tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=7,
        )
        self._tree.heading("label", text="Nome do App")
        self._tree.heading("link", text="Link / ID do Pacote")
        self._tree.column("label", width=120)
        self._tree.column("link", width=240)

        tree_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=tree_scroll.set)

        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        btn_panel = ttk.Frame(frame)
        btn_panel.pack(side=tk.RIGHT, fill=tk.Y)

        self._btn_add = ttk.Button(btn_panel, text="Adicionar…", command=self._on_add)
        self._btn_add.pack(fill=tk.X, pady=(0, 4))

        self._btn_edit = ttk.Button(btn_panel, text="Editar…", command=self._on_edit)
        self._btn_edit.pack(fill=tk.X, pady=(0, 4))

        self._btn_remove = ttk.Button(btn_panel, text="Remover", command=self._on_remove)
        self._btn_remove.pack(fill=tk.X, pady=(0, 14))

        self._btn_reset = ttk.Button(btn_panel, text="Padrões", command=self._on_reset)
        self._btn_reset.pack(fill=tk.X, pady=(0, 4))

        self._btn_save = ttk.Button(btn_panel, text="Salvar", command=self._on_save)
        self._btn_save.pack(fill=tk.X, side=tk.BOTTOM)

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
