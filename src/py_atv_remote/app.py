"""Application entrypoint and composition root built with PyQt6."""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys

from PyQt6 import QtWidgets

from py_atv_remote.infrastructure.cert_store import CertStore
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.infrastructure.paths import AppPaths
from py_atv_remote.services.async_runner import AsyncRunner
from py_atv_remote.services.discovery_service import DiscoveryService
from py_atv_remote.services.events import EventBus
from py_atv_remote.services.pairing_service import PairingService
from py_atv_remote.services.remote_session import RemoteSessionService
from py_atv_remote.ui.device_manager import DeviceManager
from py_atv_remote.ui.main_window import MainWindow
from py_atv_remote.ui.qt_dispatcher import QtDispatcher
from py_atv_remote.ui.shortcuts_dialog import ShortcutsDialog

LOGGER = logging.getLogger("py_atv_remote")

DARK_STYLESHEET = """
QWidget {
    background-color: #18181b;
    color: #f4f4f5;
    font-family: "Liberation Sans", "DejaVu Sans", "Segoe UI", sans-serif;
    font-size: 11px;
}

QPushButton {
    background-color: #27272a;
    color: #f4f4f5;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 4px 8px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #3f3f46;
    border-color: #52525b;
}
QPushButton:pressed {
    background-color: #18181b;
}
QPushButton:disabled {
    background-color: #202023;
    color: #52525b;
    border-color: #27272a;
}

QPushButton#headerMenuButton {
    font-size: 14px;
    padding: 0px;
}
QPushButton#headerMenuButton::menu-indicator {
    image: none;
    width: 0px;
}

QPushButton#dpadArrow {
    font-size: 13px;
    font-weight: bold;
}

QPushButton#primaryButton, QPushButton#dpadCenter {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-weight: bold;
}
QPushButton#primaryButton:hover, QPushButton#dpadCenter:hover {
    background-color: #1d4ed8;
}
QPushButton#primaryButton:pressed, QPushButton#dpadCenter:pressed {
    background-color: #1e40af;
}

QPushButton#powerButton {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-weight: bold;
}
QPushButton#powerButton:hover {
    background-color: #b91c1c;
}
QPushButton#powerButton:pressed {
    background-color: #991b1b;
}

QPushButton#dangerButton {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-weight: bold;
}
QPushButton#dangerButton:hover {
    background-color: #b91c1c;
}

QPushButton#mediaButton {
    background-color: #334155;
    color: #f4f4f5;
    border: 1px solid #475569;
    border-radius: 8px;
    font-weight: bold;
}
QPushButton#mediaButton:hover {
    background-color: #475569;
    border-color: #64748b;
}

QPushButton#shortcutButton {
    background-color: #27272a;
    color: #f4f4f5;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    font-size: 10px;
    font-weight: bold;
}
QPushButton#shortcutButton:hover {
    background-color: #3f3f46;
    border-color: #52525b;
}

QFrame#statusBar {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 8px;
}
QFrame#pairingBanner {
    background-color: #1e3a8a;
    border-radius: 8px;
}

QComboBox {
    background-color: #27272a;
    color: #f4f4f5;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 2px 8px;
    font-size: 11px;
}
QComboBox:hover {
    border-color: #52525b;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #3f3f46;
}
QComboBox QAbstractItemView {
    background-color: #27272a;
    color: #f4f4f5;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 4px;
}

QLineEdit {
    background-color: #27272a;
    color: #f4f4f5;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 4px 8px;
    font-size: 11px;
}
QLineEdit:focus {
    border-color: #2563eb;
}

QTableWidget {
    background-color: #27272a;
    color: #f4f4f5;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    gridline-color: #3f3f46;
}
QTableWidget::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #18181b;
    color: #f4f4f5;
    border: 1px solid #3f3f46;
    padding: 4px 8px;
    font-weight: bold;
}

QMenu {
    background-color: #27272a;
    color: #f4f4f5;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background-color: #3f3f46;
    margin: 4px 0;
}
"""


class App:
    """Coordinates lifecycle, dependency injection, and shutdown."""

    def __init__(self, debug: bool = False, argv: list[str] | None = None) -> None:
        self._setup_logging(debug)

        # 1. Qt Application
        qapp_instance = QtWidgets.QApplication.instance()
        if isinstance(qapp_instance, QtWidgets.QApplication):
            self.qapp = qapp_instance
        else:
            self.qapp = QtWidgets.QApplication(argv if argv is not None else sys.argv)
        self.qapp.setStyleSheet(DARK_STYLESHEET)

        # 2. Infrastructure
        self.paths = AppPaths()
        self.config_store = ConfigStore(self.paths)
        self.cert_store = CertStore(self.paths)

        # 3. Dispatcher & Services
        self.dispatcher = QtDispatcher()
        self.event_bus = EventBus(self.dispatcher)
        self.runner = AsyncRunner()
        self.runner.start()
        self.dispatcher.start()

        self.session = RemoteSessionService(
            config_store=self.config_store,
            cert_store=self.cert_store,
            event_bus=self.event_bus,
        )

        self.discovery = DiscoveryService(
            config_store=self.config_store,
            event_bus=self.event_bus,
            on_profile_ip_updated=self.session.handle_ip_updated,
        )

        self.pairing = PairingService(
            config_store=self.config_store,
            cert_store=self.cert_store,
        )

        # 4. Start background mDNS discovery
        self.runner.submit(self.discovery.start())

        # 5. UI Window
        self.main_window = MainWindow(
            config_store=self.config_store,
            remote_session=self.session,
            event_bus=self.event_bus,
            async_runner=self.runner,
            open_device_manager=self.open_device_manager,
            open_shortcuts_dialog=self.open_shortcuts_dialog,
        )

        self.qapp.aboutToQuit.connect(self.shutdown)

    def open_device_manager(self) -> None:
        """Open the TV device management dialog."""
        dialog = DeviceManager(
            parent=self.main_window,
            config_store=self.config_store,
            cert_store=self.cert_store,
            discovery_service=self.discovery,
            pairing_service=self.pairing,
            remote_session=self.session,
            event_bus=self.event_bus,
            async_runner=self.runner,
            on_tv_selected=self._on_tv_selected_from_manager,
        )
        dialog.exec()

    def open_shortcuts_dialog(self) -> None:
        """Open the app shortcuts customization dialog."""
        dialog = ShortcutsDialog(
            parent=self.main_window,
            config_store=self.config_store,
            on_saved=self.main_window.refresh_app_shortcuts,
        )
        dialog.exec()

    def _on_tv_selected_from_manager(self, tv_id: str) -> None:
        self.main_window.refresh_tvs(selected_tv_id=tv_id)
        if tv_id:
            self.runner.submit(self.session.select_tv(tv_id))

    def run(self) -> int:
        """Show main window and start Qt main event loop."""
        self.main_window.show()
        return self.qapp.exec()

    def shutdown(self) -> None:
        """Gracefully release network connections, cancel tasks, and close window."""
        LOGGER.info("Shutting down py-atv-remote...")
        with contextlib.suppress(Exception):
            self.session.disconnect()

        try:
            future = self.runner.submit(self.discovery.stop())
            future.result(timeout=1.0)
        except Exception:
            pass

        self.dispatcher.stop()
        self.runner.stop(timeout=2.0)
        LOGGER.info("Shutdown complete.")

    @staticmethod
    def _setup_logging(debug: bool) -> None:
        level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )


def main(argv: list[str] | None = None) -> int:
    """CLI executable entry point."""
    parser = argparse.ArgumentParser(
        prog="py-atv-remote",
        description="Controle remoto desktop para Android TV / Google TV",
    )
    parser.add_argument(
        "--debug",
        "-v",
        action="store_true",
        help="Habilita logs detalhados de depuração",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    app = App(debug=args.debug, argv=argv if argv is not None else sys.argv)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
