"""Test that the integration sets up and creates its entities."""
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.chandler_system.client import DeviceData
from custom_components.chandler_system.const import (
    CONF_AUTH_TOKEN,
    CONF_DEVICE_NAME,
    DOMAIN,
)

ADDRESS = "AA:BB:CC:DD:EE:FF"


class FakeClient:
    """A ChandlerClient that reports data without touching Bluetooth."""

    instances: list["FakeClient"] = []

    def __init__(self, ble_device, auth_token, data_callback=None):
        self.is_connected = False
        self.writes: list[dict] = []
        self.data = DeviceData(
            regen_active=True,
            regen_state=9,
            regen_current_position=2,
            num_regen_positions=6,
            regen_time_remaining=4,
            regen_time_type=1,
            regen_soak_timer=15,
            regen_soak_mode=True,
            regen_in_aeration=False,
            regen_counter_resettable=7,
            total_gallons_resettable=123456,
            regen_time_hours=2,
            water_hardness=25,
            day_override=7,
            reserve_capacity=30,
            total_grains_capacity=32,
            brine_tank_remaining_salt=250,
            brine_tank_total_salt=40,
            auto_reserve_mode=True,
            display_off=False,
            valve_error=0,
            valve_status=0,
            gallons_between_regens=[1234.56],
        )
        FakeClient.instances.append(self)

    def set_ble_device(self, ble_device):
        pass

    async def connect(self):
        self.is_connected = True
        return True

    async def disconnect(self):
        self.is_connected = False

    async def async_write_keys(self, payload):
        self.writes.append(payload)


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
    with patch(
        "custom_components.chandler_system.bluetooth.async_ble_device_from_address",
        return_value=object(),
    ), patch(
        "custom_components.chandler_system.ChandlerClient", FakeClient
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry


async def test_entities_are_created(hass: HomeAssistant, setup_integration):
    """Every platform should produce entities."""
    states = {
        entity_id: hass.states.get(entity_id).state
        for entity_id in hass.states.async_entity_ids()
    }

    assert states["binary_sensor.water_softener_regeneration_active"] == "on"
    assert states["sensor.water_softener_regeneration_state"] == "Moving To Brine Soak"
    assert states["sensor.water_softener_regeneration_step_time_remaining"] == "240"
    assert states["sensor.water_softener_regenerations_since_reset"] == "7"
    assert states["sensor.water_softener_gallons_since_reset"] == "1234.56"
    assert states["number.water_softener_water_hardness_setting"] == "25"
    assert states["switch.water_softener_auto_reserve_mode"] == "on"
    assert "button.water_softener_start_regeneration_now" in states


async def test_regen_position_attributes(hass: HomeAssistant, setup_integration):
    state = hass.states.get("sensor.water_softener_regeneration_position")

    assert state.state == "2"
    assert state.attributes["total_positions"] == 6


async def test_grains_capacity_scales_on_read_and_write(
    hass: HomeAssistant, setup_integration
):
    """astg reads as thousands of grains but writes as the raw 0-399 value."""
    entity_id = "number.water_softener_total_grains_capacity_setting"
    assert hass.states.get(entity_id).state == "32000"

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": 45000},
        blocking=True,
    )

    assert FakeClient.instances[0].writes == [{"astg": 45}]


async def test_salt_number_scales_to_tenths(hass: HomeAssistant, setup_integration):
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.water_softener_salt_remaining_setting", "value": 30},
        blocking=True,
    )

    assert FakeClient.instances[0].writes == [{"dbtr": 300}]


async def test_button_sends_regen_command(hass: HomeAssistant, setup_integration):
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.water_softener_start_regeneration_now"},
        blocking=True,
    )

    assert FakeClient.instances[0].writes == [{"grn": 1}]


async def test_switch_writes_boolean_as_int(hass: HomeAssistant, setup_integration):
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.water_softener_auto_reserve_mode"},
        blocking=True,
    )

    assert FakeClient.instances[0].writes == [{"asar": 0}]


async def test_services_are_registered(hass: HomeAssistant, setup_integration):
    for service in (
        "start_regeneration",
        "find_home",
        "set_salt_level",
        "reset_counters",
        "sync_clock",
    ):
        assert hass.services.has_service(DOMAIN, service)


async def test_start_regeneration_service(hass: HomeAssistant, setup_integration):
    device = next(
        iter(hass.data["device_registry"].devices.get_devices_for_config_entry_id(
            setup_integration.entry_id
        ))
    )

    await hass.services.async_call(
        DOMAIN,
        "start_regeneration",
        {"device_id": device.id, "when": "next_scheduled"},
        blocking=True,
    )

    assert FakeClient.instances[0].writes == [{"grl": 1}]


async def test_unload_disconnects(hass: HomeAssistant, setup_integration):
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert not FakeClient.instances[0].is_connected
    assert not hass.services.has_service(DOMAIN, "start_regeneration")
