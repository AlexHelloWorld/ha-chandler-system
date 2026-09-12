"""Button platform for Chandler Water System integration."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BUTTON_DESCRIPTIONS,
    DOMAIN,
    ChandlerButtonEntityDescription,
)
from .entity import ChandlerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Chandler buttons from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    async_add_entities(
        ChandlerButton(
            coordinator=coordinator,
            description=description,
            device_address=coordinator.address,
            device_name=data["device_name"],
        )
        for description in BUTTON_DESCRIPTIONS
    )


class ChandlerButton(ChandlerEntity, ButtonEntity):
    """Button that sends a command to a Chandler valve."""

    entity_description: ChandlerButtonEntityDescription

    async def async_press(self) -> None:
        """Send the button's command to the device."""
        # The device pushes the resulting state change on its own; there is
        # nothing to poll for.
        await self.coordinator.async_write_keys(
            self.entity_description.press_payload()
        )
