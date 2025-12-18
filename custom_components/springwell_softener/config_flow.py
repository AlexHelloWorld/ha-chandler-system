"""Config flow for Springwell Water Softener integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    CONF_AUTH_TOKEN,
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_NAME,
    DEFAULT_NAME,
    DOMAIN,
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
        # Remove dashes and convert to uppercase
        return token.replace("-", "").upper()

    return None


class SpringwellSoftenerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Springwell Water Softener.

    Config flows provide the UI for users to set up the integration.
    This is what appears when users click "Add Integration" in HA.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step.

        This is the first step shown to users. We ask them to provide
        the Bluetooth device address and auth token of their softener.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the input
            device_address = user_input[CONF_DEVICE_ADDRESS].strip()
            device_name = user_input.get(CONF_DEVICE_NAME, DEFAULT_NAME)
            device_name = device_name.strip()
            auth_token_raw = user_input[CONF_AUTH_TOKEN]

            # Validate auth token
            auth_token = validate_auth_token(auth_token_raw)
            if auth_token is None:
                errors[CONF_AUTH_TOKEN] = "invalid_auth_token"
            else:
                # Check if this device is already configured
                await self.async_set_unique_id(device_address)
                self._abort_if_unique_id_configured()

                _LOGGER.info(
                    "Setting up Springwell Softener: %s (%s)",
                    device_name,
                    device_address,
                )

                return self.async_create_entry(
                    title=device_name,
                    data={
                        CONF_DEVICE_ADDRESS: device_address,
                        CONF_DEVICE_NAME: device_name,
                        CONF_AUTH_TOKEN: auth_token,
                    },
                )

        # Show the form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ADDRESS): str,
                    vol.Required(CONF_AUTH_TOKEN): str,
                    vol.Optional(CONF_DEVICE_NAME, default=DEFAULT_NAME): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "device_address_hint": "e.g., AA:BB:CC:DD:EE:FF",
                "auth_token_hint": "UUID from Springwell app",
            },
        )
