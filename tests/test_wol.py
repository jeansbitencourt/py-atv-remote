"""Tests for Wake-on-LAN magic packet creation and broadcast."""

from unittest.mock import MagicMock, patch

import pytest

from py_atv_remote.infrastructure.wol import build_magic_packet, send_wol


def test_build_magic_packet() -> None:
    mac = "6a:5d:ac:20:7c:23"
    packet = build_magic_packet(mac)

    assert len(packet) == 102
    assert packet.startswith(b"\xff" * 6)
    expected_mac_bytes = bytes.fromhex("6a5dac207c23")
    assert packet[6:12] == expected_mac_bytes
    assert packet[12:18] == expected_mac_bytes
    assert packet[96:102] == expected_mac_bytes


def test_build_magic_packet_invalid_mac() -> None:
    with pytest.raises(ValueError):
        build_magic_packet("invalid-mac")


def test_send_wol_socket() -> None:
    with patch("socket.socket") as mock_socket_cls:
        mock_sock = MagicMock()
        mock_socket_cls.return_value.__enter__.return_value = mock_sock

        send_wol("6a:5d:ac:20:7c:23")

        mock_sock.setsockopt.assert_called_once()
        mock_sock.sendto.assert_called_once()
        args, _ = mock_sock.sendto.call_args
        assert len(args[0]) == 102
        assert args[1] == ("255.255.255.255", 9)
