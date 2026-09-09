"""Packet framing for the Chandler Systems Bluetooth protocol."""
from __future__ import annotations

import json
from enum import Enum
from typing import Any

from . import crc16

# Header bits
HEADER_FIRST_PACKET = 0x80
HEADER_LAST_PACKET = 0x40
HEADER_KEEP_ALIVE = 0x20
HEADER_KEEP_ALIVE_TYPE = 0x10
HEADER_ACK_NAK = 0x08
HEADER_ACK_NAK_TYPE = 0x04
HEADER_TIMEOUT = 0x02
HEADER_TIMEOUT_TYPE = 0x01
HEADER_NOP = 0x00

HEADER_SINGLE_PACKET = HEADER_FIRST_PACKET | HEADER_LAST_PACKET

# Status packets, each a single byte built from the header bits above.
PACKET_ACK = HEADER_SINGLE_PACKET | HEADER_ACK_NAK | HEADER_ACK_NAK_TYPE  # 0xCC
PACKET_NAK = HEADER_SINGLE_PACKET | HEADER_ACK_NAK  # 0xC8
PACKET_MARCO = HEADER_SINGLE_PACKET | HEADER_KEEP_ALIVE  # 0xE0
PACKET_POLO = HEADER_SINGLE_PACKET | HEADER_KEEP_ALIVE | HEADER_KEEP_ALIVE_TYPE  # 0xF0
PACKET_TIMEOUT_QUERY = HEADER_SINGLE_PACKET | HEADER_TIMEOUT  # 0xC2
PACKET_TIMEOUT_ACK = HEADER_SINGLE_PACKET | HEADER_TIMEOUT | HEADER_TIMEOUT_TYPE  # 0xC3

# Raw packets: sent as bare bytes with no header or checksum.
PACKET_AUTH_REQUEST = 0xEA
PACKET_DEVICE_RESET = ord("R")

HEADER_SIZE_BYTES = 1
CRC_SIZE_BYTES = 2
_EMPTY_JSON_SIZE_BYTES = 2
MIN_DATA_PACKET_SIZE = HEADER_SIZE_BYTES + CRC_SIZE_BYTES + _EMPTY_JSON_SIZE_BYTES

# The nRF52840 radio in these valves caps the MTU here regardless of what the
# host offers.
MAX_PACKET_SIZE = 251


class StatusPacket(Enum):
    """A single-byte status packet received from the device."""

    ACK = PACKET_ACK
    NAK = PACKET_NAK
    MARCO = PACKET_MARCO
    POLO = PACKET_POLO
    TIMEOUT_QUERY = PACKET_TIMEOUT_QUERY
    TIMEOUT_ACK = PACKET_TIMEOUT_ACK


class PacketError(Exception):
    """Raised when a packet cannot be built or parsed."""


def classify_status(data: bytes) -> StatusPacket | None:
    """Identify a single-byte status packet, or None if this isn't one."""
    if len(data) != 1:
        return None
    try:
        return StatusPacket(data[0])
    except ValueError:
        return None


def build_status_packet(packet: int) -> bytes:
    """Build a single-byte status packet."""
    return bytes([packet])


def build_data_packet(payload: dict[str, Any]) -> bytes:
    """Build a single data packet carrying a JSON payload.

    The checksum covers the header and the JSON, and is appended
    little-endian.
    """
    body = bytes([HEADER_SINGLE_PACKET]) + json.dumps(
        payload, separators=(",", ":")
    ).encode("utf-8")

    if len(body) + CRC_SIZE_BYTES > MAX_PACKET_SIZE:
        raise PacketError(
            f"Payload of {len(body)} bytes exceeds the {MAX_PACKET_SIZE} byte "
            "packet limit and would need chunking"
        )

    checksum = crc16.compute(body)
    return body + bytes([checksum & 0xFF, (checksum >> 8) & 0xFF])


def parse_data_packet(data: bytes) -> tuple[int, bytes]:
    """Validate a received data packet and return its header and JSON bytes.

    Raises PacketError if the packet is too short or the checksum is bad; the
    caller should NAK so the device retransmits.
    """
    if len(data) < MIN_DATA_PACKET_SIZE:
        raise PacketError(f"Packet of {len(data)} bytes is below the minimum size")

    body = data[:-CRC_SIZE_BYTES]
    checksum = (data[-1] << 8) | data[-CRC_SIZE_BYTES]

    if not crc16.verify(checksum, body):
        raise PacketError(f"Checksum mismatch on packet {data.hex()}")

    return body[0], body[HEADER_SIZE_BYTES:]


def is_flag_set(header: int, flag: int) -> bool:
    """Check whether a header bit is set."""
    return (header & flag) > 0
