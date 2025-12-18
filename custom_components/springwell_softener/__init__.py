"""The Springwell Water Softener integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .client import SoftenerData, SpringwellClient
from .const import (
    CONF_AUTH_TOKEN,
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_NAME,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# List of platforms to support
PLATFORMS: list[Platform] = [Platform.SENSOR]

# Update interval for the coordinator
UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)


class SpringwellDataUpdateCoordinator(DataUpdateCoordinator[SoftenerData]):
    """Coordinator to manage data updates from the Springwell device.

    This coordinator maintains a persistent Bluetooth connection to the device
    and receives push updates when the device state changes.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: SpringwellClient,
        device_name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Springwell {device_name}",
            update_interval=UPDATE_INTERVAL,
        )
        self._client = client
        self._device_name = device_name
        self._connection_lock = asyncio.Lock()
        self._reconnect_task: asyncio.Task | None = None

        # Set the client's data callback to trigger coordinator updates
        self._client._data_callback = self._on_data_received

    def _on_data_received(self, data: SoftenerData) -> None:
        """Handle new data received from the device."""
        _LOGGER.debug("Received data update from device")
        self.async_set_updated_data(data)

    @property
    def client(self) -> SpringwellClient:
        """Return the Bluetooth client."""
        return self._client

    async def _async_update_data(self) -> SoftenerData:
        """Fetch data from the device.

        This is called periodically by the coordinator. Since the device
        pushes data to us, we mainly use this to ensure the connection
        is still active and reconnect if needed.
        """
        async with self._connection_lock:
            # Check if we need to reconnect
            if not self._client.is_connected:
                _LOGGER.info("Connection lost, attempting to reconnect...")
                try:
                    if not await self._client.connect():
                        raise UpdateFailed("Failed to reconnect to device")
                    _LOGGER.info("Reconnected successfully")
                except Exception as e:
                    raise UpdateFailed(f"Failed to reconnect: {e}") from e

            # Return the current data
            return self._client.data

    async def async_connect(self) -> bool:
        """Connect to the device."""
        async with self._connection_lock:
            if self._client.is_connected:
                return True

            _LOGGER.info("Connecting to Springwell device...")
            try:
                result = await self._client.connect()
                if result:
                    _LOGGER.info("Connected to Springwell device")
                    # Initial data is available after connection
                    self.async_set_updated_data(self._client.data)
                return result
            except Exception as e:
                _LOGGER.error("Failed to connect: %s", e)
                return False

    async def async_disconnect(self) -> None:
        """Disconnect from the device."""
        async with self._connection_lock:
            await self._client.disconnect()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Springwell Water Softener from a config entry.

    This is called when Home Assistant loads the integration after
    the user has completed the config flow.
    """
    _LOGGER.info("Setting up Springwell Softener integration")

    device_address = entry.data[CONF_DEVICE_ADDRESS]
    device_name = entry.data.get(CONF_DEVICE_NAME, DEFAULT_NAME)
    auth_token = entry.data[CONF_AUTH_TOKEN]

    # Create the Bluetooth client
    client = SpringwellClient(
        address=device_address,
        auth_token=auth_token,
    )

    # Create the coordinator
    coordinator = SpringwellDataUpdateCoordinator(
        hass=hass,
        client=client,
        device_name=device_name,
    )

    # Try to connect
    try:
        if not await coordinator.async_connect():
            _LOGGER.error("Failed to connect to device during setup")
            # Don't fail setup - allow offline devices
            # The coordinator will retry on updates

        # Do initial refresh
        await coordinator.async_config_entry_first_refresh()
    except Exception as e:
        _LOGGER.warning("Initial connection failed: %s. Will retry.", e)

    # Store coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "device_address": device_address,
        "device_name": device_name,
    }

    # Forward the setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
        entry, PLATFORMS
    )

    # Disconnect from the device
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator: SpringwellDataUpdateCoordinator = data["coordinator"]
        await coordinator.async_disconnect()

    return unload_ok
