"""Tests for TkDispatcher queue draining."""

from unittest.mock import MagicMock

from py_atv_remote.ui.tk_dispatcher import TkDispatcher


def test_tk_dispatcher_enqueue_and_drain() -> None:
    mock_root = MagicMock()
    dispatcher = TkDispatcher(mock_root, poll_interval_ms=10)
    dispatcher.start()

    dispatched = []

    def task1() -> None:
        dispatched.append(1)

    def task2() -> None:
        dispatched.append(2)

    dispatcher.post(task1)
    dispatcher.post(task2)

    # Manually trigger drain
    dispatcher._drain()

    assert dispatched == [1, 2]
    mock_root.after.assert_called_with(10, dispatcher._drain)


def test_tk_dispatcher_lifecycle() -> None:
    mock_root = MagicMock()
    mock_root.after.return_value = "timer_123"

    dispatcher = TkDispatcher(mock_root)
    dispatcher.start()
    assert dispatcher._running is True
    assert dispatcher._timer_id == "timer_123"

    dispatcher.stop()
    assert dispatcher._running is False
    mock_root.after_cancel.assert_called_with("timer_123")
