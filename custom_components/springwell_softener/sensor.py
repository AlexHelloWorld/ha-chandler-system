"""Sensor platform for Springwell Water Softener integration."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SENSOR_DESCRIPTIONS,
    SpringwellSensorEntityDescription,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Springwell Softener sensors from a config entry."""
    _LOGGER.info("Setting up Springwell Softener sensors")

    data = hass.data[DOMAIN][entry.entry_id]
    device_address = data["device_address"]
    device_name = data["device_name"]

    # Create one sensor entity for each description
    # This is much cleaner than having separate classes!
    sensors = [
        SpringwellSensor(
            description=description,
            device_address=device_address,
            device_name=device_name,
        )
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(sensors, update_before_add=True)


class SpringwellSensor(SensorEntity):
    """Generic sensor for Springwell Water Softener.

    This single class handles ALL sensor types. The behavior is controlled
    by the SpringwellSensorEntityDescription passed to the constructor.
    """

    _attr_has_entity_name = True

    # This tells HA to use description attributes automatically
    entity_description: SpringwellSensorEntityDescription

    def __init__(
        self,
        description: SpringwellSensorEntityDescription,
        device_address: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            description: Defines this sensor's name, unit, icon, etc.
            device_address: Bluetooth MAC address of the softener
            device_name: User-friendly name for the device
        """
        # Setting entity_description automatically applies:
        # - name, icon, device_class, state_class
        # - native_unit_of_measurement, etc.
        self.entity_description = description

        self._device_address = device_address
        self._device_name = device_name

        # Set initial mock value (for testing without real device)
        self._attr_native_value = description.mock_value

        # Unique ID combines device address + sensor key
        self._attr_unique_id = f"{device_address}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info to group all sensors under one device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_address)},
            name=self._device_name,
            manufacturer="Springwell",
            model="Water Softener",
            sw_version="0.1.0",
        )

    async def async_update(self) -> None:
        """Fetch new state data for this sensor.

        TODO: Implement actual Bluetooth read based on entity_description.key
        """
        key = self.entity_description.key
        _LOGGER.debug("Updating Springwell sensor: %s", key)

        # Future: read from Bluetooth and update self._attr_native_value
