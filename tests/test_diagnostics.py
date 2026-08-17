"""Tests for the Eaton xStorage Home diagnostics and system health."""

import pytest
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    get_system_health_info,
)
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.eaton_battery_storage.const import DOMAIN
from custom_components.eaton_battery_storage.system_health import system_health_info

from .conftest import ENTRY_DATA, MINOR_VERSION, SERIAL, USER_INPUT, VERSION


async def setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up a config entry and return it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data=ENTRY_DATA,
        version=VERSION,
        minor_version=MINOR_VERSION,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.usefixtures("mock_connected_device")
async def test_diagnostics_redact_credentials_and_serial(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Credentials and identifying data never reach the diagnostics download."""
    assert await async_setup_component(hass, "diagnostics", {})
    entry = await setup_entry(hass)

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    entry_data = diagnostics["entry"]["data"]
    assert entry_data["password"] == REDACTED
    assert entry_data["username"] == REDACTED
    assert entry_data["email"] == REDACTED
    assert diagnostics["data"]["device"]["inverterSerialNumber"] == REDACTED
    assert USER_INPUT["password"] not in str(diagnostics)


@pytest.mark.usefixtures("mock_connected_device")
async def test_system_health_reports_a_loaded_entry(hass: HomeAssistant) -> None:
    """System health reports the reachability of a loaded entry."""
    assert await async_setup_component(hass, "system_health", {})
    await setup_entry(hass)

    info = await get_system_health_info(hass, DOMAIN)

    assert info["device_reachable"] is True
    assert info["api_host"] == USER_INPUT["host"]
    assert info["last_successful_update"] != "Never"


async def test_system_health_without_a_loaded_entry(hass: HomeAssistant) -> None:
    """System health does not crash when no entry is loaded."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data=ENTRY_DATA,
        version=VERSION,
        minor_version=MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    assert await system_health_info(hass) == {
        "device_reachable": False,
        "last_successful_update": "Never",
    }
