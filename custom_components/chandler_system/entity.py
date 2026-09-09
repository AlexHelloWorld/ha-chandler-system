"""Base entity for the Chandler Water System integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from . import ChandlerDataUpdateCoordinator


class ChandlerEntity(CoordinatorEntity):
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
        self._device_address = device_address
        self._device_name = device_name
        self._attr_unique_id = f"{device_address}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info to group all entities under one device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_address)},
            name=self._device_name,
            manufacturer="Chandler Systems",
            model="Water System",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data is not None

    def _value(self, value_fn: Any) -> Any:
        """Run a description's value_fn against the current data."""
        if value_fn is None or self.coordinator.data is None:
            return None
        return value_fn(self.coordinator.data)
