"""Sensor platform for Chandler Water System integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SENSOR_DESCRIPTIONS
from .entity import ChandlerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Chandler Water System sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    async_add_entities(
        ChandlerSensor(
            coordinator=coordinator,
            description=description,
            device_address=coordinator.address,
            device_name=data["device_name"],
        )
        for description in SENSOR_DESCRIPTIONS
    )


class ChandlerSensor(ChandlerEntity, SensorEntity):
    """Sensor for Chandler Water System devices."""

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        try:
            return self._value(self.entity_description.value_fn)
        except Exception as err:
            _LOGGER.debug(
                "Error getting value for %s: %s",
                self.entity_description.key,
                err,
            )
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return supplementary data such as history arrays and error logs."""
        attributes_fn = self.entity_description.attributes_fn
        if attributes_fn is None or self.coordinator.data is None:
            return None

        try:
            return attributes_fn(self.coordinator.data)
        except Exception as err:
            _LOGGER.debug(
                "Error getting attributes for %s: %s",
                self.entity_description.key,
                err,
            )
            return None
