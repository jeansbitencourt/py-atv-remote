"""Tests for background AsyncRunner."""

import asyncio
import time

from py_atv_remote.services.async_runner import AsyncRunner


def test_async_runner_start_submit_and_stop() -> None:
    runner = AsyncRunner()
    assert not runner.is_running

    runner.start()
    assert runner.is_running

    async def add(a: int, b: int) -> int:
        await asyncio.sleep(0.01)
        return a + b

    future = runner.submit(add(10, 32))
    result = future.result(timeout=2.0)
    assert result == 42

    called = []

    def sync_cb() -> None:
        called.append(True)

    runner.call_soon(sync_cb)
    time.sleep(0.05)
    assert called == [True]

    runner.stop()
    assert not runner.is_running


def test_async_runner_cancel_on_stop() -> None:
    runner = AsyncRunner()
    runner.start()

    async def infinite_task() -> None:
        while True:
            await asyncio.sleep(0.1)

    future = runner.submit(infinite_task())
    assert not future.done()

    runner.stop()
    assert not runner.is_running
    assert future.cancelled() or future.done()
