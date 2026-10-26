"""Remote session service managing single active TV connection and commands."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from androidtvremote2 import VolumeInfo

from py_atv_remote.domain.errors import PairingRequiredError, TvNotFoundError, TvUnreachableError
from py_atv_remote.domain.keys import RemoteKey
from py_atv_remote.domain.models import ConnectionState, TvProfile, VolumeState
from py_atv_remote.infrastructure.arp import lookup_mac_for_ip
from py_atv_remote.infrastructure.atv_client import AndroidTvClientAdapter, RemoteClient
from py_atv_remote.infrastructure.cert_store import CertStore
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.infrastructure.wol import send_wol
from py_atv_remote.services.events import EventBus

LOGGER = logging.getLogger(__name__)


class RemoteSessionService:
    """Coordinates the persistent connection and control commands for the currently selected TV."""

    def __init__(
        self,
        config_store: ConfigStore,
        cert_store: CertStore,
        event_bus: EventBus,
        client_factory: Callable[[TvProfile], RemoteClient] | None = None,
        wol_sender: Callable[[str], None] | None = None,
    ) -> None:
        self._config_store = config_store
        self._cert_store = cert_store
        self._event_bus = event_bus
        self._client_factory = client_factory or self._default_client_factory
        self._wol_sender = wol_sender or send_wol

        self._current_profile: TvProfile | None = None
        self._state: ConnectionState = ConnectionState.IDLE
        self._client: RemoteClient | None = None
        self._lock = asyncio.Lock()
        self._background_tasks: set[asyncio.Task[None]] = set()

        self._volume: VolumeState | None = None
        self._current_app: str | None = None
        self._is_on: bool | None = None

    def _default_client_factory(self, profile: TvProfile) -> RemoteClient:
        return AndroidTvClientAdapter(
            client_name=self._config_store.get_client_name(),
            certfile=str(self._cert_store.get_cert_path(profile.id)),
            keyfile=str(self._cert_store.get_key_path(profile.id)),
            host=profile.host,
            api_port=profile.api_port,
            pair_port=profile.pair_port,
        )

    @property
    def current_profile(self) -> TvProfile | None:
        """Return the currently selected TV profile."""
        return self._current_profile

    @property
    def state(self) -> ConnectionState:
        """Return the current connection state."""
        return self._state

    @property
    def volume(self) -> VolumeState | None:
        """Return the last known volume state."""
        return self._volume

    @property
    def current_app(self) -> str | None:
        """Return the currently active app package on the TV."""
        return self._current_app

    @property
    def is_on(self) -> bool | None:
        """Return whether the TV is currently powered on."""
        return self._is_on

    def _set_state(self, state: ConnectionState) -> None:
        self._state = state
        self._event_bus.emit_state(state, self._current_profile)

    async def select_tv(self, tv_id: str) -> None:
        """Select a TV by ID and establish a persistent TLS session."""
        async with self._lock:
            profile = self._config_store.get_tv(tv_id)
            if profile is None:
                raise TvNotFoundError(f"TV profile with ID '{tv_id}' not found.")

            if (
                self._current_profile
                and self._current_profile.id == tv_id
                and self._client is not None
                and self._state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING)
            ):
                LOGGER.info("TV %s is already active.", tv_id)
                return

            self._disconnect_locked()
            self._current_profile = profile
            self._config_store.set_last_selected_id(tv_id)

            if not self._cert_store.has_certs(tv_id):
                LOGGER.info("TV %s has no certificates yet, requires pairing.", tv_id)
                self._set_state(ConnectionState.NEEDS_PAIRING)
                return

            self._set_state(ConnectionState.CONNECTING)
            client = self._client_factory(profile)
            self._client = client
            self._setup_callbacks(client)

            try:
                await client.connect()
                client.keep_reconnecting(invalid_auth_callback=self._on_invalid_auth)
                self._cert_store.secure_permissions(profile.id)
                self._set_state(ConnectionState.CONNECTED)
                LOGGER.info("Connected to TV '%s' (%s)", profile.name, profile.host)

                # Learn hardware WoL MAC from ARP table if missing
                if not profile.wol_mac:
                    learned_mac = lookup_mac_for_ip(profile.host)
                    if learned_mac:
                        LOGGER.info("Learned WoL MAC for '%s': %s", profile.name, learned_mac)
                        profile = profile.with_wol_mac(learned_mac)
                        self._current_profile = profile
                        self._config_store.save_tv(profile)
            except PairingRequiredError:
                LOGGER.warning("TV '%s' rejected auth; pairing required.", profile.name)
                self._set_state(ConnectionState.NEEDS_PAIRING)
            except TvUnreachableError as exc:
                LOGGER.warning("TV '%s' unreachable: %s", profile.name, exc)
                self._set_state(ConnectionState.OFFLINE)

    def _setup_callbacks(self, client: RemoteClient) -> None:
        client.add_is_on_updated_callback(self._on_is_on_updated)
        client.add_current_app_updated_callback(self._on_current_app_updated)
        client.add_volume_info_updated_callback(self._on_volume_info_updated)
        client.add_is_available_updated_callback(self._on_is_available_updated)

    def _on_is_on_updated(self, is_on: bool) -> None:
        self._is_on = is_on
        self._event_bus.emit_is_on(is_on)

    def _on_current_app_updated(self, current_app: str) -> None:
        self._current_app = current_app
        self._event_bus.emit_current_app(current_app)

    def _on_volume_info_updated(self, vol_info: VolumeInfo) -> None:
        vol = VolumeState(
            level=vol_info.get("level", 0),
            max_level=vol_info.get("max", 100),
            muted=vol_info.get("muted", False),
        )
        self._volume = vol
        self._event_bus.emit_volume(vol)

    def _on_is_available_updated(self, is_available: bool) -> None:
        if is_available:
            if self._state != ConnectionState.CONNECTED:
                self._set_state(ConnectionState.CONNECTED)
        else:
            if self._state == ConnectionState.CONNECTED:
                self._set_state(ConnectionState.RECONNECTING)

    def _on_invalid_auth(self) -> None:
        LOGGER.warning("Auth became invalid during reconnect.")
        self._set_state(ConnectionState.NEEDS_PAIRING)

    def send_key(self, key: RemoteKey) -> None:
        """Send a remote control key command."""
        if self._client is None or self._state not in (
            ConnectionState.CONNECTED,
            ConnectionState.RECONNECTING,
        ):
            LOGGER.warning("Cannot send key %s: TV is not connected (state: %s)", key, self._state)
            return
        self._client.send_key_command(key.value)

    def send_text(self, text: str) -> None:
        """Send input text string to the TV."""
        if self._client is None or self._state != ConnectionState.CONNECTED:
            LOGGER.warning("Cannot send text: TV is not connected.")
            return
        self._client.send_text(text)

    def launch_app(self, link_or_id: str) -> None:
        """Launch an application on the TV."""
        if self._client is None or self._state != ConnectionState.CONNECTED:
            LOGGER.warning("Cannot launch app: TV is not connected.")
            return
        self._client.send_launch_app_command(link_or_id)

    async def power(self) -> None:
        """Handle power toggle: send POWER key if connected, or Wake-on-LAN if offline."""
        if self._state == ConnectionState.CONNECTED:
            self.send_key(RemoteKey.POWER)
            return

        if self._current_profile and self._current_profile.wol_mac:
            LOGGER.info(
                "TV is offline. Sending Wake-on-LAN to %s...",
                self._current_profile.wol_mac,
            )
            self._wol_sender(self._current_profile.wol_mac)
            await self.retry_connection()
        else:
            # Attempt reconnect anyway
            await self.retry_connection()

    async def retry_connection(self) -> None:
        """Retry connection to the currently selected TV."""
        if self._current_profile:
            await self.select_tv(self._current_profile.id)

    def handle_ip_updated(self, updated_profile: TvProfile) -> None:
        """Handle dynamic IP change notification for the active profile."""
        if self._current_profile and self._current_profile.id == updated_profile.id:
            LOGGER.info("Active TV changed IP to %s. Reconnecting...", updated_profile.host)
            self._current_profile = updated_profile
            task = asyncio.create_task(self.select_tv(updated_profile.id))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    def disconnect(self) -> None:
        """Disconnect the active TV session."""
        self._disconnect_locked()

    def _disconnect_locked(self) -> None:
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception as exc:
                LOGGER.debug("Error disconnecting client: %s", exc)
            self._client = None

        self._current_profile = None
        self._volume = None
        self._current_app = None
        self._is_on = None
        self._set_state(ConnectionState.IDLE)
