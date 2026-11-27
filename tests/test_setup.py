"""Test integration setup, polling cadence, auto clock sync, entities, and services."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.chandler_system.const as const
from custom_components.chandler_system.client import (
    ChandlerAuthError,
    ChandlerConnectionError,
    DeviceData,
)
from custom_components.chandler_system.const import (
    CONF_ACTIVE_FLOW_POLL_INTERVAL,
    CONF_AUTH_TOKEN,
    CONF_AUTO_SYNC_CLOCK,
    CONF_CLOCK_SYNC_THRESHOLD,
    CONF_DEVICE_NAME,
    CONF_POLL_INTERVAL,
    DOMAIN,
)

ADDRESS = "AA:BB:CC:DD:EE:FF"


def _sample_data(**overrides) -> DeviceData:
    defaults = {
        "firmware_version": 618,
        "serial_number_a": 885281167,
        "serial_number_b": 166204050,
        "valve_type": 1,
        "valve_series": 4,
        "regen_motor_in_progress": False,
        "regen_active": True,
        "regen_state": 9,
        "regen_current_position": 2,
        "num_regen_positions": 6,
        "regen_time_remaining": 4,
        "regen_time_type": 1,
        "regen_soak_timer": 15,
        "regen_soak_mode": False,
        "regen_in_aeration": False,
        "cycle_position_times": [0, 10, 60, 10, 8, 5, 3],
        "regen_counter_resettable": 7,
        "total_gallons_resettable": 123456,
        "total_gallons": 500000,
        "gallons_since_last_regen": 25000,
        "regen_time_hours": 2,
        "time_hours": 2,
        "time_minutes": 0,
        "time_seconds": 0,
        "clock_sample_time": datetime(2026, 11, 27, 2, 0, 0, tzinfo=timezone.utc),
        "water_hardness": 25,
        "day_override": 7,
        "current_day_override": 3,
        "regen_day_override": 14,
        "prefill_enabled": True,
        "prefill_duration": 2,
        "reserve_capacity": 30,
        "total_grains_capacity": 32,
        "brine_tank_remaining_salt": 250,
        "brine_tank_total_salt": 200,
        "auto_reserve_mode": True,
        "display_off": False,
        "valve_error": None,
        "valve_status": 0,
        "present_flow": 0,
        "gallons_between_regens": [1234.56],
        "raw_data": {"dlf": 618},
    }
    defaults.update(overrides)
    return DeviceData(**defaults)


class FakeClient:
    """A polling ChandlerClient fake that requires no Bluetooth hardware."""

    instances: list["FakeClient"] = []
    next_poll_error: Exception | None = None
    next_poll_data: DeviceData | None = None

    def __init__(self, ble_device, auth_token, data_callback=None):
        self.writes: list[dict] = []
        self.poll_calls = 0
        self.data = _sample_data()
        FakeClient.instances.append(self)

    def set_ble_device(self, ble_device):
        pass

    async def async_poll(self, ble_device=None, *, post_poll_write=None):
        self.poll_calls += 1
        if FakeClient.next_poll_error is not None:
            err = FakeClient.next_poll_error
            FakeClient.next_poll_error = None
            raise err
        if FakeClient.next_poll_data is not None:
            self.data = FakeClient.next_poll_data
            FakeClient.next_poll_data = None
        if post_poll_write is not None:
            payload = post_poll_write(self.data)
            if payload:
                self.writes.append(payload)
        return self.data

    async def async_write_keys(self, payload, ble_device=None):
        self.writes.append(payload)
        return self.data

    async def disconnect(self):
        pass


@pytest.fixture
def entry(hass: HomeAssistant):
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: ADDRESS,
            CONF_AUTH_TOKEN: "8dffdfbd40cc4b868df81d48463b20f1",
            CONF_DEVICE_NAME: "Water Softener",
        },
        unique_id=ADDRESS,
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
async def setup_integration(hass: HomeAssistant, entry):
    """Set up the integration with Bluetooth and the BLE client faked out."""
    FakeClient.instances.clear()
    FakeClient.next_poll_error = None
    FakeClient.next_poll_data = None
    with patch(
        "custom_components.chandler_system.bluetooth.async_ble_device_from_address",
        return_value=object(),
    ), patch("custom_components.chandler_system.ChandlerClient", FakeClient):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry


async def test_entities_and_device_metadata(hass: HomeAssistant, setup_integration):
    """All platforms create entities and device registry receives handshake metadata."""
    states = {
        entity_id: hass.states.get(entity_id).state
        for entity_id in hass.states.async_entity_ids()
    }

    assert states["binary_sensor.water_softener_regeneration_active"] == "on"
    assert states["binary_sensor.water_softener_valve_error"] == "off"
    assert states["sensor.water_softener_regeneration_state"] == "Moving To Brine Soak"
    assert states["sensor.water_softener_regeneration_stage"] == "Position 2 of 6"
    assert states["sensor.water_softener_regeneration_step_time_remaining"] == "4.0"
    # 4 min left in pos 2 + 10 + 8 + 5 + 3 = 30.0 min
    assert states["sensor.water_softener_regeneration_total_time_remaining"] == "30.0"
    assert states["sensor.water_softener_regenerations_since_reset"] == "7"
    assert states["sensor.water_softener_gallons_since_reset"] == "1234.56"
    assert states["sensor.water_softener_firmware_version"] == "C6.18"
    assert states["sensor.water_softener_valve_type"] == "Metered Softener"
    assert states["sensor.water_softener_device_time"] == "02:00:00"
    assert states["number.water_softener_water_hardness"] == "25"
    assert states["number.water_softener_current_day_override"] == "3"
    assert states["number.water_softener_regen_day_override"] == "14"
    assert states["number.water_softener_brine_prefill_duration"] == "2"
    assert states["switch.water_softener_auto_reserve_mode"] == "on"
    assert states["switch.water_softener_brine_prefill"] == "on"
    assert "button.water_softener_refresh_now" in states
    assert "button.water_softener_refill_salt_tank" in states
    assert "button.water_softener_reset_regeneration_counter" in states
    assert "button.water_softener_reset_gallons_counter" in states

    # Verify HA Water Dashboard device_class
    total_gal = hass.states.get("sensor.water_softener_total_gallons_processed")
    assert total_gal.attributes["device_class"] == "water"
    assert total_gal.state == "5000.0"

    # Verify Device Registry populated from Device List API
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, ADDRESS)})
    assert device is not None
    assert device.sw_version == "C6.18"
    assert device.hw_version == "Series 4 (CS125)"
    assert device.model == "Metered Softener"
    assert device.serial_number == "34C4518F9E81292"


async def test_writable_controls_send_expected_keys(
    hass: HomeAssistant, setup_integration
):
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.water_softener_total_grains_capacity", "value": 45000},
        blocking=True,
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.water_softener_brine_prefill_duration", "value": 3},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.water_softener_brine_prefill"},
        blocking=True,
    )
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.water_softener_refill_salt_tank"},
        blocking=True,
    )
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.water_softener_reset_gallons_counter"},
        blocking=True,
    )

    assert FakeClient.instances[0].writes == [
        {"astg": 45},
        {"dpd": 3},
        {"dpe": 0},
        {"dbtr": 2000},  # 200 lb capacity * 10 tenths
        {"shgr": 0},
    ]


async def test_flow_aware_adaptive_polling(hass: HomeAssistant, setup_integration):
    """Active flow speeds polling to 15s; idle returns to 60s (no regen speedup)."""
    coordinator = hass.data[DOMAIN][setup_integration.entry_id]["coordinator"]
    # Initial sample has regen_active=True, present_flow=0 -> stays at normal 60s
    assert coordinator.update_interval == timedelta(seconds=60)

    FakeClient.next_poll_data = _sample_data(present_flow=350, regen_active=False)
    await coordinator.async_refresh()
    assert coordinator.update_interval == timedelta(seconds=15)

    FakeClient.next_poll_data = _sample_data(present_flow=0, regen_active=False)
    await coordinator.async_refresh()
    assert coordinator.update_interval == timedelta(seconds=60)


async def test_transient_failures_retain_data_and_backoff(
    hass: HomeAssistant, setup_integration
):
    """1-2 transient BLE failures keep entities available; 3rd marks unavailable."""
    coordinator = hass.data[DOMAIN][setup_integration.entry_id]["coordinator"]

    FakeClient.next_poll_error = ChandlerConnectionError("phone app connected")
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert coordinator.consecutive_failures == 1
    total_state = hass.states.get("sensor.water_softener_total_gallons_processed")
    assert total_state.state == "5000.0"

    FakeClient.next_poll_error = ChandlerConnectionError("still busy")
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert coordinator.consecutive_failures == 2
    assert coordinator.update_interval == timedelta(seconds=120)

    FakeClient.next_poll_error = ChandlerConnectionError("offline")
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    assert coordinator.consecutive_failures == 3


async def test_auto_clock_sync_triggers_on_drift_and_skips_during_regen(
    hass: HomeAssistant, setup_integration
):
    """Auto clock sync runs inside poll when drifted & idle, with 1h cooldown."""
    coordinator = hass.data[DOMAIN][setup_integration.entry_id]["coordinator"]
    client = FakeClient.instances[0]
    client.writes.clear()

    # Drifted by 5 min, but regen_active=True -> must NOT sync!
    FakeClient.next_poll_data = _sample_data(
        regen_active=True,
        time_hours=10,
        time_minutes=5,
        time_seconds=0,
        clock_sample_time=datetime(2026, 11, 27, 10, 0, 0, tzinfo=timezone.utc),
    )
    await coordinator.async_refresh()
    assert client.writes == []

    # Drifted by 5 min and idle -> syncs inside the same poll!
    FakeClient.next_poll_data = _sample_data(
        regen_active=False,
        time_hours=10,
        time_minutes=5,
        time_seconds=0,
        clock_sample_time=datetime(2026, 11, 27, 10, 0, 0, tzinfo=timezone.utc),
    )
    await coordinator.async_refresh()
    assert len(client.writes) == 1
    assert set(client.writes[0]) == {"dh", "dm", "ds"}

    # Immediate next poll still drifted -> 1h cooldown prevents repeat spam
    FakeClient.next_poll_data = _sample_data(
        regen_active=False,
        time_hours=10,
        time_minutes=5,
        time_seconds=0,
        clock_sample_time=datetime(2026, 11, 27, 10, 0, 0, tzinfo=timezone.utc),
    )
    await coordinator.async_refresh()
    assert len(client.writes) == 1


async def test_auth_error_triggers_reauth(hass: HomeAssistant, setup_integration):
    coordinator = hass.data[DOMAIN][setup_integration.entry_id]["coordinator"]
    FakeClient.next_poll_error = ChandlerAuthError("bad token")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(f["context"].get("source") == "reauth" for f in flows)


async def test_set_cycle_position_times_service(hass: HomeAssistant, setup_integration):
    device = next(
        iter(
            dr.async_get(hass).devices.get_devices_for_config_entry_id(
                setup_integration.entry_id
            )
        )
    )
    await hass.services.async_call(
        DOMAIN,
        "set_cycle_position_times",
        {"device_id": device.id, "positions": [12, 55, 10, 8]},
        blocking=True,
    )
    # Preserves index 0 (service position = 0)
    assert FakeClient.instances[0].writes == [{"aspt": [0, 12, 55, 10, 8]}]


async def test_options_flow_updates_intervals(hass: HomeAssistant, setup_integration):
    result = await hass.config_entries.options.async_init(setup_integration.entry_id)
    assert result["type"] == "form"

    updated = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_POLL_INTERVAL: 45,
            CONF_ACTIVE_FLOW_POLL_INTERVAL: 15,
            CONF_AUTO_SYNC_CLOCK: False,
            CONF_CLOCK_SYNC_THRESHOLD: 180,
        },
    )
    assert updated["type"] == "create_entry"
    assert setup_integration.options[CONF_POLL_INTERVAL] == 45
    assert setup_integration.options[CONF_AUTO_SYNC_CLOCK] is False


async def test_refill_button_raises_without_capacity(
    hass: HomeAssistant, setup_integration
):
    coordinator = hass.data[DOMAIN][setup_integration.entry_id]["coordinator"]
    coordinator.data.brine_tank_total_salt = None

    with pytest.raises(HomeAssistantError, match="capacity"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.water_softener_refill_salt_tank"},
            blocking=True,
        )


def test_fake_client_matches_the_real_interface():
    """Guard against FakeClient drifting from ChandlerClient."""
    import inspect

    from custom_components.chandler_system.client import ChandlerClient

    for name in (
        "__init__",
        "async_poll",
        "async_write_keys",
        "disconnect",
        "set_ble_device",
    ):
        real = inspect.signature(getattr(ChandlerClient, name))
        fake = inspect.signature(getattr(FakeClient, name))
        assert list(real.parameters) == list(fake.parameters), name


async def test_unload_cleans_up_services(hass: HomeAssistant, setup_integration):
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "start_regeneration")
    assert not hass.services.has_service(DOMAIN, "set_cycle_position_times")
    assert const.DOMAIN == DOMAIN
