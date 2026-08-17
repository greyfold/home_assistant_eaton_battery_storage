"""Tests for the Eaton xStorage Home switch platform."""

import pytest
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
)
from homeassistant.components.switch import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.eaton_battery_storage.const import DOMAIN

from .conftest import (
    BASE_URL,
    JSON_HEADERS,
    MINOR_VERSION,
    SERIAL,
    USER_INPUT,
    VERSION,
    mock_device,
    mock_settings,
)

ENERGY_SAVING_ENTITY_ID = "switch.eaton_xstorage_home_energy_saving_mode"
POWER_ENTITY_ID = "switch.eaton_xstorage_home_inverter_power"


async def setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up a config entry and return it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data=USER_INPUT,
        version=VERSION,
        minor_version=MINOR_VERSION,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def last_payload(aioclient_mock: AiohttpClientMocker, method: str, path: str) -> dict:
    """Return the body of the most recent write to an endpoint."""
    return next(
        data
        for call_method, url, data, _headers in reversed(aioclient_mock.mock_calls)
        if call_method.upper() == method and url.path == path
    )


async def test_energy_saving_mode_writes_whole_settings_document(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Only the targeted field changes and composite values are flattened."""
    mock_settings(aioclient_mock, successful=True)
    mock_device(aioclient_mock)
    await setup_entry(hass)

    assert hass.states.get(ENERGY_SAVING_ENTITY_ID).state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENERGY_SAVING_ENTITY_ID},
        blocking=True,
    )

    assert last_payload(aioclient_mock, "PUT", "/api/settings") == {
        "settings": {
            "country": 2635167,
            "city": 2643743,
            "timezone": "Europe/London",
            "bmsBackupLevel": 30,
            "energySavingMode": {"enabled": True, "houseConsumptionThreshold": 400},
        }
    }


async def test_energy_saving_mode_reports_a_rejected_write(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A device that rejects the write surfaces a translated error."""
    mock_settings(aioclient_mock, successful=False)
    mock_device(aioclient_mock)
    await setup_entry(hass)

    with pytest.raises(HomeAssistantError, match="Failed to change energy saving mode"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENERGY_SAVING_ENTITY_ID},
            blocking=True,
        )


@pytest.mark.usefixtures("mock_connected_device")
async def test_power_switch_accepts_a_json_empty_string(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The device answers this endpoint with a bare JSON "", not a result object."""
    aioclient_mock.post(f"{BASE_URL}/api/device/power", json="", headers=JSON_HEADERS)
    await setup_entry(hass)

    assert hass.states.get(POWER_ENTITY_ID).state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: POWER_ENTITY_ID},
        blocking=True,
    )

    assert last_payload(aioclient_mock, "POST", "/api/device/power") == {
        "parameters": {"state": False}
    }


@pytest.mark.usefixtures("mock_connected_device")
async def test_power_switch_reports_a_rejected_command(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A refused power command surfaces an error and drops the optimistic state."""
    aioclient_mock.post(
        f"{BASE_URL}/api/device/power",
        status=500,
        json={"error": "nope"},
        headers=JSON_HEADERS,
    )
    await setup_entry(hass)

    with pytest.raises(HomeAssistantError, match="Failed to change the inverter power"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: POWER_ENTITY_ID},
            blocking=True,
        )

    assert hass.states.get(POWER_ENTITY_ID).state == STATE_ON
