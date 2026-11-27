"""Test short-lived BLE polling sessions, teardown, and cooldown behavior."""
import asyncio
import json
from unittest.mock import patch

import pytest

from custom_components.chandler_system import crc16, protocol
from custom_components.chandler_system.client import (
    ChandlerAuthError,
    ChandlerClient,
    ChandlerConnectionError,
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


def framed(header: int, payload: bytes) -> bytes:
    """Frame a raw chunk with an arbitrary header and valid device CRC."""
    body = bytes([header]) + payload
    checksum = crc16.compute(body)
    return body + bytes([checksum & 0xFF, (checksum >> 8) & 0xFF])


class FakeBleakClient:
    """Simulated BleakClient that speaks the Chandler handshake and burst flow."""

    def __init__(
        self,
        *,
        auth_ok: bool = True,
        burst_packets: list[bytes] | None = None,
        write_reply: int | None = protocol.PACKET_ACK,
        post_write_packets: list[bytes] | None = None,
        disconnect_on_reset: bool = True,
        disconnected_cb=None,
    ):
        self.is_connected = True
        self.written: list[bytes] = []
        self.stop_notify_calls = 0
        self.disconnect_calls = 0
        self.notify_callback = None
        self._auth_ok = auth_ok
        self._burst_packets = list(burst_packets or [])
        self._write_reply = write_reply
        self._post_write_packets = list(post_write_packets or [])
        self._disconnect_on_reset = disconnect_on_reset
        self._disconnected_cb = disconnected_cb
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
        if not self.is_connected:
            raise RuntimeError("writing to a closed link")
        raw = bytes(data)
        self.written.append(raw)

        # Auth request 0xEA -> ACK
        if raw == bytes([protocol.PACKET_AUTH_REQUEST]):
            self._emit(bytes([protocol.PACKET_ACK]))
            return

        # Device reset 'R' -> valve closes link gracefully
        if raw == bytes([protocol.PACKET_DEVICE_RESET]):
            if self._disconnect_on_reset:
                self.is_connected = False
                if self._disconnected_cb is not None:
                    self._disconnected_cb(self)
            return

        # Status bytes (ACK, POLO, TIMEOUT_ACK) don't need replies
        if len(raw) == 1:
            return

        # 16-byte raw auth token -> {"as": 2} + burst (or {"as": 1})
        if not self._authenticated and len(raw) == 16:
            if not self._auth_ok:
                self._emit(device_packet({"as": 1}))
                return
            self._authenticated = True
            self._emit(device_packet({"as": 2}))
            for pkt in self._burst_packets:
                self._emit(pkt)
            return

        # Data write packet from host -> ACK/NAK + optional echo packets
        if self._write_reply is not None:
            self._emit(bytes([self._write_reply]))
        for pkt in self._post_write_packets:
            self._emit(pkt)


class FakeBLEDevice:
    name = "Combo Water Filter"
    address = "AA:BB:CC:DD:EE:FF"


@pytest.fixture
def fast_timeouts(monkeypatch):
    """Shorten session timers so connection lifecycle tests run in milliseconds."""
    monkeypatch.setattr(
        "custom_components.chandler_system.client.POLL_BURST_QUIET_TIMEOUT", 0.02
    )
    monkeypatch.setattr(
        "custom_components.chandler_system.client.POLL_INITIAL_DATA_TIMEOUT", 0.05
    )
    monkeypatch.setattr(
        "custom_components.chandler_system.client.POLL_MAX_DRAIN_DURATION", 0.5
    )
    monkeypatch.setattr(
        "custom_components.chandler_system.client.POST_WRITE_QUIET_TIMEOUT", 0.02
    )
    monkeypatch.setattr(
        "custom_components.chandler_system.client.POST_WRITE_MAX_DURATION", 0.2
    )
    monkeypatch.setattr(
        "custom_components.chandler_system.client.DEVICE_RESET_WAIT_DISCONNECT", 0.02
    )
    monkeypatch.setattr(
        "custom_components.chandler_system.client.DEVICE_RESET_MIN_DELAY", 0.0
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


def _patch_establish(factory):
    async def fake_establish(_cls, _dev, _addr, disconnected_callback=None, **_kw):
        ble = factory(disconnected_callback)
        return ble

    return patch(
        "custom_components.chandler_system.client.establish_connection",
        side_effect=fake_establish,
    )


async def test_poll_drains_burst_and_sends_device_reset(client):
    """A normal poll authenticates, drains JSON packets, and closes with 'R'."""
    created = []

    def make(cb):
        ble = FakeBleakClient(
            burst_packets=[
                device_packet({"dlf": 618, "dwh": 15, "gpf": 245}),
                device_packet({"dwu": 4520, "shgt": 123456}),
            ],
            disconnected_cb=cb,
        )
        created.append(ble)
        return ble

    with _patch_establish(make):
        data = await client.async_poll()

    ble = created[0]
    assert data.firmware_version == 618
    assert data.water_hardness == 15
    assert data.present_flow_gpm == 2.45
    assert data.total_gallons_value == 1234.56
    assert bytes([protocol.PACKET_DEVICE_RESET]) in ble.written
    assert client.state is ConnectionState.DISCONNECTED
    assert client._client is None


async def test_poll_handles_keepalive_and_multi_packet_json(client):
    """MARCOs are answered with POLO and split JSON waits for the last chunk."""
    created = []

    def make(cb):
        ble = FakeBleakClient(
            burst_packets=[
                bytes([protocol.PACKET_MARCO]),
                framed(protocol.HEADER_FIRST_PACKET, b'{"dwh":22,'),
                bytes([protocol.PACKET_TIMEOUT_QUERY]),
                framed(protocol.HEADER_LAST_PACKET, b'"ddo":14}'),
            ],
            disconnected_cb=cb,
        )
        created.append(ble)
        return ble

    with _patch_establish(make):
        data = await client.async_poll()

    ble = created[0]
    assert data.water_hardness == 22
    assert data.day_override == 14
    assert bytes([protocol.PACKET_POLO]) in ble.written
    assert bytes([protocol.PACKET_TIMEOUT_ACK]) in ble.written
    assert bytes([protocol.PACKET_DEVICE_RESET]) in ble.written


async def test_poll_runs_post_poll_write_in_same_session(client):
    """Auto clock sync piggybacks on the open poll session without reconnecting."""
    connect_count = 0

    def make(cb):
        nonlocal connect_count
        connect_count += 1
        return FakeBleakClient(
            burst_packets=[device_packet({"dh": 10, "dm": 0, "ds": 0})],
            post_write_packets=[device_packet({"dh": 12, "dm": 30, "ds": 5})],
            disconnected_cb=cb,
        )

    with _patch_establish(make):
        data = await client.async_poll(
            post_poll_write=lambda _d: {"dh": 12, "dm": 30, "ds": 5}
        )

    assert connect_count == 1
    assert data.time_hours == 12
    assert data.time_minutes == 30
    assert data.time_seconds == 5


async def test_poll_raises_auth_error_on_rejected_token(client):
    """An explicit {'as': 1} raises ChandlerAuthError and still closes cleanly."""
    created = []

    def make(cb):
        ble = FakeBleakClient(auth_ok=False, disconnected_cb=cb)
        created.append(ble)
        return ble

    with _patch_establish(make):
        with pytest.raises(ChandlerAuthError):
            await client.async_poll()

    assert bytes([protocol.PACKET_DEVICE_RESET]) in created[0].written
    assert client.state is ConnectionState.DISCONNECTED


async def test_poll_raises_connection_error_on_establish_failure(client):
    """A connect failure raises ChandlerConnectionError and leaves no link."""
    with patch(
        "custom_components.chandler_system.client.establish_connection",
        side_effect=RuntimeError("proxy busy"),
    ):
        with pytest.raises(ChandlerConnectionError, match="Failed to connect"):
            await client.async_poll()

    assert client._client is None
    assert client.state is ConnectionState.DISCONNECTED


async def test_close_session_disconnects_even_if_stop_notify_fails(client):
    """stop_notify errors must not prevent disconnect() when valve stays open."""
    ble = FakeBleakClient(disconnect_on_reset=False)

    async def fail_stop(_char):
        raise RuntimeError("BlueZ busy")

    ble.stop_notify = fail_stop
    client._client = ble
    client._state = ConnectionState.CONNECTED

    await client._close_session(graceful=True)

    assert ble.disconnect_calls == 1
    assert not ble.is_connected
    assert client._client is None


async def test_fresh_poll_clears_transient_error_but_preserves_identity(client):
    """A cleared gve must not remain stuck across polls; firmware metadata is kept."""
    polls = [
        [device_packet({"dlf": 618, "dlsa": 1, "dlsb": 2, "gve": 4})],
        # gve omitted -> healthy; dlf omitted -> preserved from prior poll
        [device_packet({"dwh": 20})],
    ]

    def make(cb):
        return FakeBleakClient(burst_packets=polls.pop(0), disconnected_cb=cb)

    with _patch_establish(make):
        first = await client.async_poll()
        second = await client.async_poll()

    assert first.has_valve_error is True
    assert second.has_valve_error is False
    assert second.valve_error is None
    assert second.firmware_version == 618
    assert second.serial_number == "12"


async def test_min_session_gap_waits_between_sessions(client, monkeypatch):
    """Back-to-back sessions respect MIN_SESSION_GAP so the radio can reset."""
    monkeypatch.setattr(
        "custom_components.chandler_system.client.MIN_SESSION_GAP", 0.05
    )

    def make(cb):
        return FakeBleakClient(
            burst_packets=[device_packet({"dwh": 10})], disconnected_cb=cb
        )

    loop = asyncio.get_running_loop()
    with _patch_establish(make):
        await client.async_poll()
        t0 = loop.time()
        await client.async_poll()
        elapsed = loop.time() - t0

    assert elapsed >= 0.04


async def test_superseded_link_cannot_feed_next_session(client):
    """Notifications emitted on an old session's callback never reach the new queue."""
    callbacks = []

    def make(cb):
        ble = FakeBleakClient(
            burst_packets=[device_packet({"dwh": 10})], disconnected_cb=cb
        )
        orig_start = ble.start_notify

        async def record_start(char, notify_cb):
            callbacks.append(notify_cb)
            await orig_start(char, notify_cb)

        ble.start_notify = record_start
        return ble

    with _patch_establish(make):
        await client.async_poll()
        await client.async_poll()

    assert len(callbacks) == 2
    assert callbacks[0] is not callbacks[1]
    callbacks[0](None, b"\xcc")
    assert client._notification_queue.empty()


async def test_send_packet_raises_when_link_is_down(client):
    """Writing while disconnected raises ChandlerWriteError."""
    client._client = FakeBleakClient()
    client._client.is_connected = False

    with pytest.raises(ChandlerWriteError, match="not connected"):
        await client._send_packet(protocol.build_status_packet(protocol.PACKET_ACK))


async def test_disconnect_on_idle_client_is_safe(client):
    await client.disconnect()
    assert client._client is None
    assert client.state is ConnectionState.DISCONNECTED
    assert isinstance(client.data, DeviceData)
