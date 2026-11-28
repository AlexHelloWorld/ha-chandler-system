"""Bluetooth polling client for Chandler Water System devices."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection
from homeassistant.util import dt as dt_util

from . import protocol
from .const import (
    CHAR_UUID_READ,
    CHAR_UUID_WRITE,
    FIRMWARE_QUARTER_GALLON_VERSION,
    REGEN_STATE_MAP,
    REGEN_TIME_TYPE_MINUTES,
    REGEN_TIME_TYPE_SECONDS,
    VALVE_SERIES_MAP,
    VALVE_TYPE_MAP,
    get_error_text,
)
from .protocol import StatusPacket

_LOGGER = logging.getLogger(__name__)

# How long to wait for the device to ACK a write before giving up.
WRITE_ACK_TIMEOUT = 5.0
# Overall budget for the authentication handshake.
AUTH_TIMEOUT = 20.0
# How long to wait for any single reply during the handshake.
AUTH_REPLY_TIMEOUT = 8.0
# After the valve ACKs 0xEA, pause briefly so we receive and ACK any initial
# unauthenticated data burst before writing the raw 16-byte auth token.
AUTH_INITIAL_DATA_WAIT = 0.5
# Quiet window after an initial packet completes before sending the token.
AUTH_INITIAL_DATA_QUIET = 0.15
# Upper bound on draining initial post-0xCC data before sending the token.
AUTH_INITIAL_DATA_MAX_WAIT = 2.0
# Minimum idle interval after sending the token before retrying it on MARCO.
AUTH_TOKEN_RETRY_INTERVAL = 2.0
# Maximum number of times to transmit the auth token within one handshake.
AUTH_TOKEN_MAX_ATTEMPTS = 4
# Wait this long after the last data packet before ending a poll drain.
POLL_BURST_QUIET_TIMEOUT = 1.5
# Maximum wait for the first post-auth data packet before assuming dump is done.
POLL_INITIAL_DATA_TIMEOUT = 4.0
# Hard cap on draining a single poll burst so a chatty link never hangs.
POLL_MAX_DRAIN_DURATION = 15.0
# Short quiet drain after a write ACK to capture the echoed updated value.
POST_WRITE_QUIET_TIMEOUT = 1.0
POST_WRITE_MAX_DURATION = 4.0
# After sending the device-reset ('R') byte, wait for the valve itself to drop
# the BLE link before tearing down on our side.
DEVICE_RESET_WAIT_DISCONNECT = 0.5
DEVICE_RESET_MIN_DELAY = 0.15
# Minimum gap between closing one BLE session and opening the next so the
# nRF52840 radio always finishes releasing its slot and resuming advertising.
MIN_SESSION_GAP = 3.0

# Authentication states reported by the device in the "as" key.
AUTH_STATE_NOT_AUTHENTICATED = 1
AUTH_STATE_AUTHENTICATED = 2


class ChandlerWriteError(Exception):
    """Raised when a write to the device could not be delivered."""


class ChandlerAuthError(Exception):
    """Raised when the device rejects the authentication token."""


class ChandlerConnectionError(Exception):
    """Raised when a BLE poll or write session could not be established."""


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
    """Data class to hold all parsed device data from a poll snapshot."""

    # Device list / identity (supports both C6.19+ and C6.18- keys)
    serial_number_a: int | None = None  # gesa / dlsa
    serial_number_b: int | None = None  # gesb / dlsb
    firmware_version: int | None = None  # gef / dlf (e.g. 618 -> C6.18)
    valve_type: int | None = None  # gedt / dlvt (1-27)
    valve_series: int | None = None  # dlvs (2-6)
    regen_motor_in_progress: bool | None = None  # dlr (0-1)

    # Dashboard data (all integers per API spec)
    time_hours: int | None = None  # dh (0-23, military time)
    time_minutes: int | None = None  # dm (0-59)
    time_seconds: int | None = None  # ds (0-59)
    clock_sample_time: datetime | None = None  # local timestamp when dh/dm/ds arrived
    battery_level_mv: int | None = None  # dbl (mV, 0-9700)
    total_gallons_remaining: int | None = None  # dtgr (1/100 gallons)
    peak_flow_daily: int | None = None  # dpfd (1/100 GPM)
    water_hardness: int | None = None  # dwh (GPG, 0-99)
    day_override: int | None = None  # ddo (days, 0-29)
    current_day_override: int | None = None  # dcdo (days, 0-29)
    water_used_today: int | None = None  # dwu (1/100 gallons)
    average_water_used: int | None = None  # dwau (1/100 gallons)
    regen_time_hours: int | None = None  # drth (0-23, military time)
    regen_time_type: int | None = None  # drtt (0=s, 1=min, 2=salt lb)
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
    reserve_capacity: int | None = None  # asrc (0-49 %)
    reserve_capacity_gallons: int | None = None  # asrg (1/100 gallons)
    total_grains_capacity: int | None = None  # astg (1000 GPG)
    aeration_days: int | None = None  # asad (0-9)
    chlorine_pulses: int | None = None  # ascp (0-4)
    display_off: bool | None = None  # asdo (0-1)
    num_regen_positions: int | None = None  # asnp
    cycle_position_times: list[int] = field(default_factory=list)  # aspt

    # Status & History
    days_in_operation: int | None = None  # shdo
    days_since_last_regen: int | None = None  # shdr
    gallons_since_last_regen: int | None = None  # shgs (/4 C6.19+, /100 C6.18-)
    regen_counter: int | None = None  # shrc
    regen_counter_resettable: int | None = None  # shrr
    total_gallons: int | None = None  # shgt (/4 C6.19+, /100 C6.18-)
    total_gallons_resettable: int | None = None  # shgr (/4 C6.19+, /100 C6.18-)

    # Global
    valve_status: int | None = None  # gvs
    valve_error: int | None = None  # gve
    present_flow: int | None = None  # gpf (1/100 GPM)
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
    def firmware_version_text(self) -> str | None:
        """Format raw firmware integer (e.g. 618 -> 'C6.18')."""
        if self.firmware_version is None:
            return None
        return f"C{self.firmware_version // 100}.{self.firmware_version % 100:02d}"

    @property
    def serial_number(self) -> str | None:
        """Format split 32-bit serial number parts as uppercase hex string."""
        if self.serial_number_a is None or self.serial_number_b is None:
            return None
        return f"{self.serial_number_a:X}{self.serial_number_b:X}"

    @property
    def valve_type_text(self) -> str | None:
        """Human-readable valve type from Device List API."""
        if self.valve_type is None:
            return None
        return VALVE_TYPE_MAP.get(self.valve_type, f"Unknown ({self.valve_type})")

    @property
    def valve_series_text(self) -> str | None:
        """Human-readable valve series from Device List API."""
        if self.valve_series is None:
            return None
        return VALVE_SERIES_MAP.get(
            self.valve_series, f"Series {self.valve_series}"
        )

    @property
    def history_gallon_divisor(self) -> float:
        """Return divisor for shgs/shgt/shgr based on firmware version.

        Per Signature-API-Guide (api-status-and-history.md):
        - C6.19 and newer: quarter-gallon counts (divide by 4)
        - C6.18 and older (or unknown): hundredths of a gallon (divide by 100)
        """
        if (
            self.firmware_version is not None
            and self.firmware_version >= FIRMWARE_QUARTER_GALLON_VERSION
        ):
            return 4.0
        return 100.0

    @property
    def total_gallons_value(self) -> float | None:
        """Lifetime total gallons processed, scaled for firmware version."""
        if self.total_gallons is None:
            return None
        return self.total_gallons / self.history_gallon_divisor

    @property
    def gallons_since_last_regen_value(self) -> float | None:
        """Gallons processed since last regen, scaled for firmware version."""
        if self.gallons_since_last_regen is None:
            return None
        return self.gallons_since_last_regen / self.history_gallon_divisor

    @property
    def total_gallons_resettable_value(self) -> float | None:
        """Resettable gallon total, scaled for firmware version."""
        if self.total_gallons_resettable is None:
            return None
        return self.total_gallons_resettable / self.history_gallon_divisor

    @property
    def present_flow_gpm(self) -> float | None:
        """Current water flow in GPM (0.0 when snapshot received without gpf)."""
        if self.present_flow is not None:
            return self.present_flow / 100.0
        if self.raw_data:
            return 0.0
        return None

    @property
    def battery_level_volts(self) -> float | None:
        """Get battery level in volts."""
        if self.battery_level_mv is not None:
            return self.battery_level_mv / 1000.0
        return None

    @property
    def salt_low(self) -> bool | None:
        """Check if salt is low from valve status (bit 7)."""
        if self.valve_status is not None:
            return bool(self.valve_status & 0x80)
        return None

    @property
    def water_state(self) -> bool | None:
        """Water state bit from valve status (bit 6, commercial/shutoff boards)."""
        if self.valve_status is not None:
            return bool(self.valve_status & 0x40)
        return None

    @property
    def bypass_state(self) -> bool | None:
        """Bypass state bit from valve status (bit 5, commercial/bypass boards)."""
        if self.valve_status is not None:
            return bool(self.valve_status & 0x20)
        return None

    @property
    def salt_level_percent(self) -> float | None:
        """Calculate salt level percentage.

        Note: remaining is in 1/10 pounds, total is in pounds.
        """
        remaining = self.brine_tank_remaining_salt
        total = self.brine_tank_total_salt
        if remaining is not None and total:
            return min(100.0, (remaining / 10.0 / total) * 100.0)
        return None

    @property
    def regen_state_text(self) -> str | None:
        """Human-readable regeneration state.

        Returns None for a code outside the documented range so Home Assistant
        does not reject an enum value outside its declared options.
        """
        if self.regen_state is None:
            return None
        return REGEN_STATE_MAP.get(self.regen_state)

    @property
    def regen_stage_text(self) -> str | None:
        """Human-readable summary of the active regeneration stage."""
        if self.regen_active is None:
            return None
        if not self.regen_active:
            return "Idle"
        if self.regen_soak_mode:
            return "Brine Soak"
        if self.regen_in_aeration:
            return "Aeration"
        if self.regen_current_position is not None:
            if self.num_regen_positions:
                return (
                    f"Position {self.regen_current_position} "
                    f"of {self.num_regen_positions}"
                )
            return f"Position {self.regen_current_position}"
        return self.regen_state_text or "Regenerating"

    @property
    def regen_step_remaining_seconds(self) -> int | None:
        """Seconds left in the current regeneration step.

        Returns 0 when idle. When the device reports salt pounds (drtt == 2),
        there is no time unit to convert.
        """
        if self.regen_active is False:
            return 0
        if self.regen_time_remaining is None:
            return None
        if self.regen_time_type == REGEN_TIME_TYPE_SECONDS:
            return self.regen_time_remaining
        if self.regen_time_type == REGEN_TIME_TYPE_MINUTES:
            return self.regen_time_remaining * 60
        return None

    @property
    def regen_step_remaining_minutes(self) -> float | None:
        """Minutes left in the current regeneration step (0 when idle)."""
        seconds = self.regen_step_remaining_seconds
        if seconds is None:
            return None
        return round(seconds / 60.0, 2)

    @property
    def regen_total_remaining_minutes(self) -> float | None:
        """Estimated total minutes left across current and remaining steps.

        Combines current step remaining time (or brine soak timer) with the
        configured durations of any later cycle positions from ``aspt``.
        """
        if self.regen_active is False:
            return 0.0
        if self.regen_active is None:
            return None

        current_min = self.regen_step_remaining_minutes
        if (
            current_min is None
            and self.regen_soak_mode
            and self.regen_soak_timer is not None
        ):
            current_min = float(self.regen_soak_timer)
        if current_min is None:
            return None

        future_min = 0.0
        pos = self.regen_current_position
        if (
            self.cycle_position_times
            and pos is not None
            and 0 < pos < len(self.cycle_position_times)
        ):
            future_min = float(
                sum(t for t in self.cycle_position_times[pos + 1 :] if t > 0)
            )
        return round(current_min + future_min, 1)

    @property
    def last_error(self) -> ErrorLogEntry | None:
        """Most recent real error, or None if the log holds only empty slots."""
        for entry in self.error_log:
            if entry.error_code != 0:
                return entry
        return None

    @property
    def has_valve_error(self) -> bool | None:
        """Whether the valve is currently reporting an error.

        The valve omits ``gve`` when healthy, so a populated snapshot without
        ``gve`` means no active error rather than unknown.
        """
        if self.valve_error is not None:
            return self.valve_error != 0
        if self.raw_data:
            return False
        return None


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


def _parse_int_list(raw: Any) -> list[int]:
    """Parse an integer array (such as aspt cycle position times)."""
    if not isinstance(raw, list):
        return []
    return [int(value) for value in raw if isinstance(value, (int, float))]


class ChandlerClient:
    """Short-lived BLE polling client for Chandler Water System devices.

    Rather than holding a persistent GATT link open (which wedges the valve
    firmware if radio drops prevent sending the ``R`` reset byte), every poll
    and write runs in a bounded, serialized session that always closes
    gracefully with ``R`` and observes a cooldown gap before reconnecting.
    """

    def __init__(
        self,
        ble_device: BLEDevice,
        auth_token: str,
        data_callback: Callable[[DeviceData], None] | None = None,
    ) -> None:
        """Initialize the client."""
        self._ble_device = ble_device
        self._auth_token = bytearray.fromhex(auth_token.replace("-", ""))
        self._data_callback = data_callback

        self._client: BleakClient | None = None
        self._state = ConnectionState.DISCONNECTED
        self._notification_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._data_buffer = bytearray()
        self._data = DeviceData()
        self._session_lock = asyncio.Lock()
        self._disconnect_event = asyncio.Event()
        self._last_disconnect_monotonic: float = 0.0

    def set_ble_device(self, ble_device: BLEDevice) -> None:
        """Update the BLE device reference before the next session."""
        self._ble_device = ble_device

    @property
    def state(self) -> ConnectionState:
        """Get the current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if currently inside an active authenticated session."""
        return (
            self._state == ConnectionState.CONNECTED
            and self._client is not None
            and self._client.is_connected
        )

    @property
    def data(self) -> DeviceData:
        """Get the most recently completed device snapshot."""
        return self._data

    @property
    def address(self) -> str:
        """Get the device address."""
        return self._ble_device.address

    def _make_notification_callback(
        self, queue: asyncio.Queue[bytes]
    ) -> Callable[[Any, bytes], None]:
        """Bind notifications to one session's queue so stale links stay isolated."""

        def handle(_sender: Any, data: bytes) -> None:
            _LOGGER.debug("Received: %s", data.hex())
            queue.put_nowait(data)

        return handle

    def _on_disconnected(self, client: BleakClient) -> None:
        """Signal disconnect event for the active session."""
        if client is not self._client:
            return
        _LOGGER.debug("BLE link closed by peer or transport")
        self._state = ConnectionState.DISCONNECTED
        self._disconnect_event.set()

    async def _respect_session_gap(self) -> None:
        """Ensure the nRF52840 radio had time to release its previous link."""
        if self._last_disconnect_monotonic <= 0:
            return
        elapsed = asyncio.get_running_loop().time() - self._last_disconnect_monotonic
        remaining = MIN_SESSION_GAP - elapsed
        if remaining > 0:
            _LOGGER.debug("Waiting %.2fs inter-session cooldown", remaining)
            await asyncio.sleep(remaining)

    async def _send_packet(
        self, data: bytes | bytearray, *, redact: bool = False
    ) -> None:
        """Send a raw packet to the valve's write characteristic."""
        if self._client is None or not self._client.is_connected:
            raise ChandlerWriteError("Bluetooth link is not connected")

        _LOGGER.debug("Sending: %s", "<REDACTED>" if redact else data.hex())
        await self._client.write_gatt_char(
            CHAR_UUID_WRITE, data, response=False
        )

    async def _wait_for_response(self, timeout: float = 5.0) -> bytes:
        """Wait for one notification packet from the active session's queue."""
        return await asyncio.wait_for(
            self._notification_queue.get(), timeout=timeout
        )

    async def _authenticate(self, target: DeviceData) -> None:
        """Authenticate with the valve on the currently open BLE link.

        Follows the vendor handshake order: send ``0xEA``, wait for ``0xCC``,
        receive and ACK any initial unauthenticated data burst, then transmit
        the raw 16-byte auth token. Because the token has no ACK and the valve
        stays in a MARCO/POLO keep-alive loop until a valid token is accepted,
        re-send the token on idle keep-alives if no ``as`` reply arrives.

        Raises ChandlerAuthError if the token is explicitly rejected, or
        ChandlerConnectionError on timeout or transport drop.
        """
        self._state = ConnectionState.AUTHENTICATING
        target.auth_state = None

        await self._send_packet(
            protocol.build_status_packet(protocol.PACKET_AUTH_REQUEST)
        )

        loop = asyncio.get_running_loop()
        deadline = loop.time() + AUTH_TIMEOUT
        ack_received = False
        ack_at = 0.0
        initial_data_seen = False
        last_initial_data_at = 0.0
        token_sent = False
        token_attempts = 0
        last_token_sent_at = 0.0
        last_post_token_data_at = 0.0
        pre_token_data_packets = 0
        post_token_data_packets = 0
        marco_count = 0

        async def _send_auth_token(reason: str) -> None:
            nonlocal token_sent, token_attempts, last_token_sent_at
            # Clear any pre-token {"as": 1} from the initial unauthenticated dump.
            target.auth_state = None
            token_attempts += 1
            if token_attempts > 1:
                _LOGGER.debug(
                    "Re-sending auth token (attempt %d/%d, %s)",
                    token_attempts,
                    AUTH_TOKEN_MAX_ATTEMPTS,
                    reason,
                )
            await self._send_packet(self._auth_token, redact=True)
            token_sent = True
            last_token_sent_at = loop.time()

        def _timeout_summary() -> str:
            return (
                f"ack={ack_received}, token_attempts={token_attempts}, "
                f"pre_pkts={pre_token_data_packets}, "
                f"post_pkts={post_token_data_packets}, "
                f"marcos={marco_count}, state={target.auth_state}"
            )

        while True:
            if self._disconnect_event.is_set() or (
                self._client is not None and not self._client.is_connected
            ):
                raise ChandlerConnectionError(
                    "Bluetooth link dropped during authentication"
                )

            now = loop.time()
            remaining = deadline - now
            if remaining <= 0:
                raise ChandlerConnectionError(
                    f"Authentication timed out after {AUTH_TIMEOUT:.0f}s "
                    f"({_timeout_summary()})"
                )

            waiting_initial = ack_received and not token_sent
            if waiting_initial:
                max_left = (ack_at + AUTH_INITIAL_DATA_MAX_WAIT) - now
                if max_left <= 0:
                    await _send_auth_token("initial burst ceiling")
                    continue
                if initial_data_seen and not self._data_buffer:
                    quiet_left = (
                        last_initial_data_at + AUTH_INITIAL_DATA_QUIET
                    ) - now
                    if quiet_left <= 0:
                        await _send_auth_token("initial burst settled")
                        continue
                    wait = min(remaining, max_left, quiet_left)
                elif self._data_buffer:
                    wait = min(remaining, max_left)
                else:
                    init_left = (ack_at + AUTH_INITIAL_DATA_WAIT) - now
                    if init_left <= 0:
                        await _send_auth_token("no initial data")
                        continue
                    wait = min(remaining, max_left, init_left)
            else:
                wait = min(remaining, AUTH_REPLY_TIMEOUT)

            try:
                data = await self._wait_for_response(timeout=wait)
            except asyncio.TimeoutError as err:
                if loop.time() >= deadline:
                    raise ChandlerConnectionError(
                        f"Authentication timed out after {AUTH_TIMEOUT:.0f}s "
                        f"({_timeout_summary()})"
                    ) from err
                if waiting_initial:
                    if self._data_buffer and (
                        loop.time() < ack_at + AUTH_INITIAL_DATA_MAX_WAIT
                    ):
                        continue
                    await _send_auth_token("initial wait elapsed")
                    continue
                if remaining <= AUTH_REPLY_TIMEOUT:
                    raise ChandlerConnectionError(
                        f"Authentication timed out after {AUTH_TIMEOUT:.0f}s "
                        f"({_timeout_summary()})"
                    ) from err
                raise ChandlerConnectionError(
                    f"No reply from device during authentication "
                    f"(waited {wait:.1f}s, {_timeout_summary()})"
                ) from err

            status = protocol.classify_status(data)
            if not ack_received and status is StatusPacket.ACK:
                ack_received = True
                ack_at = loop.time()
                continue

            if status is StatusPacket.MARCO:
                marco_count += 1

            result = await self._handle_incoming(data, target)
            if result is True:
                if token_sent:
                    post_token_data_packets += 1
                    last_post_token_data_at = loop.time()
                else:
                    pre_token_data_packets += 1
                    initial_data_seen = True
                    last_initial_data_at = loop.time()

            if target.auth_state == AUTH_STATE_AUTHENTICATED:
                self._state = ConnectionState.CONNECTED
                _LOGGER.debug(
                    "Authentication successful (%s)", _timeout_summary()
                )
                return

            if token_sent and target.auth_state == AUTH_STATE_NOT_AUTHENTICATED:
                raise ChandlerAuthError(
                    "Device rejected the authentication token. Generate a new "
                    "one in the Chandler/Springwell app and reconfigure."
                )

            if (
                status in (StatusPacket.MARCO, StatusPacket.TIMEOUT_QUERY)
                and not self._data_buffer
            ):
                if ack_received and not token_sent:
                    await _send_auth_token("idle keep-alive")
                elif (
                    token_sent
                    and target.auth_state in (None, 0)
                    and token_attempts < AUTH_TOKEN_MAX_ATTEMPTS
                ):
                    last_activity = max(
                        last_token_sent_at, last_post_token_data_at
                    )
                    if (
                        loop.time() - last_activity
                        >= AUTH_TOKEN_RETRY_INTERVAL
                    ):
                        await _send_auth_token("idle keep-alive")

    async def _process_packet(self, data: bytes, target: DeviceData) -> bool:
        """Validate a received data packet, ACK/NAK it, and parse complete JSON.

        Returns True if a valid data packet was accepted.
        """
        try:
            header, payload = protocol.parse_data_packet(data)
        except protocol.PacketError as err:
            _LOGGER.warning("Rejecting packet: %s", err)
            await self._send_packet(
                protocol.build_status_packet(protocol.PACKET_NAK)
            )
            return False

        await self._send_packet(
            protocol.build_status_packet(protocol.PACKET_ACK)
        )

        # A new first packet supersedes any stale partial buffer.
        if protocol.is_flag_set(header, protocol.HEADER_FIRST_PACKET):
            self._data_buffer.clear()

        self._data_buffer.extend(payload)

        if protocol.is_flag_set(header, protocol.HEADER_LAST_PACKET):
            self._parse_json_data(target)
            self._data_buffer.clear()

        return True

    def _parse_json_data(self, target: DeviceData | None = None) -> None:
        """Parse accumulated JSON bytes into the target DeviceData."""
        dest = self._data if target is None else target
        try:
            json_str = self._data_buffer.decode("utf-8")
            json_data = json.loads(json_str)
            _LOGGER.debug("Parsed JSON: %s", json_data)

            dest.raw_data.update(json_data)
            self._map_json_to_data(json_data, dest)

            if self._data_callback and dest is self._data:
                self._data_callback(dest)

        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            _LOGGER.warning("Failed to parse JSON: %s", err)
            _LOGGER.debug(
                "Unparseable JSON buffer (%d bytes): %s",
                len(self._data_buffer),
                self._data_buffer.hex(),
            )

    def _map_json_to_data(
        self, json_data: dict[str, Any], target: DeviceData | None = None
    ) -> None:
        """Map JSON keys from the Signature API to DeviceData fields."""
        dest = self._data if target is None else target

        # Device List (accept both C6.19+ and C6.18- keys)
        if "gesa" in json_data:
            dest.serial_number_a = json_data["gesa"]
        elif "dlsa" in json_data:
            dest.serial_number_a = json_data["dlsa"]
        if "gesb" in json_data:
            dest.serial_number_b = json_data["gesb"]
        elif "dlsb" in json_data:
            dest.serial_number_b = json_data["dlsb"]
        if "gef" in json_data:
            dest.firmware_version = json_data["gef"]
        elif "dlf" in json_data:
            dest.firmware_version = json_data["dlf"]
        if "gedt" in json_data:
            dest.valve_type = json_data["gedt"]
        elif "dlvt" in json_data:
            dest.valve_type = json_data["dlvt"]
        if "dlvs" in json_data:
            dest.valve_series = json_data["dlvs"]
        if "dlr" in json_data:
            dest.regen_motor_in_progress = bool(json_data["dlr"])

        # Dashboard clock (capture sample timestamp when clock fields arrive)
        clock_updated = False
        if "dh" in json_data:
            dest.time_hours = json_data["dh"]
            clock_updated = True
        if "dm" in json_data:
            dest.time_minutes = json_data["dm"]
            clock_updated = True
        if "ds" in json_data:
            dest.time_seconds = json_data["ds"]
            clock_updated = True
        if clock_updated:
            dest.clock_sample_time = dt_util.now()

        # Dashboard metrics & settings
        if "dbl" in json_data:
            dest.battery_level_mv = json_data["dbl"]
        if "dtgr" in json_data:
            dest.total_gallons_remaining = json_data["dtgr"]
        if "dpfd" in json_data:
            dest.peak_flow_daily = json_data["dpfd"]
        if "dwh" in json_data:
            dest.water_hardness = json_data["dwh"]
        if "ddo" in json_data:
            dest.day_override = json_data["ddo"]
        if "dcdo" in json_data:
            dest.current_day_override = json_data["dcdo"]
        if "dwu" in json_data:
            dest.water_used_today = json_data["dwu"]
        if "dwau" in json_data:
            dest.average_water_used = json_data["dwau"]
        if "drth" in json_data:
            dest.regen_time_hours = json_data["drth"]
        if "drtt" in json_data:
            dest.regen_time_type = json_data["drtt"]
        if "drtr" in json_data:
            dest.regen_time_remaining = json_data["drtr"]
        if "drcp" in json_data:
            dest.regen_current_position = json_data["drcp"]
        if "dria" in json_data:
            dest.regen_in_aeration = bool(json_data["dria"])
        if "dps" in json_data:
            dest.regen_soak_mode = bool(json_data["dps"])
        if "drst" in json_data:
            dest.regen_soak_timer = json_data["drst"]
        if "dpe" in json_data:
            dest.prefill_enabled = bool(json_data["dpe"])
        if "dpd" in json_data:
            dest.prefill_duration = json_data["dpd"]

        # Brine tank
        if "dbts" in json_data:
            dest.brine_tank_total_salt = json_data["dbts"]
        if "dbtr" in json_data:
            dest.brine_tank_remaining_salt = json_data["dbtr"]
        if "dbtw" in json_data:
            dest.brine_tank_width = json_data["dbtw"]
        if "dbth" in json_data:
            dest.brine_tank_height = json_data["dbth"]
        if "dbrt" in json_data:
            dest.brine_tank_reserve_time = json_data["dbrt"]

        # Advanced settings
        if "asd" in json_data:
            dest.days_until_regen = json_data["asd"]
        if "asr" in json_data:
            dest.regen_day_override = json_data["asr"]
        if "asar" in json_data:
            dest.auto_reserve_mode = bool(json_data["asar"])
        if "asrc" in json_data:
            dest.reserve_capacity = json_data["asrc"]
        if "asrg" in json_data:
            dest.reserve_capacity_gallons = json_data["asrg"]
        if "astg" in json_data:
            dest.total_grains_capacity = json_data["astg"]
        if "asad" in json_data:
            dest.aeration_days = json_data["asad"]
        if "ascp" in json_data:
            dest.chlorine_pulses = json_data["ascp"]
        if "asdo" in json_data:
            dest.display_off = bool(json_data["asdo"])
        if "asnp" in json_data:
            dest.num_regen_positions = json_data["asnp"]
        if "aspt" in json_data:
            dest.cycle_position_times = _parse_int_list(json_data["aspt"])

        # Status & History
        if "shdo" in json_data:
            dest.days_in_operation = json_data["shdo"]
        if "shdr" in json_data:
            dest.days_since_last_regen = json_data["shdr"]
        if "shgs" in json_data:
            dest.gallons_since_last_regen = json_data["shgs"]
        if "shrc" in json_data:
            dest.regen_counter = json_data["shrc"]
        if "shrr" in json_data:
            dest.regen_counter_resettable = json_data["shrr"]
        if "shgt" in json_data:
            dest.total_gallons = json_data["shgt"]
        if "shgr" in json_data:
            dest.total_gallons_resettable = json_data["shgr"]
        if "shel" in json_data:
            dest.error_log = _parse_error_log(json_data["shel"])

        # Graphs
        if "grp" in json_data:
            dest.peak_flow_history = _parse_graph(json_data["grp"])
        if "ggd" in json_data:
            dest.daily_gallons_history = _parse_graph(json_data["ggd"])
        if "ggr" in json_data:
            dest.gallons_between_regens = _parse_graph(json_data["ggr"])

        # Global
        if "gvs" in json_data:
            dest.valve_status = json_data["gvs"]
        if "gve" in json_data:
            dest.valve_error = json_data["gve"]
        if "gpf" in json_data:
            dest.present_flow = json_data["gpf"]
        if "gra" in json_data:
            dest.regen_active = bool(json_data["gra"])
        if "grs" in json_data:
            dest.regen_state = json_data["grs"]
        if "as" in json_data:
            dest.auth_state = json_data["as"]

    async def _handle_incoming(
        self, data: bytes, target: DeviceData | None = None
    ) -> StatusPacket | bool | None:
        """Dispatch one incoming packet.

        Returns StatusPacket for ACK/NAK, True when a valid data packet was
        processed, or None for keep-alives / ignored bytes.
        """
        dest = self._data if target is None else target
        status = protocol.classify_status(data)

        if status is StatusPacket.MARCO:
            await self._send_packet(
                protocol.build_status_packet(protocol.PACKET_POLO)
            )
            return None
        if status is StatusPacket.TIMEOUT_QUERY:
            await self._send_packet(
                protocol.build_status_packet(protocol.PACKET_TIMEOUT_ACK)
            )
            return None
        if status in (StatusPacket.ACK, StatusPacket.NAK):
            return status
        if status is not None:
            _LOGGER.debug("Ignoring status packet %s", status.name)
            return None
        if len(data) <= 1:
            _LOGGER.debug("Ignoring unrecognized byte %s", data.hex())
            return None
        return await self._process_packet(data, dest)

    async def _drain_packets(
        self,
        target: DeviceData,
        *,
        quiet_timeout: float = POLL_BURST_QUIET_TIMEOUT,
        initial_timeout: float = POLL_INITIAL_DATA_TIMEOUT,
        max_duration: float = POLL_MAX_DRAIN_DURATION,
        wait_for_first: bool = True,
    ) -> None:
        """Read incoming data packets until the valve's burst settles."""
        loop = asyncio.get_running_loop()
        start = loop.time()
        last_data = start
        received_any = not wait_for_first

        while True:
            if self._disconnect_event.is_set() or (
                self._client is not None and not self._client.is_connected
            ):
                _LOGGER.debug("Link closed while draining packets")
                return

            now = loop.time()
            remaining_total = max_duration - (now - start)
            if remaining_total <= 0:
                if self._data_buffer:
                    _LOGGER.warning(
                        "Poll drain hit %.1fs ceiling with partial buffer",
                        max_duration,
                    )
                return

            if received_any:
                remaining_wait = quiet_timeout - (now - last_data)
                if remaining_wait <= 0:
                    if not self._data_buffer:
                        return
                    # Finish an in-flight multi-packet JSON before leaving.
                    remaining_wait = min(remaining_total, quiet_timeout)
            else:
                remaining_wait = initial_timeout - (now - start)
                if remaining_wait <= 0:
                    return

            timeout = min(remaining_total, remaining_wait)
            try:
                data = await self._wait_for_response(timeout=timeout)
            except asyncio.TimeoutError:
                if not self._data_buffer:
                    return
                continue

            result = await self._handle_incoming(data, target)
            if result is True:
                received_any = True
                last_data = loop.time()

    async def _write_in_session(
        self, payload: dict[str, Any], target: DeviceData
    ) -> None:
        """Write one JSON payload on the active session and wait for its ACK.

        Writes are strictly serial: a status byte does not identify which write
        it answers, so only one write can be in flight at a time. Interleaved
        data packets and keep-alives are still handled while waiting.
        """
        packet = protocol.build_data_packet(payload)

        for attempt in range(2):
            try:
                await self._send_packet(packet)
            except Exception as err:
                raise ChandlerWriteError(
                    f"Failed to send {payload}: {err}"
                ) from err

            deadline = asyncio.get_running_loop().time() + WRITE_ACK_TIMEOUT
            status: StatusPacket | None = None

            while True:
                if self._disconnect_event.is_set() or (
                    self._client is not None and not self._client.is_connected
                ):
                    raise ChandlerWriteError(
                        f"Write abandoned because the connection dropped ({payload})"
                    )

                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise ChandlerWriteError(
                        f"Timed out waiting for the device to acknowledge {payload}"
                    )

                try:
                    data = await self._wait_for_response(timeout=remaining)
                except asyncio.TimeoutError as err:
                    raise ChandlerWriteError(
                        f"Timed out waiting for the device to acknowledge {payload}"
                    ) from err

                result = await self._handle_incoming(data, target)
                if isinstance(result, StatusPacket):
                    status = result
                    break

            if status is StatusPacket.ACK:
                return
            if status is StatusPacket.NAK:
                _LOGGER.warning(
                    "Device rejected write %s (attempt %d)",
                    payload,
                    attempt + 1,
                )

        raise ChandlerWriteError(f"Device rejected write {payload}")

    def _reset_session_state(self) -> None:
        """Reset queues and buffers for a fresh BLE session."""
        self._notification_queue = asyncio.Queue()
        self._data_buffer.clear()
        self._disconnect_event = asyncio.Event()

    async def _open_session(self, target: DeviceData) -> None:
        """Connect, subscribe, and authenticate for one short-lived session."""
        await self._respect_session_gap()
        self._state = ConnectionState.CONNECTING
        self._reset_session_state()

        _LOGGER.debug(
            "Opening BLE session to %s (%s)",
            self._ble_device.name,
            self._ble_device.address,
        )
        try:
            self._client = await establish_connection(
                BleakClient,
                self._ble_device,
                self._ble_device.address,
                disconnected_callback=self._on_disconnected,
                max_attempts=2,
            )
            await self._client.start_notify(
                CHAR_UUID_READ,
                self._make_notification_callback(self._notification_queue),
            )
            await self._authenticate(target)

            if self._disconnect_event.is_set() or not self._client.is_connected:
                raise ChandlerConnectionError("Link dropped during handshake")
        except (ChandlerAuthError, ChandlerConnectionError):
            await self._close_session(graceful=True)
            raise
        except Exception as err:
            await self._close_session(graceful=False)
            raise ChandlerConnectionError(
                f"Failed to connect to {self._ble_device.address}: {err}"
            ) from err

    async def _send_device_reset(self) -> None:
        """Send 'R' so the valve gracefully releases its BLE slot."""
        try:
            await self._send_packet(
                protocol.build_status_packet(protocol.PACKET_DEVICE_RESET)
            )
        except Exception as err:
            _LOGGER.debug("Device reset command failed: %s", err)
            return

        loop = asyncio.get_running_loop()
        sent_at = loop.time()
        try:
            await asyncio.wait_for(
                self._disconnect_event.wait(),
                timeout=DEVICE_RESET_WAIT_DISCONNECT,
            )
        except asyncio.TimeoutError:
            pass

        # Guarantee at least the vendor-recommended 150ms settle window.
        elapsed = loop.time() - sent_at
        if elapsed < DEVICE_RESET_MIN_DELAY:
            await asyncio.sleep(DEVICE_RESET_MIN_DELAY - elapsed)

    async def _close_session(self, *, graceful: bool = True) -> None:
        """Always release the BLE link cleanly and record cooldown timestamp."""
        client = self._client
        had_client = client is not None
        try:
            if client is not None and client.is_connected:
                if graceful:
                    await self._send_device_reset()

                # Detach reference before disconnecting so Bleak's callback
                # does not treat our intentional close as an unexpected drop.
                self._client = None

                if client.is_connected:
                    try:
                        await client.stop_notify(CHAR_UUID_READ)
                    except Exception as err:
                        _LOGGER.debug("Error unsubscribing: %s", err)
                    try:
                        await client.disconnect()
                    except Exception as err:
                        _LOGGER.debug("Error disconnecting BLE link: %s", err)
        finally:
            self._client = None
            self._state = ConnectionState.DISCONNECTED
            self._data_buffer.clear()
            if had_client:
                self._last_disconnect_monotonic = asyncio.get_running_loop().time()

    def _preserve_identity_fields(self, snapshot: DeviceData) -> None:
        """Carry forward static Device List fields if omitted from a poll."""
        prev = self._data
        if snapshot.firmware_version is None:
            snapshot.firmware_version = prev.firmware_version
        if snapshot.serial_number_a is None:
            snapshot.serial_number_a = prev.serial_number_a
        if snapshot.serial_number_b is None:
            snapshot.serial_number_b = prev.serial_number_b
        if snapshot.valve_type is None:
            snapshot.valve_type = prev.valve_type
        if snapshot.valve_series is None:
            snapshot.valve_series = prev.valve_series

    async def async_poll(
        self,
        ble_device: BLEDevice | None = None,
        *,
        post_poll_write: Callable[[DeviceData], dict[str, Any] | None] | None = None,
    ) -> DeviceData:
        """Open a short session, drain a full state snapshot, and close with 'R'.

        If ``post_poll_write`` returns a JSON payload (e.g. for automatic clock
        sync), that write is sent inside the same authenticated session before
        disconnecting.
        """
        async with self._session_lock:
            if ble_device is not None:
                self._ble_device = ble_device

            snapshot = DeviceData()
            await self._open_session(snapshot)
            try:
                await self._drain_packets(
                    snapshot,
                    quiet_timeout=POLL_BURST_QUIET_TIMEOUT,
                    initial_timeout=POLL_INITIAL_DATA_TIMEOUT,
                    max_duration=POLL_MAX_DRAIN_DURATION,
                    wait_for_first=True,
                )
                self._preserve_identity_fields(snapshot)

                if post_poll_write is not None:
                    payload = post_poll_write(snapshot)
                    if payload:
                        try:
                            await self._write_in_session(payload, snapshot)
                            await self._drain_packets(
                                snapshot,
                                quiet_timeout=POST_WRITE_QUIET_TIMEOUT,
                                initial_timeout=POST_WRITE_QUIET_TIMEOUT,
                                max_duration=POST_WRITE_MAX_DURATION,
                                wait_for_first=False,
                            )
                        except ChandlerWriteError as err:
                            _LOGGER.warning(
                                "Post-poll write %s failed: %s", payload, err
                            )
            finally:
                await self._close_session(graceful=True)

            self._data = snapshot
            if self._data_callback:
                self._data_callback(snapshot)
            return snapshot

    async def async_write_keys(
        self,
        payload: dict[str, Any],
        ble_device: BLEDevice | None = None,
    ) -> DeviceData:
        """Open a short session, drain initial burst, write payload, and close.

        Draining the initial burst before writing prevents half-duplex
        congestion while the valve is streaming its connect dump, and ensures
        the ACK we wait on strictly belongs to our write.
        """
        # Validate framing before even touching Bluetooth.
        protocol.build_data_packet(payload)

        async with self._session_lock:
            if ble_device is not None:
                self._ble_device = ble_device

            snapshot = DeviceData()
            await self._open_session(snapshot)
            try:
                await self._drain_packets(
                    snapshot,
                    quiet_timeout=POLL_BURST_QUIET_TIMEOUT,
                    initial_timeout=POLL_INITIAL_DATA_TIMEOUT,
                    max_duration=POLL_MAX_DRAIN_DURATION,
                    wait_for_first=True,
                )
                self._preserve_identity_fields(snapshot)

                await self._write_in_session(payload, snapshot)
                await self._drain_packets(
                    snapshot,
                    quiet_timeout=POST_WRITE_QUIET_TIMEOUT,
                    initial_timeout=POST_WRITE_QUIET_TIMEOUT,
                    max_duration=POST_WRITE_MAX_DURATION,
                    wait_for_first=False,
                )
            finally:
                await self._close_session(graceful=True)

            self._data = snapshot
            if self._data_callback:
                self._data_callback(snapshot)
            return snapshot

    async def disconnect(self) -> None:
        """Release any active BLE session cleanly (called on unload)."""
        async with self._session_lock:
            await self._close_session(graceful=True)
