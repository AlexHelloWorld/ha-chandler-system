"""Constants for the Chandler Water System integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.button import ButtonEntityDescription
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfMass,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.util import dt as dt_util

DOMAIN = "chandler_system"

# Bluetooth UUIDs
# Advertised service UUID (for discovery)
SERVICE_UUID_ADVERTISED = "8d53dc1d-1db7-4cd3-868b-8a527460aa84"
# GATT service UUID (for communication)
SERVICE_UUID_GATT = "a725458c-bee1-4d2e-9555-edf5a8082303"
# Characteristic UUIDs
CHAR_UUID_READ = "a725458c-bee2-4d2e-9555-edf5a8082303"
CHAR_UUID_WRITE = "a725458c-bee3-4d2e-9555-edf5a8082303"
# Manufacturer ID (Chandler Systems, Inc.)
MANUFACTURER_ID = 1850

# Configuration & option keys
CONF_DEVICE_ADDRESS = "device_address"
CONF_DEVICE_NAME = "device_name"
CONF_AUTH_TOKEN = "auth_token"
CONF_DISCOVERED_DEVICE = "discovered_device"
CONF_POLL_INTERVAL = "poll_interval"
CONF_ACTIVE_FLOW_POLL_INTERVAL = "active_flow_poll_interval"
CONF_AUTO_SYNC_CLOCK = "auto_sync_clock"
CONF_CLOCK_SYNC_THRESHOLD = "clock_sync_threshold"

# Default values
DEFAULT_NAME = "Chandler Water System"
DEFAULT_POLL_INTERVAL = 60  # seconds (normal idle polling)
DEFAULT_ACTIVE_FLOW_POLL_INTERVAL = 15  # seconds (faster polling while flow > 0)
DEFAULT_AUTO_SYNC_CLOCK = True
DEFAULT_CLOCK_SYNC_THRESHOLD = 120  # seconds
MIN_POLL_INTERVAL = 15
MAX_POLL_INTERVAL = 3600
MIN_ACTIVE_FLOW_POLL_INTERVAL = 10
MAX_ACTIVE_FLOW_POLL_INTERVAL = 300
MIN_CLOCK_SYNC_THRESHOLD = 30
MAX_CLOCK_SYNC_THRESHOLD = 3600
# Backwards-compatible alias
DEFAULT_SCAN_INTERVAL = DEFAULT_POLL_INTERVAL
CONNECTION_TIMEOUT = 30.0  # seconds

# Firmware C6.19+ transmits shgs/shgt/shgr in quarter-gallons instead of hundredths.
FIRMWARE_QUARTER_GALLON_VERSION = 619


@dataclass(frozen=True, kw_only=True)
class ChandlerSensorEntityDescription(SensorEntityDescription):
    """Describes a Chandler sensor entity."""

    value_fn: Callable[[Any], Any] | None = None
    attributes_fn: Callable[[Any], dict[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class ChandlerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Chandler binary sensor entity."""

    value_fn: Callable[[Any], bool | None]


@dataclass(frozen=True, kw_only=True)
class ChandlerButtonEntityDescription(ButtonEntityDescription):
    """Describes a Chandler button entity."""

    # Built when pressed, so a payload can depend on the moment it is sent.
    # None means the button triggers a coordinator action rather than a raw write.
    press_payload: Callable[[Any], dict[str, Any] | None] | None = None
    action: str | None = None


@dataclass(frozen=True, kw_only=True)
class ChandlerNumberEntityDescription(NumberEntityDescription):
    """Describes a Chandler number entity."""

    value_fn: Callable[[Any], float | None]
    # API key written when the value is set
    write_key: str
    # Multiplier converting the displayed value to the device's raw units
    write_scale: float = 1.0


@dataclass(frozen=True, kw_only=True)
class ChandlerSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Chandler switch entity."""

    value_fn: Callable[[Any], bool | None]
    write_key: str


# Sensor keys
SENSOR_WATER_USED_TODAY = "water_used_today"
SENSOR_AVERAGE_WATER_USED = "average_water_used"
SENSOR_TOTAL_GALLONS_REMAINING = "total_gallons_remaining"
SENSOR_PEAK_FLOW_DAILY = "peak_flow_daily"
SENSOR_PRESENT_FLOW = "present_flow"
SENSOR_DAYS_UNTIL_REGEN = "days_until_regen"
SENSOR_DAYS_SINCE_LAST_REGEN = "days_since_last_regen"
SENSOR_GALLONS_SINCE_LAST_REGEN = "gallons_since_last_regen"
SENSOR_SALT_LEVEL = "salt_level"
SENSOR_SALT_REMAINING = "salt_remaining"
SENSOR_SALT_CAPACITY = "salt_capacity"
SENSOR_BATTERY_LEVEL = "battery_level"
SENSOR_REGEN_COUNTER = "regen_counter"
SENSOR_TOTAL_GALLONS = "total_gallons"
SENSOR_DAYS_IN_OPERATION = "days_in_operation"
SENSOR_VALVE_ERROR = "valve_error"
SENSOR_RESERVE_CAPACITY_GALLONS = "reserve_capacity_gallons"
SENSOR_REGEN_STATE = "regen_state"
SENSOR_REGEN_STAGE = "regen_stage"
SENSOR_REGEN_POSITION = "regen_position"
SENSOR_REGEN_STEP_REMAINING = "regen_step_remaining"
SENSOR_REGEN_TOTAL_REMAINING = "regen_total_remaining"
SENSOR_BRINE_SOAK_REMAINING = "brine_soak_remaining"
SENSOR_CYCLE_POSITION_TIMES = "cycle_position_times"
SENSOR_REGEN_COUNTER_RESETTABLE = "regen_counter_resettable"
SENSOR_TOTAL_GALLONS_RESETTABLE = "total_gallons_resettable"
SENSOR_LAST_ERROR = "last_error"
SENSOR_GALLONS_BETWEEN_REGENS = "gallons_between_regens"
SENSOR_DAILY_GALLONS_HISTORY = "daily_gallons_history"
SENSOR_PEAK_FLOW_HISTORY = "peak_flow_history"
SENSOR_DEVICE_TIME = "device_time"
SENSOR_CLOCK_DRIFT = "clock_drift"
SENSOR_FIRMWARE_VERSION = "firmware_version"
SENSOR_VALVE_TYPE = "valve_type"

# Binary sensor keys
BINARY_SENSOR_REGEN_ACTIVE = "regen_active_state"
BINARY_SENSOR_REGEN_MOTOR = "regen_motor_moving"
BINARY_SENSOR_IN_AERATION = "in_aeration"
BINARY_SENSOR_BRINE_SOAK = "in_brine_soak"
BINARY_SENSOR_SALT_LOW = "salt_low_state"
BINARY_SENSOR_VALVE_ERROR = "valve_error_state"

# Button keys
BUTTON_REFRESH = "refresh_now"
BUTTON_REGEN_NOW = "regen_now"
BUTTON_REGEN_LATER = "regen_later"
BUTTON_FIND_HOME = "find_home"
BUTTON_SYNC_CLOCK = "sync_clock"
BUTTON_REFILL_SALT = "refill_salt_tank"
BUTTON_RESET_REGEN_COUNTER = "reset_regen_counter"
BUTTON_RESET_GALLONS_COUNTER = "reset_gallons_counter"

# Number keys
NUMBER_WATER_HARDNESS = "water_hardness"
NUMBER_DAY_OVERRIDE = "day_override"
NUMBER_CURRENT_DAY_OVERRIDE = "current_day_override"
NUMBER_REGEN_DAY_OVERRIDE = "regen_day_override"
NUMBER_REGEN_TIME_HOUR = "regen_time_hour"
NUMBER_RESERVE_CAPACITY = "reserve_capacity"
NUMBER_TOTAL_GRAINS = "total_grains_capacity"
NUMBER_SALT_REMAINING = "set_salt_remaining"
NUMBER_PREFILL_DURATION = "prefill_duration"
NUMBER_AERATION_DAYS = "aeration_days"
NUMBER_CHLORINE_PULSES = "chlorine_pulses"

# Switch keys
SWITCH_AUTO_RESERVE = "auto_reserve_mode"
SWITCH_DISPLAY_OFF = "display_off"
SWITCH_PREFILL_ENABLED = "prefill_enabled"


ERROR_MAP: dict[int, str] = {
    # 0 is reported as "No Error" rather than listed here.
    2: "Lost Home",
    3: "No Encoder Slots (Normal Current)",
    4: "Can't Find Home",
    5: "No Encoder Slots (High Current)",
    6: "No Encoder Slots (No Current)",
    7: "TWEDO Motor Timeout",
    192: "Regen Aborted (On Battery)",
}

REGEN_STATE_MAP: dict[int, str] = {
    0: "Idle",
    1: "Moving To Next Position",
    2: "Moving To Final Position",
    3: "TWEDO Waiting For Motor State",
    4: "Waiting For TWEDO State",
    5: "Waiting In Position",
    6: "Moving To Service",
    7: "Moving To Bypass",
    8: "In Bypass",
    9: "Moving To Brine Soak",
    10: "Waiting In Brine Soak",
    11: "Moving To Creep Position",
    12: "Creeping To Position",
}

VALVE_TYPE_MAP: dict[int, str] = {
    1: "Metered Softener",
    2: "Timeclock Softener",
    3: "Metered Softener",
    4: "Backwashing Filter",
    5: "Backwashing Filter",
    6: "HydroxR Filter",
    7: "ReactR Filter",
    8: "Ultra Filter",
    9: "Aeration Filter",
    10: "Aeration Filter",
    11: "Aeration Filter",
    12: "Aeration Filter",
    13: "Aeration Filter",
    14: "Aeration Filter",
    15: "Aeration Filter",
    16: "Aeration Filter",
    17: "Metered Softener",
    18: "Backwashing Filter",
    19: "Metered Softener",
    20: "Backwashing Filter",
    21: "Metered Softener",
    22: "Backwashing Filter",
    23: "Aeration Filter",
    24: "Aeration Filter",
    25: "Aeration Filter",
    26: "Backwashing Filter",
    27: "Backwashing Filter",
}

VALVE_SERIES_MAP: dict[int, str] = {
    2: "Series 2 (D12)",
    3: "Series 3 (D15)",
    4: "Series 4 (CS125)",
    5: "Series 5 (CS150)",
    6: "Series 6 (CS121)",
}

# Units the device uses for the remaining regeneration step time (drtt).
REGEN_TIME_TYPE_SECONDS = 0
REGEN_TIME_TYPE_MINUTES = 1
REGEN_TIME_TYPE_SALT_POUNDS = 2

REGEN_TIME_TYPE_MAP: dict[int, str] = {
    REGEN_TIME_TYPE_SECONDS: "seconds",
    REGEN_TIME_TYPE_MINUTES: "minutes",
    REGEN_TIME_TYPE_SALT_POUNDS: "salt_pounds",
}


def get_error_text(error_code: int | None) -> str:
    """Convert error code to human-readable text."""
    # Device doesn't send gve field when there's no error
    if error_code is None or error_code == 0:
        return "No Error"

    return ERROR_MAP.get(error_code, f"Unknown Error ({error_code})")


# Value extraction helper functions
def _hundredths(value: int | None) -> float | None:
    """Convert 1/100 value to actual (e.g., 1/100 gallons -> gallons)."""
    return value / 100.0 if value is not None else None


def _tenths(value: int | None) -> float | None:
    """Convert 1/10 value to actual (e.g., 1/10 pounds -> pounds)."""
    return value / 10.0 if value is not None else None


def _thousands(value: int | None) -> int | None:
    """Multiply by 1000 (e.g., 1000 GPG -> grains)."""
    return value * 1000 if value is not None else None


def _first(values: list[float]) -> float | None:
    """Take the newest entry from a graph array."""
    return values[0] if values else None


def clock_payload() -> dict[str, int]:
    """Build the write that sets the valve's clock to local time."""
    now = dt_util.now()
    return {"dh": now.hour, "dm": now.minute, "ds": now.second}


def _refill_salt_payload(data: Any) -> dict[str, int] | None:
    """Build a write that resets remaining salt to the tank's total capacity."""
    if data is None or not data.brine_tank_total_salt:
        return None
    return {"dbtr": int(data.brine_tank_total_salt) * 10}


def _format_device_time(data: Any) -> str | None:
    """Render the valve's own clock."""
    hours, minutes = data.time_hours, data.time_minutes
    if hours is None or minutes is None:
        return None
    if data.time_seconds is not None:
        return f"{hours:02d}:{minutes:02d}:{data.time_seconds:02d}"
    return f"{hours:02d}:{minutes:02d}"


def _clock_drift_seconds(data: Any) -> int | None:
    """Signed seconds the valve's clock is ahead of local time.

    Compares the reported clock against the timestamp captured when those
    packets arrived so polling intervals do not appear as fake drift.
    """
    hours, minutes = data.time_hours, data.time_minutes
    if hours is None or minutes is None:
        return None

    reference = data.clock_sample_time or dt_util.now()
    if data.time_seconds is not None:
        device = hours * 3600 + minutes * 60 + data.time_seconds
        local = reference.hour * 3600 + reference.minute * 60 + reference.second
    else:
        device = hours * 3600 + minutes * 60
        local = reference.hour * 3600 + reference.minute * 60

    # Wrapped into plus or minus twelve hours so readings taken either side
    # of midnight do not come out as most of a day.
    return (device - local + 43200) % 86400 - 43200


def _format_cycle_times(data: Any) -> str | None:
    """Render configured cycle position durations (skipping index 0 service)."""
    times = data.cycle_position_times
    if not times:
        return None
    steps = times[1:] if len(times) > 1 else times
    return ", ".join(str(t) for t in steps)


# Define all sensors based on the API guide
SENSOR_DESCRIPTIONS: tuple[ChandlerSensorEntityDescription, ...] = (
    # Water usage sensors (SensorDeviceClass.WATER enables HA Energy Dashboard)
    ChandlerSensorEntityDescription(
        key=SENSOR_WATER_USED_TODAY,
        translation_key=SENSOR_WATER_USED_TODAY,
        name="Water Used Today",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        icon="mdi:water",
        value_fn=lambda d: _hundredths(d.water_used_today),
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_AVERAGE_WATER_USED,
        translation_key=SENSOR_AVERAGE_WATER_USED,
        name="Average Daily Water Usage",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:water-outline",
        value_fn=lambda d: _hundredths(d.average_water_used),
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_TOTAL_GALLONS_REMAINING,
        translation_key=SENSOR_TOTAL_GALLONS_REMAINING,
        name="Treated Water Remaining",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:water-check",
        value_fn=lambda d: _hundredths(d.total_gallons_remaining),
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_TOTAL_GALLONS,
        translation_key=SENSOR_TOTAL_GALLONS,
        name="Total Gallons Processed",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        icon="mdi:counter",
        value_fn=lambda d: d.total_gallons_value,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_GALLONS_SINCE_LAST_REGEN,
        translation_key=SENSOR_GALLONS_SINCE_LAST_REGEN,
        name="Gallons Since Last Regeneration",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        icon="mdi:water-sync",
        value_fn=lambda d: d.gallons_since_last_regen_value,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_TOTAL_GALLONS_RESETTABLE,
        translation_key=SENSOR_TOTAL_GALLONS_RESETTABLE,
        name="Gallons Since Reset",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        icon="mdi:counter",
        value_fn=lambda d: d.total_gallons_resettable_value,
    ),

    # Flow sensors
    ChandlerSensorEntityDescription(
        key=SENSOR_PRESENT_FLOW,
        translation_key=SENSOR_PRESENT_FLOW,
        name="Current Flow Rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        suggested_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:water-pump",
        value_fn=lambda d: d.present_flow_gpm,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_PEAK_FLOW_DAILY,
        translation_key=SENSOR_PEAK_FLOW_DAILY,
        name="Peak Flow Today",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        suggested_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:speedometer",
        value_fn=lambda d: _hundredths(d.peak_flow_daily),
    ),

    # Regeneration sensors
    ChandlerSensorEntityDescription(
        key=SENSOR_DAYS_UNTIL_REGEN,
        translation_key=SENSOR_DAYS_UNTIL_REGEN,
        name="Days Until Regeneration",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:calendar-clock",
        value_fn=lambda d: d.days_until_regen,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_DAYS_SINCE_LAST_REGEN,
        translation_key=SENSOR_DAYS_SINCE_LAST_REGEN,
        name="Days Since Last Regeneration",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:calendar-check",
        value_fn=lambda d: d.days_since_last_regen,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_REGEN_COUNTER,
        translation_key=SENSOR_REGEN_COUNTER,
        name="Total Regeneration Cycles",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:refresh",
        value_fn=lambda d: d.regen_counter,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_REGEN_COUNTER_RESETTABLE,
        translation_key=SENSOR_REGEN_COUNTER_RESETTABLE,
        name="Regenerations Since Reset",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:refresh",
        value_fn=lambda d: d.regen_counter_resettable,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_REGEN_STATE,
        translation_key=SENSOR_REGEN_STATE,
        name="Regeneration State",
        device_class=SensorDeviceClass.ENUM,
        options=list(REGEN_STATE_MAP.values()),
        icon="mdi:state-machine",
        value_fn=lambda d: d.regen_state_text,
        attributes_fn=lambda d: {"raw_state": d.regen_state},
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_REGEN_STAGE,
        translation_key=SENSOR_REGEN_STAGE,
        name="Regeneration Stage",
        icon="mdi:progress-clock",
        value_fn=lambda d: d.regen_stage_text,
        attributes_fn=lambda d: {
            "current_position": d.regen_current_position,
            "total_positions": d.num_regen_positions,
            "in_aeration": d.regen_in_aeration,
            "in_brine_soak": d.regen_soak_mode,
            "cycle_position_times": d.cycle_position_times,
        },
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_REGEN_POSITION,
        translation_key=SENSOR_REGEN_POSITION,
        name="Regeneration Position",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:valve",
        value_fn=lambda d: d.regen_current_position,
        attributes_fn=lambda d: {"total_positions": d.num_regen_positions},
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_REGEN_STEP_REMAINING,
        translation_key=SENSOR_REGEN_STEP_REMAINING,
        name="Regeneration Step Time Remaining",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:timer-sand",
        value_fn=lambda d: d.regen_step_remaining_minutes,
        attributes_fn=lambda d: {
            "raw_value": d.regen_time_remaining,
            "unit_type": REGEN_TIME_TYPE_MAP.get(d.regen_time_type)
            if d.regen_time_type is not None
            else None,
            "seconds_remaining": d.regen_step_remaining_seconds,
        },
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_REGEN_TOTAL_REMAINING,
        translation_key=SENSOR_REGEN_TOTAL_REMAINING,
        name="Regeneration Total Time Remaining",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:timer",
        value_fn=lambda d: d.regen_total_remaining_minutes,
        attributes_fn=lambda d: {
            "cycle_position_times": d.cycle_position_times,
        },
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_BRINE_SOAK_REMAINING,
        translation_key=SENSOR_BRINE_SOAK_REMAINING,
        name="Brine Soak Time Remaining",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer-outline",
        value_fn=lambda d: d.regen_soak_timer,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_CYCLE_POSITION_TIMES,
        translation_key=SENSOR_CYCLE_POSITION_TIMES,
        name="Cycle Position Times",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:format-list-numbered",
        value_fn=_format_cycle_times,
        attributes_fn=lambda d: {"positions": d.cycle_position_times},
    ),

    # Salt sensors (kept as sensors for HA long-term statistics)
    ChandlerSensorEntityDescription(
        key=SENSOR_SALT_LEVEL,
        translation_key=SENSOR_SALT_LEVEL,
        name="Salt Level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:shaker-outline",
        suggested_display_precision=1,
        value_fn=lambda d: d.salt_level_percent,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_SALT_REMAINING,
        translation_key=SENSOR_SALT_REMAINING,
        name="Salt Remaining",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.POUNDS,
        suggested_unit_of_measurement=UnitOfMass.POUNDS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:shaker",
        value_fn=lambda d: _tenths(d.brine_tank_remaining_salt),
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_SALT_CAPACITY,
        translation_key=SENSOR_SALT_CAPACITY,
        name="Salt Tank Capacity",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.POUNDS,
        suggested_unit_of_measurement=UnitOfMass.POUNDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:shaker-outline",
        value_fn=lambda d: d.brine_tank_total_salt,
    ),

    # Capacity sensor
    ChandlerSensorEntityDescription(
        key=SENSOR_RESERVE_CAPACITY_GALLONS,
        translation_key=SENSOR_RESERVE_CAPACITY_GALLONS,
        name="Reserve Capacity Gallons",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:storage-tank",
        value_fn=lambda d: _hundredths(d.reserve_capacity_gallons),
    ),

    # System & diagnostics
    ChandlerSensorEntityDescription(
        key=SENSOR_BATTERY_LEVEL,
        translation_key=SENSOR_BATTERY_LEVEL,
        name="Battery Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:battery",
        value_fn=lambda d: d.battery_level_volts,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_DAYS_IN_OPERATION,
        translation_key=SENSOR_DAYS_IN_OPERATION,
        name="Days In Operation",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:calendar-range",
        value_fn=lambda d: d.days_in_operation,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_VALVE_ERROR,
        translation_key=SENSOR_VALVE_ERROR,
        name="Valve Error Detail",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert",
        value_fn=lambda d: get_error_text(d.valve_error),
        attributes_fn=lambda d: {
            "error_code": d.valve_error or 0,
            "valve_status": d.valve_status,
            "bypass_state": d.bypass_state,
            "water_state": d.water_state,
        },
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_LAST_ERROR,
        translation_key=SENSOR_LAST_ERROR,
        name="Last Error",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert-box",
        value_fn=lambda d: (
            d.last_error.error_text if d.last_error else "No Error"
        ),
        attributes_fn=lambda d: {
            "error_log": [entry.as_dict() for entry in d.error_log]
        },
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_DEVICE_TIME,
        translation_key=SENSOR_DEVICE_TIME,
        name="Device Time",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:clock-outline",
        value_fn=_format_device_time,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_CLOCK_DRIFT,
        translation_key=SENSOR_CLOCK_DRIFT,
        name="Clock Drift",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:clock-alert-outline",
        value_fn=_clock_drift_seconds,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_FIRMWARE_VERSION,
        translation_key=SENSOR_FIRMWARE_VERSION,
        name="Firmware Version",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:chip",
        value_fn=lambda d: d.firmware_version_text,
        attributes_fn=lambda d: {
            "raw_firmware": d.firmware_version,
            "history_gallon_divisor": d.history_gallon_divisor,
            "serial_number": d.serial_number,
            "valve_series": d.valve_series_text,
        },
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_VALVE_TYPE,
        translation_key=SENSOR_VALVE_TYPE,
        name="Valve Type",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:pipe-valve",
        value_fn=lambda d: d.valve_type_text,
        attributes_fn=lambda d: {
            "raw_valve_type": d.valve_type,
            "valve_series": d.valve_series_text,
        },
    ),

    # History graphs
    ChandlerSensorEntityDescription(
        key=SENSOR_GALLONS_BETWEEN_REGENS,
        translation_key=SENSOR_GALLONS_BETWEEN_REGENS,
        name="Gallons Used Last Regeneration Cycle",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:chart-bar",
        value_fn=lambda d: _first(d.gallons_between_regens),
        attributes_fn=lambda d: {"history": d.gallons_between_regens},
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_DAILY_GALLONS_HISTORY,
        translation_key=SENSOR_DAILY_GALLONS_HISTORY,
        name="Gallons Used Yesterday",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:chart-bar",
        value_fn=lambda d: _first(d.daily_gallons_history),
        attributes_fn=lambda d: {"history": d.daily_gallons_history},
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_PEAK_FLOW_HISTORY,
        translation_key=SENSOR_PEAK_FLOW_HISTORY,
        name="Peak Flow Yesterday",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        suggested_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:chart-line",
        value_fn=lambda d: _first(d.peak_flow_history),
        attributes_fn=lambda d: {"history": d.peak_flow_history},
    ),
)


BINARY_SENSOR_DESCRIPTIONS: tuple[ChandlerBinarySensorEntityDescription, ...] = (
    ChandlerBinarySensorEntityDescription(
        key=BINARY_SENSOR_REGEN_ACTIVE,
        translation_key=BINARY_SENSOR_REGEN_ACTIVE,
        name="Regeneration Active",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:refresh-circle",
        value_fn=lambda d: d.regen_active,
    ),
    ChandlerBinarySensorEntityDescription(
        key=BINARY_SENSOR_REGEN_MOTOR,
        translation_key=BINARY_SENSOR_REGEN_MOTOR,
        name="Regeneration Motor Moving",
        device_class=BinarySensorDeviceClass.MOVING,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:cog-sync",
        value_fn=lambda d: d.regen_motor_in_progress,
    ),
    ChandlerBinarySensorEntityDescription(
        key=BINARY_SENSOR_SALT_LOW,
        translation_key=BINARY_SENSOR_SALT_LOW,
        name="Salt Low",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:shaker-outline",
        value_fn=lambda d: d.salt_low,
    ),
    ChandlerBinarySensorEntityDescription(
        key=BINARY_SENSOR_VALVE_ERROR,
        translation_key=BINARY_SENSOR_VALVE_ERROR,
        name="Valve Error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert",
        value_fn=lambda d: d.has_valve_error,
    ),
    ChandlerBinarySensorEntityDescription(
        key=BINARY_SENSOR_IN_AERATION,
        translation_key=BINARY_SENSOR_IN_AERATION,
        name="In Aeration",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:air-filter",
        value_fn=lambda d: d.regen_in_aeration,
    ),
    ChandlerBinarySensorEntityDescription(
        key=BINARY_SENSOR_BRINE_SOAK,
        translation_key=BINARY_SENSOR_BRINE_SOAK,
        name="In Brine Soak",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:water-percent",
        value_fn=lambda d: d.regen_soak_mode,
    ),
)


BUTTON_DESCRIPTIONS: tuple[ChandlerButtonEntityDescription, ...] = (
    ChandlerButtonEntityDescription(
        key=BUTTON_REFRESH,
        translation_key=BUTTON_REFRESH,
        name="Refresh Now",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:refresh",
        action="refresh",
    ),
    ChandlerButtonEntityDescription(
        key=BUTTON_REGEN_NOW,
        translation_key=BUTTON_REGEN_NOW,
        name="Start Regeneration Now",
        icon="mdi:play-circle",
        press_payload=lambda _d: {"grn": 1},
    ),
    ChandlerButtonEntityDescription(
        key=BUTTON_REGEN_LATER,
        translation_key=BUTTON_REGEN_LATER,
        name="Schedule Regeneration",
        icon="mdi:clock-plus",
        press_payload=lambda _d: {"grl": 1},
    ),
    ChandlerButtonEntityDescription(
        key=BUTTON_FIND_HOME,
        translation_key=BUTTON_FIND_HOME,
        name="Find Home",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:home-search",
        press_payload=lambda _d: {"gfh": 1},
    ),
    ChandlerButtonEntityDescription(
        key=BUTTON_SYNC_CLOCK,
        translation_key=BUTTON_SYNC_CLOCK,
        name="Sync Clock",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:clock-check",
        press_payload=lambda _d: clock_payload(),
    ),
    ChandlerButtonEntityDescription(
        key=BUTTON_REFILL_SALT,
        translation_key=BUTTON_REFILL_SALT,
        name="Refill Salt Tank",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:shaker-outline",
        press_payload=_refill_salt_payload,
    ),
    ChandlerButtonEntityDescription(
        key=BUTTON_RESET_REGEN_COUNTER,
        translation_key=BUTTON_RESET_REGEN_COUNTER,
        name="Reset Regeneration Counter",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:counter",
        press_payload=lambda _d: {"shrr": 0},
    ),
    ChandlerButtonEntityDescription(
        key=BUTTON_RESET_GALLONS_COUNTER,
        translation_key=BUTTON_RESET_GALLONS_COUNTER,
        name="Reset Gallons Counter",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:water-remove",
        press_payload=lambda _d: {"shgr": 0},
    ),
)


NUMBER_DESCRIPTIONS: tuple[ChandlerNumberEntityDescription, ...] = (
    ChandlerNumberEntityDescription(
        key=NUMBER_WATER_HARDNESS,
        translation_key=NUMBER_WATER_HARDNESS,
        name="Water Hardness",
        native_unit_of_measurement="GPG",
        native_min_value=0,
        native_max_value=99,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        icon="mdi:water-opacity",
        value_fn=lambda d: d.water_hardness,
        write_key="dwh",
    ),
    ChandlerNumberEntityDescription(
        key=NUMBER_DAY_OVERRIDE,
        translation_key=NUMBER_DAY_OVERRIDE,
        name="Day Override",
        native_unit_of_measurement=UnitOfTime.DAYS,
        native_min_value=0,
        native_max_value=29,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        icon="mdi:calendar-sync",
        value_fn=lambda d: d.day_override,
        write_key="ddo",
    ),
    ChandlerNumberEntityDescription(
        key=NUMBER_CURRENT_DAY_OVERRIDE,
        translation_key=NUMBER_CURRENT_DAY_OVERRIDE,
        name="Current Day Override",
        native_unit_of_measurement=UnitOfTime.DAYS,
        native_min_value=0,
        native_max_value=29,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        icon="mdi:calendar-today",
        value_fn=lambda d: d.current_day_override,
        write_key="dcdo",
    ),
    ChandlerNumberEntityDescription(
        key=NUMBER_REGEN_DAY_OVERRIDE,
        translation_key=NUMBER_REGEN_DAY_OVERRIDE,
        name="Regen Day Override",
        native_unit_of_measurement=UnitOfTime.DAYS,
        native_min_value=0,
        native_max_value=29,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        icon="mdi:calendar-refresh",
        value_fn=lambda d: d.regen_day_override,
        write_key="asr",
    ),
    ChandlerNumberEntityDescription(
        key=NUMBER_REGEN_TIME_HOUR,
        translation_key=NUMBER_REGEN_TIME_HOUR,
        name="Regeneration Hour",
        native_unit_of_measurement=UnitOfTime.HOURS,
        native_min_value=0,
        native_max_value=23,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        icon="mdi:clock-outline",
        value_fn=lambda d: d.regen_time_hours,
        write_key="drth",
    ),
    ChandlerNumberEntityDescription(
        key=NUMBER_RESERVE_CAPACITY,
        translation_key=NUMBER_RESERVE_CAPACITY,
        name="Reserve Capacity",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=49,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        icon="mdi:storage-tank",
        value_fn=lambda d: d.reserve_capacity,
        write_key="asrc",
    ),
    ChandlerNumberEntityDescription(
        key=NUMBER_TOTAL_GRAINS,
        translation_key=NUMBER_TOTAL_GRAINS,
        name="Total Grains Capacity",
        native_unit_of_measurement="grains",
        # The device stores this in thousands of grains (0-399).
        native_min_value=0,
        native_max_value=399_000,
        native_step=1000,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        icon="mdi:gauge",
        value_fn=lambda d: _thousands(d.total_grains_capacity),
        write_key="astg",
        write_scale=1 / 1000,
    ),
    ChandlerNumberEntityDescription(
        key=NUMBER_SALT_REMAINING,
        translation_key=NUMBER_SALT_REMAINING,
        name="Salt Remaining Setting",
        native_unit_of_measurement=UnitOfMass.POUNDS,
        native_min_value=0,
        native_max_value=400,
        native_step=1,
        device_class=NumberDeviceClass.WEIGHT,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        icon="mdi:shaker",
        value_fn=lambda d: _tenths(d.brine_tank_remaining_salt),
        write_key="dbtr",
        write_scale=10,
    ),
    ChandlerNumberEntityDescription(
        key=NUMBER_PREFILL_DURATION,
        translation_key=NUMBER_PREFILL_DURATION,
        name="Brine Prefill Duration",
        native_unit_of_measurement=UnitOfTime.HOURS,
        native_min_value=1,
        native_max_value=4,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        icon="mdi:timer-cog-outline",
        value_fn=lambda d: d.prefill_duration,
        write_key="dpd",
    ),
    ChandlerNumberEntityDescription(
        key=NUMBER_AERATION_DAYS,
        translation_key=NUMBER_AERATION_DAYS,
        name="Aeration Days",
        native_unit_of_measurement=UnitOfTime.DAYS,
        native_min_value=0,
        native_max_value=9,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        mode=NumberMode.BOX,
        icon="mdi:air-filter",
        value_fn=lambda d: d.aeration_days,
        write_key="asad",
    ),
    ChandlerNumberEntityDescription(
        key=NUMBER_CHLORINE_PULSES,
        translation_key=NUMBER_CHLORINE_PULSES,
        name="Chlorine Pulses",
        native_min_value=0,
        native_max_value=4,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        mode=NumberMode.BOX,
        icon="mdi:flask-outline",
        value_fn=lambda d: d.chlorine_pulses,
        write_key="ascp",
    ),
)


SWITCH_DESCRIPTIONS: tuple[ChandlerSwitchEntityDescription, ...] = (
    ChandlerSwitchEntityDescription(
        key=SWITCH_AUTO_RESERVE,
        translation_key=SWITCH_AUTO_RESERVE,
        name="Auto Reserve Mode",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:auto-mode",
        value_fn=lambda d: d.auto_reserve_mode,
        write_key="asar",
    ),
    ChandlerSwitchEntityDescription(
        key=SWITCH_PREFILL_ENABLED,
        translation_key=SWITCH_PREFILL_ENABLED,
        name="Brine Prefill",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:water-plus-outline",
        value_fn=lambda d: d.prefill_enabled,
        write_key="dpe",
    ),
    ChandlerSwitchEntityDescription(
        key=SWITCH_DISPLAY_OFF,
        translation_key=SWITCH_DISPLAY_OFF,
        name="Display Off",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:monitor-off",
        value_fn=lambda d: d.display_off,
        write_key="asdo",
    ),
)
