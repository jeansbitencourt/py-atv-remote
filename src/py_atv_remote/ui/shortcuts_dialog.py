"""Dialog for configuring TV application shortcuts built with PyQt6."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6 import QtWidgets

from py_atv_remote.domain.models import AppShortcut
from py_atv_remote.infrastructure.config_store import DEFAULT_APP_SHORTCUTS, ConfigStore


class ShortcutsDialog(QtWidgets.QDialog):
    """Dialog allowing users to customize app launcher shortcuts."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        config_store: ConfigStore,
        on_saved: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._config_store = config_store
        self._on_saved = on_saved

        self.setWindowTitle("Editar Atalhos de Apps")
        self.setModal(True)
        self.resize(500, 320)

        self._shortcuts: list[AppShortcut] = list(self._config_store.get_app_shortcuts())

        self._build_ui()
        self._refresh_table()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        info = QtWidgets.QLabel("Atalhos rápidos para abrir aplicativos na TV:", self)
        info.setStyleSheet("font-size: 12px; font-weight: bold; color: #ffffff;")
        layout.addWidget(info)

        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setSpacing(10)

        # Table
        self._table = QtWidgets.QTableWidget(0, 2, self)
        self._table.setHorizontalHeaderLabels(["Nome do App", "Link / ID do Pacote"])
        if (h_header := self._table.horizontalHeader()) is not None:
            h_header.setStretchLastSection(True)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setColumnWidth(0, 150)
        if (v_header := self._table.verticalHeader()) is not None:
            v_header.setVisible(False)
        content_layout.addWidget(self._table, stretch=1)

        # Buttons Panel
        btn_panel = QtWidgets.QVBoxLayout()
        btn_panel.setSpacing(6)

        self._btn_add = QtWidgets.QPushButton("Adicionar…", self)
        self._btn_add.clicked.connect(self._on_add)
        btn_panel.addWidget(self._btn_add)

        self._btn_edit = QtWidgets.QPushButton("Editar…", self)
        self._btn_edit.clicked.connect(self._on_edit)
        btn_panel.addWidget(self._btn_edit)

        self._btn_remove = QtWidgets.QPushButton("Remover", self)
        self._btn_remove.clicked.connect(self._on_remove)
        btn_panel.addWidget(self._btn_remove)

        btn_panel.addSpacing(10)

        self._btn_reset = QtWidgets.QPushButton("Padrões", self)
        self._btn_reset.clicked.connect(self._on_reset)
        btn_panel.addWidget(self._btn_reset)

        btn_panel.addStretch(1)

        self._btn_save = QtWidgets.QPushButton("Salvar", self)
        self._btn_save.setObjectName("primaryButton")
        self._btn_save.clicked.connect(self._on_save)
        btn_panel.addWidget(self._btn_save)

        content_layout.addLayout(btn_panel)
        layout.addLayout(content_layout)

    def _refresh_table(self) -> None:
        self._table.setRowCount(0)
        for row_idx, item in enumerate(self._shortcuts):
            self._table.insertRow(row_idx)
            item_label = QtWidgets.QTableWidgetItem(item.label)
            item_link = QtWidgets.QTableWidgetItem(item.link)
            self._table.setItem(row_idx, 0, item_label)
            self._table.setItem(row_idx, 1, item_link)

    def _get_selected_index(self) -> int | None:
        sel_model = self._table.selectionModel()
        if sel_model is None:
            return None
        rows = sel_model.selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def _on_add(self) -> None:
        label, ok = QtWidgets.QInputDialog.getText(
            self, "Novo Atalho", "Nome do App (ex: YouTube, Spotify):"
        )
        if not ok or not label.strip():
            return

        msg = (
            "Link web ou ID do pacote Android:\n"
            "(Ex: https://www.youtube.com ou com.spotify.tv.android):"
        )
        link, ok = QtWidgets.QInputDialog.getText(self, "Link ou Pacote", msg)
        if not ok or not link.strip():
            return

        self._shortcuts.append(AppShortcut(label=label.strip(), link=link.strip()))
        self._refresh_table()

    def _on_edit(self) -> None:
        idx = self._get_selected_index()
        if idx is None:
            QtWidgets.QMessageBox.information(self, "Seleção", "Selecione um atalho para editar.")
            return

        current = self._shortcuts[idx]
        new_label, ok = QtWidgets.QInputDialog.getText(
            self, "Editar Atalho", "Nome do App:", text=current.label
        )
        if not ok or not new_label.strip():
            return

        new_link, ok = QtWidgets.QInputDialog.getText(
            self, "Editar Link", "Link ou ID do pacote:", text=current.link
        )
        if not ok or not new_link.strip():
            return

        self._shortcuts[idx] = AppShortcut(label=new_label.strip(), link=new_link.strip())
        self._refresh_table()

    def _on_remove(self) -> None:
        idx = self._get_selected_index()
        if idx is None:
            QtWidgets.QMessageBox.information(self, "Seleção", "Selecione um atalho para remover.")
            return

        del self._shortcuts[idx]
        self._refresh_table()

    def _on_reset(self) -> None:
        self._shortcuts = list(DEFAULT_APP_SHORTCUTS)
        self._refresh_table()

    def _on_save(self) -> None:
        self._config_store.set_app_shortcuts(self._shortcuts)
        self._on_saved()
        self.accept()
