"""Base entity for the Chandler Water System integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from . import ChandlerDataUpdateCoordinator


class ChandlerEntity(CoordinatorEntity["ChandlerDataUpdateCoordinator"]):
    """Common device grouping and availability for Chandler entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ChandlerDataUpdateCoordinator,
        description: EntityDescription,
        device_address: str,
        device_name: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{device_address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_address)},
            connections={(dr.CONNECTION_BLUETOOTH, device_address)},
            name=device_name,
            manufacturer="Chandler Systems",
            model="Water System",
        )

    def _value(self, value_fn: Any) -> Any:
        """Run a description's value_fn against the current data."""
        if value_fn is None or self.coordinator.data is None:
            return None
        return value_fn(self.coordinator.data)
