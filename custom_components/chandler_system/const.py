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
    UnitOfTime,
    UnitOfVolume,
)

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

# Configuration keys
CONF_DEVICE_ADDRESS = "device_address"
CONF_DEVICE_NAME = "device_name"
CONF_AUTH_TOKEN = "auth_token"
CONF_DISCOVERED_DEVICE = "discovered_device"

# Default values
DEFAULT_NAME = "Chandler Water System"
DEFAULT_SCAN_INTERVAL = 60  # seconds
CONNECTION_TIMEOUT = 30.0  # seconds


@dataclass(frozen=True, kw_only=True)
class ChandlerSensorEntityDescription(SensorEntityDescription):
    """Describes a Chandler sensor entity.

    Extends the base SensorEntityDescription to add custom fields
    for value extraction and transformation.
    """

    # Function to extract value from DeviceData
    value_fn: Callable[[Any], Any] | None = None
    # Whether the raw value needs to be divided (for hundredths values)
    divisor: float | None = None
    # Function producing extra state attributes from DeviceData
    attributes_fn: Callable[[Any], dict[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class ChandlerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Chandler binary sensor entity."""

    value_fn: Callable[[Any], bool | None]


@dataclass(frozen=True, kw_only=True)
class ChandlerButtonEntityDescription(ButtonEntityDescription):
    """Describes a Chandler button entity."""

    # The exact JSON payload written to the device when pressed
    press_payload: dict[str, Any]


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


# Sensor keys - matching API guide field names
SENSOR_WATER_USED_TODAY = "water_used_today"
SENSOR_AVERAGE_WATER_USED = "average_water_used"
SENSOR_TOTAL_GALLONS_REMAINING = "total_gallons_remaining"
SENSOR_PEAK_FLOW_DAILY = "peak_flow_daily"
SENSOR_PRESENT_FLOW = "present_flow"
SENSOR_WATER_HARDNESS = "water_hardness"
SENSOR_DAYS_UNTIL_REGEN = "days_until_regen"
SENSOR_DAYS_SINCE_LAST_REGEN = "days_since_last_regen"
SENSOR_GALLONS_SINCE_LAST_REGEN = "gallons_since_last_regen"
SENSOR_SALT_LEVEL = "salt_level"
SENSOR_SALT_REMAINING = "salt_remaining"
SENSOR_BATTERY_LEVEL = "battery_level"
SENSOR_REGEN_COUNTER = "regen_counter"
SENSOR_TOTAL_GALLONS = "total_gallons"
SENSOR_DAYS_IN_OPERATION = "days_in_operation"
SENSOR_SALT_LOW = "salt_low"
SENSOR_REGEN_ACTIVE = "regen_active"
SENSOR_VALVE_ERROR = "valve_error"
SENSOR_RESERVE_CAPACITY_GALLONS = "reserve_capacity_gallons"
SENSOR_TOTAL_GRAINS_CAPACITY = "total_grains_capacity"
SENSOR_REGEN_STATE = "regen_state"
SENSOR_REGEN_POSITION = "regen_position"
SENSOR_REGEN_STEP_REMAINING = "regen_step_remaining"
SENSOR_BRINE_SOAK_REMAINING = "brine_soak_remaining"
SENSOR_REGEN_COUNTER_RESETTABLE = "regen_counter_resettable"
SENSOR_TOTAL_GALLONS_RESETTABLE = "total_gallons_resettable"
SENSOR_NEXT_REGEN_TIME = "next_regen_time"
SENSOR_LAST_ERROR = "last_error"
SENSOR_GALLONS_BETWEEN_REGENS = "gallons_between_regens"
SENSOR_DAILY_GALLONS_HISTORY = "daily_gallons_history"
SENSOR_PEAK_FLOW_HISTORY = "peak_flow_history"

# Binary sensor keys
BINARY_SENSOR_REGEN_ACTIVE = "regen_active_state"
BINARY_SENSOR_IN_AERATION = "in_aeration"
BINARY_SENSOR_BRINE_SOAK = "in_brine_soak"
BINARY_SENSOR_SALT_LOW = "salt_low_state"
BINARY_SENSOR_VALVE_ERROR = "valve_error_state"

# Button keys
BUTTON_REGEN_NOW = "regen_now"
BUTTON_REGEN_LATER = "regen_later"
BUTTON_FIND_HOME = "find_home"

# Number keys
NUMBER_WATER_HARDNESS = "set_water_hardness"
NUMBER_DAY_OVERRIDE = "set_day_override"
NUMBER_REGEN_TIME_HOUR = "set_regen_time_hour"
NUMBER_RESERVE_CAPACITY = "set_reserve_capacity"
NUMBER_TOTAL_GRAINS = "set_total_grains"
NUMBER_SALT_REMAINING = "set_salt_remaining"

# Switch keys
SWITCH_AUTO_RESERVE = "auto_reserve_mode"
SWITCH_DISPLAY_OFF = "display_off"


ERROR_MAP = {
    # 0 is reported as "No Error" rather than listed here.
    2: "Lost Home",
    3: "No Encoder Slots (Normal Current)",
    4: "Can't Find Home",
    5: "No Encoder Slots (High Current)",
    6: "No Encoder Slots (No Current)",
    7: "TWEDO Motor Timeout",
    192: "Regen Aborted (On Battery)",
}

REGEN_STATE_MAP = {
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

# Units the device uses for the remaining regeneration step time (drtt).
REGEN_TIME_TYPE_SECONDS = 0
REGEN_TIME_TYPE_MINUTES = 1
REGEN_TIME_TYPE_SALT_POUNDS = 2


def get_error_text(error_code: int | None) -> str:
    """Convert error code to human-readable text."""
    # Device doesn't send gve field when there's no error
    if error_code is None or error_code == 0:
        return "No Error"

    return ERROR_MAP.get(error_code, f"Unknown Error ({error_code})")


# Value extraction helper functions
def _hundredths(value: int | None) -> float | None:
    """Convert 1/100 value to actual (e.g., 1/100 gallons → gallons)."""
    return value / 100.0 if value is not None else None


def _hundredths_or_zero(value: int | None) -> float:
    """Convert 1/100 value to actual, defaulting to 0."""
    return value / 100.0 if value else 0.0


def _tenths(value: int | None) -> float | None:
    """Convert 1/10 value to actual (e.g., 1/10 pounds → pounds)."""
    return value / 10.0 if value is not None else None


def _thousands(value: int | None) -> int | None:
    """Multiply by 1000 (e.g., 1000 GPG → grains)."""
    return value * 1000 if value is not None else None


def _first(values: list[float]) -> float | None:
    """Take the newest entry from a graph array."""
    return values[0] if values else None


def _format_regen_hour(data: Any) -> str | None:
    """Render the scheduled regeneration hour as a clock time."""
    hour = data.regen_time_hours
    if hour is None:
        return None
    return f"{hour:02d}:00"


# Define all sensors based on the API guide
SENSOR_DESCRIPTIONS: tuple[ChandlerSensorEntityDescription, ...] = (
    # Water usage sensors
    ChandlerSensorEntityDescription(
        key=SENSOR_WATER_USED_TODAY,
        translation_key=SENSOR_WATER_USED_TODAY,
        name="Water Used Today",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:water",
        value_fn=lambda d: _hundredths(d.water_used_today),
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_AVERAGE_WATER_USED,
        translation_key=SENSOR_AVERAGE_WATER_USED,
        name="Average Daily Water Usage",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-outline",
        value_fn=lambda d: _hundredths(d.average_water_used),
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_TOTAL_GALLONS_REMAINING,
        translation_key=SENSOR_TOTAL_GALLONS_REMAINING,
        name="Treated Water Remaining",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-check",
        value_fn=lambda d: _hundredths(d.total_gallons_remaining),
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_TOTAL_GALLONS,
        translation_key=SENSOR_TOTAL_GALLONS,
        name="Total Gallons Processed",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
        value_fn=lambda d: _hundredths(d.total_gallons),
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_GALLONS_SINCE_LAST_REGEN,
        translation_key=SENSOR_GALLONS_SINCE_LAST_REGEN,
        name="Gallons Since Last Regeneration",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:water-sync",
        value_fn=lambda d: _hundredths(d.gallons_since_last_regen),
    ),

    # Flow sensors
    ChandlerSensorEntityDescription(
        key=SENSOR_PRESENT_FLOW,
        translation_key=SENSOR_PRESENT_FLOW,
        name="Current Flow Rate",
        native_unit_of_measurement="gal/min",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-pump",
        value_fn=lambda d: _hundredths_or_zero(d.present_flow),
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_PEAK_FLOW_DAILY,
        translation_key=SENSOR_PEAK_FLOW_DAILY,
        name="Peak Flow Today",
        native_unit_of_measurement="gal/min",
        state_class=SensorStateClass.MEASUREMENT,
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
    # Superseded by the binary sensor of the same name; kept so existing
    # dashboards and automations do not break.
    ChandlerSensorEntityDescription(
        key=SENSOR_REGEN_ACTIVE,
        translation_key=SENSOR_REGEN_ACTIVE,
        name="Regeneration Active",
        icon="mdi:refresh-circle",
        entity_registry_enabled_default=False,
        value_fn=lambda d: "On" if d.regen_active else "Off",
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
        key=SENSOR_REGEN_POSITION,
        translation_key=SENSOR_REGEN_POSITION,
        name="Regeneration Position",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:valve",
        value_fn=lambda d: d.regen_current_position,
        attributes_fn=lambda d: {"total_positions": d.num_regen_positions},
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_REGEN_STEP_REMAINING,
        translation_key=SENSOR_REGEN_STEP_REMAINING,
        name="Regeneration Step Time Remaining",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer-sand",
        value_fn=lambda d: d.regen_step_remaining_seconds,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_BRINE_SOAK_REMAINING,
        translation_key=SENSOR_BRINE_SOAK_REMAINING,
        name="Brine Soak Time Remaining",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer-outline",
        value_fn=lambda d: d.regen_soak_timer,
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
        key=SENSOR_TOTAL_GALLONS_RESETTABLE,
        translation_key=SENSOR_TOTAL_GALLONS_RESETTABLE,
        name="Gallons Since Reset",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
        value_fn=lambda d: _hundredths(d.total_gallons_resettable),
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_NEXT_REGEN_TIME,
        translation_key=SENSOR_NEXT_REGEN_TIME,
        name="Scheduled Regeneration Time",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:clock-outline",
        value_fn=_format_regen_hour,
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
        key=SENSOR_GALLONS_BETWEEN_REGENS,
        translation_key=SENSOR_GALLONS_BETWEEN_REGENS,
        name="Gallons Used Last Regeneration Cycle",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:chart-bar",
        value_fn=lambda d: _first(d.gallons_between_regens),
        attributes_fn=lambda d: {"history": d.gallons_between_regens},
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_DAILY_GALLONS_HISTORY,
        translation_key=SENSOR_DAILY_GALLONS_HISTORY,
        name="Gallons Used Yesterday",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:chart-bar",
        value_fn=lambda d: _first(d.daily_gallons_history),
        attributes_fn=lambda d: {"history": d.daily_gallons_history},
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_PEAK_FLOW_HISTORY,
        translation_key=SENSOR_PEAK_FLOW_HISTORY,
        name="Peak Flow Yesterday",
        native_unit_of_measurement="gal/min",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:chart-line",
        value_fn=lambda d: _first(d.peak_flow_history),
        attributes_fn=lambda d: {"history": d.peak_flow_history},
    ),

    # Salt sensors
    ChandlerSensorEntityDescription(
        key=SENSOR_SALT_LEVEL,
        translation_key=SENSOR_SALT_LEVEL,
        name="Salt Level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:shaker-outline",
        suggested_display_precision=2,
        value_fn=lambda d: d.salt_level_percent,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_SALT_REMAINING,
        translation_key=SENSOR_SALT_REMAINING,
        name="Salt Remaining",
        native_unit_of_measurement="lb",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:shaker",
        value_fn=lambda d: _tenths(d.brine_tank_remaining_salt),
    ),
    # Superseded by the Salt Low binary sensor.
    ChandlerSensorEntityDescription(
        key=SENSOR_SALT_LOW,
        translation_key=SENSOR_SALT_LOW,
        name="Salt Low Alert",
        icon="mdi:alert-circle",
        entity_registry_enabled_default=False,
        value_fn=lambda d: "Low" if d.salt_low else "OK",
    ),

    # System sensors
    ChandlerSensorEntityDescription(
        key=SENSOR_WATER_HARDNESS,
        translation_key=SENSOR_WATER_HARDNESS,
        name="Water Hardness",
        native_unit_of_measurement="GPG",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-opacity",
        value_fn=lambda d: d.water_hardness,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_BATTERY_LEVEL,
        translation_key=SENSOR_BATTERY_LEVEL,
        name="Battery Voltage",
        native_unit_of_measurement="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery",
        value_fn=lambda d: d.battery_level_volts,
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_DAYS_IN_OPERATION,
        translation_key=SENSOR_DAYS_IN_OPERATION,
        name="Days In Operation",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:calendar-range",
        value_fn=lambda d: d.days_in_operation,
    ),
    # Superseded by the Valve Error binary sensor and the Last Error sensor.
    ChandlerSensorEntityDescription(
        key=SENSOR_VALVE_ERROR,
        translation_key=SENSOR_VALVE_ERROR,
        name="Valve Error",
        icon="mdi:alert",
        entity_registry_enabled_default=False,
        value_fn=lambda d: get_error_text(d.valve_error),
    ),

    # Capacity sensors
    ChandlerSensorEntityDescription(
        key=SENSOR_RESERVE_CAPACITY_GALLONS,
        translation_key=SENSOR_RESERVE_CAPACITY_GALLONS,
        name="Reserve Capacity",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:storage-tank",
        value_fn=lambda d: _hundredths(d.reserve_capacity_gallons),
    ),
    ChandlerSensorEntityDescription(
        key=SENSOR_TOTAL_GRAINS_CAPACITY,
        translation_key=SENSOR_TOTAL_GRAINS_CAPACITY,
        name="Total Grains Capacity",
        native_unit_of_measurement="grains",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge",
        # astg is stored as value / 1000
        value_fn=lambda d: _thousands(d.total_grains_capacity),
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
        key=BUTTON_REGEN_NOW,
        translation_key=BUTTON_REGEN_NOW,
        name="Start Regeneration Now",
        icon="mdi:play-circle",
        press_payload={"grn": 1},
    ),
    ChandlerButtonEntityDescription(
        key=BUTTON_REGEN_LATER,
        translation_key=BUTTON_REGEN_LATER,
        name="Schedule Regeneration",
        icon="mdi:clock-plus",
        press_payload={"grl": 1},
    ),
    ChandlerButtonEntityDescription(
        key=BUTTON_FIND_HOME,
        translation_key=BUTTON_FIND_HOME,
        name="Find Home",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:home-search",
        press_payload={"gfh": 1},
    ),
)


NUMBER_DESCRIPTIONS: tuple[ChandlerNumberEntityDescription, ...] = (
    ChandlerNumberEntityDescription(
        key=NUMBER_WATER_HARDNESS,
        translation_key=NUMBER_WATER_HARDNESS,
        name="Water Hardness Setting",
        native_unit_of_measurement="GPG",
        native_min_value=0,
        native_max_value=99,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
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
        icon="mdi:calendar-sync",
        value_fn=lambda d: d.day_override,
        write_key="ddo",
    ),
    ChandlerNumberEntityDescription(
        key=NUMBER_REGEN_TIME_HOUR,
        translation_key=NUMBER_REGEN_TIME_HOUR,
        name="Regeneration Hour",
        native_min_value=0,
        native_max_value=23,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:clock-outline",
        value_fn=lambda d: d.regen_time_hours,
        write_key="drth",
    ),
    ChandlerNumberEntityDescription(
        key=NUMBER_RESERVE_CAPACITY,
        translation_key=NUMBER_RESERVE_CAPACITY,
        name="Reserve Capacity Setting",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=49,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:storage-tank",
        value_fn=lambda d: d.reserve_capacity,
        write_key="asrc",
    ),
    ChandlerNumberEntityDescription(
        key=NUMBER_TOTAL_GRAINS,
        translation_key=NUMBER_TOTAL_GRAINS,
        name="Total Grains Capacity Setting",
        native_unit_of_measurement="grains",
        # The device stores this in thousands of grains (0-399).
        native_min_value=0,
        native_max_value=399_000,
        native_step=1000,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:gauge",
        value_fn=lambda d: _thousands(d.total_grains_capacity),
        write_key="astg",
        write_scale=1 / 1000,
    ),
    ChandlerNumberEntityDescription(
        key=NUMBER_SALT_REMAINING,
        translation_key=NUMBER_SALT_REMAINING,
        name="Salt Remaining Setting",
        native_unit_of_measurement="lb",
        native_min_value=0,
        native_max_value=400,
        native_step=1,
        device_class=NumberDeviceClass.WEIGHT,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:shaker",
        value_fn=lambda d: _tenths(d.brine_tank_remaining_salt),
        write_key="dbtr",
        write_scale=10,
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
        key=SWITCH_DISPLAY_OFF,
        translation_key=SWITCH_DISPLAY_OFF,
        name="Display Off",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:monitor-off",
        value_fn=lambda d: d.display_off,
        write_key="asdo",
    ),
)
