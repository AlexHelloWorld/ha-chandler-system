"""Binary sensor platform for Chandler Water System integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BINARY_SENSOR_DESCRIPTIONS,
    DOMAIN,
    ChandlerBinarySensorEntityDescription,
)
from .entity import ChandlerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Chandler binary sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    async_add_entities(
        ChandlerBinarySensor(
            coordinator=coordinator,
            description=description,
            device_address=coordinator.address,
            device_name=data["device_name"],
        )
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class ChandlerBinarySensor(ChandlerEntity, BinarySensorEntity):
    """Binary sensor for Chandler Water System devices."""

    entity_description: ChandlerBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return True if the underlying flag is set."""
        return self._value(self.entity_description.value_fn)
