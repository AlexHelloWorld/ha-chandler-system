"""Test Chandler Bluetooth packet framing."""
import json

import pytest

from custom_components.chandler_system import protocol


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


def test_build_data_packet_round_trips_through_receive_path():
    """A packet we build must validate under the guide's receive algorithm.

    This is the guard against a CRC byte-order mistake, which would otherwise
    fail silently on the device as an ignored write.
    """
    payload = {"grn": 1}
    packet = protocol.build_data_packet(payload)

    header, body = protocol.parse_data_packet(packet)

    assert header == protocol.HEADER_SINGLE_PACKET
    assert json.loads(body) == payload


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
