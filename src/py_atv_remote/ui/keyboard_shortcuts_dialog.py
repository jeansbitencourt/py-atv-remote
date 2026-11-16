"""Modal help dialog listing the physical keyboard shortcuts."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

SHORTCUT_ROWS: tuple[tuple[str, str], ...] = (
    ("↑  ↓  ←  →", "Navegar pelo D-Pad"),
    ("Enter / Enter numérico", "Selecionar / OK"),
    ("Esc / Backspace", "Voltar"),
    ("Home / H", "Tela inicial"),
    ("I", "Alternar entradas"),
    ("P", "Ligar ou desligar a TV"),
    ("Espaço", "Reproduzir / pausar"),
    ("J / L", "Rebobinar / avançar"),
    ("+ / = / + numérico", "Aumentar volume"),
    ("- / - numérico", "Diminuir volume"),
    ("M", "Alternar mudo"),
)


class KeyboardShortcutsDialog(QtWidgets.QDialog):
    """Show the keyboard shortcuts available in the main remote window."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Atalhos do Teclado")
        self.setModal(True)
        self.setMinimumWidth(440)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        heading = QtWidgets.QLabel("Consulte os atalhos do controle remoto:", self)
        heading.setStyleSheet("font-size: 12px; font-weight: bold; color: #ffffff;")
        layout.addWidget(heading)

        self._table = QtWidgets.QTableWidget(len(SHORTCUT_ROWS), 2, self)
        self._table.setHorizontalHeaderLabels(["Tecla", "Ação"])
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        if (horizontal_header := self._table.horizontalHeader()) is not None:
            horizontal_header.setStretchLastSection(True)
        if (vertical_header := self._table.verticalHeader()) is not None:
            vertical_header.setVisible(False)

        for row_index, (key, action) in enumerate(SHORTCUT_ROWS):
            self._table.setItem(row_index, 0, QtWidgets.QTableWidgetItem(key))
            self._table.setItem(row_index, 1, QtWidgets.QTableWidgetItem(action))

        self._table.resizeColumnsToContents()
        layout.addWidget(self._table)

        note = QtWidgets.QLabel(
            "Os atalhos funcionam com a janela principal ativa. No campo de texto, "
            "as teclas continuam editando o conteúdo; Enter envia o texto e Esc tira "
            "o foco. P também pode tentar Wake-on-LAN quando a TV está offline.",
            self,
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #a1a1aa; font-size: 10px;")
        layout.addWidget(note)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close,
            parent=self,
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
