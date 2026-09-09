"""CRC-16 checksums for Chandler Bluetooth packets.

The algorithm is CRC-16/CCITT-FALSE (aka IBM-3740): polynomial 0x1021, initial
value 0xFFFF, non-reflected. Its catalogue check value over b"123456789" is
0x29B1.

The vendor guide calls this "CRC-16/KERMIT aka CRC-16/CCITT", which is wrong --
KERMIT is the reflected variant seeded with 0x0000 and checks to 0x2189. Do not
"correct" this implementation to match the vendor's name: the bytes below are
what the device actually computes, and swapping in a stock KERMIT routine would
invalidate every packet.
"""
from __future__ import annotations

DEFAULT_SEED = 0xFFFF

# The residue of a correct message with its CRC appended.
_VALID_RESIDUE = 0x0000


def compute(buffer: bytes | bytearray, seed: int = DEFAULT_SEED) -> int:
    """Compute the CRC-16 checksum of a buffer."""
    if not buffer:
        return 0

    crc = seed
    for byte in buffer:
        crc = (crc >> 8 | (crc << 8)) & 0xFFFF
        crc ^= byte & 0xFF
        crc ^= (crc & 0xFF) >> 4
        crc ^= (crc << 12) & 0xFFFF
        crc ^= ((crc & 0xFF) << 5) & 0xFFFF

    return crc & 0xFFFF


def verify(crc: int, buffer: bytes | bytearray, seed: int = DEFAULT_SEED) -> bool:
    """Check that a received CRC matches the buffer it was transmitted with."""
    if crc != compute(buffer, seed):
        return False

    buffer_with_crc = bytes(buffer) + bytes([(crc >> 8) & 0xFF, crc & 0xFF])
    return compute(buffer_with_crc, seed) == _VALID_RESIDUE
