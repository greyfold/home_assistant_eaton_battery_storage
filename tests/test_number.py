"""Tests for the Eaton xStorage Home number platform."""

from typing import Any

import pytest
from homeassistant.components.number import (
    ATTR_VALUE,
    SERVICE_SET_VALUE,
)
from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.eaton_battery_storage.const import DOMAIN

from .conftest import (
    DEVICE_RESULT,
    MINOR_VERSION,
    SERIAL,
    TECH_INPUT,
    USER_INPUT,
    VERSION,
    mock_device,
    mock_settings,
)

CHARGE_POWER_KEY = "charge_power"
CHARGE_POWER_WATT_KEY = "charge_power_watt"


async def setup_entry(hass: HomeAssistant, data: dict[str, Any]) -> MockConfigEntry:
    """Set up a config entry and return it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data=data,
        version=VERSION,
        minor_version=MINOR_VERSION,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def set_number(hass: HomeAssistant, entity_id: str, value: float) -> None:
    """Set the value of a number entity."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )
    await hass.async_block_till_done()


def entity_id_for(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str:
    """Return the entity ID of a number entity by its unique ID suffix."""
    return er.async_get(hass).async_get_entity_id(
        NUMBER_DOMAIN, DOMAIN, f"{entry.entry_id}_{key}"
    )


@pytest.mark.parametrize(
    ("data", "device", "technical_status", "expected_max"),
    [
        pytest.param(
            TECH_INPUT,
            DEVICE_RESULT,
            {"inverterPowerRating": 6000},
            6000,
            id="technician_reads_inverter_power_rating",
        ),
        pytest.param(
            USER_INPUT,
            {**DEVICE_RESULT, "inverterVaRating": 4600},
            {},
            4600,
            id="customer_falls_back_to_va_rating",
        ),
        pytest.param(
            TECH_INPUT,
            {**DEVICE_RESULT, "inverterVaRating": 3600},
            {"inverterPowerRating": 0},
            3600,
            id="rating_reported_as_zero_falls_back_to_va_rating",
        ),
        pytest.param(
            USER_INPUT,
            DEVICE_RESULT,
            {},
            3600,
            id="unknown_rating_falls_back_to_smallest_model",
        ),
    ],
)
async def test_watt_range_follows_inverter_rating(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    data: dict[str, Any],
    device: dict[str, Any],
    technical_status: dict[str, Any],
    expected_max: int,
) -> None:
    """The watt entities span 5-100 % of the rating the device reports."""
    mock_device(aioclient_mock, device=device, technical_status=technical_status)

    entry = await setup_entry(hass, data)
    state = hass.states.get(entity_id_for(hass, entry, CHARGE_POWER_WATT_KEY))

    assert state.attributes["max"] == expected_max
    assert state.attributes["min"] == expected_max * 0.05


async def test_percentage_conversion_uses_inverter_rating(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Setting a percentage stores the matching wattage for the actual model."""
    mock_device(aioclient_mock, technical_status={"inverterPowerRating": 6000})

    entry = await setup_entry(hass, TECH_INPUT)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id_for(hass, entry, CHARGE_POWER_KEY),
            ATTR_VALUE: 50,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    watt_state = hass.states.get(entity_id_for(hass, entry, CHARGE_POWER_WATT_KEY))

    assert watt_state.state == "3000"


async def test_wattage_conversion_updates_the_percentage(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The two representations of the same setting stay in step."""
    mock_device(aioclient_mock, technical_status={"inverterPowerRating": 6000})
    entry = await setup_entry(hass, TECH_INPUT)

    await set_number(hass, entity_id_for(hass, entry, CHARGE_POWER_WATT_KEY), 1500)

    percent_state = hass.states.get(entity_id_for(hass, entry, CHARGE_POWER_KEY))
    watt_state = hass.states.get(entity_id_for(hass, entry, CHARGE_POWER_WATT_KEY))

    assert percent_state.state == "25"
    assert percent_state.attributes["wattage"] == 1500
    assert watt_state.attributes["percent"] == 25


@pytest.mark.parametrize(
    ("key", "value", "expected_settings"),
    [
        pytest.param(
            "set_house_consumption_threshold",
            500,
            {"energySavingMode": {"enabled": False, "houseConsumptionThreshold": 500}},
            id="house_consumption_threshold",
        ),
        pytest.param(
            "set_battery_backup_level",
            45,
            {"bmsBackupLevel": 45},
            id="battery_backup_level",
        ),
    ],
)
async def test_a_setting_is_written_back_to_the_device(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    key: str,
    value: int,
    expected_settings: dict[str, Any],
) -> None:
    """Writing a number patches only its own field of the settings document."""
    mock_settings(aioclient_mock, successful=True)
    mock_device(aioclient_mock)
    entry = await setup_entry(hass, TECH_INPUT)
    entity_id = entity_id_for(hass, entry, key)

    await set_number(hass, entity_id, value)

    written = next(
        data
        for method, url, data, _ in reversed(aioclient_mock.mock_calls)
        if method.upper() == "PUT" and url.path == "/api/settings"
    )
    assert written["settings"].items() >= expected_settings.items()


@pytest.mark.parametrize(
    ("key", "value", "expected_error"),
    [
        pytest.param(
            "set_house_consumption_threshold",
            500,
            "Failed to set the house consumption threshold to 500 W",
            id="house_consumption_threshold",
        ),
        pytest.param(
            "set_battery_backup_level",
            45,
            "Failed to set the battery backup level to 45 %",
            id="battery_backup_level",
        ),
    ],
)
async def test_a_rejected_write_restores_the_device_value(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    key: str,
    value: int,
    expected_error: str,
) -> None:
    """A refused write must not leave the optimistic value on display."""
    mock_settings(aioclient_mock, successful=False)
    mock_device(aioclient_mock)
    entry = await setup_entry(hass, TECH_INPUT)
    entity_id = entity_id_for(hass, entry, key)
    before = hass.states.get(entity_id).state

    with pytest.raises(HomeAssistantError, match=expected_error):
        await set_number(hass, entity_id, value)

    assert hass.states.get(entity_id).state == before


async def test_values_saved_before_the_store_was_scoped_are_kept(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """Every entry used to share one store, so upgrading must not reset it."""
    hass_storage[f"{DOMAIN}_number_values.json"] = {
        "version": 1,
        "data": {CHARGE_POWER_KEY: 75, "charge_duration": 9},
    }
    mock_device(aioclient_mock)

    entry = await setup_entry(hass, TECH_INPUT)

    assert hass.states.get(entity_id_for(hass, entry, CHARGE_POWER_KEY)).state == "75"
    assert hass.states.get(entity_id_for(hass, entry, "charge_duration")).state == "9"
