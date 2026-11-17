"""Main desktop application window for py-atv-remote built with PyQt6."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine

from PyQt6 import QtCore, QtGui, QtWidgets

from py_atv_remote.domain.keys import RemoteKey
from py_atv_remote.domain.models import ConnectionState, TvProfile, VolumeState
from py_atv_remote.domain.preview import PreviewEvent, PreviewState
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.services.async_runner import AsyncRunner
from py_atv_remote.services.events import EventBus
from py_atv_remote.services.preview_service import PreviewService
from py_atv_remote.services.remote_session import RemoteSessionService
from py_atv_remote.ui.keybindings import handle_key_event
from py_atv_remote.ui.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
from py_atv_remote.ui.preview_dialog import PreviewDialog
from py_atv_remote.ui.qt_dispatcher import QtDispatcher
from py_atv_remote.ui.widgets.dpad import DPad
from py_atv_remote.ui.widgets.repeat_button import RepeatButton
from py_atv_remote.ui.widgets.status_bar import StatusBar

LOGGER = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    """Main window controller for the remote control application."""

    def __init__(
        self,
        config_store: ConfigStore,
        remote_session: RemoteSessionService,
        event_bus: EventBus,
        async_runner: AsyncRunner,
        open_device_manager: Callable[[], None],
        open_shortcuts_dialog: Callable[[], None],
        parent: QtWidgets.QWidget | None = None,
        prepare_shutdown: Callable[[], Coroutine[object, object, None]] | None = None,
    ) -> None:
        super().__init__(parent)
        self._config_store = config_store
        self._session = remote_session
        self._event_bus = event_bus
        self._runner = async_runner
        self._preview_dispatcher = QtDispatcher(self)
        self.preview = PreviewService(config_store, self._preview_dispatcher)
        self._preview_unsubscribe = self.preview.subscribe(self._on_preview_event)
        self._closing = False
        self._close_ready = False
        self._prepare_shutdown = prepare_shutdown
        self._open_device_manager = open_device_manager
        self._open_shortcuts_dialog = open_shortcuts_dialog
        self._application = QtWidgets.QApplication.instance()
        if self._application is None:
            raise RuntimeError("MainWindow requires a QApplication instance.")

        self._tvs: list[TvProfile] = []
        self._selected_tv_id: str | None = None

        self._setup_window()
        self._build_ui()
        self._application.installEventFilter(self)
        self._setup_event_subscriptions()
        self._load_saved_tvs()

    def _setup_window(self) -> None:
        self.setWindowTitle("py-atv-remote")
        self.setFixedSize(324, 600)

        # Apply always-on-top preference
        always_on_top = self._config_store.get_always_on_top()
        if always_on_top:
            self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.WindowStaysOnTopHint)

    def _build_ui(self) -> None:
        central_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(4)

        # 1. Header Frame: TV Selector + Manage Devices (+) + Settings Menu (⚙)
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(6)

        self._tv_selector = QtWidgets.QComboBox(self)
        self._tv_selector.setFixedHeight(32)
        self._tv_selector.currentIndexChanged.connect(self._on_tv_option_selected)
        header_layout.addWidget(self._tv_selector, stretch=1)

        self._btn_add_tv = QtWidgets.QPushButton("+", self)
        self._btn_add_tv.setFixedSize(32, 32)
        self._btn_add_tv.setToolTip("Gerenciar e Parear TVs")
        self._btn_add_tv.clicked.connect(self._open_device_manager)
        header_layout.addWidget(self._btn_add_tv)

        self._btn_menu = QtWidgets.QPushButton("⚙", self)
        self._btn_menu.setObjectName("headerMenuButton")
        self._btn_menu.setFixedSize(32, 32)
        self._btn_menu.setToolTip("Opções")
        self._options_menu = QtWidgets.QMenu(self._btn_menu)

        self._action_always_top = QtGui.QAction("Sempre no topo", self)
        self._action_always_top.setCheckable(True)
        self._action_always_top.setChecked(self._config_store.get_always_on_top())
        self._action_always_top.triggered.connect(self._toggle_always_on_top)
        self._options_menu.addAction(self._action_always_top)

        self._options_menu.aboutToShow.connect(self._refresh_preview_actions)
        self._options_menu.addSeparator()

        action_manage = QtGui.QAction("Gerenciar TVs…", self)
        action_manage.triggered.connect(self._open_device_manager)
        self._options_menu.addAction(action_manage)

        action_shortcuts = QtGui.QAction("Editar Atalhos de Apps…", self)
        action_shortcuts.triggered.connect(self._open_shortcuts_dialog)
        self._options_menu.addAction(action_shortcuts)

        action_keyboard_shortcuts = QtGui.QAction("Consultar Atalhos do Teclado…", self)
        action_keyboard_shortcuts.triggered.connect(self._show_keyboard_shortcuts)
        self._options_menu.addAction(action_keyboard_shortcuts)

        preview_menu = self._options_menu.addMenu("Visualização da TV")
        assert preview_menu is not None
        preview_menu.addAction("Configurar e ativar…", self._configure_preview)
        self._action_preview_open = preview_menu.addAction(
            "Abrir visualização", self._start_preview
        )
        preview_menu.addAction(
            "Fechar visualização", lambda: self._runner.submit(self.preview.stop())
        )
        preview_menu.addAction("Como habilitar na TV…", self._preview_help)

        self._btn_menu.setMenu(self._options_menu)
        header_layout.addWidget(self._btn_menu)

        main_layout.addLayout(header_layout)

        # 2. Status Bar
        self._status_bar = StatusBar(self)
        main_layout.addWidget(self._status_bar)

        # 3. Needs Pairing Banner (hidden by default)
        self._pairing_banner = QtWidgets.QFrame(self)
        self._pairing_banner.setObjectName("pairingBanner")
        self._pairing_banner.setVisible(False)
        banner_layout = QtWidgets.QHBoxLayout(self._pairing_banner)
        banner_layout.setContentsMargins(8, 4, 8, 4)

        lbl_pairing = QtWidgets.QLabel("Esta TV precisa ser pareada.", self)
        lbl_pairing.setStyleSheet("color: #ffffff; font-size: 11px;")
        banner_layout.addWidget(lbl_pairing, stretch=1)

        btn_pair_banner = QtWidgets.QPushButton("Parear Agora", self)
        btn_pair_banner.setObjectName("primaryButton")
        btn_pair_banner.setFixedHeight(26)
        btn_pair_banner.clicked.connect(self._open_device_manager)
        banner_layout.addWidget(btn_pair_banner)

        main_layout.addWidget(self._pairing_banner)

        # 4. Top Action Row: Power, Input (Entradas), Settings (Ajustes)
        top_row = QtWidgets.QHBoxLayout()
        top_row.setSpacing(6)

        self._btn_power = QtWidgets.QPushButton("Power", self)
        self._btn_power.setObjectName("powerButton")
        self._btn_power.setFixedHeight(32)
        self._btn_power.clicked.connect(self._on_power_pressed)
        top_row.addWidget(self._btn_power)

        self._btn_tv_input = QtWidgets.QPushButton("Entradas", self)
        self._btn_tv_input.setFixedHeight(32)
        self._btn_tv_input.setToolTip("Alternar Entradas HDMI / TV")
        self._btn_tv_input.clicked.connect(lambda: self._send_key(RemoteKey.TV_INPUT))
        top_row.addWidget(self._btn_tv_input)

        self._btn_tv_settings = QtWidgets.QPushButton("Ajustes", self)
        self._btn_tv_settings.setFixedHeight(32)
        self._btn_tv_settings.clicked.connect(lambda: self._send_key(RemoteKey.SETTINGS))
        top_row.addWidget(self._btn_tv_settings)

        main_layout.addLayout(top_row)

        # 5. D-Pad Frame
        self._dpad = DPad(on_key=self._send_key, parent=self)
        main_layout.addWidget(self._dpad, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        # 6. System Row: Voltar, Início
        sys_row = QtWidgets.QHBoxLayout()
        sys_row.setSpacing(6)

        self._btn_back = QtWidgets.QPushButton("Voltar", self)
        self._btn_back.setFixedHeight(32)
        self._btn_back.clicked.connect(lambda: self._send_key(RemoteKey.BACK))
        sys_row.addWidget(self._btn_back)

        self._btn_home = QtWidgets.QPushButton("Início", self)
        self._btn_home.setFixedHeight(32)
        self._btn_home.clicked.connect(lambda: self._send_key(RemoteKey.HOME))
        sys_row.addWidget(self._btn_home)

        main_layout.addLayout(sys_row)

        # 7. Media Row: ◄◄, ►||, ►►
        media_row = QtWidgets.QHBoxLayout()
        media_row.setSpacing(6)

        self._btn_rewind = QtWidgets.QPushButton("◄◄", self)
        self._btn_rewind.setObjectName("mediaButton")
        self._btn_rewind.setFixedHeight(32)
        self._btn_rewind.clicked.connect(lambda: self._send_key(RemoteKey.MEDIA_REWIND))
        media_row.addWidget(self._btn_rewind)

        self._btn_play_pause = QtWidgets.QPushButton("►||", self)
        self._btn_play_pause.setObjectName("mediaButton")
        self._btn_play_pause.setFixedHeight(32)
        self._btn_play_pause.clicked.connect(lambda: self._send_key(RemoteKey.MEDIA_PLAY_PAUSE))
        media_row.addWidget(self._btn_play_pause)

        self._btn_fast_forward = QtWidgets.QPushButton("►►", self)
        self._btn_fast_forward.setObjectName("mediaButton")
        self._btn_fast_forward.setFixedHeight(32)
        self._btn_fast_forward.clicked.connect(lambda: self._send_key(RemoteKey.MEDIA_FAST_FORWARD))
        media_row.addWidget(self._btn_fast_forward)

        main_layout.addLayout(media_row)

        # 8. Volume Row: Vol -, Mudo, Vol +
        vol_row = QtWidgets.QHBoxLayout()
        vol_row.setSpacing(6)

        self._btn_vol_down = RepeatButton(
            "Vol -", self, command=lambda: self._send_key(RemoteKey.VOLUME_DOWN)
        )
        self._btn_vol_down.setFixedHeight(32)
        vol_row.addWidget(self._btn_vol_down)

        self._btn_mute = QtWidgets.QPushButton("Mudo", self)
        self._btn_mute.setFixedHeight(32)
        self._btn_mute.clicked.connect(lambda: self._send_key(RemoteKey.MUTE))
        vol_row.addWidget(self._btn_mute)

        self._btn_vol_up = RepeatButton(
            "Vol +", self, command=lambda: self._send_key(RemoteKey.VOLUME_UP)
        )
        self._btn_vol_up.setFixedHeight(32)
        vol_row.addWidget(self._btn_vol_up)

        main_layout.addLayout(vol_row)

        # 9. App Shortcuts Container (2-column grid for clean fit)
        self._shortcuts_widget = QtWidgets.QWidget(self)
        self._shortcuts_layout = QtWidgets.QGridLayout(self._shortcuts_widget)
        self._shortcuts_layout.setContentsMargins(0, 0, 0, 0)
        self._shortcuts_layout.setSpacing(4)
        main_layout.addWidget(self._shortcuts_widget)
        self.refresh_app_shortcuts()

        # 10. Text Input Row
        text_row = QtWidgets.QHBoxLayout()
        text_row.setSpacing(6)

        self._txt_input = QtWidgets.QLineEdit(self)
        self._txt_input.setPlaceholderText("Digitar na TV…")
        self._txt_input.setFixedHeight(32)
        self._txt_input.returnPressed.connect(self._on_send_text)
        text_row.addWidget(self._txt_input, stretch=1)

        self._btn_send_text = QtWidgets.QPushButton("Enviar", self)
        self._btn_send_text.setObjectName("primaryButton")
        self._btn_send_text.setFixedSize(62, 32)
        self._btn_send_text.clicked.connect(self._on_send_text)
        text_row.addWidget(self._btn_send_text)

        main_layout.addLayout(text_row)

        self._update_controls_state(ConnectionState.IDLE)

    def _setup_event_subscriptions(self) -> None:
        self._event_bus.on_state(self._on_state_event)
        self._event_bus.on_volume(self._on_volume_event)
        self._event_bus.on_current_app(self._on_current_app_event)
        self._event_bus.on_error(self._on_error_event)

    def _load_saved_tvs(self) -> None:
        self._tvs = self._config_store.list_tvs()
        names = [tv.name for tv in self._tvs]
        self._tv_selector.blockSignals(True)
        self._tv_selector.clear()
        if names:
            for tv in self._tvs:
                self._tv_selector.addItem(tv.name, tv.id)
        else:
            self._tv_selector.addItem("Nenhuma TV cadastrada")

        last_id = self._config_store.get_last_selected_id()
        selected_index = -1
        if last_id:
            for idx, tv in enumerate(self._tvs):
                if tv.id == last_id:
                    selected_index = idx
                    break

        if selected_index >= 0:
            target = self._tvs[selected_index]
            self._tv_selector.setCurrentIndex(selected_index)
            self._selected_tv_id = target.id
            self._tv_selector.blockSignals(False)
            self._connect_to_selected_tv()
        elif self._tvs:
            target = self._tvs[0]
            self._tv_selector.setCurrentIndex(0)
            self._selected_tv_id = target.id
            self._tv_selector.blockSignals(False)
            self._connect_to_selected_tv()
        else:
            self._tv_selector.blockSignals(False)

    def refresh_tvs(self, selected_tv_id: str | None = None) -> None:
        """Reload the list of saved TVs in the selector dropdown."""
        self._runner.submit(self.preview.stop())
        self._tvs = self._config_store.list_tvs()
        names = [tv.name for tv in self._tvs]
        self._tv_selector.blockSignals(True)
        self._tv_selector.clear()
        if names:
            for tv in self._tvs:
                self._tv_selector.addItem(tv.name, tv.id)
        else:
            self._tv_selector.addItem("Nenhuma TV cadastrada")

        last_id = self._config_store.get_last_selected_id()
        target_id = selected_tv_id or self._selected_tv_id or last_id
        selected_idx = -1
        if target_id:
            for idx, tv in enumerate(self._tvs):
                if tv.id == target_id:
                    selected_idx = idx
                    break

        if selected_idx >= 0:
            self._tv_selector.setCurrentIndex(selected_idx)
            self._selected_tv_id = self._tvs[selected_idx].id
        elif self._tvs:
            self._tv_selector.setCurrentIndex(0)
            self._selected_tv_id = self._tvs[0].id
        else:
            self._selected_tv_id = None
        self._tv_selector.blockSignals(False)

    def refresh_app_shortcuts(self) -> None:
        """Rebuild app shortcut buttons from config in a 2-column grid."""
        # Clear existing buttons
        while self._shortcuts_layout.count():
            layout_item = self._shortcuts_layout.takeAt(0)
            if layout_item is not None:
                widget = layout_item.widget()
                if widget is not None:
                    widget.deleteLater()

        shortcuts = self._config_store.get_app_shortcuts()
        if not shortcuts:
            return

        items = shortcuts[:6]
        count = len(items)
        for idx, shortcut_entry in enumerate(items):
            row = idx // 2
            col = idx % 2
            span = 2 if (idx == count - 1 and count % 2 == 1) else 1

            btn = QtWidgets.QPushButton(shortcut_entry.label, self._shortcuts_widget)
            btn.setObjectName("shortcutButton")
            btn.setFixedHeight(28)
            link_target = shortcut_entry.link
            btn.clicked.connect(self._make_launch_handler(link_target))
            self._shortcuts_layout.addWidget(btn, row, col, 1, span)

    def _preview_help(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Depuração na TV",
            "Na TV, abra Configurações → Sobre e pressione várias vezes o número da "
            "compilação. Nas Opções do desenvolvedor, habilite Depuração sem fio. "
            "Escolha Parear com código. A porta de pareamento é diferente da porta "
            "de conexão. Em TVs antigas, procure Depuração pela rede (porta usual 5555). "
            "Use uma rede confiável. Conteúdo protegido pode aparecer preto.",
        )

    def _configure_preview(self) -> None:
        tv_id = self._selected_tv_id
        if not tv_id:
            return
        profile = next((tv for tv in self._tvs if tv.id == tv_id), None)
        if profile is None:
            return
        self._runner.submit(self.preview.stop())
        dialog = PreviewDialog(
            self, profile, self._config_store, self._runner, self._preview_dispatcher
        )
        if (
            dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted
            and dialog.confirmed_without_identity
        ):
            settings = self._config_store.get_preview_settings(tv_id)
            self._runner.submit(self.preview.confirm_unidentified_once(tv_id, settings.endpoint))

    def _refresh_preview_actions(self) -> None:
        settings = self._config_store.get_preview_settings(self._selected_tv_id or "")
        if self._action_preview_open is not None:
            self._action_preview_open.setEnabled(settings.enabled and bool(self._selected_tv_id))

    def _on_preview_event(self, event: PreviewEvent) -> None:
        if self._closing or event.tv_id != self._selected_tv_id:
            return
        if event.state == PreviewState.ERROR:
            QtWidgets.QMessageBox.warning(self, "Visualização da TV", event.message)
        if self._action_preview_open is not None:
            self._action_preview_open.setText(
                "Visualização em andamento…"
                if event.state in (PreviewState.PREPARING, PreviewState.RUNNING)
                else "Abrir visualização"
            )

    def _start_preview(self) -> None:
        if self._selected_tv_id:
            settings = self._config_store.get_preview_settings(self._selected_tv_id)
            if not settings.identity:
                self._configure_preview()
            if self._config_store.get_preview_settings(self._selected_tv_id).enabled:
                self._runner.submit(self.preview.start(self._selected_tv_id))

    def _make_launch_handler(self, link: str) -> Callable[[], None]:
        return lambda: self._session.launch_app(link)

    def _show_keyboard_shortcuts(self) -> None:
        dialog = KeyboardShortcutsDialog(self)
        dialog.exec()

    def _on_tv_option_selected(self, _index: int) -> None:
        tv_id = self._tv_selector.currentData()
        if isinstance(tv_id, str):
            self._runner.submit(self.preview.stop())
            self._selected_tv_id = tv_id
            self._connect_to_selected_tv()

    def _connect_to_selected_tv(self) -> None:
        if not self._selected_tv_id:
            return
        tv_id = self._selected_tv_id
        self._status_bar.update_current_app(None)
        self._status_bar.update_volume(None)
        self._status_bar.update_state(ConnectionState.CONNECTING)
        self._update_controls_state(ConnectionState.CONNECTING)
        self._pairing_banner.setVisible(False)
        self._runner.submit(self._session.select_tv(tv_id))

    def _send_key(self, key: RemoteKey) -> None:
        self._session.send_key(key)

    def _on_send_text(self) -> None:
        text = self._txt_input.text()
        if text:
            self._session.send_text(text)
            self._txt_input.clear()

    def _on_power_pressed(self) -> None:
        self._runner.submit(self._session.power())

    def _toggle_always_on_top(self) -> None:
        val = self._action_always_top.isChecked()
        self._config_store.set_always_on_top(val)
        flags = self.windowFlags()
        if val:
            flags |= QtCore.Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~QtCore.Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _on_state_event(self, state: ConnectionState, profile: TvProfile | None) -> None:
        if profile is not None and profile.id != self._selected_tv_id:
            return
        if profile is None and self._session.current_profile is not None:
            return
        self._status_bar.update_state(state)
        self._update_controls_state(state)

        if state == ConnectionState.NEEDS_PAIRING:
            self._pairing_banner.setVisible(True)
        else:
            self._pairing_banner.setVisible(False)

    def _on_volume_event(self, volume: VolumeState) -> None:
        self._status_bar.update_volume(volume)

    def _on_current_app_event(self, app_id: str) -> None:
        self._status_bar.update_current_app(app_id)

    def _on_error_event(self, message: str, _exc: Exception | None = None) -> None:
        QtWidgets.QMessageBox.critical(self, "Erro de Comunicação", message)

    def _update_controls_state(self, state: ConnectionState) -> None:
        """Enable or disable remote control widgets based on connection state."""
        connected = state in (ConnectionState.CONNECTED, ConnectionState.RECONNECTING)

        self._dpad.set_enabled(connected)
        for btn in (
            self._btn_tv_input,
            self._btn_tv_settings,
            self._btn_back,
            self._btn_home,
            self._btn_rewind,
            self._btn_play_pause,
            self._btn_fast_forward,
            self._btn_vol_down,
            self._btn_mute,
            self._btn_vol_up,
            self._btn_send_text,
        ):
            btn.setEnabled(connected)

        for i in range(self._shortcuts_layout.count()):
            layout_item = self._shortcuts_layout.itemAt(i)
            if layout_item is not None:
                widget = layout_item.widget()
                if widget is not None:
                    widget.setEnabled(connected)

        # Power button remains clickable anytime
        self._btn_power.setEnabled(True)

    def eventFilter(self, watched: QtCore.QObject | None, event: QtCore.QEvent | None) -> bool:
        """Route shortcuts before focused child widgets consume their key events."""
        if event is None:
            return False
        if event.type() != QtCore.QEvent.Type.KeyPress or not isinstance(event, QtGui.QKeyEvent):
            return super().eventFilter(watched, event)
        if not isinstance(watched, QtWidgets.QWidget) or watched.window() is not self:
            return super().eventFilter(watched, event)
        if QtWidgets.QApplication.activePopupWidget() is not None:
            return super().eventFilter(watched, event)

        def is_remote_enabled() -> bool:
            return self._session.state in (
                ConnectionState.CONNECTED,
                ConnectionState.RECONNECTING,
            )

        handled = handle_key_event(
            event,
            self,
            self._send_key,
            is_remote_enabled,
            on_power=self._on_power_pressed,
        )
        if handled:
            event.accept()
        return handled or super().eventFilter(watched, event)

    def closeEvent(self, event: QtGui.QCloseEvent | None) -> None:
        if event is None:
            return
        if not self._close_ready and self._runner.is_running:
            event.ignore()
            if not self._closing:
                self._closing = True
                self.setEnabled(False)

                async def finish() -> None:
                    try:
                        await self.preview.stop()
                        if self._prepare_shutdown is not None:
                            await self._prepare_shutdown()
                    finally:
                        self._preview_dispatcher.post(self._finish_close)

                self._runner.submit(finish())
            return
        self._preview_unsubscribe()
        if self._application is not None:
            self._application.removeEventFilter(self)
        super().closeEvent(event)

    def _finish_close(self) -> None:
        self._close_ready = True
        self.close()
