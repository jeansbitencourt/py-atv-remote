"""ARP table inspection for discovering hardware MAC addresses on Linux."""

from __future__ import annotations

import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)

PROC_NET_ARP = Path("/proc/net/arp")


def parse_arp_table(content: str) -> dict[str, str]:
    """Parse /proc/net/arp content into a dictionary mapping IP -> MAC."""
    mapping: dict[str, str] = {}
    lines = content.strip().splitlines()
    if not lines:
        return mapping

    # Skip header: IP address  HW type  Flags  HW address  Mask  Device
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 4:
            ip = parts[0].strip()
            mac = parts[3].strip().lower()
            # Ignore incomplete ARP entries (00:00:00:00:00:00)
            if mac and mac != "00:00:00:00:00:00" and len(mac) == 17:
                mapping[ip] = mac
    return mapping


def lookup_mac_for_ip(ip: str, arp_file: Path | None = None) -> str | None:
    """Lookup the hardware MAC address associated with an IP in the local ARP table."""
    target_path = arp_file or PROC_NET_ARP
    if not target_path.exists():
        return None

    try:
        content = target_path.read_text(encoding="utf-8")
        mapping = parse_arp_table(content)
        return mapping.get(ip)
    except OSError as exc:
        LOGGER.debug("Could not read ARP table from %s: %s", target_path, exc)
        return None
