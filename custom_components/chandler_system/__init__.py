"""The Chandler Water System integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .client import ChandlerClient, ChandlerWriteError, DeviceData
from .const import (
    CONF_AUTH_TOKEN,
    CONF_DEVICE_NAME,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]
UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)


class ChandlerDataUpdateCoordinator(DataUpdateCoordinator[DeviceData]):
    """Coordinator to manage data updates from the Chandler device.

    Maintains a persistent Bluetooth connection and receives push updates.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        auth_token: str,
        device_name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Chandler {device_name}",
            update_interval=UPDATE_INTERVAL,
        )
        self._address = address
        self._auth_token = auth_token
        self._device_name = device_name
        self._client: ChandlerClient | None = None
        self._connection_lock = asyncio.Lock()

    def _on_data_received(self, data: DeviceData) -> None:
        """Handle new data received from the device."""
        _LOGGER.debug("Received data update from device")
        self.async_set_updated_data(data)

    @property
    def client(self) -> ChandlerClient | None:
        """Return the Bluetooth client."""
        return self._client

    @property
    def address(self) -> str:
        """Return the device address."""
        return self._address

    async def _async_ensure_connected(self) -> ChandlerClient:
        """Return a connected client, connecting or reconnecting as needed.

        The caller must hold the connection lock.
        """
        # Get current BLE device from HA's bluetooth
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )

        if ble_device is None:
            raise UpdateFailed(
                f"Device {self._address} not found. "
                "Is it powered on and in range?"
            )

        # Check if we need to create or update client
        if self._client is None:
            self._client = ChandlerClient(
                ble_device=ble_device,
                auth_token=self._auth_token,
                data_callback=self._on_data_received,
            )
        else:
            # Update BLE device (address may be stale)
            self._client.set_ble_device(ble_device)

        # Connect if not connected
        if not self._client.is_connected:
            _LOGGER.info("Connecting to Chandler device...")
            try:
                if not await self._client.connect():
                    raise UpdateFailed("Failed to connect to device")
                _LOGGER.info("Connected successfully")
            except UpdateFailed:
                raise
            except Exception as err:
                raise UpdateFailed(f"Connection failed: {err}") from err

        return self._client

    async def _async_update_data(self) -> DeviceData:
        """Fetch data from the device.

        Called periodically. Ensures connection is active and reconnects
        if needed.
        """
        async with self._connection_lock:
            client = await self._async_ensure_connected()
            return client.data

    async def async_write_keys(self, payload: dict) -> None:
        """Write API keys to the device.

        The valve ignores writes that match its current value, so a successful
        call means the command was delivered, not that anything changed.
        """
        async with self._connection_lock:
            try:
                client = await self._async_ensure_connected()
                await client.async_write_keys(payload)
            except (UpdateFailed, ChandlerWriteError) as err:
                raise HomeAssistantError(
                    f"Failed to send {payload} to the water system: {err}"
                ) from err

    async def async_disconnect(self) -> None:
        """Disconnect from the device."""
        async with self._connection_lock:
            if self._client:
                await self._client.disconnect()
                self._client = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Chandler Water System from a config entry."""
    _LOGGER.info("Setting up Chandler Water System integration")

    address = entry.data[CONF_ADDRESS]
    device_name = entry.data.get(CONF_DEVICE_NAME, DEFAULT_NAME)
    auth_token = entry.data[CONF_AUTH_TOKEN]

    # Check if device is available
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address, connectable=True
    )

    if ble_device is None:
        raise ConfigEntryNotReady(
            f"Device {address} not found. Is it powered on and in range?"
        )

    # Create coordinator
    coordinator = ChandlerDataUpdateCoordinator(
        hass=hass,
        address=address,
        auth_token=auth_token,
        device_name=device_name,
    )

    # Do initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "device_name": device_name,
    }

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async_setup_services(hass)

    _LOGGER.info("Chandler Water System integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Chandler Water System integration")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )

    # Disconnect
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator: ChandlerDataUpdateCoordinator = data["coordinator"]
        await coordinator.async_disconnect()

        if not hass.data[DOMAIN]:
            async_unload_services(hass)

    return unload_ok

