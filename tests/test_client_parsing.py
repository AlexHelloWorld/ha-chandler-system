"""Test how device JSON maps onto DeviceData and sensor descriptions."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

import custom_components.chandler_system.const as const
from custom_components.chandler_system.client import (
    ChandlerClient,
    DeviceData,
    _parse_error_log,
    _parse_graph,
    _parse_int_list,
)


@pytest.fixture
def client():
    """A client with just enough wired up to exercise JSON mapping."""
    instance = ChandlerClient.__new__(ChandlerClient)
    instance._data = DeviceData()
    instance._data_callback = None
    return instance


def _sensor(key: str):
    return next(d for d in const.SENSOR_DESCRIPTIONS if d.key == key)


def test_firmware_c618_legacy_keys_and_hundredths_gallons(client):
    """C6.18 and older use dlf/dlsa/dlsb/dlvt and divide shgt/shgs/shgr by 100."""
    client._map_json_to_data(
        {
            "dlf": 618,
            "dlsa": 885281167,
            "dlsb": 166204050,
            "dlvt": 1,
            "dlvs": 4,
            "dlr": 1,
            "shgt": 123475,
            "shgs": 45025,
            "shgr": 10050,
        }
    )
    data = client.data

    assert data.firmware_version == 618
    assert data.firmware_version_text == "C6.18"
    assert data.serial_number == "34C4518F9E81292"
    assert data.valve_type_text == "Metered Softener"
    assert data.valve_series_text == "Series 4 (CS125)"
    assert data.regen_motor_in_progress is True
    assert data.history_gallon_divisor == 100.0
    assert data.total_gallons_value == 1234.75
    assert data.gallons_since_last_regen_value == 450.25
    assert data.total_gallons_resettable_value == 100.5


def test_firmware_c619_new_keys_and_quarter_gallons(client):
    """C6.19+ uses gef/gesa/gesb/gedt and divides shgt/shgs/shgr by 4."""
    client._map_json_to_data(
        {
            "gef": 619,
            "gesa": 885281167,
            "gesb": 166204050,
            "gedt": 4,
            "shgt": 4939,
            "shgs": 400,
            "shgr": 100,
        }
    )
    data = client.data

    assert data.firmware_version == 619
    assert data.firmware_version_text == "C6.19"
    assert data.serial_number == "34C4518F9E81292"
    assert data.valve_type_text == "Backwashing Filter"
    assert data.history_gallon_divisor == 4.0
    assert data.total_gallons_value == 1234.75
    assert data.gallons_since_last_regen_value == 100.0
    assert data.total_gallons_resettable_value == 25.0


def test_unknown_firmware_defaults_to_c618_hundredths(client):
    """If firmware is absent, fall back safely to C6.18 hundredths scaling."""
    client._map_json_to_data({"shgt": 123475})
    assert client.data.history_gallon_divisor == 100.0
    assert client.data.total_gallons_value == 1234.75


def test_regen_state_text(client):
    client._map_json_to_data({"grs": 10})
    assert client.data.regen_state_text == "Waiting In Brine Soak"


def test_regen_state_text_unknown_code(client):
    """An undocumented code must not become a state outside the enum options."""
    client._map_json_to_data({"grs": 99})
    assert client.data.regen_state_text is None

    description = _sensor("regen_state")
    value = description.value_fn(client.data)
    assert value is None or value in description.options
    assert description.attributes_fn(client.data) == {"raw_state": 99}


def test_every_documented_regen_state_is_a_valid_enum_option(client):
    description = _sensor("regen_state")
    for code in const.REGEN_STATE_MAP:
        client._map_json_to_data({"grs": code})
        assert description.value_fn(client.data) in description.options


@pytest.mark.parametrize(
    ("time_type", "remaining", "expected_sec", "expected_min"),
    [
        (0, 45, 45, 0.75),  # seconds
        (1, 5, 300, 5.0),  # minutes
        (2, 8, None, None),  # salt pounds carry no time
    ],
)
def test_regen_step_remaining_conversions(
    client, time_type, remaining, expected_sec, expected_min
):
    client._map_json_to_data({"gra": 1, "drtt": time_type, "drtr": remaining})
    assert client.data.regen_step_remaining_seconds == expected_sec
    assert client.data.regen_step_remaining_minutes == expected_min


def test_regen_stage_and_total_minutes_remaining(client):
    """Active regen reports stage and sums current + remaining aspt step times."""
    client._map_json_to_data(
        {
            "gra": 1,
            "drcp": 2,
            "asnp": 4,
            "drtt": 1,
            "drtr": 15,
            "dps": 0,
            "dria": 0,
            "aspt": [0, 10, 60, 10, 8],
        }
    )
    assert client.data.regen_stage_text == "Position 2 of 4"
    # 15 min left in pos 2 + 10 min (pos 3) + 8 min (pos 4) = 33.0 min
    assert client.data.regen_total_remaining_minutes == 33.0
    assert _sensor("cycle_position_times").value_fn(client.data) == "10, 60, 10, 8"


def test_regen_stage_idle_brine_soak_and_aeration(client):
    client._map_json_to_data({"gra": 0, "drcp": 0, "drtt": 1, "drtr": 12})
    assert client.data.regen_stage_text == "Idle"
    assert client.data.regen_step_remaining_minutes == 0.0
    assert client.data.regen_total_remaining_minutes == 0.0

    client._map_json_to_data({"gra": 1, "dps": 1, "drst": 25})
    assert client.data.regen_stage_text == "Brine Soak"

    client._map_json_to_data({"gra": 1, "dps": 0, "dria": 1})
    assert client.data.regen_stage_text == "Aeration"


def test_valve_status_bits(client):
    client._map_json_to_data({"gvs": 0b11100000})
    assert client.data.salt_low is True
    assert client.data.water_state is True
    assert client.data.bypass_state is True

    client._map_json_to_data({"gvs": 0})
    assert client.data.salt_low is False
    assert client.data.water_state is False
    assert client.data.bypass_state is False


def test_has_valve_error_handles_omitted_gve(client):
    assert client.data.has_valve_error is None

    # Populated snapshot without gve means healthy (False), not unknown.
    client.data.raw_data["dwh"] = 15
    assert client.data.has_valve_error is False

    client._map_json_to_data({"gve": 4})
    assert client.data.has_valve_error is True

    client._map_json_to_data({"gve": 0})
    assert client.data.has_valve_error is False


def test_present_flow_gpm(client):
    assert client.data.present_flow_gpm is None

    client.data.raw_data["dwh"] = 15
    assert client.data.present_flow_gpm == 0.0

    client._map_json_to_data({"gpf": 568})
    assert client.data.present_flow_gpm == 5.68


def test_error_log_decoding(client):
    client._map_json_to_data(
        {
            "shel": [
                {"d": 11, "h": 1, "m": 8, "s": 45, "e": 6},
                {"d": 0, "h": 0, "m": 0, "s": 0, "e": 0},
            ]
        }
    )

    assert len(client.data.error_log) == 2
    assert client.data.last_error.as_dict() == {
        "days_in_operation": 11,
        "time": "01:08:45",
        "error_code": 6,
        "error": "No Encoder Slots (No Current)",
    }


def test_last_error_skips_empty_slots():
    log = _parse_error_log(
        [{"d": 0, "h": 0, "m": 0, "s": 0, "e": 0}] * 5
        + [{"d": 3, "h": 2, "m": 1, "s": 0, "e": 4}]
    )
    assert DeviceData(error_log=log).last_error.error_code == 4


def test_graph_and_int_list_parsers(client):
    client._map_json_to_data(
        {"grp": [1524, 0], "ggd": [45000], "ggr": [123456], "aspt": [0, 10, 60]}
    )
    assert client.data.peak_flow_history == [15.24, 0.0]
    assert client.data.daily_gallons_history == [450.0]
    assert client.data.gallons_between_regens == [1234.56]
    assert client.data.cycle_position_times == [0, 10, 60]

    assert _parse_graph(None) == []
    assert _parse_graph([1, "bad", 2]) == [0.01, 0.02]
    assert _parse_int_list("bad") == []
    assert _parse_error_log("nonsense") == []


def test_clock_drift_uses_sample_timestamp_not_render_time(client):
    """Drift stays stable between polls instead of growing every second."""
    sampled_at = datetime(2026, 11, 27, 10, 0, 0, tzinfo=timezone.utc)
    rendered_later = datetime(2026, 11, 27, 10, 4, 30, tzinfo=timezone.utc)

    with patch(
        "custom_components.chandler_system.client.dt_util.now",
        return_value=sampled_at,
    ):
        client._map_json_to_data({"dh": 10, "dm": 2, "ds": 30})

    with patch.object(const.dt_util, "now", return_value=rendered_later):
        # Still 150s ahead at sample time, NOT -120s due to 4.5 min poll age!
        assert _sensor("clock_drift").value_fn(client.data) == 150


def test_clock_drift_across_midnight_and_without_seconds(client):
    just_before_midnight = datetime(2026, 11, 27, 23, 59, 45, tzinfo=timezone.utc)
    with patch(
        "custom_components.chandler_system.client.dt_util.now",
        return_value=just_before_midnight,
    ):
        client._map_json_to_data({"dh": 0, "dm": 1})

    # Seconds omitted -> minute-resolution comparison: 00:01 - 23:59 = +120s
    assert _sensor("clock_drift").value_fn(client.data) == 120
    assert _sensor("device_time").value_fn(client.data) == "00:01"


def test_writable_fields_parsed(client):
    client._map_json_to_data(
        {
            "dcdo": 3,
            "asr": 14,
            "dpe": 1,
            "dpd": 2,
            "asad": 4,
            "ascp": 2,
            "dbts": 200,
            "dbtr": 1500,
        }
    )
    d = client.data
    assert d.current_day_override == 3
    assert d.regen_day_override == 14
    assert d.prefill_enabled is True
    assert d.prefill_duration == 2
    assert d.aeration_days == 4
    assert d.chlorine_pulses == 2
    assert d.salt_level_percent == 75.0
