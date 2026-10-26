"""Tests for mDNS service info parsing."""

from unittest.mock import MagicMock

from py_atv_remote.infrastructure.mdns_browser import normalize_mac_or_id, parse_service_info


def test_normalize_mac_or_id() -> None:
    assert normalize_mac_or_id(b"84:C8:A0:2B:91:4C") == "84c8a02b914c"
    assert normalize_mac_or_id("84-C8-A0-2B-91-4C") == "84c8a02b914c"
    assert normalize_mac_or_id("84C8A02B914C") == "84c8a02b914c"
    assert normalize_mac_or_id(None) is None
    assert normalize_mac_or_id("") is None


def test_parse_service_info() -> None:
    info = MagicMock()
    info.parsed_addresses.return_value = [
        "2804:1790:9229:5b00:d89b:2db4:9dc4:4583",
        "192.168.2.104",
    ]
    info.port = 6466
    info.properties = {
        b"bt": b"84:C8:A0:2B:91:4C",
        b"isDeviceInStandbyMode": b"false",
    }

    tv = parse_service_info("TV da sala._androidtvremote2._tcp.local.", info)
    assert tv is not None
    assert tv.name == "TV da sala"
    assert tv.host == "192.168.2.104"  # Preferred IPv4
    assert tv.id == "84c8a02b914c"
    assert tv.in_standby is False
    assert tv.source == "mdns"


def test_parse_service_info_standby_true() -> None:
    info = MagicMock()
    info.parsed_addresses.return_value = ["192.168.2.109"]
    info.port = 6466
    info.properties = {
        b"bt": b"84:3E:1D:6B:5E:7D",
        b"isDeviceInStandbyMode": b"true",
    }

    tv = parse_service_info("TV do quarto._androidtvremote2._tcp.local.", info)
    assert tv is not None
    assert tv.name == "TV do quarto"
    assert tv.host == "192.168.2.109"
    assert tv.id == "843e1d6b5e7d"
    assert tv.in_standby is True
