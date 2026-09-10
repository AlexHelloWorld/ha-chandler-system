"""Test Chandler Bluetooth packet framing."""
import json

import pytest

from custom_components.chandler_system import crc16, protocol


def test_status_packet_values():
    """The status bytes must match the bit math in the API guide."""
    assert protocol.PACKET_ACK == 0xCC
    assert protocol.PACKET_NAK == 0xC8
    assert protocol.PACKET_MARCO == 0xE0
    assert protocol.PACKET_POLO == 0xF0
    assert protocol.PACKET_TIMEOUT_QUERY == 0xC2
    assert protocol.PACKET_TIMEOUT_ACK == 0xC3
    assert protocol.HEADER_SINGLE_PACKET == 0xC0


def test_classify_status():
    assert protocol.classify_status(b"\xcc") is protocol.StatusPacket.ACK
    assert protocol.classify_status(b"\xc8") is protocol.StatusPacket.NAK
    assert protocol.classify_status(b"\xe0") is protocol.StatusPacket.MARCO
    assert protocol.classify_status(b"\xc2") is protocol.StatusPacket.TIMEOUT_QUERY


def test_classify_status_ignores_non_status():
    assert protocol.classify_status(b"\x00") is None
    assert protocol.classify_status(b"\xc0\x7b\x7d\x00\x00") is None
    assert protocol.classify_status(b"") is None


def test_build_data_packet_shape():
    packet = protocol.build_data_packet({"grn": 1})

    assert packet[0] == protocol.HEADER_SINGLE_PACKET
    assert packet[1:-2] == b'{"grn":1}'
    assert len(packet) == 1 + 9 + 2


# Captured from hardware. The valve acknowledged this exact packet, and
# rejected the same payload with the checksum bytes the other way round.
ACCEPTED_BY_DEVICE = bytes.fromhex("c07b226473223a34357d9153")
# Captured from hardware: a packet the valve itself transmitted.
SENT_BY_DEVICE = bytes.fromhex("c07b22646d223a31387dd896")


def test_build_data_packet_matches_what_the_device_accepted():
    """Pins the outgoing checksum order against a packet the valve ACKed."""
    assert protocol.build_data_packet({"ds": 45}) == ACCEPTED_BY_DEVICE


def test_parse_data_packet_accepts_what_the_device_sent():
    """Pins the incoming checksum order against a packet the valve sent."""
    header, body = protocol.parse_data_packet(SENT_BY_DEVICE)

    assert header == protocol.HEADER_SINGLE_PACKET
    assert json.loads(body) == {"dm": 18}


def test_the_two_directions_use_opposite_byte_order():
    """The asymmetry is deliberate, not a bug waiting to be tidied away.

    The device transmits its checksum little-endian but requires big-endian
    on what it receives. Making the two directions agree -- the obvious
    "cleanup" -- breaks every write.
    """
    checksum = crc16.compute(ACCEPTED_BY_DEVICE[:-2])
    outgoing = ACCEPTED_BY_DEVICE[-2:]
    assert outgoing == bytes([(checksum >> 8) & 0xFF, checksum & 0xFF])

    checksum = crc16.compute(SENT_BY_DEVICE[:-2])
    incoming = SENT_BY_DEVICE[-2:]
    assert incoming == bytes([checksum & 0xFF, (checksum >> 8) & 0xFF])

    assert outgoing[::-1] != outgoing  # the two orders are distinguishable here


def test_a_packet_we_build_is_rejected_by_our_own_parser():
    """Documents the consequence of the asymmetry.

    Our parser implements the receive direction, so it will not validate a
    packet built for the send direction. That is expected, and this test
    exists so nobody "fixes" it.
    """
    with pytest.raises(protocol.PacketError, match="Checksum mismatch"):
        protocol.parse_data_packet(protocol.build_data_packet({"ds": 45}))


def test_parse_data_packet_rejects_corruption():
    packet = bytearray(protocol.build_data_packet({"dwh": 25}))
    packet[3] ^= 0xFF

    with pytest.raises(protocol.PacketError, match="Checksum mismatch"):
        protocol.parse_data_packet(bytes(packet))


def test_parse_data_packet_rejects_short_packet():
    with pytest.raises(protocol.PacketError, match="below the minimum size"):
        protocol.parse_data_packet(b"\xc0\x7b")


def test_build_data_packet_rejects_oversized_payload():
    with pytest.raises(protocol.PacketError, match="would need chunking"):
        protocol.build_data_packet({"x": "y" * protocol.MAX_PACKET_SIZE})


def test_data_packet_json_is_compact():
    """Whitespace wastes MTU on a radio capped at 251 bytes."""
    packet = protocol.build_data_packet({"dh": 1, "dm": 2})

    assert b" " not in packet[1:-2]
