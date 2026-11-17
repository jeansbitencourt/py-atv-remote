"""Per-TV ADB configuration with cancellable asynchronous operations."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from concurrent.futures import Future

from PyQt6 import QtWidgets

from py_atv_remote.domain.models import TvProfile
from py_atv_remote.domain.preview import AdbIdentity, PreviewError, PreviewSettings
from py_atv_remote.infrastructure.adb import AdbClient, Toolchain, validate_endpoint
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.services.async_runner import AsyncRunner
from py_atv_remote.services.events import Dispatcher


class PreviewDialog(QtWidgets.QDialog):
    """Pair, discover, verify and save without network I/O on the Qt thread."""

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        profile: TvProfile,
        store: ConfigStore,
        runner: AsyncRunner,
        dispatcher: Dispatcher,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Visualização — {profile.name}")
        self.setMinimumWidth(640)
        self._alive = True
        self._profile = profile
        self._store = store
        self._runner = runner
        self._dispatcher = dispatcher
        self._future: Future[None] | None = None
        self._verified_endpoint = ""
        self._identity = ""
        self.confirmed_without_identity = False
        settings = store.get_preview_settings(profile.id)
        layout = QtWidgets.QFormLayout(self)
        self.enabled = QtWidgets.QCheckBox("Ativar visualização para esta TV")
        self.enabled.setChecked(settings.enabled)
        layout.addRow(self.enabled)
        self.mode = QtWidgets.QComboBox()
        self.mode.addItem("Depuração sem fio (código / já pareada)", "wireless_tls")
        self.mode.addItem("Depuração pela rede (ADB TCP/IP tradicional)", "tcpip_legacy")
        self.mode.setCurrentIndex(1 if settings.mode == "tcpip_legacy" else 0)
        layout.addRow("Modalidade", self.mode)
        self.endpoint = QtWidgets.QLineEdit(settings.endpoint or f"{profile.host}:")
        self.endpoint.textChanged.connect(self._invalidate_identity)
        layout.addRow("Endereço de conexão (IP:porta)", self.endpoint)
        self.discover_button = QtWidgets.QPushButton("Descobrir porta de conexão")
        self.discover_button.clicked.connect(self._discover)
        layout.addRow(self.discover_button)
        self.pair_endpoint = QtWidgets.QLineEdit(f"{profile.host}:")
        layout.addRow("Endereço de pareamento (IP:porta)", self.pair_endpoint)
        self.code = QtWidgets.QLineEdit()
        self.code.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.code.setMaxLength(6)
        layout.addRow("Código de seis dígitos", self.code)
        self.pair_button = QtWidgets.QPushButton("Parear com código")
        self.pair_button.clicked.connect(self._pair)
        layout.addRow(self.pair_button)
        self.verify_button = QtWidgets.QPushButton("Conectar e confirmar TV…")
        self.verify_button.clicked.connect(self._verify)
        layout.addRow(self.verify_button)
        self.quality = QtWidgets.QComboBox()
        for label, value in (
            ("Econômica", "economic"),
            ("Equilibrada", "balanced"),
            ("Maior qualidade", "high"),
        ):
            self.quality.addItem(label, value)
        self.quality.setCurrentIndex(max(0, self.quality.findData(settings.quality)))
        layout.addRow("Qualidade", self.quality)
        diagnostics = QtWidgets.QPushButton("Verificar ADB e scrcpy")
        diagnostics.clicked.connect(self._diagnostics)
        layout.addRow(diagnostics)
        help_button = QtWidgets.QPushButton("Como habilitar na TV…")
        help_button.clicked.connect(self.show_help)
        layout.addRow(help_button)
        forget = QtWidgets.QPushButton("Esquecer configuração local")
        forget.clicked.connect(self._forget)
        layout.addRow(forget)
        self.status = QtWidgets.QLabel("Confirme a TV antes de salvar a ativação.")
        self.status.setWordWrap(True)
        layout.addRow(self.status)
        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        save_button = self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Save)
        cancel_button = self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.setText("Salvar")
        if cancel_button is not None:
            cancel_button.setText("Cancelar")
        self._extra_controls = (diagnostics, forget, self.enabled, self.quality)
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)
        self.finished.connect(self._closed)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self._mode_changed()

    def _mode_changed(self) -> None:
        legacy = self.mode.currentData() == "tcpip_legacy"
        self.pair_endpoint.setEnabled(not legacy)
        self.code.setEnabled(not legacy)
        self.pair_button.setEnabled(not legacy)
        self.discover_button.setEnabled(not legacy)
        if legacy and self.endpoint.text().endswith(":"):
            self.endpoint.setText(f"{self._profile.host}:5555")

    def _invalidate_identity(self) -> None:
        self._verified_endpoint = ""
        self._identity = ""
        self.confirmed_without_identity = False

    def _closed(self, _result: int) -> None:
        self._alive = False
        self.code.clear()
        if self._future is not None:
            self._future.cancel()

    def _busy(self, busy: bool) -> None:
        for widget in (
            self.mode,
            self.endpoint,
            self.pair_endpoint,
            self.code,
            self.verify_button,
            self.pair_button,
            self.discover_button,
        ):
            widget.setEnabled(not busy)
        for extra in self._extra_controls:
            extra.setEnabled(not busy)
        save = self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Save)
        if save is not None:
            save.setEnabled(not busy)
        if not busy:
            self._mode_changed()

    def _submit(
        self,
        operation: Callable[[], Coroutine[object, object, object]],
        completed: Callable[[object], None],
    ) -> None:
        if self._future is not None and not self._future.done():
            return
        # Kept callbacks on the main thread even when cancellation closes the dialog.
        self._busy(True)
        self.status.setText("Aguarde…")

        async def run() -> None:
            try:
                result = await operation()
            except PreviewError as exc:
                message = str(exc)

                def error(message: str = message) -> None:
                    if self._alive:
                        self._busy(False)
                        self.status.setText(message)

                self._dispatcher.post(error)
                return

            def finish() -> None:
                if self._alive:
                    self._busy(False)
                    completed(result)

            self._dispatcher.post(finish)

        self._future = self._runner.submit(run())

    def _diagnostics(self) -> None:
        async def operation() -> object:
            return await Toolchain.resolve().validate()

        def completed(result: object) -> None:
            QtWidgets.QMessageBox.information(self, "Ferramentas de visualização", str(result))

        self._submit(operation, completed)

    def _pair(self) -> None:
        endpoint, code = self.pair_endpoint.text().strip(), self.code.text()
        self.code.clear()

        async def operation() -> object:
            await AdbClient(Toolchain.resolve()).pair(endpoint, code)
            return None

        def completed(_result: object) -> None:
            self.status.setText("Pareamento concluído. Descubra ou informe a porta de conexão.")
            self._discover()

        self._submit(operation, completed)

    def _discover(self) -> None:
        # Use the configured host, never another Android advertised on the network.
        host = self.endpoint.text().rpartition(":")[0] or self._profile.host

        async def operation() -> object:
            return await AdbClient(Toolchain.resolve()).discover(host)

        def completed(result: object) -> None:
            assert isinstance(result, list)
            endpoints = [str(item) for item in result]
            if not endpoints:
                self.status.setText(
                    "mDNS sem resultado. Informe a porta de conexão mostrada na TV."
                )
            elif len(endpoints) == 1:
                self.endpoint.setText(endpoints[0])
                self.status.setText("Porta encontrada. Clique em Conectar e confirmar TV.")
            else:
                endpoint, ok = QtWidgets.QInputDialog.getItem(
                    self,
                    "Porta de conexão",
                    "Selecione o endereço exibido na TV:",
                    endpoints,
                    0,
                    False,
                )
                if ok:
                    self.endpoint.setText(endpoint)

        self._submit(operation, completed)

    def _verify(self) -> None:
        endpoint = self.endpoint.text().strip()

        async def operation() -> object:
            return await AdbClient(Toolchain.resolve()).connect(endpoint)

        def completed(result: object) -> None:
            assert isinstance(result, AdbIdentity)
            answer = QtWidgets.QMessageBox.question(
                self,
                "Confirmar TV",
                f"Associar {self._profile.name} a este dispositivo?\n"
                f"Modelo: {result.model}\nIdentificador: {result.serial or 'não informado'}\n"
                f"Endereço: {endpoint}\n"
                + (
                    "Sem identificador estável: confirme novamente a cada abertura."
                    if not result.serial
                    else ""
                ),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if answer == QtWidgets.QMessageBox.StandardButton.Yes:
                self.confirmed_without_identity = not result.serial
                self._identity = result.serial
                self._verified_endpoint = endpoint
                self.status.setText("TV confirmada. Salve para concluir.")

        self._submit(operation, completed)

    def _save(self) -> None:
        endpoint = self.endpoint.text().strip()
        if self.enabled.isChecked():
            try:
                validate_endpoint(endpoint)
            except PreviewError as exc:
                self.status.setText(str(exc))
                return
            if self._verified_endpoint != endpoint:
                self.status.setText("Clique em Conectar e confirmar TV antes de salvar.")
                return
        self._store.set_preview_settings(
            self._profile.id,
            PreviewSettings(
                enabled=self.enabled.isChecked(),
                endpoint=endpoint,
                mode=str(self.mode.currentData()),
                identity=self._identity,
                quality=str(self.quality.currentData()),
            ),
        )
        self.accept()

    def _forget(self) -> None:
        self._store.forget_preview_settings(self._profile.id)
        self.enabled.setChecked(False)
        self._invalidate_identity()
        self.status.setText(
            "Associação local removida. Para revogar a autorização, na TV abra "
            "Depuração sem fio → Dispositivos pareados → Esquecer."
        )

    def show_help(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Depuração na TV",
            "Na TV: Configurações → Sobre → pressione várias vezes o número da compilação.\n"
            "Abra Opções do desenvolvedor → Depuração sem fio → Parear com código.\n"
            "A porta de pareamento é diferente da porta de conexão na tela principal.\n"
            "Em TVs antigas, procure Depuração pela rede (porta usual 5555). Depuração USB "
            "sozinha pode não habilitar acesso pela rede. Os menus variam por fabricante.\n"
            "Use uma rede confiável e o mesmo Wi-Fi. Redes de convidados podem bloquear acesso.\n"
            "Conteúdo protegido pode aparecer preto; encoder e rede também podem causar falhas.\n"
            "A janela externa não controla a TV. Use o controle principal para enviar comandos.",
        )
