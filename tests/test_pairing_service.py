"""Tests for PairingService."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from py_atv_remote.domain.errors import InvalidPinError
from py_atv_remote.domain.models import DiscoveredTv
from py_atv_remote.infrastructure.cert_store import CertStore
from py_atv_remote.infrastructure.config_store import ConfigStore
from py_atv_remote.infrastructure.paths import AppPaths
from py_atv_remote.services.pairing_service import PairingService


@pytest.mark.asyncio
async def test_pairing_workflow_success(tmp_path: Path) -> None:
    paths = AppPaths(base_dir=tmp_path)
    config_store = ConfigStore(paths)
    cert_store = CertStore(paths)
    service = PairingService(config_store, cert_store)

    target = DiscoveredTv(
        id="84c8a02b914c",
        name="TV da sala",
        host="192.168.2.104",
        source="mdns",
    )

    with (
        patch("py_atv_remote.services.pairing_service.AndroidTVRemote") as mock_cls,
    ):
        mock_instance = AsyncMock()
        mock_instance.async_generate_cert_if_missing.return_value = True
        mock_instance.async_get_name_and_mac.return_value = (
            "Philips Google TV TA7",
            "84:C8:A0:2B:91:4C",
        )
        mock_instance.async_start_pairing.return_value = None
        mock_instance.async_finish_pairing.return_value = None
        mock_cls.return_value = mock_instance

        # 1. Start pairing
        session = await service.start_pairing(target)
        assert session.tv_id == "84c8a02b914c"
        assert session.model == "Philips Google TV TA7"
        mock_instance.async_start_pairing.assert_awaited_once()

        # 2. Finish pairing with valid PIN
        profile = await service.finish_pairing(session, "A1B2C3")
        assert profile.id == "84c8a02b914c"
        assert profile.name == "TV da sala"
        assert profile.model == "Philips Google TV TA7"
        mock_instance.async_finish_pairing.assert_awaited_once_with("A1B2C3")

        # Verify saved in config store
        saved = config_store.get_tv("84c8a02b914c")
        assert saved is not None
        assert saved.name == "TV da sala"


@pytest.mark.asyncio
async def test_pairing_invalid_pin(tmp_path: Path) -> None:
    paths = AppPaths(base_dir=tmp_path)
    config_store = ConfigStore(paths)
    cert_store = CertStore(paths)
    service = PairingService(config_store, cert_store)

    target = DiscoveredTv(id="test_tv", name="Test", host="192.168.1.50")

    with patch("py_atv_remote.services.pairing_service.AndroidTVRemote") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.async_get_name_and_mac.return_value = ("Test", "AA:BB:CC:DD:EE:FF")
        mock_cls.return_value = mock_instance

        session = await service.start_pairing(target)

        # Empty PIN
        with pytest.raises(InvalidPinError):
            await service.finish_pairing(session, "")

        # TV rejects PIN
        from androidtvremote2 import InvalidAuth

        mock_instance.async_finish_pairing.side_effect = InvalidAuth("Wrong code")
        with pytest.raises(InvalidPinError):
            await service.finish_pairing(session, "000000")


@pytest.mark.asyncio
async def test_pairing_cancel(tmp_path: Path) -> None:
    paths = AppPaths(base_dir=tmp_path)
    config_store = ConfigStore(paths)
    cert_store = CertStore(paths)
    service = PairingService(config_store, cert_store)

    target = DiscoveredTv(id="tv_cancel", name="Cancel TV", host="192.168.1.99")

    with patch("py_atv_remote.services.pairing_service.AndroidTVRemote") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.disconnect = MagicMock()
        mock_instance.async_get_name_and_mac.return_value = ("Model", "11:22:33:44:55:66")
        mock_cls.return_value = mock_instance

        session = await service.start_pairing(target)
        # Create dummy cert file to test cleanup
        cert_p = cert_store.get_cert_path(session.tv_id)
        cert_p.write_text("DUMMY")

        service.cancel_pairing(session)
        mock_instance.disconnect.assert_called_once()
        assert not cert_p.exists()
