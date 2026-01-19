"""Constants for the Chandler Water System integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
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


def _get_error_text(error_code: int | None) -> str:
    """Convert error code to human-readable text."""
    # Device doesn't send gve field when there's no error
    if error_code is None or error_code == 0:
        return "No Error"

    error_map = {
        # 0 is handled above as "No Error"
        2: "Lost Home",
        3: "No Encoder Slots (Normal Current)",
        4: "Can't Find Home",
        5: "No Encoder Slots (High Current)",
        6: "No Encoder Slots (No Current)",
        7: "TWEDO Motor Timeout",
        192: "Regen Aborted (On Battery)",
    }
    return error_map.get(error_code, f"Unknown Error ({error_code})")


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
    ChandlerSensorEntityDescription(
        key=SENSOR_REGEN_ACTIVE,
        translation_key=SENSOR_REGEN_ACTIVE,
        name="Regeneration Active",
        icon="mdi:refresh-circle",
        value_fn=lambda d: "On" if d.regen_active else "Off",
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
    ChandlerSensorEntityDescription(
        key=SENSOR_SALT_LOW,
        translation_key=SENSOR_SALT_LOW,
        name="Salt Low Alert",
        icon="mdi:alert-circle",
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
    ChandlerSensorEntityDescription(
        key=SENSOR_VALVE_ERROR,
        translation_key=SENSOR_VALVE_ERROR,
        name="Valve Error",
        icon="mdi:alert",
        value_fn=lambda d: _get_error_text(d.valve_error),
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
