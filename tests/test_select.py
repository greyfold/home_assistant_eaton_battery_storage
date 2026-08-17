"""Tests for the Eaton xStorage Home select platform."""

import json
from datetime import timedelta
from pathlib import Path

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.select import (
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest import raises
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.eaton_battery_storage.const import DOMAIN
from custom_components.eaton_battery_storage.coordinator import PENDING_MODE_TIMEOUT
from custom_components.eaton_battery_storage.select import (
    DEFAULT_HOUSE_PEAK_CONSUMPTION,
    DEFAULT_MODE_OPTIONS,
    DEFAULT_OPTIMAL_SOC,
    MANUAL_MODE_OPTIONS,
)

from .conftest import (
    BASE_URL,
    JSON_HEADERS,
    MINOR_VERSION,
    SERIAL,
    SETTINGS_RESULT,
    TECH_INPUT,
    VERSION,
    mock_device,
    mock_settings,
)

CURRENT_MODE_ENTITY_ID = "select.eaton_xstorage_home_current_operation_mode"
DEFAULT_MODE_ENTITY_ID = "select.eaton_xstorage_home_default_operation_mode"

# What the inverter answers a command with, captured from a real device.
COMMAND_ACCEPTED = {
    "successful": True,
    "message": "Content Ready",
    "result": {
        "command": "SET_CHARGE",
        "duration": 1,
        "recurrence": "MANUAL_EVENT",
        "type": "MANUAL",
        "parameters": {"action": "ACTION_CHARGE", "power": 20, "soc": 80},
    },
}


async def setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up a config entry and return it."""
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


def last_command(aioclient_mock: AiohttpClientMocker) -> dict:
    """Return the body of the most recent device command."""
    return next(
        data
        for method, url, data, _headers in reversed(aioclient_mock.mock_calls)
        if method.upper() == "POST" and url.path == "/api/device/command"
    )


async def test_selecting_a_mode_sends_the_configured_helpers(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The command carries the duration, power and target SOC helper values."""
    aioclient_mock.post(
        f"{BASE_URL}/api/device/command", json=COMMAND_ACCEPTED, headers=JSON_HEADERS
    )
    mock_device(aioclient_mock)
    await setup_entry(hass)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: CURRENT_MODE_ENTITY_ID, ATTR_OPTION: "manual_charge"},
        blocking=True,
    )

    assert last_command(aioclient_mock) == {
        "command": "SET_CHARGE",
        "duration": 1,
        "parameters": {"action": "ACTION_CHARGE", "power": 20, "soc": 80},
    }


async def test_the_accepted_mode_is_shown_without_waiting_for_a_poll(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The mode the device echoes back wins over the one it still reports."""
    aioclient_mock.post(
        f"{BASE_URL}/api/device/command", json=COMMAND_ACCEPTED, headers=JSON_HEADERS
    )
    # The status endpoint keeps answering with the previous mode for a while.
    mock_device(aioclient_mock)
    await setup_entry(hass)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: CURRENT_MODE_ENTITY_ID, ATTR_OPTION: "manual_charge"},
        blocking=True,
    )

    assert hass.states.get(CURRENT_MODE_ENTITY_ID).state == "manual_charge"


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        pytest.param(
            timedelta(minutes=1), "manual_charge", id="held_while_the_device_lags"
        ),
        pytest.param(
            PENDING_MODE_TIMEOUT + timedelta(minutes=1),
            "basic_mode",
            id="the_device_wins_once_the_hold_expires",
        ),
    ],
)
async def test_the_accepted_mode_outlives_a_lagging_poll(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    elapsed: timedelta,
    expected: str,
) -> None:
    """A poll that still reports the previous mode does not undo the selection."""
    aioclient_mock.post(
        f"{BASE_URL}/api/device/command", json=COMMAND_ACCEPTED, headers=JSON_HEADERS
    )
    mock_device(aioclient_mock)
    entry = await setup_entry(hass)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: CURRENT_MODE_ENTITY_ID, ATTR_OPTION: "manual_charge"},
        blocking=True,
    )

    freezer.tick(elapsed)
    await entry.runtime_data.async_refresh()

    assert hass.states.get(CURRENT_MODE_ENTITY_ID).state == expected


@pytest.mark.parametrize(
    ("current_mode", "expected"),
    [
        pytest.param(
            {
                "command": "SET_CHARGE",
                "parameters": {"action": "ACTION_DISCHARGE"},
            },
            "manual_discharge",
            id="discharge_echoed_as_a_charge_command",
        ),
        pytest.param(
            {"command": "SET_CHARGE", "parameters": {"action": "ACTION_CHARGE"}},
            "manual_charge",
            id="charge",
        ),
        pytest.param(
            {"command": "SET_DISCHARGE"},
            "manual_discharge",
            id="discharge_without_an_action",
        ),
        pytest.param(
            {"command": "SET_BASIC_MODE"},
            "basic_mode",
            id="intelligent_mode_ignores_the_action",
        ),
    ],
)
async def test_running_mode_is_reported(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    current_mode: dict,
    expected: str,
) -> None:
    """A running manual mode is told apart by its action, not its command."""
    mock_device(aioclient_mock, status={"currentMode": current_mode})
    await setup_entry(hass)

    assert hass.states.get(CURRENT_MODE_ENTITY_ID).state == expected


async def test_a_rejected_command_raises(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A device that rejects the command surfaces a translated error."""
    aioclient_mock.post(
        f"{BASE_URL}/api/device/command",
        json={"successful": False},
        headers=JSON_HEADERS,
    )
    mock_device(aioclient_mock)
    await setup_entry(hass)

    with raises(HomeAssistantError, match="basic_mode"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: CURRENT_MODE_ENTITY_ID, ATTR_OPTION: "basic_mode"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("option", "expected_parameters"),
    [
        pytest.param(
            "peak_shaving",
            {"maxHousePeakConsumption": 400},
            id="peak_shaving_reads_the_configured_threshold",
        ),
        pytest.param(
            "variable_grid_injection", {"maximumPower": 0}, id="variable_grid_injection"
        ),
        pytest.param(
            "frequency_regulation",
            {"powerAllocation": 0, "optimalSoc": 30},
            id="frequency_regulation_reads_the_backup_level",
        ),
        pytest.param("basic_mode", {}, id="basic_mode_takes_no_parameters"),
    ],
)
async def test_an_intelligent_mode_carries_its_settings(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    option: str,
    expected_parameters: dict,
) -> None:
    """Each mode is sent with the parameters the device expects for it."""
    aioclient_mock.post(
        f"{BASE_URL}/api/device/command", json=COMMAND_ACCEPTED, headers=JSON_HEADERS
    )
    mock_settings(aioclient_mock, successful=True)
    mock_device(aioclient_mock)
    await setup_entry(hass)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: CURRENT_MODE_ENTITY_ID, ATTR_OPTION: option},
        blocking=True,
    )

    assert last_command(aioclient_mock)["parameters"] == expected_parameters


async def test_the_default_mode_is_read_from_the_settings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The default mode select shows what the device has stored."""
    mock_device(
        aioclient_mock,
        settings={**SETTINGS_RESULT, "defaultMode": {"command": "SET_PEAK_SHAVING"}},
    )
    await setup_entry(hass)

    assert hass.states.get(DEFAULT_MODE_ENTITY_ID).state == "peak_shaving"


@pytest.mark.parametrize(
    ("option", "expected_default_mode"),
    [
        pytest.param(
            "peak_shaving",
            {
                "command": "SET_PEAK_SHAVING",
                "parameters": {"maxHousePeakConsumption": 400},
            },
            id="peak_shaving",
        ),
        pytest.param(
            "frequency_regulation",
            {
                "command": "SET_FREQUENCY_REGULATION",
                "parameters": {"powerAllocation": 0, "optimalSoc": 30},
            },
            id="frequency_regulation",
        ),
        pytest.param(
            "maximize_auto_consumption",
            {"command": "SET_MAXIMIZE_AUTO_CONSUMPTION", "parameters": {}},
            id="maximize_auto_consumption",
        ),
    ],
)
async def test_the_default_mode_is_written_to_the_settings(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    option: str,
    expected_default_mode: dict,
) -> None:
    """Changing the default mode patches the settings document."""
    mock_settings(aioclient_mock, successful=True)
    mock_device(aioclient_mock)
    await setup_entry(hass)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: DEFAULT_MODE_ENTITY_ID, ATTR_OPTION: option},
        blocking=True,
    )

    written = next(
        data
        for method, url, data, _ in reversed(aioclient_mock.mock_calls)
        if method.upper() == "PUT" and url.path == "/api/settings"
    )
    assert written["settings"]["defaultMode"] == expected_default_mode


async def test_a_rejected_default_mode_write_raises(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A device that refuses the settings write surfaces a translated error."""
    mock_settings(aioclient_mock, successful=False)
    mock_device(aioclient_mock)
    await setup_entry(hass)

    with raises(HomeAssistantError, match="basic_mode"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: DEFAULT_MODE_ENTITY_ID, ATTR_OPTION: "basic_mode"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("option", "settings", "status", "expected_parameters"),
    [
        pytest.param(
            "frequency_regulation",
            {},
            {"energyFlow": {"batteryBackupLevel": 45}},
            {"powerAllocation": 0, "optimalSoc": 45},
            id="frequency_regulation_falls_back_to_the_reported_level",
        ),
        pytest.param(
            "frequency_regulation",
            {},
            {"energyFlow": {}},
            {"powerAllocation": 0, "optimalSoc": DEFAULT_OPTIMAL_SOC},
            id="frequency_regulation_falls_back_to_the_default",
        ),
        pytest.param(
            "peak_shaving",
            {},
            {"energyFlow": {}},
            {"maxHousePeakConsumption": DEFAULT_HOUSE_PEAK_CONSUMPTION},
            id="peak_shaving_falls_back_to_the_default_threshold",
        ),
    ],
)
async def test_a_mode_falls_back_when_the_device_reports_no_setting(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    option: str,
    settings: dict,
    status: dict,
    expected_parameters: dict,
) -> None:
    """A missing setting must not send the device a null parameter."""
    aioclient_mock.post(
        f"{BASE_URL}/api/device/command", json=COMMAND_ACCEPTED, headers=JSON_HEADERS
    )
    mock_device(aioclient_mock, settings=settings, status=status)
    await setup_entry(hass)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: CURRENT_MODE_ENTITY_ID, ATTR_OPTION: option},
        blocking=True,
    )

    assert last_command(aioclient_mock)["parameters"] == expected_parameters


def test_every_option_has_a_translation() -> None:
    """A select option is a key, so a missing label shows the raw key to the user."""
    strings = json.loads(
        (
            Path(__file__).parent.parent
            / "custom_components/eaton_battery_storage/strings.json"
        ).read_text()
    )
    select_strings = strings["entity"]["select"]

    for translation_key, options in (
        ("default_operation_mode", DEFAULT_MODE_OPTIONS),
        ("current_operation_mode", DEFAULT_MODE_OPTIONS | MANUAL_MODE_OPTIONS),
    ):
        assert set(select_strings[translation_key]["state"]) == set(options)
