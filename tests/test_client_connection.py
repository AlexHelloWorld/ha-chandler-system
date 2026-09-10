"""Test connection lifecycle: reconnect, teardown, and drop handling."""
import asyncio
from unittest.mock import patch

import pytest

from custom_components.chandler_system import protocol
from custom_components.chandler_system.client import (
    ChandlerClient,
    ChandlerWriteError,
    ConnectionState,
    DeviceData,
)


class FakeBleakClient:
    """A BleakClient that records the calls that release a connection."""

    def __init__(self, connected=True):
        self.is_connected = connected
        self.written: list[bytes] = []
        self.stop_notify_calls = 0
        self.disconnect_calls = 0
        self.notify_callback = None

    async def start_notify(self, _char, callback):
        self.notify_callback = callback

    async def stop_notify(self, _char):
        self.stop_notify_calls += 1

    async def disconnect(self):
        self.disconnect_calls += 1
        self.is_connected = False

    async def write_gatt_char(self, _char, data, response=False):
        if not self.is_connected:
            raise RuntimeError("writing to a closed link")
        self.written.append(bytes(data))


class FakeBLEDevice:
    name = "Water Softener"
    address = "AA:BB:CC:DD:EE:FF"


@pytest.fixture
def client():
    instance = ChandlerClient.__new__(ChandlerClient)
    instance._data = DeviceData()
    instance._data_callback = None
    instance._data_buffer = bytearray()
    instance._notification_queue = asyncio.Queue()
    instance._write_lock = asyncio.Lock()
    instance._ack_waiter = None
    instance._unmatched_acks = 0
    instance._state = ConnectionState.DISCONNECTED
    instance._stop_event = asyncio.Event()
    instance._monitor_task = None
    instance._client = None
    instance._ble_device = FakeBLEDevice()
    instance._auth_token = bytearray(b"\x01")
    return instance


def patch_connect(new_client):
    """Patch out the BLE connect and the handshake."""
    return (
        patch(
            "custom_components.chandler_system.client.establish_connection",
            return_value=new_client,
        ),
        patch.object(ChandlerClient, "_authenticate", return_value=True),
    )


async def _connect(client, new_client):
    establish, authenticate = patch_connect(new_client)
    with establish as mock_establish, authenticate:
        result = await client.connect()
    await client.disconnect()
    return result, mock_establish


async def test_reconnects_when_state_is_stale(client):
    """A dropped link must not block reconnection.

    The monitor loop can take its full idle timeout to notice a drop, so the
    client's own state still says connected. Refusing on that basis left the
    integration unable to reconnect for the length of that window.
    """
    dropped = FakeBleakClient(connected=False)
    client._client = dropped
    client._state = ConnectionState.CONNECTED

    fresh = FakeBleakClient()
    result, mock_establish = await _connect(client, fresh)

    assert result is True
    assert mock_establish.called


async def test_connect_releases_a_previous_link(client):
    """A still-open link is closed before a new one is established."""
    stale = FakeBleakClient(connected=True)
    client._client = stale
    client._state = ConnectionState.CONNECTED

    await _connect(client, FakeBleakClient())

    assert stale.stop_notify_calls == 1
    assert stale.disconnect_calls == 1


async def test_connect_registers_a_disconnect_callback(client):
    """Bleak reports drops directly, rather than us inferring them."""
    establish, authenticate = patch_connect(FakeBleakClient())
    with establish as mock_establish, authenticate:
        await client.connect()
    await client.disconnect()

    callback = mock_establish.call_args.kwargs["disconnected_callback"]
    assert callback == client._on_disconnected


async def test_a_superseded_link_cannot_feed_the_next_session(client):
    """Notifications from a replaced link must not reach the new session.

    A stray acknowledgement arriving this way would be read as the response
    to whatever write is currently in flight.
    """
    first = FakeBleakClient()
    establish, authenticate = patch_connect(first)
    with establish, authenticate:
        await client.connect()
    orphan_callback = first.notify_callback

    # The link drops and we reconnect.
    first.is_connected = False
    second = FakeBleakClient()
    establish, authenticate = patch_connect(second)
    with establish, authenticate:
        await client.connect()
    await client.disconnect()

    assert second.notify_callback is not orphan_callback

    orphan_callback(None, b"\xcc")
    assert client._notification_queue.empty()


async def test_failed_connect_leaves_no_link_behind(client):
    """A connect that raises must not strand a half-open connection."""
    with patch(
        "custom_components.chandler_system.client.establish_connection",
        side_effect=RuntimeError("boom"),
    ):
        assert await client.connect() is False

    assert client._client is None
    assert client._state is ConnectionState.DISCONNECTED


async def test_teardown_is_safe_with_nothing_connected(client):
    await client._teardown()

    assert client._client is None
    assert client._state is ConnectionState.DISCONNECTED


async def test_disconnect_callback_marks_disconnected_and_wakes_loop(client):
    live = FakeBleakClient()
    client._client = live
    client._state = ConnectionState.CONNECTED

    client._on_disconnected(live)

    assert client._state is ConnectionState.DISCONNECTED
    assert client._stop_event.is_set()
    assert not client._notification_queue.empty()


async def test_disconnect_callback_ignores_a_superseded_link(client):
    """A late callback from a replaced link must not disturb the new one."""
    current = FakeBleakClient()
    client._client = current
    client._state = ConnectionState.CONNECTED

    client._on_disconnected(FakeBleakClient())

    assert client._state is ConnectionState.CONNECTED
    assert not client._stop_event.is_set()


async def test_disconnect_callback_fails_a_pending_write(client):
    """A write in flight fails at once instead of waiting out its timeout."""
    live = FakeBleakClient()
    client._client = live
    client._state = ConnectionState.CONNECTED

    write = asyncio.create_task(client.async_write_keys({"grn": 1}))
    await asyncio.sleep(0)

    client._on_disconnected(live)

    with pytest.raises(ChandlerWriteError, match="dropped"):
        await write


async def test_monitor_loop_exit_fails_a_pending_write(client):
    client._client = FakeBleakClient()
    client._state = ConnectionState.CONNECTED
    waiter = asyncio.get_running_loop().create_future()
    client._ack_waiter = waiter

    client._stop_event.set()
    await client._monitor_loop()

    assert waiter.done()
    with pytest.raises(ChandlerWriteError):
        waiter.result()


async def test_send_packet_raises_when_the_link_is_down(client):
    """Silently dropping the packet made a dead link look like a timeout."""
    client._client = FakeBleakClient(connected=False)

    with pytest.raises(ChandlerWriteError, match="not connected"):
        await client._send_packet(protocol.build_status_packet(protocol.PACKET_ACK))
