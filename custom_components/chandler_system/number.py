"""Number platform for Chandler Water System integration."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    NUMBER_DESCRIPTIONS,
    ChandlerNumberEntityDescription,
)
from .entity import ChandlerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Chandler number entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    async_add_entities(
        ChandlerNumber(
            coordinator=coordinator,
            description=description,
            device_address=coordinator.address,
            device_name=data["device_name"],
        )
        for description in NUMBER_DESCRIPTIONS
    )


class ChandlerNumber(ChandlerEntity, NumberEntity):
    """Writable setting on a Chandler valve."""

    entity_description: ChandlerNumberEntityDescription

    @property
    def native_value(self) -> float | None:
        """Return the value the device currently reports."""
        return self._value(self.entity_description.value_fn)

    async def async_set_native_value(self, value: float) -> None:
        """Write a new value to the device."""
        description = self.entity_description
        raw_value = round(value * description.write_scale)

        await self.coordinator.async_write_keys({description.write_key: raw_value})
