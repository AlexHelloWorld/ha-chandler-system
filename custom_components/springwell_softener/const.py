"""Constants for the Springwell Water Softener integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfVolumeFlowRate,
)

DOMAIN = "springwell_softener"

# Configuration keys
CONF_DEVICE_ADDRESS = "device_address"
CONF_DEVICE_NAME = "device_name"

# Default values
DEFAULT_NAME = "Springwell Softener"
DEFAULT_SCAN_INTERVAL = 60  # seconds

# Platforms
PLATFORMS = ["sensor"]

# Sensor keys
SENSOR_SALT_LEVEL = "salt_level"
SENSOR_WATER_FLOW = "water_flow"
SENSOR_WATER_USED_TODAY = "water_used_today"
SENSOR_DAYS_UNTIL_REGEN = "days_until_regen"
SENSOR_CURRENT_CAPACITY = "current_capacity"

# Bluetooth UUIDs (placeholders - need actual device UUIDs)
SERVICE_UUID = "00000000-0000-0000-0000-000000000000"
CHARACTERISTIC_UUID = "00000000-0000-0000-0000-000000000001"


@dataclass(frozen=True, kw_only=True)
class SpringwellSensorEntityDescription(SensorEntityDescription):
    """Describes a Springwell sensor entity.

    Extends the base SensorEntityDescription to add any custom fields
    specific to our integration (like mock_value for testing).
    """

    mock_value: float | int | str | None = None


# Define all sensors in one place - easy to add/remove/modify
SENSOR_DESCRIPTIONS: tuple[SpringwellSensorEntityDescription, ...] = (
    SpringwellSensorEntityDescription(
        key=SENSOR_SALT_LEVEL,
        translation_key=SENSOR_SALT_LEVEL,
        name="Salt Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,  # Closest match for "level"
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:shaker-outline",
        mock_value=75,
    ),
    SpringwellSensorEntityDescription(
        key=SENSOR_WATER_FLOW,
        translation_key=SENSOR_WATER_FLOW,
        name="Water Flow",
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-pump",
        mock_value=2.5,
    ),
    SpringwellSensorEntityDescription(
        key=SENSOR_WATER_USED_TODAY,
        translation_key=SENSOR_WATER_USED_TODAY,
        name="Water Used Today",
        native_unit_of_measurement="gal",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:water",
        mock_value=150,
    ),
    SpringwellSensorEntityDescription(
        key=SENSOR_DAYS_UNTIL_REGEN,
        translation_key=SENSOR_DAYS_UNTIL_REGEN,
        name="Days Until Regeneration",
        native_unit_of_measurement="days",
        icon="mdi:calendar-clock",
        mock_value=3,
    ),
    SpringwellSensorEntityDescription(
        key=SENSOR_CURRENT_CAPACITY,
        translation_key=SENSOR_CURRENT_CAPACITY,
        name="Current Capacity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge",
        mock_value=65,
    ),
)
