"""Device manager dialog for listing, discovering, renaming, and pairing TVs."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PyQt6 import QtGui, QtWidgets

from py_atv_remote.domain.errors import TvUnreachableError
from py_atv_remote.domain.models import DiscoveredTv, TvProfile
from py_atv_remote.infrastructure.cert_store import CertStore
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.services.async_runner import AsyncRunner
from py_atv_remote.services.discovery_service import DiscoveryService
from py_atv_remote.services.events import EventBus
from py_atv_remote.services.pairing_service import PairingService, PairingSession
from py_atv_remote.services.remote_session import RemoteSessionService
from py_atv_remote.ui.pair_dialog import PairDialog

LOGGER = logging.getLogger(__name__)


class DeviceManager(QtWidgets.QDialog):
    """Dialog allowing users to view discovered TVs, pair new devices, and manage saved profiles."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        config_store: ConfigStore,
        cert_store: CertStore,
        discovery_service: DiscoveryService,
        pairing_service: PairingService,
        remote_session: RemoteSessionService,
        event_bus: EventBus,
        async_runner: AsyncRunner,
        on_tv_selected: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self._config_store = config_store
        self._cert_store = cert_store
        self._discovery = discovery_service
        self._pairing = pairing_service
        self._session = remote_session
        self._event_bus = event_bus
        self._runner = async_runner
        self._on_tv_selected = on_tv_selected

        self.setWindowTitle("Gerenciador de Android TVs")
        self.setModal(True)
        self.resize(650, 400)

        self._items: dict[int, DiscoveredTv | TvProfile] = {}

        self._build_ui()
        self._setup_events()
        self._refresh_list()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QtWidgets.QLabel("TVs Encontradas na Rede e Cadastradas", self)
        header.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setSpacing(10)

        # Table
        self._table = QtWidgets.QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(["Nome", "Endereço IP", "Status", "ID / MAC"])
        if (h_header := self._table.horizontalHeader()) is not None:
            h_header.setStretchLastSection(True)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setColumnWidth(0, 180)
        self._table.setColumnWidth(1, 120)
        self._table.setColumnWidth(2, 160)
        if (v_header := self._table.verticalHeader()) is not None:
            v_header.setVisible(False)
        self._table.itemDoubleClicked.connect(lambda _item: self._on_double_click())
        content_layout.addWidget(self._table, stretch=1)

        # Buttons Panel
        btn_panel = QtWidgets.QVBoxLayout()
        btn_panel.setSpacing(6)

        self._btn_use = QtWidgets.QPushButton("Usar esta TV", self)
        self._btn_use.setObjectName("primaryButton")
        self._btn_use.clicked.connect(self._on_use_clicked)
        btn_panel.addWidget(self._btn_use)

        self._btn_pair = QtWidgets.QPushButton("Parear TV…", self)
        self._btn_pair.clicked.connect(self._on_pair_clicked)
        btn_panel.addWidget(self._btn_pair)

        self._btn_rename = QtWidgets.QPushButton("Renomear…", self)
        self._btn_rename.clicked.connect(self._on_rename_clicked)
        btn_panel.addWidget(self._btn_rename)

        self._btn_forget = QtWidgets.QPushButton("Esquecer TV", self)
        self._btn_forget.setObjectName("dangerButton")
        self._btn_forget.clicked.connect(self._on_forget_clicked)
        btn_panel.addWidget(self._btn_forget)

        btn_panel.addSpacing(10)

        self._btn_add_ip = QtWidgets.QPushButton("Adicionar por IP…", self)
        self._btn_add_ip.clicked.connect(self._on_add_ip_clicked)
        btn_panel.addWidget(self._btn_add_ip)

        self._btn_scan = QtWidgets.QPushButton("Varredura Completa", self)
        self._btn_scan.clicked.connect(self._on_scan_clicked)
        btn_panel.addWidget(self._btn_scan)

        btn_panel.addStretch(1)

        content_layout.addLayout(btn_panel)
        layout.addLayout(content_layout)

        # Status Label
        self._status_lbl = QtWidgets.QLabel("Varredura mDNS ativa em segundo plano.", self)
        self._status_lbl.setStyleSheet("color: #a1a1aa; font-size: 10px;")
        layout.addWidget(self._status_lbl)

    def _setup_events(self) -> None:
        self._unsub_disc = self._event_bus.on_tv_discovered(lambda _tv: self._refresh_list())
        self._unsub_disp = self._event_bus.on_tv_disappeared(lambda _id: self._refresh_list())

    def closeEvent(self, event: QtGui.QCloseEvent | None) -> None:
        self._unsub_disc()
        self._unsub_disp()
        if event is not None:
            super().closeEvent(event)

    def _refresh_list(self) -> None:
        self._table.setRowCount(0)
        self._items.clear()

        saved_tvs = {tv.id: tv for tv in self._config_store.list_tvs()}
        discovered_tvs = {tv.id or tv.host: tv for tv in self._discovery.discovered_tvs}

        row_idx = 0

        # 1. Add saved TVs
        for tv_id, profile in saved_tvs.items():
            disc = discovered_tvs.get(tv_id)
            has_certs = self._cert_store.has_certs(tv_id)

            if not has_certs:
                status = "Pareamento Pendente"
            elif self._session.current_profile and self._session.current_profile.id == tv_id:
                status = f"Ativa ({self._session.state.value})"
            elif disc is not None:
                status = "Na rede (Standby)" if disc.in_standby else "Na rede (Online)"
            else:
                status = "Cadastrada (Offline)"

            host = disc.host if disc else profile.host
            self._table.insertRow(row_idx)
            self._table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(profile.name))
            self._table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(host))
            self._table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(status))
            self._table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(tv_id))
            self._items[row_idx] = profile
            row_idx += 1

        # 2. Add un-paired discovered TVs
        for _disc_key, disc_tv in discovered_tvs.items():
            if disc_tv.id and disc_tv.id in saved_tvs:
                continue

            status = "Nova TV encontrada"
            if disc_tv.in_standby:
                status = "Nova (Standby)"

            self._table.insertRow(row_idx)
            self._table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(disc_tv.name))
            self._table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(disc_tv.host))
            self._table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(status))
            self._table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(disc_tv.id or "-"))
            self._items[row_idx] = disc_tv
            row_idx += 1

    def _get_selected_item(self) -> DiscoveredTv | TvProfile | None:
        sel_model = self._table.selectionModel()
        if sel_model is None:
            return None
        rows = sel_model.selectedRows()
        if not rows:
            return None
        return self._items.get(rows[0].row())

    def _on_use_clicked(self) -> None:
        item = self._get_selected_item()
        if not item:
            QtWidgets.QMessageBox.information(
                self, "Seleção", "Selecione uma TV na lista para usar."
            )
            return

        if isinstance(item, TvProfile):
            self._on_tv_selected(item.id)
            self.accept()
        else:
            res = QtWidgets.QMessageBox.question(
                self,
                "Pareamento Necessário",
                f"A TV '{item.name}' ainda não está pareada. Deseja pareá-la agora?",
            )
            if res == QtWidgets.QMessageBox.StandardButton.Yes:
                self._start_pairing_flow(item)

    def _on_double_click(self) -> None:
        self._on_use_clicked()

    def _on_pair_clicked(self) -> None:
        item = self._get_selected_item()
        if not item:
            QtWidgets.QMessageBox.information(
                self, "Seleção", "Selecione uma TV na lista para parear."
            )
            return
        self._start_pairing_flow(item)

    def _start_pairing_flow(self, target: DiscoveredTv | TvProfile) -> None:
        self._status_lbl.setText(f"Iniciando pareamento com {target.name}…")

        async def _do_start() -> None:
            try:
                session = await self._pairing.start_pairing(target)
                self._runner.call_soon(lambda: self._open_pair_dialog(session))
            except TvUnreachableError as exc:
                err_text = str(exc)
                self._runner.call_soon(
                    lambda: QtWidgets.QMessageBox.critical(self, "TV Inacessível", err_text)
                )
            except Exception as exc:
                err_text = str(exc)
                self._runner.call_soon(
                    lambda: QtWidgets.QMessageBox.critical(self, "Erro de Pareamento", err_text)
                )
            finally:
                self._runner.call_soon(
                    lambda: self._status_lbl.setText("Varredura mDNS ativa em segundo plano.")
                )

        self._runner.submit(_do_start())

    def _open_pair_dialog(self, session: PairingSession) -> None:
        dialog = PairDialog(
            parent=self,
            pairing_service=self._pairing,
            pairing_session=session,
            async_runner=self._runner,
            on_success=self._on_pair_success,
        )
        dialog.exec()

    def _on_pair_success(self, profile: TvProfile) -> None:
        self._refresh_list()
        QtWidgets.QMessageBox.information(
            self,
            "Sucesso",
            f"A TV '{profile.name}' foi pareada com sucesso!",
        )
        self._on_tv_selected(profile.id)
        self.accept()

    def _on_rename_clicked(self) -> None:
        item = self._get_selected_item()
        if not isinstance(item, TvProfile):
            QtWidgets.QMessageBox.information(
                self, "Renomear", "Selecione uma TV já cadastrada para renomear."
            )
            return

        new_name, ok = QtWidgets.QInputDialog.getText(
            self, "Renomear TV", f"Novo nome para '{item.name}':", text=item.name
        )
        if ok and new_name.strip():
            updated = item.with_name(new_name.strip())
            self._config_store.save_tv(updated)
            self._refresh_list()
            self._on_tv_selected(updated.id)

    def _on_forget_clicked(self) -> None:
        item = self._get_selected_item()
        if not isinstance(item, TvProfile):
            QtWidgets.QMessageBox.information(
                self, "Esquecer TV", "Selecione uma TV cadastrada para remover."
            )
            return

        res = QtWidgets.QMessageBox.question(
            self,
            "Confirmar Remoção",
            f"Deseja esquecer e remover os certificados da TV '{item.name}'?\n"
            "Será necessário parear novamente para controlá-la.",
        )
        if res != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        if self._session.current_profile and self._session.current_profile.id == item.id:
            self._session.disconnect()

        self._config_store.delete_tv(item.id)
        self._cert_store.delete_certs(item.id)
        self._refresh_list()
        self._on_tv_selected("")

    def _on_add_ip_clicked(self) -> None:
        ip_addr, ok = QtWidgets.QInputDialog.getText(
            self,
            "Adicionar TV por IP",
            "Digite o endereço IPv4 da Android TV:\n(Ex: 192.168.2.104)",
        )
        if not ok or not ip_addr.strip():
            return

        host = ip_addr.strip()
        self._status_lbl.setText(f"Verificando {host}:6466…")

        async def _probe() -> None:
            try:
                tv = await self._discovery.probe_manual(host)
                self._runner.call_soon(lambda: self._start_pairing_flow(tv))
            except TvUnreachableError:
                self._runner.call_soon(
                    lambda: QtWidgets.QMessageBox.critical(
                        self,
                        "TV Inacessível",
                        f"Não foi possível conectar em {host}:6466.\n"
                        "Verifique se o IP está correto e a TV está ligada na mesma rede Wi-Fi.",
                    )
                )
            finally:
                self._runner.call_soon(
                    lambda: self._status_lbl.setText("Varredura mDNS ativa em segundo plano.")
                )

        self._runner.submit(_probe())

    def _on_scan_clicked(self) -> None:
        self._status_lbl.setText("Executando varredura TCP na sub-rede…")
        self._btn_scan.setEnabled(False)

        async def _do_scan() -> None:
            try:
                await self._discovery.full_scan()
                self._runner.call_soon(self._refresh_list)
            finally:
                self._runner.call_soon(self._on_scan_finished)

        self._runner.submit(_do_scan())

    def _on_scan_finished(self) -> None:
        self._btn_scan.setEnabled(True)
        self._status_lbl.setText("Varredura concluída.")
