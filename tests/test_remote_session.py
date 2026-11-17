"""Tests for RemoteSessionService."""

import asyncio
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


class PendingRemoteClient(FakeRemoteClient):
    """Simulate an offline TV whose handshake never completes."""

    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def connect(self) -> None:
        self.started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.cancelled.set()


def session_with_clients(
    tmp_path: Path, clients: dict[str, FakeRemoteClient], **options: float
) -> tuple[RemoteSessionService, ConfigStore, EventBus]:
    paths = AppPaths(base_dir=tmp_path)
    store = ConfigStore(paths)
    certs = CertStore(paths)
    for tv_id in clients:
        store.save_tv(TvProfile(tv_id, tv_id, f"{tv_id}.local", wol_mac="00:11:22:33:44:55"))
        certs.get_cert_path(tv_id).write_text("CERT")
        certs.get_key_path(tv_id).write_text("KEY")
    bus = EventBus(DirectDispatcher())
    return (
        RemoteSessionService(store, certs, bus, client_factory=lambda p: clients[p.id], **options),
        store,
        bus,
    )


async def test_switch_from_pending_offline_tv_connects_without_waiting(tmp_path: Path) -> None:
    offline, online = PendingRemoteClient(), FakeRemoteClient()
    session, store, _ = session_with_clients(tmp_path, {"offline": offline, "online": online})
    first = asyncio.create_task(session.select_tv("offline"))
    await offline.started.wait()
    try:
        await asyncio.wait_for(session.select_tv("online"), timeout=0.5)
        assert session.state == ConnectionState.CONNECTED
        assert session.current_profile is not None and session.current_profile.id == "online"
        assert store.get_last_selected_id() == "online"
        assert offline.disconnected and offline.cancelled.is_set()
        session.send_key(RemoteKey.DPAD_UP)
        assert online.sent_keys == ["KEYCODE_DPAD_UP"]
    finally:
        session.disconnect()
        first.cancel()
        await asyncio.gather(first, return_exceptions=True)


async def test_callbacks_from_replaced_client_are_ignored(tmp_path: Path) -> None:
    old, current = FakeRemoteClient(), FakeRemoteClient()
    session, _, _ = session_with_clients(tmp_path, {"old": old, "current": current})
    await session.select_tv("old")
    await session.select_tv("current")
    old._is_available_cbs[0](False)
    assert session.state == ConnectionState.CONNECTED
    assert old._invalid_auth_cb is not None
    old._invalid_auth_cb()
    old._current_app_cbs[0]("old.app")
    old._volume_cbs[0]({"level": 90, "max": 100, "muted": False})
    old._is_on_cbs[0](False)
    assert session.state == ConnectionState.CONNECTED
    assert session.current_app is None and session.volume is None and session.is_on is None
    session.disconnect()
    current._is_available_cbs[0](True)
    assert session.state == ConnectionState.IDLE


async def test_pending_connection_times_out_and_can_retry(tmp_path: Path) -> None:
    pending = PendingRemoteClient()
    clients: dict[str, FakeRemoteClient] = {"tv": pending}
    session, _, _ = session_with_clients(tmp_path, clients, connect_timeout=0.02)
    await session.select_tv("tv")
    assert session.state == ConnectionState.OFFLINE
    assert pending.disconnected and pending.cancelled.is_set()
    clients["tv"] = FakeRemoteClient()
    await session.retry_connection()
    assert session.state == ConnectionState.CONNECTED
    session.disconnect()


async def test_disconnect_cancels_pending_connection(tmp_path: Path) -> None:
    pending = PendingRemoteClient()
    session, _, _ = session_with_clients(tmp_path, {"tv": pending})
    task = asyncio.create_task(session.select_tv("tv"))
    await pending.started.wait()
    try:
        session.disconnect()
        await asyncio.wait_for(asyncio.shield(task), 0.5)
        assert pending.cancelled.is_set()
        assert session.state == ConnectionState.IDLE
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_dhcp_change_replaces_active_client(tmp_path: Path) -> None:
    old, replacement = FakeRemoteClient(), FakeRemoteClient()
    clients = {"tv": old}
    session, store, _ = session_with_clients(tmp_path, clients)
    await session.select_tv("tv")
    profile = store.get_tv("tv")
    assert profile is not None
    updated = profile.with_host("192.168.1.42")
    store.save_tv(updated)
    clients["tv"] = replacement
    session.handle_ip_updated(updated)
    await asyncio.gather(*session._background_tasks)
    assert old.disconnected and replacement.connected
    assert session.current_profile is not None and session.current_profile.host == updated.host
    session.disconnect()


async def test_reselecting_connected_tv_republishes_current_state(tmp_path: Path) -> None:
    client = FakeRemoteClient()
    session, _, bus = session_with_clients(tmp_path, {"tv": client})
    await session.select_tv("tv")
    states: list[ConnectionState] = []
    bus.on_state(lambda state, _profile: states.append(state))
    await session.select_tv("tv")
    assert states == [ConnectionState.CONNECTED]
    assert not client.disconnected
    session.disconnect()
