"""Test the write/acknowledgement path against a simulated valve."""
import asyncio
import json

import pytest

from custom_components.chandler_system import crc16, protocol
from custom_components.chandler_system.client import (
    ChandlerClient,
    ChandlerWriteError,
    ConnectionState,
    DeviceData,
)


def device_packet(payload: dict) -> bytes:
    """Frame a payload the way the device does, checksum little-endian.

    Not the same as protocol.build_data_packet, which frames for the
    opposite direction; see the note in protocol.parse_data_packet.
    """
    body = bytes([protocol.HEADER_SINGLE_PACKET]) + json.dumps(
        payload, separators=(",", ":")
    ).encode("utf-8")
    checksum = crc16.compute(body)
    return body + bytes([checksum & 0xFF, (checksum >> 8) & 0xFF])


class FakeValve:
    """Stands in for the BLE link, recording writes and replying like a valve."""

    def __init__(self, reply=protocol.PACKET_ACK, replies=None):
        self.is_connected = True
        self.written: list[bytes] = []
        # `replies` scripts one status byte per data packet, in order;
        # `reply` uses the same byte every time.
        self.replies = list(replies) if replies is not None else None
        self.reply = reply
        self.stop_notify_calls = 0
        self.disconnect_calls = 0
        self.client: ChandlerClient | None = None

    async def write_gatt_char(self, _char, data, response=False):
        self.written.append(bytes(data))
        if len(data) <= 1:
            return

        if self.replies is not None:
            status = self.replies.pop(0) if self.replies else None
        else:
            status = self.reply

        if status is not None:
            # The real device answers a data packet with a status byte, which
            # arrives via the notification queue.
            self.client._notification_queue.put_nowait(bytes([status]))

    async def stop_notify(self, _char):
        self.stop_notify_calls += 1

    async def disconnect(self):
        self.disconnect_calls += 1
        self.is_connected = False

    @property
    def data_packets(self) -> list[dict]:
        """The JSON payloads of every data packet we received."""
        return [
            json.loads(packet[1:-protocol.CRC_SIZE_BYTES])
            for packet in self.written
            if len(packet) > 1
        ]


@pytest.fixture
def client():
    """A connected client whose BLE link is a FakeValve."""
    instance = ChandlerClient.__new__(ChandlerClient)
    instance._data = DeviceData()
    instance._data_callback = None
    instance._data_buffer = bytearray()
    instance._notification_queue = asyncio.Queue()
    instance._write_lock = asyncio.Lock()
    instance._ack_waiter = None
    instance._connection_lost_callback = None
    instance._state = ConnectionState.CONNECTED
    instance._monitor_task = None
    return instance


def attach(client, valve):
    client._client = valve
    valve.client = client
    return valve


async def pump(client, count=1):
    """Drain the notification queue the way the monitor loop would."""
    for _ in range(count):
        data = await asyncio.wait_for(client._notification_queue.get(), 1)
        await client._handle_incoming(data)


async def test_write_succeeds_on_ack(client):
    valve = attach(client, FakeValve(reply=protocol.PACKET_ACK))

    write = asyncio.create_task(client.async_write_keys({"grn": 1}))
    await asyncio.sleep(0)
    await pump(client)
    await write

    assert valve.data_packets == [{"grn": 1}]


async def test_write_retries_once_then_fails_on_nak(client):
    valve = attach(client, FakeValve(reply=protocol.PACKET_NAK))

    write = asyncio.create_task(client.async_write_keys({"dwh": 25}))
    await asyncio.sleep(0)
    await pump(client, count=2)

    with pytest.raises(ChandlerWriteError, match="rejected"):
        await write

    assert valve.data_packets == [{"dwh": 25}, {"dwh": 25}]


async def test_write_succeeds_on_second_attempt_after_nak(client):
    """The point of the retry: a NAK'd packet resent and then accepted."""
    valve = attach(
        client, FakeValve(replies=[protocol.PACKET_NAK, protocol.PACKET_ACK])
    )

    write = asyncio.create_task(client.async_write_keys({"dwh": 25}))
    await asyncio.sleep(0)
    await pump(client, count=2)
    await write

    assert valve.data_packets == [{"dwh": 25}, {"dwh": 25}]


async def test_an_unanswered_write_ends_the_session(client, monkeypatch):
    """A straggling acknowledgement must not be able to reach a later write.

    Nothing in a status packet identifies which write it answers, so the only
    sound way to keep them apart is to make sure two writes never share a
    session once one has gone unanswered.
    """
    monkeypatch.setattr(
        "custom_components.chandler_system.client.WRITE_ACK_TIMEOUT", 0.01
    )
    valve = attach(client, FakeValve(reply=None))

    with pytest.raises(ChandlerWriteError, match="Timed out"):
        await client.async_write_keys({"dwh": 25})

    assert client._client is None
    assert client._state is ConnectionState.DISCONNECTED
    assert not valve.is_connected

    # A later write cannot run on the poisoned session at all.
    with pytest.raises(ChandlerWriteError, match="Not connected"):
        await client.async_write_keys({"grn": 1})


async def test_a_write_the_device_never_answers_does_not_poison_later_ones(
    client, monkeypatch
):
    """The previous guard was a counter, which assumed every timeout meant a
    reply was still in flight. When the device simply never answered, the
    count never cleared and every later write had its own acknowledgement
    discarded -- permanently, for the life of the session."""
    monkeypatch.setattr(
        "custom_components.chandler_system.client.WRITE_ACK_TIMEOUT", 0.01
    )
    attach(client, FakeValve(reply=None))

    with pytest.raises(ChandlerWriteError):
        await client.async_write_keys({"dwh": 20})

    # A fresh session, as the coordinator would establish after the failure.
    attach(client, FakeValve(reply=protocol.PACKET_ACK))
    client._state = ConnectionState.CONNECTED
    monkeypatch.setattr(
        "custom_components.chandler_system.client.WRITE_ACK_TIMEOUT", 5.0
    )

    write = asyncio.create_task(client.async_write_keys({"dwh": 21}))
    await asyncio.sleep(0)
    await pump(client)
    await write


async def test_write_raises_when_not_connected(client):
    client._state = ConnectionState.DISCONNECTED
    attach(client, FakeValve())

    with pytest.raises(ChandlerWriteError, match="Not connected"):
        await client.async_write_keys({"grn": 1})


async def test_write_times_out_when_device_stays_silent(client, monkeypatch):
    monkeypatch.setattr(
        "custom_components.chandler_system.client.WRITE_ACK_TIMEOUT", 0.01
    )
    attach(client, FakeValve(reply=None))

    with pytest.raises(ChandlerWriteError, match="Timed out"):
        await client.async_write_keys({"grn": 1})


async def test_keepalive_marco_is_answered_with_polo(client):
    valve = attach(client, FakeValve())

    await client._handle_incoming(bytes([protocol.PACKET_MARCO]))

    assert valve.written == [bytes([protocol.PACKET_POLO])]


async def test_timeout_query_is_answered(client):
    valve = attach(client, FakeValve())

    await client._handle_incoming(bytes([protocol.PACKET_TIMEOUT_QUERY]))

    assert valve.written == [bytes([protocol.PACKET_TIMEOUT_ACK])]


async def test_valid_data_packet_is_acked_and_parsed(client):
    valve = attach(client, FakeValve())

    await client._handle_incoming(device_packet({"dwh": 30}))

    assert valve.written == [bytes([protocol.PACKET_ACK])]
    assert client.data.water_hardness == 30


async def test_unrecognized_status_byte_is_ignored_not_naked(client):
    """NAKing a stray byte would ask for a retransmit the device can't give."""
    valve = attach(client, FakeValve())

    await client._handle_incoming(bytes([protocol.HEADER_NOP]))

    assert valve.written == []


async def test_corrupt_data_packet_is_naked_and_ignored(client):
    valve = attach(client, FakeValve())
    packet = bytearray(device_packet({"dwh": 30}))
    packet[-1] ^= 0xFF

    await client._handle_incoming(bytes(packet))

    assert valve.written == [bytes([protocol.PACKET_NAK])]
    assert client.data.water_hardness is None


async def test_multi_packet_json_is_reassembled(client):
    """A split payload only parses once the last-packet bit arrives."""
    attach(client, FakeValve())
    first = _framed(protocol.HEADER_FIRST_PACKET, b'{"dwh":42,')
    last = _framed(protocol.HEADER_LAST_PACKET, b'"asrc":30}')

    await client._handle_incoming(first)
    assert client.data.water_hardness is None

    await client._handle_incoming(last)
    assert client.data.water_hardness == 42
    assert client.data.reserve_capacity == 30


async def test_new_first_packet_discards_a_stale_partial(client):
    """A dropped last packet must not poison the next transfer."""
    attach(client, FakeValve())

    await client._handle_incoming(
        _framed(protocol.HEADER_FIRST_PACKET, b'{"dwh":9,"garbage')
    )
    await client._handle_incoming(
        _framed(protocol.HEADER_FIRST_PACKET | protocol.HEADER_LAST_PACKET,
                b'{"dwh":42}')
    )

    assert client.data.water_hardness == 42


async def test_authenticate_answers_keepalive_then_sends_token(client):
    """The device keeps sending marcos while it waits for the token."""
    valve = attach(client, FakeValve(reply=None))
    client._auth_token = bytearray(b"\x01\x02\x03\x04")
    client._notification_queue.put_nowait(bytes([protocol.PACKET_MARCO]))
    client._notification_queue.put_nowait(bytes([protocol.PACKET_ACK]))
    client._notification_queue.put_nowait(device_packet({"as": 2}))

    assert await client._authenticate()

    assert valve.written == [
        bytes([protocol.PACKET_AUTH_REQUEST]),
        bytes([protocol.PACKET_POLO]),
        b"\x01\x02\x03\x04",
        bytes([protocol.PACKET_ACK]),
    ]
    assert client._state is ConnectionState.CONNECTED


async def test_authenticate_acks_preauth_data(client):
    """Initial data arrives before the token and must be acknowledged."""
    valve = attach(client, FakeValve(reply=None))
    client._auth_token = bytearray(b"\x01")
    client._notification_queue.put_nowait(device_packet({"dwh": 30}))
    client._notification_queue.put_nowait(bytes([protocol.PACKET_ACK]))
    client._notification_queue.put_nowait(device_packet({"as": 2}))

    assert await client._authenticate()

    assert bytes([protocol.PACKET_ACK]) in valve.written
    assert client.data.water_hardness == 30


async def test_authenticate_fails_when_token_is_rejected(client):
    """A bad token yields an unauthenticated state, not silence."""
    attach(client, FakeValve(reply=None))
    client._auth_token = bytearray(b"\x01")
    client._notification_queue.put_nowait(bytes([protocol.PACKET_ACK]))
    client._notification_queue.put_nowait(device_packet({"as": 1}))

    assert not await client._authenticate()
    assert client._state is not ConnectionState.CONNECTED


async def test_authenticate_gives_up_when_device_never_confirms(client, monkeypatch):
    """Keep-alives alone must not keep the handshake alive forever."""
    monkeypatch.setattr(
        "custom_components.chandler_system.client.AUTH_TIMEOUT", 0.05
    )
    attach(client, FakeValve(reply=None))
    client._auth_token = bytearray(b"\x01")
    client._notification_queue.put_nowait(bytes([protocol.PACKET_ACK]))

    async def keep_marcoing():
        for _ in range(50):
            client._notification_queue.put_nowait(bytes([protocol.PACKET_MARCO]))
            await asyncio.sleep(0.005)

    pump_task = asyncio.create_task(keep_marcoing())
    assert not await client._authenticate()
    pump_task.cancel()


async def test_disconnect_sends_device_reset_before_dropping_the_link(client):
    """The valve holds the connection open unless it is told to release it."""
    valve = attach(client, FakeValve(reply=None))

    await client.disconnect()

    assert valve.written == [bytes([protocol.PACKET_DEVICE_RESET])]
    assert valve.written[0] == b"R"
    assert valve.stop_notify_calls == 1
    assert valve.disconnect_calls == 1
    assert client._state is ConnectionState.DISCONNECTED


def _framed(header: int, payload: bytes) -> bytes:
    """Frame a raw payload with an arbitrary header and a valid checksum."""
    from custom_components.chandler_system import crc16

    body = bytes([header]) + payload
    checksum = crc16.compute(body)
    return body + bytes([checksum & 0xFF, (checksum >> 8) & 0xFF])
