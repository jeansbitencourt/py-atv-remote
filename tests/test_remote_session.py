"""Tests for RemoteSessionService."""

from collections.abc import Callable
from pathlib import Path

import pytest
from androidtvremote2 import VolumeInfo

from py_atv_remote.domain.errors import TvUnreachableError
from py_atv_remote.domain.keys import RemoteKey
from py_atv_remote.domain.models import ConnectionState, TvProfile
from py_atv_remote.infrastructure.cert_store import CertStore
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.infrastructure.paths import AppPaths
from py_atv_remote.services.events import DirectDispatcher, EventBus
from py_atv_remote.services.remote_session import RemoteSessionService


class FakeRemoteClient:
    """Mock client for testing RemoteSessionService without real network."""

    def __init__(
        self,
        should_fail_connect: Exception | None = None,
    ) -> None:
        self.should_fail_connect = should_fail_connect
        self.connected = False
        self.disconnected = False
        self.sent_keys: list[str] = []
        self.sent_text: list[str] = []
        self.launched_apps: list[str] = []
        self.auto_reconnect_enabled = False

        self._is_on_cbs: list[Callable[[bool], None]] = []
        self._current_app_cbs: list[Callable[[str], None]] = []
        self._volume_cbs: list[Callable[[VolumeInfo], None]] = []
        self._is_available_cbs: list[Callable[[bool], None]] = []
        self._invalid_auth_cb: Callable[[], None] | None = None

    async def connect(self) -> None:
        if self.should_fail_connect:
            raise self.should_fail_connect
        self.connected = True

    def disconnect(self) -> None:
        self.disconnected = True
        self.connected = False

    def keep_reconnecting(self, invalid_auth_callback: Callable[[], None] | None = None) -> None:
        self.auto_reconnect_enabled = True
        self._invalid_auth_cb = invalid_auth_callback

    def send_key_command(self, key_code: str, direction: str = "SHORT") -> None:
        self.sent_keys.append(key_code)

    def send_text(self, text: str) -> None:
        self.sent_text.append(text)

    def send_launch_app_command(self, app_link_or_app_id: str) -> None:
        self.launched_apps.append(app_link_or_app_id)

    async def get_name_and_mac(self) -> tuple[str, str]:
        return "Test TV", "00:11:22:33:44:55"

    def add_is_on_updated_callback(self, callback: Callable[[bool], None]) -> None:
        self._is_on_cbs.append(callback)

    def add_current_app_updated_callback(self, callback: Callable[[str], None]) -> None:
        self._current_app_cbs.append(callback)

    def add_volume_info_updated_callback(self, callback: Callable[[VolumeInfo], None]) -> None:
        self._volume_cbs.append(callback)

    def add_is_available_updated_callback(self, callback: Callable[[bool], None]) -> None:
        self._is_available_cbs.append(callback)


@pytest.mark.asyncio
async def test_session_connect_success_and_commands(tmp_path: Path) -> None:
    paths = AppPaths(base_dir=tmp_path)
    config_store = ConfigStore(paths)
    cert_store = CertStore(paths)
    event_bus = EventBus(DirectDispatcher())

    profile = TvProfile(id="tv1", name="Living Room", host="192.168.1.100")
    config_store.save_tv(profile)

    # Populate certs
    cert_store.get_cert_path("tv1").write_text("CERT")
    cert_store.get_key_path("tv1").write_text("KEY")

    fake_client = FakeRemoteClient()
    session = RemoteSessionService(
        config_store=config_store,
        cert_store=cert_store,
        event_bus=event_bus,
        client_factory=lambda _p: fake_client,
    )

    states: list[ConnectionState] = []
    event_bus.on_state(lambda st, _p: states.append(st))

    await session.select_tv("tv1")

    assert session.state == ConnectionState.CONNECTED
    assert fake_client.connected is True
    assert fake_client.auto_reconnect_enabled is True
    assert config_store.get_last_selected_id() == "tv1"

    # Send key, text, app
    session.send_key(RemoteKey.DPAD_UP)
    session.send_text("search query")
    session.launch_app("https://www.youtube.com")

    assert fake_client.sent_keys == ["KEYCODE_DPAD_UP"]
    assert fake_client.sent_text == ["search query"]
    assert fake_client.launched_apps == ["https://www.youtube.com"]

    # Test is_available toggle -> RECONNECTING -> CONNECTED
    fake_client._is_available_cbs[0](False)
    state_after_drop: ConnectionState = session.state
    assert state_after_drop == ConnectionState.RECONNECTING

    fake_client._is_available_cbs[0](True)
    state_after_reconnect: ConnectionState = session.state
    assert state_after_reconnect == ConnectionState.CONNECTED


@pytest.mark.asyncio
async def test_session_needs_pairing_when_no_certs(tmp_path: Path) -> None:
    paths = AppPaths(base_dir=tmp_path)
    config_store = ConfigStore(paths)
    cert_store = CertStore(paths)
    event_bus = EventBus(DirectDispatcher())

    profile = TvProfile(id="tv_new", name="Bedroom", host="192.168.1.101")
    config_store.save_tv(profile)

    session = RemoteSessionService(
        config_store=config_store,
        cert_store=cert_store,
        event_bus=event_bus,
    )

    await session.select_tv("tv_new")
    assert session.state == ConnectionState.NEEDS_PAIRING


@pytest.mark.asyncio
async def test_session_offline_on_unreachable(tmp_path: Path) -> None:
    paths = AppPaths(base_dir=tmp_path)
    config_store = ConfigStore(paths)
    cert_store = CertStore(paths)
    event_bus = EventBus(DirectDispatcher())

    profile = TvProfile(id="tv_off", name="Offline TV", host="192.168.1.102")
    config_store.save_tv(profile)
    cert_store.get_cert_path("tv_off").write_text("CERT")
    cert_store.get_key_path("tv_off").write_text("KEY")

    fake_client = FakeRemoteClient(should_fail_connect=TvUnreachableError("Timeout"))
    session = RemoteSessionService(
        config_store=config_store,
        cert_store=cert_store,
        event_bus=event_bus,
        client_factory=lambda _p: fake_client,
    )

    await session.select_tv("tv_off")
    assert session.state == ConnectionState.OFFLINE
