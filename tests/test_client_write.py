"""Test the short-lived session write and acknowledgement path."""
import json
from unittest.mock import patch

import pytest
from bleak.exc import BleakError

from custom_components.chandler_system import crc16, protocol
from custom_components.chandler_system.client import (
    ChandlerClient,
    ChandlerWriteError,
    ConnectionState,
    DeviceData,
)


def device_packet(payload: dict) -> bytes:
    """Frame a payload the way the device does (little-endian CRC)."""
    body = bytes([protocol.HEADER_SINGLE_PACKET]) + json.dumps(
        payload, separators=(",", ":")
    ).encode("utf-8")
    checksum = crc16.compute(body)
    return body + bytes([checksum & 0xFF, (checksum >> 8) & 0xFF])


class FakeValve:
    """Simulated BleakClient with scriptable ACK/NAK replies for writes."""

    def __init__(
        self,
        *,
        reply=protocol.PACKET_ACK,
        replies=None,
        interleave: list[bytes] | None = None,
        echo: list[bytes] | None = None,
        fail_on_write: bool = False,
    ):
        self.is_connected = True
        self.written: list[bytes] = []
        self.replies = list(replies) if replies is not None else None
        self.reply = reply
        self.interleave = list(interleave or [])
        self.echo = list(echo or [])
        self.fail_on_write = fail_on_write
        self.stop_notify_calls = 0
        self.disconnect_calls = 0
        self.notify_callback = None
        self._authenticated = False

    async def start_notify(self, _char, callback):
        self.notify_callback = callback

    async def stop_notify(self, _char):
        self.stop_notify_calls += 1

    async def disconnect(self):
        self.disconnect_calls += 1
        self.is_connected = False

    def _emit(self, raw: bytes) -> None:
        if self.notify_callback is not None:
            self.notify_callback(None, raw)

    async def write_gatt_char(self, _char, data, response=False):
        raw = bytes(data)
        self.written.append(raw)

        if raw == bytes([protocol.PACKET_AUTH_REQUEST]):
            self._emit(bytes([protocol.PACKET_ACK]))
            return
        if raw == bytes([protocol.PACKET_DEVICE_RESET]):
            self.is_connected = False
            return
        if len(raw) == 1:
            return
        if not self._authenticated and len(raw) == 16:
            self._authenticated = True
            self._emit(device_packet({"as": 2}))
            self._emit(device_packet({"dwh": 20}))
            return

        if self.fail_on_write:
            raise BleakError("link went away mid-write")

        for pkt in self.interleave:
            self._emit(pkt)
        self.interleave.clear()

        if self.replies is not None:
            status = self.replies.pop(0) if self.replies else None
        else:
            status = self.reply

        if status is not None:
            self._emit(bytes([status]))
        if status == protocol.PACKET_ACK:
            for pkt in self.echo:
                self._emit(pkt)

    @property
    def data_packets(self) -> list[dict]:
        """The JSON payloads of every host data packet sent."""
        return [
            json.loads(packet[1 : -protocol.CRC_SIZE_BYTES])
            for packet in self.written
            if len(packet) > 1 and packet[0] == protocol.HEADER_SINGLE_PACKET
        ]


class FakeBLEDevice:
    name = "Water Softener"
    address = "AA:BB:CC:DD:EE:FF"


@pytest.fixture
def fast_timeouts(monkeypatch):
    monkeypatch.setattr(
        "custom_components.chandler_system.client.POLL_BURST_QUIET_TIMEOUT", 0.01
    )
    monkeypatch.setattr(
        "custom_components.chandler_system.client.POLL_INITIAL_DATA_TIMEOUT", 0.03
    )
    monkeypatch.setattr(
        "custom_components.chandler_system.client.POST_WRITE_QUIET_TIMEOUT", 0.01
    )
    monkeypatch.setattr(
        "custom_components.chandler_system.client.DEVICE_RESET_WAIT_DISCONNECT", 0.01
    )
    monkeypatch.setattr(
        "custom_components.chandler_system.client.DEVICE_RESET_MIN_DELAY", 0.0
    )
    monkeypatch.setattr(
        "custom_components.chandler_system.client.AUTH_INITIAL_DATA_WAIT", 0.01
    )
    monkeypatch.setattr(
        "custom_components.chandler_system.client.AUTH_INITIAL_DATA_QUIET", 0.01
    )
    monkeypatch.setattr(
        "custom_components.chandler_system.client.AUTH_INITIAL_DATA_MAX_WAIT", 0.05
    )
    monkeypatch.setattr(
        "custom_components.chandler_system.client.MIN_SESSION_GAP", 0.0
    )


@pytest.fixture
def client(fast_timeouts):
    return ChandlerClient(
        ble_device=FakeBLEDevice(),
        auth_token="8dffdfbd-40cc-4b86-8df8-1d48463b20f1",
    )


def _patch_valve(valve: FakeValve):
    return patch(
        "custom_components.chandler_system.client.establish_connection",
        return_value=valve,
    )


async def test_write_succeeds_on_ack_and_captures_echo(client):
    valve = FakeValve(
        reply=protocol.PACKET_ACK,
        echo=[device_packet({"dwh": 25})],
    )
    with _patch_valve(valve):
        data = await client.async_write_keys({"dwh": 25})

    assert valve.data_packets == [{"dwh": 25}]
    assert data.water_hardness == 25
    assert bytes([protocol.PACKET_DEVICE_RESET]) in valve.written
    assert client.state is ConnectionState.DISCONNECTED


async def test_write_retries_once_then_fails_on_nak(client):
    valve = FakeValve(reply=protocol.PACKET_NAK)
    with _patch_valve(valve):
        with pytest.raises(ChandlerWriteError, match="rejected"):
            await client.async_write_keys({"dwh": 25})

    assert valve.data_packets == [{"dwh": 25}, {"dwh": 25}]
    assert bytes([protocol.PACKET_DEVICE_RESET]) in valve.written
    assert client.state is ConnectionState.DISCONNECTED


async def test_write_succeeds_on_second_attempt_after_nak(client):
    valve = FakeValve(replies=[protocol.PACKET_NAK, protocol.PACKET_ACK])
    with _patch_valve(valve):
        await client.async_write_keys({"dwh": 25})

    assert valve.data_packets == [{"dwh": 25}, {"dwh": 25}]


async def test_write_handles_interleaved_marco_and_data_before_ack(client):
    """Interleaved keep-alives and data packets do not break ACK matching."""
    valve = FakeValve(
        reply=protocol.PACKET_ACK,
        interleave=[
            bytes([protocol.PACKET_MARCO]),
            device_packet({"gpf": 125}),
        ],
    )
    with _patch_valve(valve):
        data = await client.async_write_keys({"dwh": 30})

    assert data.present_flow_gpm == 1.25
    assert bytes([protocol.PACKET_POLO]) in valve.written
    assert valve.data_packets == [{"dwh": 30}]


async def test_write_times_out_and_closes_cleanly(client, monkeypatch):
    monkeypatch.setattr(
        "custom_components.chandler_system.client.WRITE_ACK_TIMEOUT", 0.02
    )
    valve = FakeValve(reply=None)
    with _patch_valve(valve):
        with pytest.raises(ChandlerWriteError, match="Timed out"):
            await client.async_write_keys({"grn": 1})

    assert client._client is None
    assert client.state is ConnectionState.DISCONNECTED


async def test_transport_failure_mid_write_closes_session(client):
    valve = FakeValve(fail_on_write=True)
    with _patch_valve(valve):
        with pytest.raises(ChandlerWriteError, match="Failed to send"):
            await client.async_write_keys({"dwh": 25})

    assert client._client is None
    assert client.state is ConnectionState.DISCONNECTED


async def test_oversized_payload_rejected_before_connecting(client):
    with patch(
        "custom_components.chandler_system.client.establish_connection"
    ) as mock_establish:
        with pytest.raises(protocol.PacketError, match="would need chunking"):
            await client.async_write_keys({"x": "y" * protocol.MAX_PACKET_SIZE})

    assert not mock_establish.called


async def test_corrupt_packet_is_naked_and_ignored(client):
    valve = FakeValve()
    client._client = valve
    packet = bytearray(device_packet({"dwh": 30}))
    packet[-1] ^= 0xFF

    target = DeviceData()
    accepted = await client._process_packet(bytes(packet), target)

    assert accepted is False
    assert valve.written == [bytes([protocol.PACKET_NAK])]
    assert target.water_hardness is None
