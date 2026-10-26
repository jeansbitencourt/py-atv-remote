"""Application entrypoint and composition root."""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys
import tkinter as tk

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
from py_atv_remote.ui.shortcuts_dialog import ShortcutsDialog
from py_atv_remote.ui.tk_dispatcher import TkDispatcher

LOGGER = logging.getLogger("py_atv_remote")


class App:
    """Coordinates lifecycle, dependency injection, and shutdown."""

    def __init__(self, debug: bool = False) -> None:
        self._setup_logging(debug)

        # 1. Infrastructure
        self.paths = AppPaths()
        self.config_store = ConfigStore(self.paths)
        self.cert_store = CertStore(self.paths)

        # 2. Tkinter Root Window
        self.root = tk.Tk(className="py-atv-remote")
        self.dispatcher = TkDispatcher(self.root)

        # 3. Services
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
            root=self.root,
            config_store=self.config_store,
            remote_session=self.session,
            event_bus=self.event_bus,
            async_runner=self.runner,
            open_device_manager=self.open_device_manager,
            open_shortcuts_dialog=self.open_shortcuts_dialog,
        )

        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

    def open_device_manager(self) -> None:
        """Open the TV device management dialog."""
        DeviceManager(
            parent=self.root,
            config_store=self.config_store,
            cert_store=self.cert_store,
            discovery_service=self.discovery,
            pairing_service=self.pairing,
            remote_session=self.session,
            event_bus=self.event_bus,
            async_runner=self.runner,
            on_tv_selected=self._on_tv_selected_from_manager,
        )

    def open_shortcuts_dialog(self) -> None:
        """Open the app shortcuts customization dialog."""
        ShortcutsDialog(
            parent=self.root,
            config_store=self.config_store,
            on_saved=self.main_window.refresh_app_shortcuts,
        )

    def _on_tv_selected_from_manager(self, tv_id: str) -> None:
        self.main_window.refresh_tvs(selected_tv_id=tv_id)
        if tv_id:
            self.runner.submit(self.session.select_tv(tv_id))

    def run(self) -> None:
        """Start Tkinter main event loop."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.shutdown()

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

        with contextlib.suppress(Exception):
            self.root.destroy()
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

    app = App(debug=args.debug)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
