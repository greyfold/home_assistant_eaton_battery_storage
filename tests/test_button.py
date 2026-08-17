"""Tests for the Eaton xStorage Home button platform."""

import pytest
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
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
    TECH_INPUT,
    VERSION,
    mock_device,
)

MARK_READ_ENTITY_ID = "button.eaton_xstorage_home_mark_all_notifications_read"
STOP_ENTITY_ID = "button.eaton_xstorage_home_stop_current_operation"
ACCEPTED = {"successful": True, "result": {}}


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


async def press(hass: HomeAssistant, entity_id: str) -> None:
    """Press a button."""
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )


@pytest.mark.parametrize(
    ("entity_id", "path"),
    [
        pytest.param(
            MARK_READ_ENTITY_ID, "/api/notifications/read/all", id="mark_read"
        ),
        pytest.param(STOP_ENTITY_ID, "/api/device/command", id="stop_operation"),
    ],
)
async def test_a_button_calls_the_device(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_id: str,
    path: str,
) -> None:
    """Each button reaches its own endpoint."""
    aioclient_mock.post(f"{BASE_URL}{path}", json=ACCEPTED, headers=JSON_HEADERS)
    mock_device(aioclient_mock)
    await setup_entry(hass)

    await press(hass, entity_id)

    assert any(
        method.upper() == "POST" and url.path == path
        for method, url, _, _ in aioclient_mock.mock_calls
    )


async def test_stopping_sends_the_basic_mode_command(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Stopping the current operation puts the device back into basic mode."""
    aioclient_mock.post(
        f"{BASE_URL}/api/device/command", json=ACCEPTED, headers=JSON_HEADERS
    )
    mock_device(aioclient_mock)
    await setup_entry(hass)

    await press(hass, STOP_ENTITY_ID)

    command = next(
        data
        for method, url, data, _ in reversed(aioclient_mock.mock_calls)
        if method.upper() == "POST" and url.path == "/api/device/command"
    )
    assert command == {"command": "SET_BASIC_MODE", "duration": 1, "parameters": {}}


@pytest.mark.parametrize(
    ("entity_id", "path", "expected_error"),
    [
        pytest.param(
            MARK_READ_ENTITY_ID,
            "/api/notifications/read/all",
            "Failed to mark the notifications as read",
            id="mark_read",
        ),
        pytest.param(
            STOP_ENTITY_ID,
            "/api/device/command",
            "Failed to stop the current operation",
            id="stop_operation",
        ),
    ],
)
async def test_a_rejected_press_raises(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_id: str,
    path: str,
    expected_error: str,
) -> None:
    """A device that refuses the request surfaces a translated error."""
    aioclient_mock.post(
        f"{BASE_URL}{path}", json={"successful": False}, headers=JSON_HEADERS
    )
    mock_device(aioclient_mock)
    await setup_entry(hass)

    with pytest.raises(HomeAssistantError, match=expected_error):
        await press(hass, entity_id)
