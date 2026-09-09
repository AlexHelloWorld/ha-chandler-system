"""Bluetooth client for Chandler Water System devices."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from . import protocol
from .const import (
    CHAR_UUID_READ,
    CHAR_UUID_WRITE,
    REGEN_STATE_MAP,
    REGEN_TIME_TYPE_MINUTES,
    REGEN_TIME_TYPE_SECONDS,
    get_error_text,
)
from .protocol import StatusPacket

_LOGGER = logging.getLogger(__name__)

# How long to wait for the device to ACK a write before giving up.
WRITE_ACK_TIMEOUT = 5.0
# Overall budget for the handshake, which spans several device round trips.
AUTH_TIMEOUT = 30.0
# The device needs a moment to close the link after a reset command.
DEVICE_RESET_DELAY = 0.15

# Authentication states reported by the device in the "as" key.
AUTH_STATE_NOT_AUTHENTICATED = 1
AUTH_STATE_AUTHENTICATED = 2


class ChandlerWriteError(Exception):
    """Raised when a write to the device could not be delivered."""


class ChandlerAuthError(Exception):
    """Raised when the device rejects the authentication token."""


class ConnectionState(Enum):
    """Connection state enum."""

    DISCONNECTED = 0
    CONNECTING = 1
    AUTHENTICATING = 2
    CONNECTED = 3


@dataclass(frozen=True)
class ErrorLogEntry:
    """One entry from the device's rolling 20-error log."""

    days_in_operation: int
    hours: int
    minutes: int
    seconds: int
    error_code: int

    @property
    def error_text(self) -> str:
        """Human-readable error description."""
        return get_error_text(self.error_code)

    def as_dict(self) -> dict[str, Any]:
        """Render for use as a Home Assistant state attribute."""
        return {
            "days_in_operation": self.days_in_operation,
            "time": f"{self.hours:02d}:{self.minutes:02d}:{self.seconds:02d}",
            "error_code": self.error_code,
            "error": self.error_text,
        }


@dataclass
class DeviceData:
    """Data class to hold all parsed device data."""

    # Dashboard data (all integers per API spec)
    time_hours: int | None = None  # dh (0-23, military time)
    time_minutes: int | None = None  # dm (0-59)
    time_seconds: int | None = None  # ds (0-59)
    battery_level_mv: int | None = None  # dbl (mV, 0-9700)
    total_gallons_remaining: int | None = None  # dtgr (1/100 gallons)
    peak_flow_daily: int | None = None  # dpfd (1/100 GPM)
    water_hardness: int | None = None  # dwh (GPG, 0-99)
    day_override: int | None = None  # ddo (days, 0-29)
    current_day_override: int | None = None  # dcdo (days, 0-29)
    water_used_today: int | None = None  # dwu (1/100 gallons)
    average_water_used: int | None = None  # dwau (1/100 gallons)
    regen_time_hours: int | None = None  # drth (0-23, military time)
    regen_time_type: int | None = None  # drtt (0-2)
    regen_time_remaining: int | None = None  # drtr
    regen_current_position: int | None = None  # drcp
    regen_in_aeration: bool | None = None  # dria (0-1)
    regen_soak_mode: bool | None = None  # dps (0-1)
    regen_soak_timer: int | None = None  # drst (minutes)
    prefill_enabled: bool | None = None  # dpe (0-1)
    prefill_duration: int | None = None  # dpd (hours, 1-4)

    # Brine tank
    brine_tank_total_salt: int | None = None  # dbts (pounds)
    brine_tank_remaining_salt: int | None = None  # dbtr (1/10 pounds)
    brine_tank_width: int | None = None  # dbtw (inches)
    brine_tank_height: int | None = None  # dbth (inches)
    brine_tank_reserve_time: int | None = None  # dbrt (minutes)

    # Advanced settings
    days_until_regen: int | None = None  # asd
    regen_day_override: int | None = None  # asr
    auto_reserve_mode: bool | None = None  # asar
    reserve_capacity: int | None = None  # asrc
    reserve_capacity_gallons: int | None = None  # asrg (1/100 gallons)
    total_grains_capacity: int | None = None  # astg (1000 GPG)
    aeration_days: int | None = None  # asad
    chlorine_pulses: int | None = None  # ascp
    display_off: bool | None = None  # asdo
    num_regen_positions: int | None = None  # asnp

    # Status & History
    days_in_operation: int | None = None  # shdo
    days_since_last_regen: int | None = None  # shdr
    gallons_since_last_regen: int | None = None  # shgs
    regen_counter: int | None = None  # shrc
    regen_counter_resettable: int | None = None  # shrr
    total_gallons: int | None = None  # shgt
    total_gallons_resettable: int | None = None  # shgr

    # Global
    valve_status: int | None = None  # gvs
    valve_error: int | None = None  # gve
    present_flow: int | None = None  # gpf
    regen_active: bool | None = None  # gra
    regen_state: int | None = None  # grs
    auth_state: int | None = None  # as (2 = authenticated)

    # Error log (last 20 entries, newest first)
    error_log: list[ErrorLogEntry] = field(default_factory=list)  # shel

    # Graphs (values already converted from hundredths)
    peak_flow_history: list[float] = field(default_factory=list)  # grp
    daily_gallons_history: list[float] = field(default_factory=list)  # ggd
    gallons_between_regens: list[float] = field(default_factory=list)  # ggr

    # Raw data for debugging
    raw_data: dict[str, Any] = field(default_factory=dict)

    @property
    def battery_level_volts(self) -> float | None:
        """Get battery level in volts."""
        if self.battery_level_mv is not None:
            return self.battery_level_mv / 1000.0
        return None

    @property
    def salt_low(self) -> bool | None:
        """Check if salt is low from valve status."""
        if self.valve_status is not None:
            return bool(self.valve_status & 0x80)
        return None

    @property
    def salt_level_percent(self) -> float | None:
        """Calculate salt level percentage.

        Note: remaining is in 1/10 pounds, total is in pounds.
        """
        remaining = self.brine_tank_remaining_salt
        total = self.brine_tank_total_salt
        if remaining is not None and total:
            # remaining / 10 converts to pounds, then calculate percentage
            return min(100.0, (remaining / 10.0 / total) * 100.0)
        return None

    @property
    def regen_state_text(self) -> str | None:
        """Human-readable regeneration state.

        Returns None for a code outside the documented range rather than a
        placeholder string: the sensor declares these values as its enum
        options, and Home Assistant rejects a state that is not among them.
        """
        if self.regen_state is None:
            return None
        return REGEN_STATE_MAP.get(self.regen_state)

    @property
    def regen_step_remaining_seconds(self) -> int | None:
        """Seconds left in the current regeneration step.

        The device reports the remaining amount in the unit named by
        regen_time_type; when that unit is salt pounds there is no time to
        report.
        """
        if self.regen_time_remaining is None:
            return None
        if self.regen_time_type == REGEN_TIME_TYPE_SECONDS:
            return self.regen_time_remaining
        if self.regen_time_type == REGEN_TIME_TYPE_MINUTES:
            return self.regen_time_remaining * 60
        return None

    @property
    def last_error(self) -> ErrorLogEntry | None:
        """Most recent real error, or None if the log holds only empty slots."""
        for entry in self.error_log:
            if entry.error_code != 0:
                return entry
        return None

    @property
    def has_valve_error(self) -> bool | None:
        """Whether the valve is currently reporting an error."""
        if self.valve_error is None:
            return None
        return self.valve_error != 0


def _parse_error_log(raw: Any) -> list[ErrorLogEntry]:
    """Build error log entries from the device's shel array."""
    if not isinstance(raw, list):
        return []

    entries = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        entries.append(
            ErrorLogEntry(
                days_in_operation=item.get("d", 0),
                hours=item.get("h", 0),
                minutes=item.get("m", 0),
                seconds=item.get("s", 0),
                error_code=item.get("e", 0),
            )
        )
    return entries


def _parse_graph(raw: Any) -> list[float]:
    """Convert a graph array from hundredths to whole units."""
    if not isinstance(raw, list):
        return []
    return [value / 100.0 for value in raw if isinstance(value, (int, float))]


class ChandlerClient:
    """Bluetooth client for Chandler Water System devices.

    Uses bleak-retry-connector for reliable BLE connections.
    """

    def __init__(
        self,
        ble_device: BLEDevice,
        auth_token: str,
        data_callback: Callable[[DeviceData], None] | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            ble_device: BLEDevice from Home Assistant's bluetooth
            auth_token: Authentication token (UUID without dashes)
            data_callback: Optional callback when new data is received
        """
        self._ble_device = ble_device
        self._auth_token = bytearray.fromhex(auth_token.replace("-", ""))
        self._data_callback = data_callback

        self._client: BleakClient | None = None
        self._state = ConnectionState.DISCONNECTED
        self._notification_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._data_buffer = bytearray()
        self._data = DeviceData()
        self._monitor_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._write_lock = asyncio.Lock()
        self._ack_waiter: asyncio.Future[StatusPacket] | None = None
        self._unmatched_acks = 0

    def set_ble_device(self, ble_device: BLEDevice) -> None:
        """Update the BLE device (address may change on different hosts)."""
        self._ble_device = ble_device

    @property
    def state(self) -> ConnectionState:
        """Get the current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if connected and authenticated."""
        return (
            self._state == ConnectionState.CONNECTED
            and self._client is not None
            and self._client.is_connected
        )

    @property
    def data(self) -> DeviceData:
        """Get the current device data."""
        return self._data

    @property
    def address(self) -> str:
        """Get the device address."""
        return self._ble_device.address

    def _notification_callback(self, sender: Any, data: bytes) -> None:
        """Handle incoming BLE notifications."""
        _LOGGER.debug("Received: %s", data.hex())
        self._notification_queue.put_nowait(data)

    async def _send_packet(self, data: bytes | bytearray) -> None:
        """Send a packet to the device."""
        if self._client and self._client.is_connected:
            _LOGGER.debug("Sending: %s", data.hex())
            await self._client.write_gatt_char(
                CHAR_UUID_WRITE, data, response=False
            )

    async def _wait_for_response(self, timeout: float = 5.0) -> bytes:
        """Wait for a response from the device."""
        return await asyncio.wait_for(
            self._notification_queue.get(), timeout=timeout
        )

    async def _authenticate(self) -> bool:
        """Authenticate with the device.

        Sends the ID packet, then the token once the device acknowledges it,
        then waits for the device to report itself authenticated. The device
        answers a rejected token with an unauthenticated state and otherwise
        just keeps the link alive, so only the reported state distinguishes
        success from failure.
        """
        self._state = ConnectionState.AUTHENTICATING
        self._data.auth_state = None

        await self._send_packet(
            protocol.build_status_packet(protocol.PACKET_AUTH_REQUEST)
        )

        token_sent = False
        deadline = asyncio.get_running_loop().time() + AUTH_TIMEOUT

        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                _LOGGER.error(
                    "Authentication timed out after %ss (state: %s)",
                    AUTH_TIMEOUT,
                    self._data.auth_state,
                )
                return False

            try:
                data = await self._wait_for_response(timeout=remaining)
            except asyncio.TimeoutError:
                _LOGGER.error("Authentication timeout")
                return False

            if not token_sent and protocol.classify_status(data) is StatusPacket.ACK:
                await self._send_packet(self._auth_token)
                token_sent = True
                continue

            # Before authenticating the device still sends initial data
            # and keep-alives; both need the normal responses or it
            # drops the link.
            await self._handle_incoming(data)

            if self._data.auth_state == AUTH_STATE_AUTHENTICATED:
                self._state = ConnectionState.CONNECTED
                _LOGGER.info("Authentication successful")
                return True

            if token_sent and self._data.auth_state == AUTH_STATE_NOT_AUTHENTICATED:
                _LOGGER.error(
                    "Device rejected the authentication token. Generate a new "
                    "one in the Chandler/Springwell app and reconfigure."
                )
                return False

    async def _process_packet(self, data: bytes) -> None:
        """Validate a received data packet, then ACK or NAK it."""
        try:
            header, payload = protocol.parse_data_packet(data)
        except protocol.PacketError as err:
            _LOGGER.warning("Rejecting packet: %s", err)
            await self._send_packet(
                protocol.build_status_packet(protocol.PACKET_NAK)
            )
            return

        await self._send_packet(
            protocol.build_status_packet(protocol.PACKET_ACK)
        )

        # A new first packet supersedes any partial transfer we were holding.
        if protocol.is_flag_set(header, protocol.HEADER_FIRST_PACKET):
            self._data_buffer.clear()

        self._data_buffer.extend(payload)

        if protocol.is_flag_set(header, protocol.HEADER_LAST_PACKET):
            self._parse_json_data()
            self._data_buffer.clear()

    def _parse_json_data(self) -> None:
        """Parse accumulated JSON data."""
        try:
            json_str = self._data_buffer.decode("utf-8")
            json_data = json.loads(json_str)
            _LOGGER.debug("Parsed JSON: %s", json_data)

            # Update raw data
            self._data.raw_data.update(json_data)

            # Map JSON keys to data fields
            self._map_json_to_data(json_data)

            # Notify callback
            if self._data_callback:
                self._data_callback(self._data)

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _LOGGER.warning("Failed to parse JSON: %s", e)

    def _map_json_to_data(self, json_data: dict[str, Any]) -> None:
        """Map JSON keys to DeviceData fields."""
        # Dashboard
        if "dh" in json_data:
            self._data.time_hours = json_data["dh"]
        if "dm" in json_data:
            self._data.time_minutes = json_data["dm"]
        if "ds" in json_data:
            self._data.time_seconds = json_data["ds"]
        if "dbl" in json_data:
            self._data.battery_level_mv = json_data["dbl"]
        if "dtgr" in json_data:
            self._data.total_gallons_remaining = json_data["dtgr"]
        if "dpfd" in json_data:
            self._data.peak_flow_daily = json_data["dpfd"]
        if "dwh" in json_data:
            self._data.water_hardness = json_data["dwh"]
        if "ddo" in json_data:
            self._data.day_override = json_data["ddo"]
        if "dcdo" in json_data:
            self._data.current_day_override = json_data["dcdo"]
        if "dwu" in json_data:
            self._data.water_used_today = json_data["dwu"]
        if "dwau" in json_data:
            self._data.average_water_used = json_data["dwau"]
        if "drth" in json_data:
            self._data.regen_time_hours = json_data["drth"]
        if "drtt" in json_data:
            self._data.regen_time_type = json_data["drtt"]
        if "drtr" in json_data:
            self._data.regen_time_remaining = json_data["drtr"]
        if "drcp" in json_data:
            self._data.regen_current_position = json_data["drcp"]
        if "dria" in json_data:
            self._data.regen_in_aeration = bool(json_data["dria"])
        if "dps" in json_data:
            self._data.regen_soak_mode = bool(json_data["dps"])
        if "drst" in json_data:
            self._data.regen_soak_timer = json_data["drst"]
        if "dpe" in json_data:
            self._data.prefill_enabled = bool(json_data["dpe"])
        if "dpd" in json_data:
            self._data.prefill_duration = json_data["dpd"]

        # Brine tank
        if "dbts" in json_data:
            self._data.brine_tank_total_salt = json_data["dbts"]
        if "dbtr" in json_data:
            self._data.brine_tank_remaining_salt = json_data["dbtr"]
        if "dbtw" in json_data:
            self._data.brine_tank_width = json_data["dbtw"]
        if "dbth" in json_data:
            self._data.brine_tank_height = json_data["dbth"]
        if "dbrt" in json_data:
            self._data.brine_tank_reserve_time = json_data["dbrt"]

        # Advanced settings
        if "asd" in json_data:
            self._data.days_until_regen = json_data["asd"]
        if "asr" in json_data:
            self._data.regen_day_override = json_data["asr"]
        if "asar" in json_data:
            self._data.auto_reserve_mode = bool(json_data["asar"])
        if "asrc" in json_data:
            self._data.reserve_capacity = json_data["asrc"]
        if "asrg" in json_data:
            self._data.reserve_capacity_gallons = json_data["asrg"]
        if "astg" in json_data:
            self._data.total_grains_capacity = json_data["astg"]
        if "asad" in json_data:
            self._data.aeration_days = json_data["asad"]
        if "ascp" in json_data:
            self._data.chlorine_pulses = json_data["ascp"]
        if "asdo" in json_data:
            self._data.display_off = bool(json_data["asdo"])
        if "asnp" in json_data:
            self._data.num_regen_positions = json_data["asnp"]

        # Status & History
        if "shdo" in json_data:
            self._data.days_in_operation = json_data["shdo"]
        if "shdr" in json_data:
            self._data.days_since_last_regen = json_data["shdr"]
        if "shgs" in json_data:
            self._data.gallons_since_last_regen = json_data["shgs"]
        if "shrc" in json_data:
            self._data.regen_counter = json_data["shrc"]
        if "shrr" in json_data:
            self._data.regen_counter_resettable = json_data["shrr"]
        if "shgt" in json_data:
            self._data.total_gallons = json_data["shgt"]
        if "shgr" in json_data:
            self._data.total_gallons_resettable = json_data["shgr"]
        if "shel" in json_data:
            self._data.error_log = _parse_error_log(json_data["shel"])

        # Graphs
        if "grp" in json_data:
            self._data.peak_flow_history = _parse_graph(json_data["grp"])
        if "ggd" in json_data:
            self._data.daily_gallons_history = _parse_graph(json_data["ggd"])
        if "ggr" in json_data:
            self._data.gallons_between_regens = _parse_graph(json_data["ggr"])

        # Global
        if "gvs" in json_data:
            self._data.valve_status = json_data["gvs"]
        if "gve" in json_data:
            self._data.valve_error = json_data["gve"]
        if "gpf" in json_data:
            self._data.present_flow = json_data["gpf"]
        if "gra" in json_data:
            self._data.regen_active = bool(json_data["gra"])
        if "grs" in json_data:
            self._data.regen_state = json_data["grs"]
        if "as" in json_data:
            self._data.auth_state = json_data["as"]

    async def _handle_incoming(self, data: bytes) -> None:
        """Dispatch one packet received from the device."""
        status = protocol.classify_status(data)

        if status is StatusPacket.MARCO:
            await self._send_packet(
                protocol.build_status_packet(protocol.PACKET_POLO)
            )
        elif status is StatusPacket.TIMEOUT_QUERY:
            # Last-ditch liveness check from the device before it drops us.
            await self._send_packet(
                protocol.build_status_packet(protocol.PACKET_TIMEOUT_ACK)
            )
        elif status in (StatusPacket.ACK, StatusPacket.NAK):
            self._resolve_ack(status)
        elif status is not None:
            _LOGGER.debug("Ignoring status packet %s", status.name)
        elif len(data) <= 1:
            # An undocumented status byte. NAKing it would ask the device to
            # retransmit something it does not consider a data packet, so it
            # is only logged.
            _LOGGER.debug("Ignoring unrecognized byte %s", data.hex())
        else:
            await self._process_packet(data)

    def _resolve_ack(self, status: StatusPacket) -> None:
        """Hand an ACK/NAK to a write that is waiting on one.

        A write that timed out may still have an acknowledgement in flight.
        Because the link delivers in order, that straggler is the next one we
        see, so it is discarded rather than allowed to satisfy a later write.
        """
        if self._unmatched_acks > 0:
            self._unmatched_acks -= 1
            _LOGGER.debug("Discarding late %s from a timed-out write", status.name)
            return

        waiter = self._ack_waiter
        if waiter is not None and not waiter.done():
            waiter.set_result(status)

    async def _monitor_loop(self) -> None:
        """Monitor loop to handle incoming packets."""
        _LOGGER.debug("Starting monitor loop")
        while not self._stop_event.is_set():
            try:
                data = await asyncio.wait_for(
                    self._notification_queue.get(),
                    timeout=30.0,
                )
                await self._handle_incoming(data)

            except asyncio.TimeoutError:
                # Connection might be stale, but don't break
                _LOGGER.debug("Monitor loop timeout - checking connection")
                if self._client and not self._client.is_connected:
                    _LOGGER.warning("Connection lost during monitor")
                    break
                continue
            except asyncio.CancelledError:
                _LOGGER.debug("Monitor loop cancelled")
                break
            except Exception as e:
                _LOGGER.exception("Error in monitor loop: %s", e)
                break

        _LOGGER.debug("Monitor loop ended")
        self._state = ConnectionState.DISCONNECTED

    async def connect(self) -> bool:
        """Connect to the device and authenticate.

        Uses bleak-retry-connector for reliable connection establishment.
        """
        if self._state != ConnectionState.DISCONNECTED:
            _LOGGER.warning("Already connected or connecting")
            return self.is_connected

        self._state = ConnectionState.CONNECTING
        self._stop_event.clear()

        # Anything left from a previous session would be read as a response to
        # this session's handshake.
        self._reset_session_state()

        try:
            # Use bleak-retry-connector for reliable connection
            _LOGGER.info(
                "Connecting to %s (%s)",
                self._ble_device.name,
                self._ble_device.address,
            )
            self._client = await establish_connection(
                BleakClient,
                self._ble_device,
                self._ble_device.address,
                max_attempts=3,
            )
            _LOGGER.info("BLE connection established")

            # Start notifications
            await self._client.start_notify(
                CHAR_UUID_READ, self._notification_callback
            )

            # Authenticate
            if not await self._authenticate():
                await self.disconnect()
                return False

            # Start monitor loop
            self._monitor_task = asyncio.create_task(self._monitor_loop())

            return True

        except Exception as e:
            _LOGGER.error("Failed to connect: %s", e)
            self._state = ConnectionState.DISCONNECTED
            return False

    async def async_write_keys(self, payload: dict[str, Any]) -> None:
        """Write API keys to the device and wait for it to acknowledge.

        The device silently ignores keys it does not accept and writes that
        match its current value, so an ACK confirms delivery only -- not that
        anything changed.
        """
        if not self.is_connected:
            raise ChandlerWriteError("Not connected to the device")

        packet = protocol.build_data_packet(payload)

        async with self._write_lock:
            # One retry: a NAK means the device saw a malformed packet, which
            # a straight resend usually clears.
            for attempt in range(2):
                status = await self._send_and_await_ack(packet, payload)

                if status is StatusPacket.ACK:
                    return
                if status is StatusPacket.NAK:
                    _LOGGER.warning(
                        "Device rejected write %s (attempt %d)",
                        payload,
                        attempt + 1,
                    )

            raise ChandlerWriteError(f"Device rejected write {payload}")

    async def _send_and_await_ack(
        self, packet: bytes, payload: dict[str, Any]
    ) -> StatusPacket | None:
        """Send a data packet and wait for the monitor loop to see an ACK."""
        loop = asyncio.get_running_loop()
        self._ack_waiter = loop.create_future()
        try:
            await self._send_packet(packet)
            return await asyncio.wait_for(
                self._ack_waiter, timeout=WRITE_ACK_TIMEOUT
            )
        except asyncio.TimeoutError as err:
            # The acknowledgement may still be on its way; make sure it does
            # not get mistaken for the next write's.
            self._unmatched_acks += 1
            raise ChandlerWriteError(
                f"Timed out waiting for the device to acknowledge {payload}"
            ) from err
        finally:
            self._ack_waiter = None

    def _reset_session_state(self) -> None:
        """Drop anything carried over from a previous connection."""
        while not self._notification_queue.empty():
            self._notification_queue.get_nowait()
        self._data_buffer.clear()
        self._unmatched_acks = 0
        self._ack_waiter = None

    async def _send_device_reset(self) -> None:
        """Ask the device to release the link before we drop it.

        These valves otherwise hold the connection open long past our
        disconnect, which blocks the next connection attempt.
        """
        try:
            await self._send_packet(
                protocol.build_status_packet(protocol.PACKET_DEVICE_RESET)
            )
            await asyncio.sleep(DEVICE_RESET_DELAY)
        except Exception as err:
            _LOGGER.debug("Device reset command failed: %s", err)

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        _LOGGER.info("Disconnecting from device")
        self._stop_event.set()

        # Cancel monitor task
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        # Drain remaining packets from queue
        while not self._notification_queue.empty():
            data = self._notification_queue.get_nowait()
            await self._handle_incoming(data)

        # Disconnect BLE client
        if self._client:
            try:
                if self._client.is_connected:
                    await self._send_device_reset()
                    await self._client.stop_notify(CHAR_UUID_READ)
                    await self._client.disconnect()
            except Exception as e:
                _LOGGER.debug("Error during disconnect: %s", e)
            finally:
                self._client = None

        self._state = ConnectionState.DISCONNECTED
        _LOGGER.info("Disconnected")
