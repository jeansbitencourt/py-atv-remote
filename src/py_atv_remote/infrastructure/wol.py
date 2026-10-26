"""Wake-on-LAN magic packet generator and broadcaster."""

from __future__ import annotations

import logging
import socket

LOGGER = logging.getLogger(__name__)


def build_magic_packet(mac: str) -> bytes:
    """Construct a standard 102-byte Wake-on-LAN magic packet for a MAC address."""
    clean_mac = "".join(c for c in mac if c.isalnum())
    if len(clean_mac) != 12:
        raise ValueError(f"Invalid MAC address format: '{mac}' (expected 12 hex digits)")

    mac_bytes = bytes.fromhex(clean_mac)
    return b"\xff" * 6 + mac_bytes * 16


def send_wol(
    mac: str,
    broadcast_ip: str = "255.255.255.255",
    port: int = 9,
) -> None:
    """Broadcast a Wake-on-LAN magic packet over UDP."""
    packet = build_magic_packet(mac)
    LOGGER.info("Sending WoL magic packet for %s to %s:%d", mac, broadcast_ip, port)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.sendto(packet, (broadcast_ip, port))
        except OSError as exc:
            LOGGER.warning("Failed to send Wake-on-LAN packet to %s: %s", broadcast_ip, exc)
