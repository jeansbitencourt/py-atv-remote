"""Tests for ARP table parsing."""

from pathlib import Path

from py_atv_remote.infrastructure.arp import lookup_mac_for_ip, parse_arp_table

SAMPLE_ARP_CONTENT = """IP address  HW type  Flags  HW address         Mask  Device
192.168.2.1      0x1         0x2         e8:28:c1:00:11:22     *        wlp0s20f3
192.168.2.104    0x1         0x2         6a:5d:ac:20:7c:23     *        wlp0s20f3
192.168.2.109    0x1         0x2         9e:0d:d5:40:b6:98     *        wlp0s20f3
192.168.2.200    0x1         0x0         00:00:00:00:00:00     *        wlp0s20f3
"""


def test_parse_arp_table() -> None:
    mapping = parse_arp_table(SAMPLE_ARP_CONTENT)
    assert mapping["192.168.2.1"] == "e8:28:c1:00:11:22"
    assert mapping["192.168.2.104"] == "6a:5d:ac:20:7c:23"
    assert mapping["192.168.2.109"] == "9e:0d:d5:40:b6:98"
    assert "192.168.2.200" not in mapping  # Incomplete ARP entry excluded


def test_lookup_mac_for_ip(tmp_path: Path) -> None:
    arp_file = tmp_path / "arp"
    arp_file.write_text(SAMPLE_ARP_CONTENT)

    assert lookup_mac_for_ip("192.168.2.104", arp_file=arp_file) == "6a:5d:ac:20:7c:23"
    assert lookup_mac_for_ip("192.168.2.254", arp_file=arp_file) is None
