"""Services for the Chandler Water System integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .const import DOMAIN

if TYPE_CHECKING:
    from . import ChandlerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_START_REGENERATION = "start_regeneration"
SERVICE_FIND_HOME = "find_home"
SERVICE_SET_SALT_LEVEL = "set_salt_level"
SERVICE_RESET_COUNTERS = "reset_counters"
SERVICE_SYNC_CLOCK = "sync_clock"

ATTR_DEVICE_ID = "device_id"
ATTR_WHEN = "when"
ATTR_POUNDS = "pounds"
ATTR_COUNTERS = "counters"

WHEN_NOW = "now"
WHEN_NEXT_SCHEDULED = "next_scheduled"

COUNTER_REGENERATIONS = "regenerations"
COUNTER_GALLONS = "gallons"

_TARGET_SCHEMA = {vol.Required(ATTR_DEVICE_ID): cv.string}

START_REGENERATION_SCHEMA = vol.Schema(
    {
        **_TARGET_SCHEMA,
        vol.Optional(ATTR_WHEN, default=WHEN_NOW): vol.In(
            [WHEN_NOW, WHEN_NEXT_SCHEDULED]
        ),
    }
)

FIND_HOME_SCHEMA = vol.Schema(_TARGET_SCHEMA)

SET_SALT_LEVEL_SCHEMA = vol.Schema(
    {
        **_TARGET_SCHEMA,
        vol.Required(ATTR_POUNDS): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=400)
        ),
    }
)

RESET_COUNTERS_SCHEMA = vol.Schema(
    {
        **_TARGET_SCHEMA,
        vol.Required(ATTR_COUNTERS): vol.All(
            cv.ensure_list,
            [vol.In([COUNTER_REGENERATIONS, COUNTER_GALLONS])],
            vol.Length(min=1),
        ),
    }
)

SYNC_CLOCK_SCHEMA = vol.Schema(_TARGET_SCHEMA)


def _coordinator_for_device(
    hass: HomeAssistant, device_id: str
) -> ChandlerDataUpdateCoordinator:
    """Resolve a service call's target device to its coordinator."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise HomeAssistantError(f"Device {device_id} not found")

    for entry_id in device.config_entries:
        entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
        if entry_data is not None:
            return entry_data["coordinator"]

    raise HomeAssistantError(
        f"Device {device_id} is not a Chandler Water System device"
    )


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's services."""
    if hass.services.has_service(DOMAIN, SERVICE_START_REGENERATION):
        return

    async def _write(call: ServiceCall, payload: dict[str, Any]) -> None:
        coordinator = _coordinator_for_device(hass, call.data[ATTR_DEVICE_ID])
        await coordinator.async_write_keys(payload)
        await coordinator.async_request_refresh()

    async def async_start_regeneration(call: ServiceCall) -> None:
        """Start a regeneration immediately or at the next scheduled time."""
        key = "grn" if call.data[ATTR_WHEN] == WHEN_NOW else "grl"
        await _write(call, {key: 1})

    async def async_find_home(call: ServiceCall) -> None:
        """Tell the valve to return to its home position."""
        await _write(call, {"gfh": 1})

    async def async_set_salt_level(call: ServiceCall) -> None:
        """Record how much salt is in the brine tank, e.g. after a refill."""
        await _write(call, {"dbtr": round(call.data[ATTR_POUNDS] * 10)})

    async def async_reset_counters(call: ServiceCall) -> None:
        """Zero the resettable regeneration and gallon counters."""
        counters = call.data[ATTR_COUNTERS]
        payload: dict[str, Any] = {}
        if COUNTER_REGENERATIONS in counters:
            payload["shrr"] = 0
        if COUNTER_GALLONS in counters:
            payload["shgr"] = 0
        await _write(call, payload)

    async def async_sync_clock(call: ServiceCall) -> None:
        """Set the valve's clock from Home Assistant's local time."""
        now = dt_util.now()
        await _write(call, {"dh": now.hour, "dm": now.minute, "ds": now.second})

    for service, handler, schema in (
        (
            SERVICE_START_REGENERATION,
            async_start_regeneration,
            START_REGENERATION_SCHEMA,
        ),
        (SERVICE_FIND_HOME, async_find_home, FIND_HOME_SCHEMA),
        (SERVICE_SET_SALT_LEVEL, async_set_salt_level, SET_SALT_LEVEL_SCHEMA),
        (SERVICE_RESET_COUNTERS, async_reset_counters, RESET_COUNTERS_SCHEMA),
        (SERVICE_SYNC_CLOCK, async_sync_clock, SYNC_CLOCK_SCHEMA),
    ):
        hass.services.async_register(DOMAIN, service, handler, schema=schema)


def async_unload_services(hass: HomeAssistant) -> None:
    """Remove the integration's services."""
    for service in (
        SERVICE_START_REGENERATION,
        SERVICE_FIND_HOME,
        SERVICE_SET_SALT_LEVEL,
        SERVICE_RESET_COUNTERS,
        SERVICE_SYNC_CLOCK,
    ):
        hass.services.async_remove(DOMAIN, service)
