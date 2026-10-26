"""Background asyncio event loop runner isolated in a daemon thread."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class AsyncRunner:
    """Runs and manages an asyncio event loop inside a dedicated background thread."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready_event = threading.Event()
        self._stopping = False

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """Return the active asyncio event loop."""
        if self._loop is None or not self._loop.is_running():
            raise RuntimeError("AsyncRunner loop is not running. Call start() first.")
        return self._loop

    @property
    def is_running(self) -> bool:
        """Return True if the runner thread and event loop are actively running."""
        return (
            self._thread is not None
            and self._thread.is_alive()
            and self._loop is not None
            and self._loop.is_running()
        )

    def start(self) -> None:
        """Start the background thread and wait until the event loop is ready."""
        if self.is_running:
            return

        self._stopping = False
        self._ready_event.clear()
        self._thread = threading.Thread(
            target=self._thread_entry,
            name="py-atv-remote-asyncio",
            daemon=True,
        )
        self._thread.start()

        if not self._ready_event.wait(timeout=5.0):
            raise TimeoutError("Timed out waiting for asyncio background loop to start.")

    def _thread_entry(self) -> None:
        """Entry point for the background daemon thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready_event.set()

        try:
            loop.run_forever()
        finally:
            self._cleanup_loop(loop)

    def _cleanup_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Cancel remaining tasks and close the loop."""
        try:
            tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
            if tasks:
                for task in tasks:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception as exc:
            LOGGER.debug("Error while shutting down async loop: %s", exc)
        finally:
            loop.close()

    def submit(self, coro: Coroutine[Any, Any, T]) -> concurrent.futures.Future[T]:
        """Submit a coroutine to run on the background loop from any thread."""
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def call_soon(self, fn: Callable[..., Any], *args: Any) -> None:
        """Schedule a callback to be called as soon as possible on the background loop."""
        self.loop.call_soon_threadsafe(fn, *args)

    def stop(self, timeout: float = 3.0) -> None:
        """Stop the loop, cancel all tasks, and join the background thread."""
        if not self.is_running or self._loop is None:
            return

        self._stopping = True

        def _stop_callback() -> None:
            tasks = [t for t in asyncio.all_tasks(self._loop) if not t.done()]
            for t in tasks:
                t.cancel()
            if self._loop is not None:
                self._loop.stop()

        self._loop.call_soon_threadsafe(_stop_callback)

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                LOGGER.warning("AsyncRunner thread did not terminate within timeout.")
