"""Snapshot tests covering every entity the integration creates."""

from unittest.mock import patch

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

from custom_components.eaton_battery_storage.const import CONF_HAS_PV, DOMAIN

from .conftest import ENTRY_ID, MINOR_VERSION, SERIAL, TECH_INPUT, VERSION, mock_device

TECHNICAL_STATUS = {
    "operationMode": "MAXIMIZE_AUTO_CONSUMPTION",
    "gridVoltage": 240.1,
    "gridFrequency": 50.02,
    "inverterPower": 1234,
    "inverterTemperature": 31.25,
    "inverterPowerRating": 3600,
    "bmsVoltage": 51.2,
    "bmsCurrent": 12.5,
    "bmsState": "BAT_CHARGING",
    "bmsFaultCode": None,
    "bmsStateOfCharge": 62,
    "bmsHighestCellVoltage": 3502,
    "bmsLowestCellVoltage": 3498,
}

MAINTENANCE_DIAGNOSTICS = {
    "ramUsage": {"total": 1073741824, "used": 536870912},
    "cpuUsage": {"used": 12.34},
}

# Only read back on a PV install; the no-PV fixture never creates these sensors.
PV_TECHNICAL_STATUS = {
    "pv1Voltage": 312.4,
    "pv1Current": 4.25,
    "pv2Voltage": 308.1,
    "pv2Current": 3.75,
    "dcCurrentInjectionR": 0.01,
    "dcCurrentInjectionS": 0.02,
    "dcCurrentInjectionT": 0.03,
}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "platform",
    [
        Platform.BINARY_SENSOR,
        Platform.BUTTON,
        Platform.EVENT,
        Platform.NUMBER,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
)
async def test_all_entities(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    platform: Platform,
) -> None:
    """Every registered entity and its state match the snapshot."""
    mock_device(
        aioclient_mock,
        technical_status=TECHNICAL_STATUS,
        maintenance_diagnostics=MAINTENANCE_DIAGNOSTICS,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        unique_id=SERIAL,
        data=TECH_INPUT,
        version=VERSION,
        minor_version=MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    with patch("custom_components.eaton_battery_storage.PLATFORMS", [platform]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities_on_a_pv_install(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """A PV install adds the sensors the no-PV fixture never creates."""
    mock_device(
        aioclient_mock,
        technical_status={**TECHNICAL_STATUS, **PV_TECHNICAL_STATUS},
        maintenance_diagnostics=MAINTENANCE_DIAGNOSTICS,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        unique_id=SERIAL,
        data={**TECH_INPUT, CONF_HAS_PV: True},
        version=VERSION,
        minor_version=MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    with patch("custom_components.eaton_battery_storage.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
