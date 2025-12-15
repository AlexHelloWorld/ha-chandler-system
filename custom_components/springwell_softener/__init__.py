"""The Springwell Water Softener integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# List of platforms to support
PLATFORMS_LIST: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Springwell Water Softener from a config entry.

    This is called when Home Assistant loads the integration after
    the user has completed the config flow.
    """
    _LOGGER.info("Setting up Springwell Softener integration")

    # Store an instance of the "connecting" class that does the work of
    # speaking with your actual devices (in this case, a placeholder)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "device_address": entry.data.get("device_address"),
        "device_name": entry.data.get("device_name", "Springwell Softener"),
    }

    # Forward the setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS_LIST)

    _LOGGER.info("Springwell Softener integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    This is called when the user removes the integration or when
    Home Assistant is shutting down.
    """
    _LOGGER.info("Unloading Springwell Softener integration")
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS_LIST,
    )

    # Clean up stored data
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
