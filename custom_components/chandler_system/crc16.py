"""CRC-16/KERMIT (CCITT) checksums for Chandler Bluetooth packets."""
from __future__ import annotations

DEFAULT_SEED = 0xFFFF

# The residue of a correct message with its CRC appended, per CRC-16/KERMIT.
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
