"""Button platform for Chandler Water System integration."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
    """Button that sends a command or triggers a poll on a Chandler valve."""

    entity_description: ChandlerButtonEntityDescription

    async def async_press(self) -> None:
        """Execute the button's action or send its write command."""
        if self.entity_description.action == "refresh":
            await self.coordinator.async_force_refresh()
            return

        if self.entity_description.press_payload is None:
            return

        payload = self.entity_description.press_payload(self.coordinator.data)
        if not payload:
            raise HomeAssistantError(
                f"Cannot run '{self.entity_description.name}' until the device "
                "reports the required capacity data."
            )

        await self.coordinator.async_write_keys(payload)
