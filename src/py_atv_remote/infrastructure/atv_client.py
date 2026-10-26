"""Adapter around androidtvremote2 library implementing RemoteClient protocol."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Protocol

from androidtvremote2 import (
    AndroidTVRemote,
    CannotConnect,
    ConnectionClosed,
    InvalidAuth,
    VolumeInfo,
)

from py_atv_remote.domain.errors import PairingRequiredError, TvUnreachableError

LOGGER = logging.getLogger(__name__)


class RemoteClient(Protocol):
    """Protocol defining the interface for Android TV Remote operations."""

    async def connect(self) -> None:
        """Connect to the Android TV."""
        ...

    def disconnect(self) -> None:
        """Disconnect the active session."""
        ...

    def keep_reconnecting(self, invalid_auth_callback: Callable[[], None] | None = None) -> None:
        """Enable auto-reconnect on connection loss."""
        ...

    def send_key_command(self, key_code: str, direction: str = "SHORT") -> None:
        """Send a key code command to the device."""
        ...

    def send_text(self, text: str) -> None:
        """Send a string of text to the device."""
        ...

    def send_launch_app_command(self, app_link_or_app_id: str) -> None:
        """Launch an app by package ID or deep link."""
        ...

    async def get_name_and_mac(self) -> tuple[str, str]:
        """Query the TV name and certificate MAC address."""
        ...

    def add_is_on_updated_callback(self, callback: Callable[[bool], None]) -> None: ...
    def add_current_app_updated_callback(self, callback: Callable[[str], None]) -> None: ...
    def add_volume_info_updated_callback(self, callback: Callable[[VolumeInfo], None]) -> None: ...
    def add_is_available_updated_callback(self, callback: Callable[[bool], None]) -> None: ...


class AndroidTvClientAdapter:
    """Concrete adapter wrapping androidtvremote2.AndroidTVRemote."""

    def __init__(
        self,
        client_name: str,
        certfile: str,
        keyfile: str,
        host: str,
        api_port: int = 6466,
        pair_port: int = 6467,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._raw_client = AndroidTVRemote(
            client_name=client_name,
            certfile=certfile,
            keyfile=keyfile,
            host=host,
            api_port=api_port,
            pair_port=pair_port,
            loop=loop,
            enable_ime=True,
            enable_voice=False,
        )

    @property
    def raw_client(self) -> AndroidTVRemote:
        """Return the underlying AndroidTVRemote instance."""
        return self._raw_client

    async def ensure_certificates(self) -> bool:
        """Generate certificate and key files if missing."""
        return bool(await self._raw_client.async_generate_cert_if_missing())

    async def connect(self) -> None:
        """Connect to the Android TV, translating library exceptions to domain errors."""
        await self.ensure_certificates()
        try:
            await self._raw_client.async_connect()
        except InvalidAuth as exc:
            raise PairingRequiredError("TV requires pairing before connection") from exc
        except (CannotConnect, ConnectionClosed, OSError) as exc:
            msg = f"Cannot connect to Android TV at {self._raw_client.host}"
            raise TvUnreachableError(msg) from exc

    def disconnect(self) -> None:
        self._raw_client.disconnect()

    def keep_reconnecting(self, invalid_auth_callback: Callable[[], None] | None = None) -> None:
        self._raw_client.keep_reconnecting(invalid_auth_callback=invalid_auth_callback)

    def send_key_command(self, key_code: str, direction: str = "SHORT") -> None:
        try:
            self._raw_client.send_key_command(key_code, direction=direction)
        except ConnectionClosed:
            LOGGER.warning("Cannot send key: connection is closed.")

    def send_text(self, text: str) -> None:
        try:
            self._raw_client.send_text(text)
        except ConnectionClosed:
            LOGGER.warning("Cannot send text: connection is closed.")

    def send_launch_app_command(self, app_link_or_app_id: str) -> None:
        try:
            self._raw_client.send_launch_app_command(app_link_or_app_id)
        except ConnectionClosed:
            LOGGER.warning("Cannot launch app: connection is closed.")

    async def get_name_and_mac(self) -> tuple[str, str]:
        await self.ensure_certificates()
        try:
            return await self._raw_client.async_get_name_and_mac()
        except CannotConnect as exc:
            raise TvUnreachableError(f"Cannot connect to {self._raw_client.host}") from exc

    def add_is_on_updated_callback(self, callback: Callable[[bool], None]) -> None:
        self._raw_client.add_is_on_updated_callback(callback)

    def add_current_app_updated_callback(self, callback: Callable[[str], None]) -> None:
        self._raw_client.add_current_app_updated_callback(callback)

    def add_volume_info_updated_callback(self, callback: Callable[[VolumeInfo], None]) -> None:
        self._raw_client.add_volume_info_updated_callback(callback)

    def add_is_available_updated_callback(self, callback: Callable[[bool], None]) -> None:
        self._raw_client.add_is_available_updated_callback(callback)
