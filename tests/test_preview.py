"""Preview safety, discovery, persistence and lifecycle tests without a TV."""

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from py_atv_remote.domain.models import TvProfile
from py_atv_remote.domain.preview import AdbIdentity, PreviewError, PreviewSettings, PreviewState
from py_atv_remote.infrastructure.adb import AdbClient, Toolchain, read_tail, validate_endpoint
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.infrastructure.paths import AppPaths
from py_atv_remote.services.events import DirectDispatcher
from py_atv_remote.services.preview_service import PreviewService


@pytest.fixture(autouse=True)
def validated_tools():
    with patch.object(Toolchain, "validate", AsyncMock(return_value="validated")):
        yield


@pytest.mark.parametrize(
    "endpoint",
    [
        "",
        "-host:5555",
        "1.2.3.4:0",
        "tv:65536",
        "tv:\uff11\uff12",
        "1.2.3.999:5555",
        "host;id:5555",
        "::1:5555",
    ],
)
def test_invalid_endpoints(endpoint: str) -> None:
    with pytest.raises(PreviewError):
        validate_endpoint(endpoint)


def test_mdns_filters_pairing_and_unsupported_addresses() -> None:
    assert AdbClient.parse_mdns("""List of discovered mdns services
adb-a _adb-tls-pairing._tcp. 192.168.1.2:1234
adb-b _adb-tls-connect._tcp. 192.168.1.2:4321
adb-b _adb-tls-connect._tcp. 192.168.1.2:4321
adb-c _adb-tls-connect._tcp. [::1]:1234
invalid
""") == ["192.168.1.2:4321"]


async def test_output_tail_is_bounded() -> None:
    stream = asyncio.StreamReader()
    stream.feed_data(b"a" * 20000 + b"final")
    stream.feed_eof()
    result = await read_tail(stream, 128)
    assert len(result) == 128
    assert result.endswith(b"final")


def configured_store(tmp_path: Path) -> ConfigStore:
    store = ConfigStore(AppPaths(base_dir=tmp_path))
    store.save_tv(TvProfile("tv1", "Sala", "192.168.1.2"))
    store.set_preview_settings(
        "tv1",
        PreviewSettings(
            enabled=True, endpoint="192.168.1.2:1234", identity="unique", mode="tcpip_legacy"
        ),
    )
    return store


def test_settings_survive_dhcp_and_are_removed_with_tv(tmp_path: Path) -> None:
    store = configured_store(tmp_path)
    profile = store.get_tv("tv1")
    assert profile is not None
    original = store.get_preview_settings("tv1")
    store.save_tv(profile.with_host("192.168.1.3").with_name("Nova sala"))
    assert ConfigStore(AppPaths(base_dir=tmp_path)).get_preview_settings("tv1") == original
    store.delete_tv("tv1")
    assert store.get_preview_settings("tv1") == PreviewSettings()
    store.set_preview_settings("tv1", original)
    assert store.get_preview_settings("tv1") == PreviewSettings()


def test_schema_two_migration_preserves_settings(tmp_path: Path) -> None:
    store = configured_store(tmp_path)
    config = tmp_path / "config.json"
    data = json.loads(config.read_text())
    data["schema_version"] = 2
    config.write_text(json.dumps(data))
    migrated = ConfigStore(AppPaths(base_dir=tmp_path))
    assert migrated.get_preview_settings("tv1") == store.get_preview_settings("tv1")
    assert json.loads(config.read_text())["schema_version"] == 3


async def test_identity_mismatch_never_launches_scrcpy(tmp_path: Path) -> None:
    store = configured_store(tmp_path)
    service = PreviewService(store, DirectDispatcher())
    events = []
    service.subscribe(events.append)
    with (
        patch.object(Toolchain, "resolve", return_value=Toolchain("adb", "scrcpy")),
        patch.object(AdbClient, "connect", AsyncMock(return_value=AdbIdentity("other", "TV"))),
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as launch,
    ):
        await service.start("tv1")
        await asyncio.sleep(0)
        await service.stop()
        launch.assert_not_called()
    assert any(event.state == PreviewState.ERROR for event in events)


async def test_double_start_and_stop_cancel_connection(tmp_path: Path) -> None:
    store = configured_store(tmp_path)
    service = PreviewService(store, DirectDispatcher())
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    async def connecting(_endpoint: str) -> AdbIdentity:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        return AdbIdentity("unique", "TV")

    with (
        patch.object(Toolchain, "resolve", return_value=Toolchain("adb", "scrcpy")),
        patch.object(AdbClient, "connect", side_effect=connecting) as connect,
    ):
        await service.start("tv1")
        await entered.wait()
        await service.start("tv1")
        await service.stop()
        assert cancelled.is_set()
        assert connect.call_count == 1


async def test_disabled_feature_does_not_resolve_tools(tmp_path: Path) -> None:
    store = configured_store(tmp_path)
    store.set_preview_settings("tv1", replace(store.get_preview_settings("tv1"), enabled=False))
    service = PreviewService(store, DirectDispatcher())
    with patch.object(Toolchain, "resolve") as resolve:
        await service.start("tv1")
        await asyncio.sleep(0)
        await service.stop()
        resolve.assert_not_called()


async def test_preview_launch_arguments_and_owned_cleanup(tmp_path: Path) -> None:
    store = configured_store(tmp_path)
    service = PreviewService(store, DirectDispatcher())
    entered = asyncio.Event()
    exited = asyncio.Event()

    class Process:
        returncode: int | None = None
        stdout = asyncio.StreamReader()

        async def wait(self) -> int:
            entered.set()
            await exited.wait()
            return self.returncode or 0

        def terminate(self) -> None:
            self.returncode = 0
            self.stdout.feed_eof()
            exited.set()

    process = Process()
    with (
        patch.object(Toolchain, "resolve", return_value=Toolchain("/tools/adb", "/tools/scrcpy")),
        patch.object(AdbClient, "connect", AsyncMock(return_value=AdbIdentity("unique", "TV"))),
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)) as launch,
    ):
        await service.start("tv1")
        await entered.wait()
        args, kwargs = launch.call_args
        assert args[0] == "/tools/scrcpy"
        assert args[args.index("--serial") + 1] == "192.168.1.2:1234"
        assert "--no-audio" in args and "--no-control" in args
        assert kwargs["env"]["ADB"] == "/tools/adb"
        await service.stop()
    assert exited.is_set()


async def test_pairing_code_is_stdin_only(tmp_path: Path) -> None:
    executable = tmp_path / "fake-adb"
    executable.write_text(
        "#!/usr/bin/env python3\nimport sys\n"
        "assert sys.argv[1:] == ['pair', 'tv:1234']\n"
        "code = sys.stdin.readline().strip()\n"
        "print('failed: ' + code)\nsys.exit(1)\n"
    )
    executable.chmod(0o700)
    client = AdbClient(Toolchain(str(executable), "unused"))
    with pytest.raises(PreviewError) as error:
        await client.pair("tv:1234", "654321")
    assert "654321" not in str(error.value)
    assert "[omitido]" in str(error.value)


async def test_real_child_timeout_is_reaped(tmp_path: Path) -> None:
    executable = tmp_path / "fake-adb"
    executable.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(60)\n")
    executable.chmod(0o700)
    client = AdbClient(Toolchain(str(executable), "unused"))
    with pytest.raises(PreviewError, match="tempo"):
        await client.command("devices", timeout=0.05)


async def test_system_tool_validation_keeps_full_bounded_help(tmp_path: Path) -> None:
    executable = tmp_path / "fake-tool"
    executable.write_text(
        "#!/usr/bin/env python3\nimport sys\n"
        "if '--help' in sys.argv:\n"
        " print('--serial --no-audio --no-control --video-bit-rate --max-fps')\n"
        " print('x' * 20000)\n"
        "else: print('version 5.0.1')\n"
    )
    executable.chmod(0o700)
    # Exercise the real validation method rather than the fixture's mocked method.
    from py_atv_remote.infrastructure.adb import run_command

    result = await run_command(str(executable), "--help", output_limit=131072)
    assert "--serial" in result
    assert len(result) > 8192


async def test_unidentified_tv_requires_one_time_confirmation(tmp_path: Path) -> None:
    store = configured_store(tmp_path)
    store.set_preview_settings("tv1", replace(store.get_preview_settings("tv1"), identity=""))
    service = PreviewService(store, DirectDispatcher())
    events = []
    service.subscribe(events.append)
    with patch.object(AdbClient, "connect", new_callable=AsyncMock) as connect:
        await service.start("tv1")
        await asyncio.sleep(0)
        await service.stop()
        connect.assert_not_called()
    assert any(
        event.state == PreviewState.ERROR and "Confirme" in event.message for event in events
    )
