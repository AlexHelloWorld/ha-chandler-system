"""Sensor platform for Springwell Water Softener integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    coordinator = data["coordinator"]
    device_name = data["device_name"]
    device_address = coordinator.address

    # Create one sensor entity for each description
    sensors = [
        SpringwellSensor(
            coordinator=coordinator,
            description=description,
            device_address=device_address,
            device_name=device_name,
        )
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(sensors)


class SpringwellSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Springwell Water Softener.

    This sensor uses the CoordinatorEntity pattern to efficiently
    share data updates across all sensors from a single device.
    """

    _attr_has_entity_name = True
    entity_description: SpringwellSensorEntityDescription

    def __init__(
        self,
        coordinator: Any,
        description: SpringwellSensorEntityDescription,
        device_address: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: The data update coordinator
            description: Defines this sensor's name, unit, icon, etc.
            device_address: Bluetooth MAC address of the softener
            device_name: User-friendly name for the device
        """
        super().__init__(coordinator)

        self.entity_description = description
        self._device_address = device_address
        self._device_name = device_name

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

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Check coordinator availability and that we have data
        return (
            super().available
            and self.coordinator.data is not None
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        # Use the value_fn from the description to extract the value
        if self.entity_description.value_fn is not None:
            try:
                return self.entity_description.value_fn(self.coordinator.data)
            except Exception as e:
                _LOGGER.debug(
                    "Error getting value for %s: %s",
                    self.entity_description.key,
                    e,
                )
                return None

        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
