"""Tests for EventBus and Dispatcher."""

from py_atv_remote.domain.models import ConnectionState, DiscoveredTv, TvProfile, VolumeState
from py_atv_remote.services.events import DirectDispatcher, EventBus


class RecordingDispatcher:
    def __init__(self) -> None:
        self.dispatched_count = 0

    def post(self, fn: object) -> None:
        self.dispatched_count += 1
        if callable(fn):
            fn()


def test_event_bus_delivery_and_unsubscription() -> None:
    dispatcher = RecordingDispatcher()
    bus = EventBus(dispatcher)

    received_states: list[ConnectionState] = []
    unsub = bus.on_state(lambda st, _prof: received_states.append(st))

    bus.emit_state(ConnectionState.CONNECTING, None)
    bus.emit_state(ConnectionState.CONNECTED, TvProfile(id="1", name="TV", host="10.0.0.1"))

    assert received_states == [ConnectionState.CONNECTING, ConnectionState.CONNECTED]
    assert dispatcher.dispatched_count == 2

    # Unsubscribe
    unsub()
    bus.emit_state(ConnectionState.OFFLINE, None)
    assert received_states == [ConnectionState.CONNECTING, ConnectionState.CONNECTED]


def test_event_bus_all_channels() -> None:
    bus = EventBus(DirectDispatcher())

    volumes: list[VolumeState] = []
    apps: list[str] = []
    powers: list[bool] = []
    discovered: list[DiscoveredTv] = []
    disappeared: list[str] = []
    errors: list[str] = []

    bus.on_volume(lambda v: volumes.append(v))
    bus.on_current_app(lambda a: apps.append(a))
    bus.on_is_on(lambda p: powers.append(p))
    bus.on_tv_discovered(lambda d: discovered.append(d))
    bus.on_tv_disappeared(lambda d_id: disappeared.append(d_id))
    bus.on_error(lambda msg, _exc: errors.append(msg))

    bus.emit_volume(VolumeState(level=10, max_level=100, muted=False))
    bus.emit_current_app("com.google.android.youtube.tv")
    bus.emit_is_on(True)
    bus.emit_tv_discovered(DiscoveredTv(id="abc", name="Living TV", host="192.168.1.5"))
    bus.emit_tv_disappeared("abc")
    bus.emit_error("Connection timed out")

    assert len(volumes) == 1 and volumes[0].level == 10
    assert apps == ["com.google.android.youtube.tv"]
    assert powers == [True]
    assert len(discovered) == 1 and discovered[0].name == "Living TV"
    assert disappeared == ["abc"]
    assert errors == ["Connection timed out"]
