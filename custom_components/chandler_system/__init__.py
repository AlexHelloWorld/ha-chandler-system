"""The Chandler Water System integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .client import (
    ChandlerAuthError,
    ChandlerClient,
    ChandlerConnectionError,
    ChandlerWriteError,
    DeviceData,
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
    _clock_drift_seconds,
    clock_payload,
)
from .protocol import PacketError
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Retain last good data across brief transient BLE misses (e.g. phone app in use)
# before marking entities unavailable.
MAX_CONSECUTIVE_FAILURES = 3
# Upper bound for exponential backoff after repeated poll failures.
MAX_BACKOFF_INTERVAL = 900  # 15 minutes
# Minimum interval between automatic clock-sync writes so a valve that ignores
# clock writes cannot cause repeated writes on every poll.
AUTO_CLOCK_SYNC_COOLDOWN = 3600.0  # 1 hour
# Minimum drift threshold when the valve omits seconds ("ds") from its dump.
NO_SECONDS_MIN_DRIFT = 90


class ChandlerDataUpdateCoordinator(DataUpdateCoordinator[DeviceData]):
    """Coordinator managing short-lived BLE polls and writes for a Chandler valve."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        auth_token: str,
        device_name: str,
        *,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        active_flow_poll_interval: int = DEFAULT_ACTIVE_FLOW_POLL_INTERVAL,
        auto_sync_clock: bool = DEFAULT_AUTO_SYNC_CLOCK,
        clock_sync_threshold: int = DEFAULT_CLOCK_SYNC_THRESHOLD,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Chandler {device_name}",
            update_interval=timedelta(seconds=poll_interval),
        )
        self._address = address
        self._auth_token = auth_token
        self._device_name = device_name
        self._poll_interval = poll_interval
        self._active_flow_poll_interval = active_flow_poll_interval
        self._auto_sync_clock = auto_sync_clock
        self._clock_sync_threshold = clock_sync_threshold

        self._client: ChandlerClient | None = None
        self._consecutive_failures = 0
        self._last_clock_sync_monotonic: float = 0.0
        self._last_device_meta: tuple[str | None, ...] | None = None

    @property
    def client(self) -> ChandlerClient | None:
        """Return the Bluetooth client."""
        return self._client

    @property
    def address(self) -> str:
        """Return the device address."""
        return self._address

    @property
    def consecutive_failures(self) -> int:
        """Number of consecutive failed polls since the last good reading."""
        return self._consecutive_failures

    def _get_ble_device(self) -> Any:
        """Look up a fresh connectable BLEDevice from Home Assistant."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(
                f"Device {self._address} not found. "
                "Is it powered on and in range?"
            )
        return ble_device

    def _ensure_client(self, ble_device: Any) -> ChandlerClient:
        """Return the ChandlerClient, creating or refreshing its BLEDevice."""
        if self._client is None:
            self._client = ChandlerClient(
                ble_device=ble_device,
                auth_token=self._auth_token,
            )
        else:
            self._client.set_ble_device(ble_device)
        return self._client

    def _apply_next_poll_interval(self, data: DeviceData) -> None:
        """Choose normal vs active-flow poll cadence based on live flow."""
        if (
            self._active_flow_poll_interval > 0
            and not data.regen_active
            and data.present_flow is not None
            and data.present_flow > 0
        ):
            target = min(self._poll_interval, self._active_flow_poll_interval)
        else:
            target = self._poll_interval

        new_interval = timedelta(seconds=target)
        if self.update_interval != new_interval:
            _LOGGER.debug("Adjusting poll interval to %ss", target)
            self.update_interval = new_interval

    def _apply_failure_backoff(self) -> int:
        """Back off poll cadence after failures so we never hammer the valve."""
        exponent = min(max(self._consecutive_failures - 1, 0), 4)
        backoff = min(MAX_BACKOFF_INTERVAL, self._poll_interval * (2**exponent))
        self.update_interval = timedelta(seconds=backoff)
        return backoff

    def _maybe_clock_sync_payload(self, data: DeviceData) -> dict[str, int] | None:
        """Return a clock-sync payload if auto-sync is enabled and clock drifted."""
        if not self._auto_sync_clock:
            return None
        if data.regen_active:
            return None

        drift = _clock_drift_seconds(data)
        if drift is None:
            return None

        effective_threshold = (
            max(self._clock_sync_threshold, NO_SECONDS_MIN_DRIFT)
            if data.time_seconds is None
            else self._clock_sync_threshold
        )
        if abs(drift) < effective_threshold:
            return None

        now_mono = asyncio.get_running_loop().time()
        if (
            self._last_clock_sync_monotonic > 0
            and (now_mono - self._last_clock_sync_monotonic)
            < AUTO_CLOCK_SYNC_COOLDOWN
        ):
            return None

        self._last_clock_sync_monotonic = now_mono
        payload = clock_payload()
        _LOGGER.info(
            "Valve clock drifted by %+ds (threshold %ds); syncing to %02d:%02d:%02d",
            drift,
            effective_threshold,
            payload["dh"],
            payload["dm"],
            payload["ds"],
        )
        return payload

    def _update_device_registry(self, data: DeviceData) -> None:
        """Populate HA device metadata (firmware, serial, model, series)."""
        meta = (
            data.firmware_version_text,
            data.valve_series_text,
            data.valve_type_text,
            data.serial_number,
        )
        if meta == self._last_device_meta or not any(meta):
            return

        dev_reg = dr.async_get(self.hass)
        device = dev_reg.async_get_device(identifiers={(DOMAIN, self._address)})
        if device is None:
            return

        updates: dict[str, Any] = {}
        if data.firmware_version_text:
            updates["sw_version"] = data.firmware_version_text
        if data.valve_series_text:
            updates["hw_version"] = data.valve_series_text
        if data.valve_type_text:
            updates["model"] = data.valve_type_text
        if data.serial_number:
            updates["serial_number"] = data.serial_number

        if updates:
            dev_reg.async_update_device(device.id, **updates)
        self._last_device_meta = meta

    async def _async_update_data(self) -> DeviceData:
        """Perform one bounded short-lived BLE poll and return fresh data."""
        try:
            ble_device = self._get_ble_device()
            client = self._ensure_client(ble_device)
            data = await client.async_poll(
                ble_device=ble_device,
                post_poll_write=self._maybe_clock_sync_payload,
            )
        except ChandlerAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (UpdateFailed, ChandlerConnectionError, ChandlerWriteError) as err:
            self._consecutive_failures += 1
            backoff = self._apply_failure_backoff()
            if (
                self.data is not None
                and self._consecutive_failures < MAX_CONSECUTIVE_FAILURES
            ):
                _LOGGER.warning(
                    "Poll failed (%d/%d), keeping previous data "
                    "and retrying in %ds: %s",
                    self._consecutive_failures,
                    MAX_CONSECUTIVE_FAILURES,
                    backoff,
                    err,
                )
                return self.data
            raise UpdateFailed(f"Poll failed: {err}") from err
        except Exception as err:
            self._consecutive_failures += 1
            backoff = self._apply_failure_backoff()
            if (
                self.data is not None
                and self._consecutive_failures < MAX_CONSECUTIVE_FAILURES
            ):
                _LOGGER.warning(
                    "Unexpected poll error (%d/%d), retrying in %ds: %s",
                    self._consecutive_failures,
                    MAX_CONSECUTIVE_FAILURES,
                    backoff,
                    err,
                )
                return self.data
            raise UpdateFailed(f"Unexpected error polling device: {err}") from err

        self._consecutive_failures = 0
        self._apply_next_poll_interval(data)
        self._update_device_registry(data)
        return data

    async def async_write_keys(self, payload: dict[str, Any]) -> None:
        """Open a short BLE session, write keys, refresh entities, and close.

        The valve ignores writes that match its current value, so a successful
        call means the command was delivered, not necessarily that anything
        changed.
        """
        try:
            ble_device = self._get_ble_device()
            client = self._ensure_client(ble_device)
            data = await client.async_write_keys(payload, ble_device=ble_device)
        except ChandlerAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (
            UpdateFailed,
            ChandlerConnectionError,
            ChandlerWriteError,
            PacketError,
        ) as err:
            raise HomeAssistantError(
                f"Failed to send {payload} to the water system: {err}"
            ) from err

        self._consecutive_failures = 0
        self._apply_next_poll_interval(data)
        self._update_device_registry(data)
        self.async_set_updated_data(data)

    async def async_force_refresh(self) -> None:
        """Reset backoff and trigger an immediate poll."""
        self.update_interval = timedelta(seconds=self._poll_interval)
        await self.async_request_refresh()

    async def async_disconnect(self) -> None:
        """Release any active BLE session cleanly."""
        if self._client is not None:
            await self._client.disconnect()
            self._client = None


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Chandler Water System from a config entry."""
    _LOGGER.info("Setting up Chandler Water System integration")

    address = entry.data[CONF_ADDRESS]
    device_name = entry.data.get(CONF_DEVICE_NAME, DEFAULT_NAME)
    auth_token = entry.data[CONF_AUTH_TOKEN]

    ble_device = bluetooth.async_ble_device_from_address(
        hass, address, connectable=True
    )
    if ble_device is None:
        raise ConfigEntryNotReady(
            f"Device {address} not found. Is it powered on and in range?"
        )

    options = entry.options
    coordinator = ChandlerDataUpdateCoordinator(
        hass=hass,
        address=address,
        auth_token=auth_token,
        device_name=device_name,
        poll_interval=int(options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)),
        active_flow_poll_interval=int(
            options.get(
                CONF_ACTIVE_FLOW_POLL_INTERVAL, DEFAULT_ACTIVE_FLOW_POLL_INTERVAL
            )
        ),
        auto_sync_clock=bool(
            options.get(CONF_AUTO_SYNC_CLOCK, DEFAULT_AUTO_SYNC_CLOCK)
        ),
        clock_sync_threshold=int(
            options.get(CONF_CLOCK_SYNC_THRESHOLD, DEFAULT_CLOCK_SYNC_THRESHOLD)
        ),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "device_name": device_name,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Populate device registry metadata once entities have created the device.
    if coordinator.data is not None:
        coordinator._update_device_registry(coordinator.data)

    async_setup_services(hass)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("Chandler Water System integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Chandler Water System integration")

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator: ChandlerDataUpdateCoordinator = data["coordinator"]
        await coordinator.async_disconnect()

        if not hass.data[DOMAIN]:
            async_unload_services(hass)

    return unload_ok
