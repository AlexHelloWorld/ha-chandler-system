"""Config flow and options flow for Chandler Water System integration."""
from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_ACTIVE_FLOW_POLL_INTERVAL,
    CONF_AUTH_TOKEN,
    CONF_AUTO_SYNC_CLOCK,
    CONF_CLOCK_SYNC_THRESHOLD,
    CONF_DEVICE_NAME,
    CONF_POLL_INTERVAL,
    DEFAULT_ACTIVE_FLOW_POLL_INTERVAL,
    DEFAULT_AUTO_SYNC_CLOCK,
    DEFAULT_CLOCK_SYNC_THRESHOLD,
    DEFAULT_NAME,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MANUFACTURER_ID,
    MAX_ACTIVE_FLOW_POLL_INTERVAL,
    MAX_CLOCK_SYNC_THRESHOLD,
    MAX_POLL_INTERVAL,
    MIN_CLOCK_SYNC_THRESHOLD,
    MIN_POLL_INTERVAL,
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


def is_chandler_device(service_info: BluetoothServiceInfoBleak) -> bool:
    """Check if a discovered device is a Chandler device."""
    for uuid in service_info.service_uuids:
        if (
            SERVICE_UUID_ADVERTISED.lower() in uuid.lower()
            and MANUFACTURER_ID in service_info.manufacturer_data
        ):
            return True

    return False


class ChandlerSystemConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Chandler Water System.

    Supports Bluetooth discovery, manual configuration, reauth, and options.
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._reauth_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ChandlerSystemOptionsFlow:
        """Return the options flow handler."""
        return ChandlerSystemOptionsFlow()

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

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Bluetooth discovery and get auth token."""
        assert self._discovery_info is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            auth_token = validate_auth_token(user_input[CONF_AUTH_TOKEN])

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

        name = self._discovery_info.name or "Chandler Device"
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
        """Handle user-initiated configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input.get(CONF_ADDRESS)

            if address and address in self._discovered_devices:
                self._discovery_info = self._discovered_devices[address]
                return await self.async_step_bluetooth_confirm()
            if address:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()

                return await self.async_step_manual_auth(
                    user_input={CONF_ADDRESS: address}
                )

        self._discovered_devices = {}
        for service_info in async_discovered_service_info(self.hass):
            if is_chandler_device(service_info):
                self._discovered_devices[service_info.address] = service_info

        if self._discovered_devices:
            device_options = {
                addr: f"{info.name or 'Chandler Device'} ({addr})"
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
            auth_token = validate_auth_token(user_input[CONF_AUTH_TOKEN])
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication when the valve rejects the stored token."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt the user for a regenerated API token."""
        assert self._reauth_entry is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            auth_token = validate_auth_token(user_input[CONF_AUTH_TOKEN])
            if auth_token is None:
                errors[CONF_AUTH_TOKEN] = "invalid_auth_token"
            else:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data_updates={CONF_AUTH_TOKEN: auth_token},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_AUTH_TOKEN): str}),
            errors=errors,
            description_placeholders={
                "name": self._reauth_entry.title,
                "address": self._reauth_entry.data.get(CONF_ADDRESS, ""),
            },
        )


class ChandlerSystemOptionsFlow(OptionsFlow):
    """Configure polling cadence and automatic clock sync."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_POLL_INTERVAL: int(user_input[CONF_POLL_INTERVAL]),
                    CONF_ACTIVE_FLOW_POLL_INTERVAL: int(
                        user_input[CONF_ACTIVE_FLOW_POLL_INTERVAL]
                    ),
                    CONF_AUTO_SYNC_CLOCK: bool(user_input[CONF_AUTO_SYNC_CLOCK]),
                    CONF_CLOCK_SYNC_THRESHOLD: int(
                        user_input[CONF_CLOCK_SYNC_THRESHOLD]
                    ),
                },
            )

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=options.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_POLL_INTERVAL,
                            max=MAX_POLL_INTERVAL,
                            step=5,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_ACTIVE_FLOW_POLL_INTERVAL,
                        default=options.get(
                            CONF_ACTIVE_FLOW_POLL_INTERVAL,
                            DEFAULT_ACTIVE_FLOW_POLL_INTERVAL,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=MAX_ACTIVE_FLOW_POLL_INTERVAL,
                            step=5,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_AUTO_SYNC_CLOCK,
                        default=options.get(
                            CONF_AUTO_SYNC_CLOCK, DEFAULT_AUTO_SYNC_CLOCK
                        ),
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_CLOCK_SYNC_THRESHOLD,
                        default=options.get(
                            CONF_CLOCK_SYNC_THRESHOLD,
                            DEFAULT_CLOCK_SYNC_THRESHOLD,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_CLOCK_SYNC_THRESHOLD,
                            max=MAX_CLOCK_SYNC_THRESHOLD,
                            step=10,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
