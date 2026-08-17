"""Tests for the value handling of the Eaton xStorage Home sensor platform."""

from datetime import UTC, datetime
from typing import Any

import pytest
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.sensor.const import (
    DEVICE_CLASS_STATE_CLASSES as HA_DEVICE_CLASS_STATE_CLASSES,
)
from homeassistant.components.sensor.const import DEVICE_CLASS_UNITS
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.eaton_battery_storage.const import DOMAIN, sensor_unique_id
from custom_components.eaton_battery_storage.sensor import (
    DEVICE_CLASS_STATE_CLASSES,
    SENSOR_TYPES,
)

from .conftest import (
    MINOR_VERSION,
    SERIAL,
    STATUS_RESULT,
    TECH_INPUT,
    VERSION,
    mock_device,
)


async def setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up a technician config entry and return it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data=TECH_INPUT,
        version=VERSION,
        minor_version=MINOR_VERSION,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def sensor_state(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str:
    """Return the state of the sensor for a coordinator data key."""
    entity_id = er.async_get(hass).async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, sensor_unique_id(entry.entry_id, key)
    )
    return hass.states.get(entity_id).state


async def test_state_of_charge_is_recorded_as_a_measurement(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The state of charge needs a state class to reach long term statistics."""
    mock_device(
        aioclient_mock,
        status={**STATUS_RESULT, "energyFlow": {"stateOfCharge": 62}},
    )
    entry = await setup_entry(hass)

    entity_id = er.async_get(hass).async_get_entity_id(
        SENSOR_DOMAIN,
        DOMAIN,
        sensor_unique_id(entry.entry_id, "status.energyFlow.stateOfCharge"),
    )
    state = hass.states.get(entity_id)

    assert state.state == "62"
    assert state.attributes["state_class"] is SensorStateClass.MEASUREMENT


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        pytest.param(
            "technical_status.gridVoltage",
            SensorStateClass.MEASUREMENT,
            id="voltage",
        ),
        pytest.param(
            "technical_status.bmsCurrent",
            SensorStateClass.MEASUREMENT,
            id="current",
        ),
        pytest.param(
            "technical_status.bmsTemperature",
            SensorStateClass.MEASUREMENT,
            id="temperature",
        ),
        pytest.param(
            "maintenance_diagnostics.cpuUsage.used",
            SensorStateClass.MEASUREMENT,
            id="no-device-class",
        ),
        pytest.param(
            "technical_status.bmsTotalCharge",
            SensorStateClass.TOTAL,
            id="lifetime-coulomb-counter",
        ),
        pytest.param(
            "status.today.gridConsumption",
            SensorStateClass.TOTAL_INCREASING,
            id="daily-energy",
        ),
        pytest.param(
            "status.last30daysEnergyFlow.gridConsumption",
            None,
            id="rolling-window-energy",
        ),
        pytest.param("technical_status.bmsState", None, id="enum"),
        pytest.param("device.firmwareVersion", None, id="version-string"),
        pytest.param("status.energyFlow.gridRole", None, id="role-string"),
        pytest.param("technical_status.inverterPowerRating", None, id="static-rating"),
        pytest.param("status.currentMode.parameters.soc", None, id="setpoint"),
    ],
)
async def test_state_class_matches_the_kind_of_value(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    key: str,
    expected: SensorStateClass | None,
) -> None:
    """Only numeric readings get a state class, and it matches how they change."""
    mock_device(aioclient_mock)
    entry = await setup_entry(hass)

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, sensor_unique_id(entry.entry_id, key)
    )
    # Read the registry rather than the state, so disabled entities are covered.
    capabilities = registry.async_get(entity_id).capabilities or {}

    assert capabilities.get("state_class") is expected


def test_declared_state_classes_are_possible_for_their_device_class() -> None:
    """Home Assistant rejects state classes a device class cannot have."""
    for key, description in SENSOR_TYPES.items():
        device_class = description["device_class"]
        state_class = description.get("state_class") or DEVICE_CLASS_STATE_CLASSES.get(
            device_class
        )
        if device_class is None or state_class is None:
            continue
        allowed = HA_DEVICE_CLASS_STATE_CLASSES[SensorDeviceClass(device_class)]
        assert state_class in allowed, (
            f"{key} declares {state_class} but {device_class} allows {allowed}"
        )


def test_declared_units_are_valid_for_their_device_class() -> None:
    """A device class only accepts the units Home Assistant knows how to convert."""
    for key, description in SENSOR_TYPES.items():
        device_class = description["device_class"]
        if device_class is None:
            continue
        allowed = DEVICE_CLASS_UNITS[SensorDeviceClass(device_class)]
        assert description["unit"] in allowed, (
            f"{key} declares unit {description['unit']!r}, expected one of {allowed}"
        )


@pytest.mark.parametrize(
    ("status", "key", "expected"),
    [
        pytest.param(
            {"energyFlow": {"gridRole": "PRODUCER"}},
            "status.energyFlow.gridRole",
            "Producing",
            id="grid_role_producer",
        ),
        pytest.param(
            {"energyFlow": {"nonCriticalLoadRole": "CONSUMER"}},
            "status.energyFlow.nonCriticalLoadRole",
            "Consuming",
            id="load_role_consumer",
        ),
        pytest.param(
            {"energyFlow": {"criticalLoadRole": "DISCONNECTED"}},
            "status.energyFlow.criticalLoadRole",
            "Disconnected",
            id="load_role_disconnected",
        ),
        pytest.param(
            {"energyFlow": {"operationMode": "BASIC"}},
            "status.energyFlow.operationMode",
            "Basic",
            id="operation_mode_basic",
        ),
        pytest.param(
            {"currentMode": {"recurrence": "DEFAULT_EVENT"}},
            "status.currentMode.recurrence",
            "Default",
            id="recurrence_default_event",
        ),
        pytest.param(
            {"currentMode": {"type": "DEFAULT"}},
            "status.currentMode.type",
            "Default",
            id="type_default",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_enum_values_seen_on_real_hardware_are_labelled(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: dict[str, Any],
    key: str,
    expected: str,
) -> None:
    """Values the API documentation omits still reach the user as readable text."""
    mock_device(aioclient_mock, status={**STATUS_RESULT, **status})
    entry = await setup_entry(hass)

    assert sensor_state(hass, entry, key) == expected


@pytest.mark.parametrize(
    ("technical_status", "key", "expected"),
    [
        pytest.param(
            {"bmsHighestCellVoltage": 3500, "bmsLowestCellVoltage": 3400},
            "technical_status.bmsCellVoltageDelta",
            "100.0",
            id="cell_voltage_delta",
        ),
        pytest.param(
            {"bmsLowestCellVoltage": 3400},
            "technical_status.bmsCellVoltageDelta",
            STATE_UNKNOWN,
            id="cell_voltage_delta_without_highest",
        ),
        pytest.param(
            {"bmsHighestCellVoltage": 900, "bmsLowestCellVoltage": 3400},
            "technical_status.bmsCellVoltageDelta",
            STATE_UNKNOWN,
            id="cell_voltage_delta_with_implausible_highest",
        ),
        pytest.param(
            {"bmsHighestCellVoltage": 3500, "bmsLowestCellVoltage": 900},
            "technical_status.bmsCellVoltageDelta",
            STATE_UNKNOWN,
            id="cell_voltage_delta_with_implausible_lowest",
        ),
        pytest.param(
            {"bmsHighestCellVoltage": "n/a", "bmsLowestCellVoltage": 3400},
            "technical_status.bmsCellVoltageDelta",
            STATE_UNKNOWN,
            id="cell_voltage_delta_with_non_numeric_reading",
        ),
        pytest.param(
            {"bmsHighestCellVoltage": 3500},
            "technical_status.bmsHighestCellVoltage",
            "3500",
            id="cell_voltage",
        ),
        pytest.param(
            {"bmsHighestCellVoltage": 900},
            "technical_status.bmsHighestCellVoltage",
            STATE_UNKNOWN,
            id="implausible_cell_voltage_is_dropped",
        ),
        pytest.param(
            {"bmsFaultCode": ["OVER_VOLTAGE", "GENERAL"]},
            "technical_status.bmsFaultCode",
            "Over-voltage, General BMS fault",
            id="fault_codes_are_translated",
        ),
        pytest.param(
            {"bmsFaultCode": ["NOT_A_KNOWN_CODE"]},
            "technical_status.bmsFaultCode",
            "NOT_A_KNOWN_CODE",
            id="unknown_fault_code_is_passed_through",
        ),
        pytest.param(
            {"bmsFaultCode": None},
            "technical_status.bmsFaultCode",
            "No fault",
            id="null_fault_code_reads_as_no_fault",
        ),
        pytest.param(
            {"bmsFaultCode": []},
            "technical_status.bmsFaultCode",
            "No fault",
            id="empty_fault_code_list_reads_as_no_fault",
        ),
        pytest.param(
            {"bmsFaultCode": "OVER_VOLTAGE"},
            "technical_status.bmsFaultCode",
            "OVER_VOLTAGE",
            id="scalar_fault_code_is_passed_through",
        ),
        pytest.param(
            {"bmsState": "BAT_CHARGING"},
            "technical_status.bmsState",
            "Charging",
            id="bms_state_is_translated",
        ),
        pytest.param(
            {"bmsState": "BAT_SOMETHING_NEW"},
            "technical_status.bmsState",
            "BAT_SOMETHING_NEW",
            id="unknown_bms_state_is_passed_through",
        ),
        pytest.param(
            {"bmsMaxTemperature": 25.44},
            "technical_status.bmsMaxTemperature",
            "25.4",
            id="temperature_is_rounded",
        ),
        pytest.param(
            {"bmsMaxTemperature": 0},
            "technical_status.bmsMaxTemperature",
            STATE_UNKNOWN,
            id="zero_temperature_is_dropped",
        ),
        pytest.param(
            {"gridFrequency": 0},
            "technical_status.gridFrequency",
            "0",
            id="zero_grid_frequency_is_a_grid_outage",
        ),
        pytest.param(
            {},
            "technical_status.bmsState",
            STATE_UNKNOWN,
            id="missing_key_reads_as_unknown",
        ),
    ],
)
async def test_technical_status_values(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    technical_status: dict[str, Any],
    key: str,
    expected: str,
) -> None:
    """Technical status values are filtered and translated for display."""
    mock_device(aioclient_mock, technical_status=technical_status)
    entry = await setup_entry(hass)

    assert sensor_state(hass, entry, key) == expected


@pytest.mark.parametrize(
    ("status", "key", "expected"),
    [
        pytest.param(
            {"currentMode": {"command": "SET_CHARGE"}},
            "status.currentMode.command",
            "Charge",
            id="mode_command_is_translated",
        ),
        pytest.param(
            {
                "currentMode": {
                    "command": "SET_CHARGE",
                    "parameters": {"action": "ACTION_DISCHARGE"},
                }
            },
            "status.currentMode.command",
            "Discharge",
            id="discharge_action_wins_over_the_echoed_command",
        ),
        pytest.param(
            {"currentMode": {"command": "SET_DISCHARGE"}},
            "status.currentMode.command",
            "Discharge",
            id="discharge_without_an_action_is_translated",
        ),
        pytest.param(
            {"currentMode": {"type": "SCHEDULE"}},
            "status.currentMode.type",
            "Scheduled",
            id="mode_type_is_translated",
        ),
        pytest.param(
            {"energyFlow": {"batteryStatus": "BAT_DISCHARGING"}},
            "status.energyFlow.batteryStatus",
            "Discharging",
            id="battery_status_is_translated",
        ),
        pytest.param(
            {"currentMode": {"startTime": 1154}},
            "status.currentMode.startTime",
            "11:54",
            id="numeric_time_is_formatted",
        ),
        pytest.param(
            {"currentMode": {"startTime": "0905"}},
            "status.currentMode.startTime",
            "09:05",
            id="string_time_is_formatted",
        ),
        pytest.param(
            {"currentMode": {"startTime": 9999}},
            "status.currentMode.startTime",
            "9999",
            id="out_of_range_time_is_passed_through",
        ),
    ],
)
async def test_status_values(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: dict[str, Any],
    key: str,
    expected: str,
) -> None:
    """Status values are formatted for display."""
    mock_device(aioclient_mock, status={**STATUS_RESULT, **status})
    entry = await setup_entry(hass)

    assert sensor_state(hass, entry, key) == expected


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        pytest.param(
            "maintenance_diagnostics.ramUsage.used", "1.0", id="ram_bytes_to_mebibytes"
        ),
        pytest.param(
            "maintenance_diagnostics.cpuUsage.used", "12.35", id="cpu_usage_is_rounded"
        ),
    ],
)
async def test_maintenance_diagnostics_values(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    key: str,
    expected: str,
) -> None:
    """Maintenance values are converted to the units the sensors declare."""
    mock_device(
        aioclient_mock,
        maintenance_diagnostics={
            "ramUsage": {"used": 1048576},
            "cpuUsage": {"used": 12.3456},
        },
    )
    entry = await setup_entry(hass)

    assert sensor_state(hass, entry, key) == expected


async def test_a_malformed_notification_does_not_break_the_sensor(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The device has been seen listing a bare string among the notifications.

    Reading that as a notification raises while the state is being written,
    which takes the whole entity down rather than just the one bad entry.
    """
    mock_device(
        aioclient_mock,
        notifications={"total": 2, "results": ["junk", {"alertId": "a1"}]},
    )
    entry = await setup_entry(hass)

    entity_id = er.async_get(hass).async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{entry.entry_id}_notifications"
    )
    state = hass.states.get(entity_id)

    assert state.state == "2"
    assert [item["alert_id"] for item in state.attributes["notifications"]] == ["a1"]


@pytest.mark.parametrize("unique_id_suffix", ["notifications", "latest_notification"])
async def test_notification_times_are_read_as_milliseconds(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    unique_id_suffix: str,
) -> None:
    """Notification records timestamp in milliseconds, unlike the device record."""
    mock_device(
        aioclient_mock,
        notifications={
            "total": 1,
            "results": [
                {
                    "alertId": "a1",
                    "subType": "NO_UTILITY",
                    "createdAt": 1786919563000,
                    "updatedAt": 1786919563000,
                }
            ],
        },
    )
    entry = await setup_entry(hass)

    entity_id = er.async_get(hass).async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{entry.entry_id}_{unique_id_suffix}"
    )
    attributes = hass.states.get(entity_id).attributes
    if unique_id_suffix == "notifications":
        attributes = attributes["notifications"][0]

    expected = datetime(2026, 8, 16, 22, 32, 43, tzinfo=UTC)
    assert attributes["created_at"] == expected
    assert attributes["updated_at"] == expected


async def test_a_notification_without_times_reports_none(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A record missing its timestamps must not be read as 1970."""
    mock_device(
        aioclient_mock,
        notifications={"total": 1, "results": [{"alertId": "a1"}]},
    )
    entry = await setup_entry(hass)

    entity_id = er.async_get(hass).async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{entry.entry_id}_latest_notification"
    )

    assert hass.states.get(entity_id).attributes["created_at"] is None


async def test_a_non_numeric_reading_leaves_the_sensor_unknown(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The device answers "n/a" for readings it cannot take.

    Home Assistant refuses to add a numeric sensor holding that, so without a
    guard the entity is missing entirely rather than merely having no value.
    """
    mock_device(aioclient_mock, technical_status={"bmsHighestCellVoltage": "n/a"})
    entry = await setup_entry(hass)

    key = "technical_status.bmsHighestCellVoltage"
    entity_id = er.async_get(hass).async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, sensor_unique_id(entry.entry_id, key)
    )

    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_UNKNOWN
