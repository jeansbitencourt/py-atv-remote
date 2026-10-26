"""Tests for DeviceManager dialog and thread-safe pairing flow."""

from __future__ import annotations

import sys
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PyQt6 import QtWidgets

from py_atv_remote.domain.errors import TvUnreachableError
from py_atv_remote.domain.models import DiscoveredTv, TvProfile
from py_atv_remote.infrastructure.cert_store import CertStore
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.infrastructure.paths import AppPaths
from py_atv_remote.services.events import DirectDispatcher, EventBus
from py_atv_remote.services.pairing_service import PairingSession
from py_atv_remote.ui.device_manager import DeviceManager


@pytest.fixture
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if isinstance(app, QtWidgets.QApplication):
        return app
    return QtWidgets.QApplication(sys.argv)


def test_device_manager_init_and_listing(tmp_path: Path, qapp: QtWidgets.QApplication) -> None:
    paths = AppPaths(base_dir=tmp_path)
    config_store = ConfigStore(paths)
    cert_store = CertStore(paths)

    tv = TvProfile(id="tv-1", name="Sala TV", host="192.168.1.100")
    config_store.save_tv(tv)
    cert_store.get_cert_path("tv-1").write_text("cert")
    cert_store.get_key_path("tv-1").write_text("key")

    disc_tv = DiscoveredTv(name="Quarto TV", host="192.168.1.101", id="tv-2")
    discovery = MagicMock()
    discovery.discovered_tvs = [disc_tv]

    pairing = MagicMock()
    session = MagicMock()
    event_bus = EventBus()
    runner = MagicMock()
    dispatcher = DirectDispatcher()
    on_tv_selected = MagicMock()

    manager = DeviceManager(
        parent=None,
        config_store=config_store,
        cert_store=cert_store,
        discovery_service=discovery,
        pairing_service=pairing,
        remote_session=session,
        event_bus=event_bus,
        async_runner=runner,
        dispatcher=dispatcher,
        on_tv_selected=on_tv_selected,
    )

    assert manager._table.rowCount() == 2
    assert (it := manager._table.item(0, 0)) is not None and it.text() == "Sala TV"
    assert (it := manager._table.item(0, 2)) is not None and it.text() == "Cadastrada (Offline)"
    assert (it := manager._table.item(1, 0)) is not None and it.text() == "Quarto TV"
    assert (it := manager._table.item(1, 2)) is not None and it.text() == "Nova TV encontrada"


def test_device_manager_start_pairing_dispatches_dialog(
    tmp_path: Path, qapp: QtWidgets.QApplication
) -> None:
    paths = AppPaths(base_dir=tmp_path)
    config_store = ConfigStore(paths)
    cert_store = CertStore(paths)
    discovery = MagicMock()
    discovery.discovered_tvs = []

    pairing_session = PairingSession(
        tv_id="tv-1",
        target_name="Test TV",
        host="192.168.1.50",
        api_port=6466,
        pair_port=6467,
        model="Test Model",
        client=MagicMock(),
        newly_generated_cert=False,
    )
    pairing = MagicMock()
    pairing.start_pairing = AsyncMock(return_value=pairing_session)

    runner = MagicMock()

    def run_coro(coro: Coroutine[Any, Any, Any]) -> None:
        import asyncio

        asyncio.run(coro)

    runner.submit.side_effect = run_coro

    dispatched_calls: list[str] = []

    class MockDispatcher:
        def post(self, fn: Callable[[], None]) -> None:
            dispatched_calls.append("post")
            fn()

    dispatcher = MockDispatcher()
    manager = DeviceManager(
        parent=None,
        config_store=config_store,
        cert_store=cert_store,
        discovery_service=discovery,
        pairing_service=pairing,
        remote_session=MagicMock(),
        event_bus=EventBus(),
        async_runner=runner,
        dispatcher=dispatcher,
        on_tv_selected=MagicMock(),
    )

    disc_tv = DiscoveredTv(id="tv-nova", name="Nova TV", host="192.168.1.50")

    with patch.object(manager, "_open_pair_dialog") as mock_open:
        manager._start_pairing_flow(disc_tv)
        mock_open.assert_called_once_with(pairing_session)
        assert len(dispatched_calls) >= 1


def test_device_manager_start_pairing_unreachable_error(
    tmp_path: Path, qapp: QtWidgets.QApplication
) -> None:
    paths = AppPaths(base_dir=tmp_path)
    config_store = ConfigStore(paths)
    cert_store = CertStore(paths)
    discovery = MagicMock()
    discovery.discovered_tvs = []

    pairing = MagicMock()
    pairing.start_pairing = AsyncMock(side_effect=TvUnreachableError("Timeout"))

    runner = MagicMock()

    def run_coro(coro: Coroutine[Any, Any, Any]) -> None:
        import asyncio

        asyncio.run(coro)

    runner.submit.side_effect = run_coro

    dispatcher = DirectDispatcher()
    manager = DeviceManager(
        parent=None,
        config_store=config_store,
        cert_store=cert_store,
        discovery_service=discovery,
        pairing_service=pairing,
        remote_session=MagicMock(),
        event_bus=EventBus(),
        async_runner=runner,
        dispatcher=dispatcher,
        on_tv_selected=MagicMock(),
    )

    disc_tv = DiscoveredTv(id="tv-unreachable", name="Unreachable TV", host="192.168.1.99")

    with patch.object(manager, "_show_critical") as mock_critical:
        manager._start_pairing_flow(disc_tv)
        mock_critical.assert_called_once_with("TV Inacessível", "Timeout")
