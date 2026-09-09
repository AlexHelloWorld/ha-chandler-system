"""Test the CRC-16 implementation."""
from custom_components.chandler_system import crc16

CHECK_VECTOR = b"123456789"
# Catalogue check value for CRC-16/CCITT-FALSE (IBM-3740).
CHECK_VALUE = 0x29B1
# CRC-16/KERMIT, which the vendor guide misnames this algorithm as, checks
# to a different value. Asserting both ways round keeps anyone from
# "fixing" the implementation to match the vendor's label.
KERMIT_CHECK_VALUE = 0x2189


def test_check_vector():
    """The catalogue check value pins the algorithm variant."""
    assert crc16.compute(CHECK_VECTOR) == CHECK_VALUE


def test_is_not_kermit_despite_the_vendor_naming():
    assert crc16.compute(CHECK_VECTOR) != KERMIT_CHECK_VALUE


def test_verify_round_trip():
    assert crc16.verify(crc16.compute(CHECK_VECTOR), CHECK_VECTOR)


def test_verify_rejects_wrong_crc():
    assert not crc16.verify(CHECK_VALUE ^ 0x0001, CHECK_VECTOR)


def test_verify_rejects_corrupted_buffer():
    assert not crc16.verify(CHECK_VALUE, b"12345678X")


def test_empty_buffer():
    assert crc16.compute(b"") == 0


def test_captured_device_packet():
    """A real packet from the API guide: {"as":1} with its transmitted CRC.

    This pins the little-endian byte order of the checksum against data the
    guide captured from an actual valve.
    """
    packet = bytes(
        [0xC0, 0x7B, 0x22, 0x61, 0x73, 0x22, 0x3A, 0x31, 0x7D, 0x9F, 0x38]
    )
    body = packet[:-2]
    transmitted_crc = (packet[-1] << 8) | packet[-2]

    assert crc16.compute(body) == transmitted_crc
    assert crc16.verify(transmitted_crc, body)
