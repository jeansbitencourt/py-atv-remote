"""Optional preview orchestration on the application's background loop."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from dataclasses import replace

from py_atv_remote.domain.preview import (
    QUALITY_PRESETS,
    PreviewError,
    PreviewEvent,
    PreviewState,
)
from py_atv_remote.infrastructure.adb import AdbClient, Toolchain, read_tail, terminate
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.services.events import Dispatcher


class PreviewService:
    """Maintain a single owned preview with cancellation and identity checks."""

    def __init__(self, store: ConfigStore, dispatcher: Dispatcher) -> None:
        self._store = store
        self._dispatcher = dispatcher
        self._listeners: list[Callable[[PreviewEvent], None]] = []
        self._task: asyncio.Task[None] | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._tv_id = ""
        self._confirmed_once: dict[str, str] = {}

    def subscribe(self, listener: Callable[[PreviewEvent], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def _emit(self, state: PreviewState, message: str = "") -> None:
        event = PreviewEvent(self._tv_id, state, message)
        listeners = list(self._listeners)

        def deliver() -> None:
            for listener in listeners:
                listener(event)

        self._dispatcher.post(deliver)

    async def confirm_unidentified_once(self, tv_id: str, endpoint: str) -> None:
        """Allow one launch after explicit confirmation when the TV hides its serial."""
        self._confirmed_once[tv_id] = endpoint

    async def start(self, tv_id: str) -> None:
        async with self._lock:
            if self._task is not None and not self._task.done():
                return
            self._tv_id = tv_id
            self._task = asyncio.create_task(self._run(tv_id))

    async def _run(self, tv_id: str) -> None:
        self._emit(PreviewState.PREPARING)
        reader: asyncio.Task[bytes] | None = None
        try:
            profile = self._store.get_tv(tv_id)
            settings = self._store.get_preview_settings(tv_id)
            if profile is None or not settings.enabled:
                raise PreviewError("Ative e configure a visualização para esta TV pelo menu.")
            confirmed_endpoint = self._confirmed_once.pop(tv_id, None)
            if not settings.identity and confirmed_endpoint != settings.endpoint:
                raise PreviewError("Confirme a TV em Configurar ADB antes de cada visualização.")
            tools = Toolchain.resolve()
            await tools.validate()
            adb = AdbClient(tools)
            endpoint = settings.endpoint
            if settings.mode == "wireless_tls" and settings.identity:
                try:
                    candidates = await adb.discover(profile.host)
                    if len(candidates) == 1:
                        endpoint = candidates[0]
                except PreviewError:
                    pass
            identity = await adb.connect(endpoint)
            if identity.serial != settings.identity:
                raise PreviewError(
                    "A identidade ADB mudou. Confirme a TV novamente na configuração."
                )
            current = self._store.get_preview_settings(tv_id)
            if self._store.get_tv(tv_id) is None or current != settings:
                raise PreviewError("Configuração alterada durante a conexão. Tente novamente.")
            self._store.set_preview_settings(tv_id, replace(settings, endpoint=endpoint))
            size, fps, bitrate = QUALITY_PRESETS[settings.quality]
            try:
                self._process = await asyncio.create_subprocess_exec(
                    tools.scrcpy,
                    "--serial",
                    endpoint,
                    "--window-title",
                    f"py-atv-remote | {profile.name}",
                    "--max-size",
                    str(size),
                    "--max-fps",
                    str(fps),
                    "--video-bit-rate",
                    bitrate,
                    "--no-audio",
                    "--no-control",
                    env={**os.environ, "ADB": tools.adb},
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
            except OSError as exc:
                raise PreviewError("Não foi possível iniciar scrcpy.") from exc
            reader = asyncio.create_task(read_tail(self._process.stdout))
            # A running process is not proof that decoded frames reached a visible window.
            self._emit(PreviewState.RUNNING, "Janela externa iniciada; verifique a imagem na TV.")
            code = await self._process.wait()
            details = (await reader).decode(errors="replace").strip()
            if code:
                raise PreviewError(
                    details or "scrcpy encerrou com erro. Verifique captura e encoder."
                )
        except PreviewError as exc:
            self._emit(PreviewState.ERROR, str(exc))
        finally:
            if self._process is not None:
                await terminate(self._process)
                self._process = None
            if reader is not None:
                if not reader.done():
                    reader.cancel()
                await asyncio.gather(reader, return_exceptions=True)
            self._emit(PreviewState.CLOSED)

    async def stop(self) -> None:
        async with self._lock:
            task = self._task
            if task is not None and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            self._task = None
