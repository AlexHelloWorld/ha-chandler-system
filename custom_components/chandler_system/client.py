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

from .const import (
    CHAR_UUID_READ,
    CHAR_UUID_WRITE,
)

_LOGGER = logging.getLogger(__name__)

# Protocol constants
AUTH_REQUEST = 0xEA
ACK = 0xCC
KEEP_ALIVE_MARCO = 0xE0
KEEP_ALIVE_POLO = 0xF0

# Header bits
HEADER_FIRST_PACKET = 0x80
HEADER_LAST_PACKET = 0x40


class ConnectionState(Enum):
    """Connection state enum."""

    DISCONNECTED = 0
    CONNECTING = 1
    AUTHENTICATING = 2
    CONNECTED = 3


@dataclass
class DeviceData:
    """Data class to hold all parsed device data."""

    # Dashboard data
    time_hours: int | None = None  # dh
    time_minutes: int | None = None  # dm
    battery_level_mv: int | None = None  # dbl (millivolts)
    total_gallons_remaining: float | None = None  # dtgr (hundredths)
    peak_flow_daily: float | None = None  # dpfd (in hundredths)
    water_hardness: int | None = None  # dwh (GPG)
    day_override: int | None = None  # ddo
    current_day_override: int | None = None  # dcdo
    water_used_today: float | None = None  # dwu (in hundredths)
    average_water_used: float | None = None  # dwau (in hundredths)
    regen_time_hours: int | None = None  # drth
    regen_time_type: int | None = None  # drtt
    regen_time_remaining: int | None = None  # drtr
    regen_current_position: int | None = None  # drcp
    regen_in_aeration: bool | None = None  # dria
    regen_soak_mode: bool | None = None  # dps
    regen_soak_timer: int | None = None  # drst
    prefill_enabled: bool | None = None  # dpe
    prefill_duration: int | None = None  # dpd

    # Brine tank
    brine_tank_total_salt: int | None = None  # dbts (pounds)
    brine_tank_remaining_salt: int | None = None  # dbtr (in tenths)
    brine_tank_width: int | None = None  # dbtw
    brine_tank_height: int | None = None  # dbth
    brine_tank_reserve_time: int | None = None  # dbrt

    # Advanced settings
    days_until_regen: int | None = None  # asd
    regen_day_override: int | None = None  # asr
    auto_reserve_mode: bool | None = None  # asar
    reserve_capacity: int | None = None  # asrc
    reserve_capacity_gallons: float | None = None  # asrg (hundredths)
    total_grains_capacity: int | None = None  # astg (multiply by 1000)
    aeration_days: int | None = None  # asad
    chlorine_pulses: int | None = None  # ascp
    display_off: bool | None = None  # asdo
    num_regen_positions: int | None = None  # asnp

    # Status & History
    days_in_operation: int | None = None  # shdo
    days_since_last_regen: int | None = None  # shdr
    gallons_since_last_regen: float | None = None  # shgs (hundredths)
    regen_counter: int | None = None  # shrc
    regen_counter_resettable: int | None = None  # shrr
    total_gallons: float | None = None  # shgt (in hundredths)
    total_gallons_resettable: float | None = None  # shgr (hundredths)

    # Global
    valve_status: int | None = None  # gvs
    valve_error: int | None = None  # gve
    present_flow: float | None = None  # gpf (in hundredths)
    regen_active: bool | None = None  # gra
    regen_state: int | None = None  # grs
    auth_state: int | None = None  # as (2 = authenticated)

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
    def remaining_salt_pounds(self) -> int | None:
        """Get remaining salt in pounds (rounded)."""
        if self.brine_tank_remaining_salt is not None:
            return round(self.brine_tank_remaining_salt / 10.0)
        return None

    @property
    def salt_level_percent(self) -> float | None:
        """Calculate salt level percentage."""
        remaining = self.brine_tank_remaining_salt
        total = self.brine_tank_total_salt
        if remaining is not None and total:
            return min(100.0, (remaining / 10.0 / total) * 100.0)
        return None

    @property
    def capacity_remaining_percent(self) -> float | None:
        """Calculate capacity remaining percentage."""
        remaining = self.total_gallons_remaining
        capacity = self.total_grains_capacity
        if remaining is not None and capacity:
            total = capacity * 1000
            if total > 0:
                return min(100.0, (remaining / 100.0) / total * 100.0)
        return None


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
        """Authenticate with the device."""
        self._state = ConnectionState.AUTHENTICATING

        # Send ID status packet
        await self._send_packet(bytes([AUTH_REQUEST]))

        # Wait for ACK and initial data
        while True:
            try:
                data = await self._wait_for_response(timeout=10.0)
                if len(data) == 1 and data[0] == ACK:
                    # Send auth token
                    await self._send_packet(self._auth_token)
                    self._state = ConnectionState.CONNECTED
                    _LOGGER.info("Authentication successful")
                    return True
                else:
                    # Initial data packet - send ACK
                    await self._send_packet(bytes([ACK]))
                    # Process the data
                    self._process_packet(data)
            except asyncio.TimeoutError:
                _LOGGER.error("Authentication timeout")
                return False

    def _process_packet(self, data: bytes) -> None:
        """Process a received data packet."""
        if len(data) < 3:
            return

        header = data[0]

        # Check for keep-alive
        if len(data) == 1:
            if header == KEEP_ALIVE_MARCO:
                asyncio.create_task(
                    self._send_packet(bytes([KEEP_ALIVE_POLO]))
                )
            return

        # Extract JSON payload (skip header, remove CRC16 at end)
        payload = data[1:-2]
        self._data_buffer.extend(payload)

        # Check if this is the last packet
        is_last = bool(header & HEADER_LAST_PACKET)
        if is_last:
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

    async def _monitor_loop(self) -> None:
        """Monitor loop to handle incoming packets."""
        _LOGGER.debug("Starting monitor loop")
        while not self._stop_event.is_set():
            try:
                data = await asyncio.wait_for(
                    self._notification_queue.get(),
                    timeout=30.0,
                )

                # Handle keep-alive
                if len(data) == 1:
                    if data[0] == KEEP_ALIVE_MARCO:
                        await self._send_packet(bytes([KEEP_ALIVE_POLO]))
                    continue

                # Handle ACK
                if len(data) == 1 and data[0] == ACK:
                    continue

                # Send ACK for data packets
                await self._send_packet(bytes([ACK]))

                # Process the packet
                self._process_packet(data)

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

        # Disconnect BLE client
        if self._client:
            try:
                if self._client.is_connected:
                    await self._client.stop_notify(CHAR_UUID_READ)
                    await self._client.disconnect()
            except Exception as e:
                _LOGGER.debug("Error during disconnect: %s", e)
            finally:
                self._client = None

        self._state = ConnectionState.DISCONNECTED
        _LOGGER.info("Disconnected")

    async def __aenter__(self) -> "ChandlerClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self, exc_type: Any, exc_val: Any, exc_tb: Any
    ) -> None:
        """Async context manager exit."""
        await self.disconnect()

