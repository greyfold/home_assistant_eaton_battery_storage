"""Integration for Eaton xStorage Home battery storage."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_RELOAD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.reload import async_reload_integration_platforms

from .api import EatonBatteryAPI
from .const import DOMAIN
from .coordinator import EatonXstorageHomeCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.EVENT,
]

# List of PV-related sensor keys that should be disabled when has_pv=False
PV_SENSOR_KEYS = [
    "status.energyFlow.acPvRole",
    "status.energyFlow.acPvValue",
    "status.energyFlow.dcPvRole",
    "status.energyFlow.dcPvValue",
    "status.last30daysEnergyFlow.photovoltaicProduction",
    "status.today.photovoltaicProduction",
    "device.inverterNominalVpv",
    "technical_status.pv1Voltage",
    "technical_status.pv1Current",
    "technical_status.pv2Voltage",
    "technical_status.pv2Current",
    "technical_status.dcCurrentInjectionR",
    "technical_status.dcCurrentInjectionS",
    "technical_status.dcCurrentInjectionT",
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Eaton Battery Storage integration."""
    return True  # Not used for config flow-based setup


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Eaton xStorage Home from a config entry."""
    _LOGGER.debug("Setting up Eaton xStorage Home from config entry")

    try:
        api = EatonBatteryAPI(
            username=entry.data["username"],
            password=entry.data["password"],
            inverter_sn=entry.data["inverter_sn"],
            email=entry.data["email"],
            hass=hass,
            host=entry.data["host"],
            app_id="com.eaton.xstoragehome",
            name="Eaton xStorage Home",
            manufacturer="Eaton",
        )
        await api.connect()

        coordinator = EatonXstorageHomeCoordinator(hass, api, entry)
        await coordinator.async_config_entry_first_refresh()

        # Store coordinator in entry.runtime_data following HA best practices
        entry.runtime_data = coordinator

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        # Run initial PV sensor migration for existing installations
        await async_migrate_pv_sensors(hass, entry)

        # Add update listener for options changes
        entry.async_on_unload(entry.add_update_listener(async_update_options))

        async def reload_service_handler(call):
            await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)

        hass.services.async_register(
            DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=vol.Schema({})
        )

        return True

    except Exception as ex:
        _LOGGER.exception("Failed to set up Eaton xStorage Home: %s", ex)
        raise ConfigEntryNotReady(f"Failed to connect to device: {ex}") from ex


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """Update options and handle PV sensor migration."""
    # Handle PV sensor enabling/disabling based on has_pv setting
    await async_migrate_pv_sensors(hass, entry)

    # Reload the integration to apply new settings
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_pv_sensors(hass: HomeAssistant, entry: ConfigEntry):
    """Enable or disable PV sensors based on has_pv configuration."""
    entity_registry = er.async_get(hass)
    has_pv = entry.data.get("has_pv", False)

    _LOGGER.info("Migrating PV sensors: has_pv=%s", has_pv)

    for sensor_key in PV_SENSOR_KEYS:
        entity_id = f"sensor.eaton_xstorage_{sensor_key.replace('.', '_')}"

        # Try to find the entity in the registry
        registry_entry = entity_registry.async_get(entity_id)
        if registry_entry:
            # Update the entity's enabled state based on PV configuration
            entity_registry.async_update_entity(
                entity_id,
                disabled_by=None if has_pv else er.RegistryEntryDisabler.INTEGRATION,
            )
            _LOGGER.debug(
                "%s PV sensor: %s", "Enabled" if has_pv else "Disabled", entity_id
            )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
