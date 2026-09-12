"""Test how device JSON maps onto DeviceData."""
import pytest

from custom_components.chandler_system.client import (
    ChandlerClient,
    DeviceData,
    _parse_error_log,
    _parse_graph,
)


@pytest.fixture
def client():
    """A client with just enough wired up to exercise the JSON mapping."""
    instance = ChandlerClient.__new__(ChandlerClient)
    instance._data = DeviceData()
    instance._data_callback = None
    return instance


def test_regen_state_text(client):
    client._map_json_to_data({"grs": 10})
    assert client.data.regen_state_text == "Waiting In Brine Soak"


def test_regen_state_text_unknown_code(client):
    """An undocumented code must not become a state outside the enum options.

    Home Assistant raises ValueError if an enum sensor reports a value that is
    not in its declared options, which would abort the coordinator's update of
    every entity after this one.
    """
    from custom_components.chandler_system.const import SENSOR_DESCRIPTIONS

    client._map_json_to_data({"grs": 99})
    assert client.data.regen_state_text is None

    description = next(
        d for d in SENSOR_DESCRIPTIONS if d.key == "regen_state"
    )
    value = description.value_fn(client.data)
    assert value is None or value in description.options


def test_regen_state_raw_code_kept_as_attribute(client):
    """The undecoded code stays reachable for diagnosing a firmware change."""
    from custom_components.chandler_system.const import SENSOR_DESCRIPTIONS

    client._map_json_to_data({"grs": 99})
    description = next(
        d for d in SENSOR_DESCRIPTIONS if d.key == "regen_state"
    )

    assert description.attributes_fn(client.data) == {"raw_state": 99}


def test_every_documented_regen_state_is_a_valid_enum_option(client):
    from custom_components.chandler_system.const import (
        REGEN_STATE_MAP,
        SENSOR_DESCRIPTIONS,
    )

    description = next(
        d for d in SENSOR_DESCRIPTIONS if d.key == "regen_state"
    )
    for code in REGEN_STATE_MAP:
        client._map_json_to_data({"grs": code})
        assert description.value_fn(client.data) in description.options


def test_regen_state_text_absent(client):
    assert client.data.regen_state_text is None


@pytest.mark.parametrize(
    ("time_type", "remaining", "expected"),
    [
        (0, 45, 45),  # seconds
        (1, 5, 300),  # minutes
        (2, 8, None),  # salt pounds carry no time
    ],
)
def test_regen_step_remaining_seconds(client, time_type, remaining, expected):
    client._map_json_to_data({"drtt": time_type, "drtr": remaining})
    assert client.data.regen_step_remaining_seconds == expected


def test_regen_fields(client):
    client._map_json_to_data(
        {"gra": 1, "drcp": 3, "asnp": 6, "dria": 0, "dps": 1, "drst": 20}
    )
    data = client.data

    assert data.regen_active is True
    assert data.regen_current_position == 3
    assert data.num_regen_positions == 6
    assert data.regen_in_aeration is False
    assert data.regen_soak_mode is True
    assert data.regen_soak_timer == 20


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
    """The device always sends 20 slots, padded with zeroed entries."""
    log = _parse_error_log(
        [{"d": 0, "h": 0, "m": 0, "s": 0, "e": 0}] * 5
        + [{"d": 3, "h": 2, "m": 1, "s": 0, "e": 4}]
    )
    data = DeviceData(error_log=log)

    assert data.last_error.error_code == 4


def test_last_error_none_when_log_is_clean():
    data = DeviceData(
        error_log=_parse_error_log([{"d": 0, "h": 0, "m": 0, "s": 0, "e": 0}])
    )
    assert data.last_error is None


def test_graph_arrays_convert_from_hundredths(client):
    client._map_json_to_data({"grp": [1524, 0], "ggd": [45000], "ggr": [123456]})

    assert client.data.peak_flow_history == [15.24, 0.0]
    assert client.data.daily_gallons_history == [450.0]
    assert client.data.gallons_between_regens == [1234.56]


def test_graph_ignores_malformed_payload():
    assert _parse_graph(None) == []
    assert _parse_graph([1, "bad", 2]) == [0.01, 0.02]


def test_error_log_ignores_malformed_payload():
    assert _parse_error_log("nonsense") == []


def test_has_valve_error(client):
    assert client.data.has_valve_error is None

    client._map_json_to_data({"gve": 0})
    assert client.data.has_valve_error is False

    client._map_json_to_data({"gve": 4})
    assert client.data.has_valve_error is True


def test_partial_updates_do_not_clobber_prior_fields(client):
    """The valve pushes only what changed, so absent keys must be preserved."""
    client._map_json_to_data({"dwh": 25, "grs": 0})
    client._map_json_to_data({"grs": 5})

    assert client.data.water_hardness == 25
    assert client.data.regen_state == 5


def _sensor(key):
    from custom_components.chandler_system.const import SENSOR_DESCRIPTIONS

    return next(d for d in SENSOR_DESCRIPTIONS if d.key == key)


def test_device_time_is_rendered_as_a_clock(client):
    client._map_json_to_data({"dh": 9, "dm": 5})
    assert _sensor("device_time").value_fn(client.data) == "09:05"


def test_device_time_absent_until_the_device_reports_it(client):
    assert _sensor("device_time").value_fn(client.data) is None


def test_clock_drift_is_signed(client):
    """Positive means the valve is ahead of local time."""
    from unittest.mock import patch

    import custom_components.chandler_system.const as const

    class FakeNow:
        hour, minute, second = 10, 0, 0

    client._map_json_to_data({"dh": 10, "dm": 2, "ds": 30})
    with patch.object(const.dt_util, "now", return_value=FakeNow):
        assert _sensor("clock_drift").value_fn(client.data) == 150

    client._map_json_to_data({"dh": 9, "dm": 58, "ds": 0})
    with patch.object(const.dt_util, "now", return_value=FakeNow):
        assert _sensor("clock_drift").value_fn(client.data) == -120


def test_clock_drift_across_midnight_is_not_most_of_a_day(client):
    """A reading either side of midnight is minutes apart, not 23 hours."""
    from unittest.mock import patch

    import custom_components.chandler_system.const as const

    class JustBeforeMidnight:
        hour, minute, second = 23, 59, 0

    client._map_json_to_data({"dh": 0, "dm": 1, "ds": 0})
    with patch.object(const.dt_util, "now", return_value=JustBeforeMidnight):
        assert _sensor("clock_drift").value_fn(client.data) == 120
