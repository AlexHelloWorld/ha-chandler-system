"""Switch platform for Chandler Water System integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SWITCH_DESCRIPTIONS,
    ChandlerSwitchEntityDescription,
)
from .entity import ChandlerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Chandler switches from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    async_add_entities(
        ChandlerSwitch(
            coordinator=coordinator,
            description=description,
            device_address=coordinator.address,
            device_name=data["device_name"],
        )
        for description in SWITCH_DESCRIPTIONS
    )


class ChandlerSwitch(ChandlerEntity, SwitchEntity):
    """Boolean setting on a Chandler valve."""

    entity_description: ChandlerSwitchEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the flag the device currently reports."""
        return self._value(self.entity_description.value_fn)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the setting."""
        await self._async_write(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the setting."""
        await self._async_write(False)

    async def _async_write(self, enabled: bool) -> None:
        await self.coordinator.async_write_keys(
            {self.entity_description.write_key: int(enabled)}
        )
