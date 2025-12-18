"""Config flow for Springwell Water Softener integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import (
    CONF_AUTH_TOKEN,
    CONF_DEVICE_NAME,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER_ID,
    SERVICE_UUID_ADVERTISED,
)

_LOGGER = logging.getLogger(__name__)

# Regex pattern for UUID (with or without dashes)
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?"
    r"[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
)


def validate_auth_token(token: str) -> str | None:
    """Validate and normalize auth token.

    Returns normalized token (without dashes) or None if invalid.
    """
    if not token:
        return None

    token = token.strip()
    if UUID_PATTERN.match(token):
        return token.replace("-", "").upper()

    return None


def is_springwell_device(service_info: BluetoothServiceInfoBleak) -> bool:
    """Check if a discovered device is a Springwell device."""
    # Check service UUID
    for uuid in service_info.service_uuids:
        if SERVICE_UUID_ADVERTISED.lower() in uuid.lower():
            return True

    # Check manufacturer ID
    if MANUFACTURER_ID in service_info.manufacturer_data:
        return True

    return False


class SpringwellSoftenerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Springwell Water Softener.

    Supports both Bluetooth discovery and manual configuration.
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a Bluetooth discovery."""
        _LOGGER.debug(
            "Bluetooth discovery: %s (%s)",
            discovery_info.name,
            discovery_info.address,
        )

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info

        # Show the discovered device to the user
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Bluetooth discovery and get auth token."""
        assert self._discovery_info is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            auth_token_raw = user_input[CONF_AUTH_TOKEN]
            auth_token = validate_auth_token(auth_token_raw)

            if auth_token is None:
                errors[CONF_AUTH_TOKEN] = "invalid_auth_token"
            else:
                device_name = user_input.get(
                    CONF_DEVICE_NAME,
                    self._discovery_info.name or DEFAULT_NAME,
                )

                return self.async_create_entry(
                    title=device_name,
                    data={
                        CONF_ADDRESS: self._discovery_info.address,
                        CONF_DEVICE_NAME: device_name,
                        CONF_AUTH_TOKEN: auth_token,
                    },
                )

        # Build the description with device info
        name = self._discovery_info.name or "Springwell Device"
        placeholders = {
            "name": name,
            "address": self._discovery_info.address,
        }

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AUTH_TOKEN): str,
                    vol.Optional(CONF_DEVICE_NAME, default=name): str,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-initiated configuration.

        Scans for Springwell devices and lets user choose one.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # User selected a device or manually entered address
            address = user_input.get(CONF_ADDRESS)

            if address and address in self._discovered_devices:
                # User selected a discovered device
                self._discovery_info = self._discovered_devices[address]
                return await self.async_step_bluetooth_confirm()
            elif address:
                # Manual address entry - go to auth step
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()

                # Create a minimal discovery info for manual entry
                return await self.async_step_manual_auth(
                    user_input={CONF_ADDRESS: address}
                )

        # Scan for Springwell devices
        self._discovered_devices = {}
        for service_info in async_discovered_service_info(self.hass):
            if is_springwell_device(service_info):
                self._discovered_devices[service_info.address] = service_info

        if self._discovered_devices:
            # Build selection options
            device_options = {
                addr: f"{info.name or 'Springwell'} ({addr})"
                for addr, info in self._discovered_devices.items()
            }

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ADDRESS): vol.In(device_options),
                    }
                ),
                errors=errors,
                description_placeholders={
                    "device_count": str(len(self._discovered_devices)),
                },
            )
        else:
            # No devices found - offer manual entry
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ADDRESS): str,
                    }
                ),
                errors=errors,
                description_placeholders={
                    "device_count": "0",
                },
            )

    async def async_step_manual_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual address entry - get auth token."""
        errors: dict[str, str] = {}

        if user_input is not None and CONF_AUTH_TOKEN in user_input:
            auth_token_raw = user_input[CONF_AUTH_TOKEN]
            auth_token = validate_auth_token(auth_token_raw)
            address = user_input.get(CONF_ADDRESS, "")

            if auth_token is None:
                errors[CONF_AUTH_TOKEN] = "invalid_auth_token"
            else:
                device_name = user_input.get(CONF_DEVICE_NAME, DEFAULT_NAME)

                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=device_name,
                    data={
                        CONF_ADDRESS: address,
                        CONF_DEVICE_NAME: device_name,
                        CONF_AUTH_TOKEN: auth_token,
                    },
                )

        # Get address from previous step
        address = user_input.get(CONF_ADDRESS, "") if user_input else ""

        return self.async_show_form(
            step_id="manual_auth",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS, default=address): str,
                    vol.Required(CONF_AUTH_TOKEN): str,
                    vol.Optional(CONF_DEVICE_NAME, default=DEFAULT_NAME): str,
                }
            ),
            errors=errors,
        )
