"""Tests for PairDialog modal and thread-safe PIN submission."""

from __future__ import annotations

import sys
from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from PyQt6 import QtWidgets

from py_atv_remote.domain.errors import InvalidPinError, PairingFailedError
from py_atv_remote.domain.models import TvProfile
from py_atv_remote.services.events import DirectDispatcher
from py_atv_remote.services.pairing_service import PairingSession
from py_atv_remote.ui.pair_dialog import PairDialog


@pytest.fixture
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if isinstance(app, QtWidgets.QApplication):
        return app
    return QtWidgets.QApplication(sys.argv)


def test_pair_dialog_empty_pin(qapp: QtWidgets.QApplication) -> None:
    pairing_service = MagicMock()
    runner = MagicMock()
    dispatcher = DirectDispatcher()
    session = PairingSession(
        tv_id="tv-1",
        target_name="Test TV",
        host="192.168.1.50",
        api_port=6466,
        pair_port=6467,
        model="Test Model",
        client=MagicMock(),
        newly_generated_cert=False,
    )
    on_success = MagicMock()

    dialog = PairDialog(
        parent=None,
        pairing_service=pairing_service,
        pairing_session=session,
        async_runner=runner,
        dispatcher=dispatcher,
        on_success=on_success,
    )

    # Empty PIN submission
    dialog._pin_entry.setText("   ")
    dialog._on_submit()

    assert dialog._status_lbl.text() == "Digite o PIN exibido na TV."
    assert runner.submit.call_count == 0


def test_pair_dialog_success_dispatches_to_ui(qapp: QtWidgets.QApplication) -> None:
    profile = TvProfile(id="tv-1", name="Test TV", host="192.168.1.50")
    pairing_service = MagicMock()
    pairing_service.finish_pairing = AsyncMock(return_value=profile)

    runner = MagicMock()

    # Execute the submitted coroutine immediately
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
    session = PairingSession(
        tv_id="tv-1",
        target_name="Test TV",
        host="192.168.1.50",
        api_port=6466,
        pair_port=6467,
        model="Test Model",
        client=MagicMock(),
        newly_generated_cert=False,
    )
    on_success = MagicMock()

    dialog = PairDialog(
        parent=None,
        pairing_service=pairing_service,
        pairing_session=session,
        async_runner=runner,
        dispatcher=dispatcher,
        on_success=on_success,
    )

    dialog._pin_entry.setText("A1B2C3")
    dialog._on_submit()

    assert len(dispatched_calls) == 1
    on_success.assert_called_once_with(profile)


def test_pair_dialog_invalid_pin_error(qapp: QtWidgets.QApplication) -> None:
    pairing_service = MagicMock()
    pairing_service.finish_pairing = AsyncMock(side_effect=InvalidPinError("Wrong PIN"))

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
    session = PairingSession(
        tv_id="tv-1",
        target_name="Test TV",
        host="192.168.1.50",
        api_port=6466,
        pair_port=6467,
        model="Test Model",
        client=MagicMock(),
        newly_generated_cert=False,
    )
    on_success = MagicMock()

    dialog = PairDialog(
        parent=None,
        pairing_service=pairing_service,
        pairing_session=session,
        async_runner=runner,
        dispatcher=dispatcher,
        on_success=on_success,
    )

    dialog._pin_entry.setText("000000")
    dialog._on_submit()

    assert len(dispatched_calls) == 1
    assert "PIN incorreto" in dialog._status_lbl.text()
    assert dialog._btn_submit.isEnabled() is True
    assert on_success.call_count == 0


def test_pair_dialog_pairing_failed_error(qapp: QtWidgets.QApplication) -> None:
    pairing_service = MagicMock()
    pairing_service.finish_pairing = AsyncMock(side_effect=PairingFailedError("Network down"))

    runner = MagicMock()

    def run_coro(coro: Coroutine[Any, Any, Any]) -> None:
        import asyncio

        asyncio.run(coro)

    runner.submit.side_effect = run_coro

    dispatcher = DirectDispatcher()
    session = PairingSession(
        tv_id="tv-1",
        target_name="Test TV",
        host="192.168.1.50",
        api_port=6466,
        pair_port=6467,
        model="Test Model",
        client=MagicMock(),
        newly_generated_cert=False,
    )
    on_success = MagicMock()

    dialog = PairDialog(
        parent=None,
        pairing_service=pairing_service,
        pairing_session=session,
        async_runner=runner,
        dispatcher=dispatcher,
        on_success=on_success,
    )

    dialog._pin_entry.setText("112233")
    dialog._on_submit()

    assert "Falha no pareamento" in dialog._status_lbl.text()
    assert dialog._btn_submit.isEnabled() is True
