"""Config flow for Springwell Water Softener integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_NAME,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SpringwellSoftenerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Springwell Water Softener.

    Config flows provide the UI for users to set up the integration.
    This is what appears when users click "Add Integration" in Home Assistant.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step.

        This is the first step shown to users. We ask them to provide
        the Bluetooth device address of their softener.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the input
            device_address = user_input[CONF_DEVICE_ADDRESS]
            device_name = user_input.get(CONF_DEVICE_NAME, DEFAULT_NAME)

            # Check if this device is already configured
            await self.async_set_unique_id(device_address)
            self._abort_if_unique_id_configured()

            # TODO: In future, validate by attempting to connect to the device
            # For now, we just accept the input

            _LOGGER.info(
                "Setting up Springwell Softener: %s (%s)",
                device_name,
                device_address
            )

            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_DEVICE_ADDRESS: device_address,
                    CONF_DEVICE_NAME: device_name,
                },
            )

        # Show the form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ADDRESS): str,
                    vol.Optional(CONF_DEVICE_NAME, default=DEFAULT_NAME): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "device_address_hint": "e.g., AA:BB:CC:DD:EE:FF",
            },
        )
