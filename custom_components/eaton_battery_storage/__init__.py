"""Integration for Eaton xStorage Home battery storage."""

from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    SERVICE_RELOAD,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.storage import Store

from .api import EatonAuthError, EatonBatteryAPI, EatonError, token_store_key
from .const import (
    ACCOUNT_TYPE_TECHNICIAN,
    API_EMAIL,
    APP_ID,
    CONF_EMAIL,
    CONF_HAS_PV,
    CONF_INVERTER_SN,
    CONF_USER_TYPE,
    CONF_VERIFY_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    sensor_unique_id,
)
from .coordinator import (
    EatonConfigEntry,
    EatonXstorageHomeCoordinator,
    number_store_key,
)
from .sensor import SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Sensor keys that should be disabled when has_pv=False.
PV_SENSOR_KEYS = [
    key for key, description in SENSOR_TYPES.items() if description.get("pv_related")
]


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Set up the Eaton xStorage Home integration."""

    async def reload_service_handler(_call: ServiceCall) -> None:
        await asyncio.gather(
            *(
                hass.config_entries.async_reload(entry.entry_id)
                for entry in hass.config_entries.async_loaded_entries(DOMAIN)
            )
        )

    async_register_admin_service(
        hass, DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=vol.Schema({})
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EatonConfigEntry) -> bool:
    """Set up Eaton xStorage Home from a config entry."""
    api = EatonBatteryAPI(
        hass=hass,
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        inverter_sn=entry.data.get(CONF_INVERTER_SN, ""),
        email=entry.data.get(CONF_EMAIL, API_EMAIL),
        app_id=APP_ID,
        name="Eaton xStorage Home",
        manufacturer="Eaton",
        user_type=entry.data.get(CONF_USER_TYPE, ACCOUNT_TYPE_TECHNICIAN),
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        entry_id=entry.entry_id,
    )

    try:
        await api.connect()
    except EatonAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except EatonError as err:
        raise ConfigEntryNotReady(f"Device not reachable: {err}") from err

    coordinator = EatonXstorageHomeCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # The select platform reads these to build its commands, and platforms are
    # forwarded concurrently, so they have to be in place beforehand.
    await coordinator.async_load_number_values()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Applies the has_pv option, which the reconfigure flow changes before it
    # schedules the reload that brings us back here.
    async_migrate_pv_sensors(hass, entry)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry to the current identity scheme."""
    if entry.version > 2:
        return False

    if entry.version == 1:
        host = entry.data[CONF_HOST]
        unique_id = entry.unique_id

        # Old unique IDs were "{host}_{serial}", which duplicated the device
        # whenever its IP changed. Re-key to the bare serial.
        if unique_id and unique_id.startswith(f"{host}_"):
            unique_id = unique_id.removeprefix(f"{host}_")
        elif unique_id == host:
            # Nothing better is available offline; the host stays until a reauth
            # or reconfigure reads the serial from the device.
            _LOGGER.debug("Config entry unique ID has no serial to migrate to")

        hass.config_entries.async_update_entry(
            entry, unique_id=unique_id, version=2, minor_version=1
        )
        _async_migrate_device_identifiers(hass, entry, host)

    elif entry.minor_version < 1:
        # 2.0 only existed in unreleased builds and needs no data change, but
        # the marker has to move so the entry matches what the flow creates.
        hass.config_entries.async_update_entry(entry, minor_version=1)

    return True


@callback
def _async_migrate_device_identifiers(
    hass: HomeAssistant, entry: ConfigEntry, host: str
) -> None:
    """Drop host-based device identifiers left over from older versions."""
    device_registry = dr.async_get(hass)
    host_identifier = (DOMAIN, host)

    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if host_identifier not in device.identifiers:
            continue
        remaining = device.identifiers - {host_identifier}
        device_registry.async_update_device(
            device.id, new_identifiers=remaining or {(DOMAIN, entry.entry_id)}
        )


@callback
def async_migrate_pv_sensors(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Enable or disable PV sensors based on has_pv configuration."""
    entity_registry = er.async_get(hass)
    has_pv = entry.data.get(CONF_HAS_PV, False)

    for sensor_key in PV_SENSOR_KEYS:
        # Entity unique IDs are scoped to the config entry, so resolve the
        # actual entity_id from the registry by unique_id rather than guessing
        # the slug (which does not match the auto-generated entity_id).
        unique_id = sensor_unique_id(entry.entry_id, sensor_key)
        entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if entity_id is None:
            _LOGGER.debug("PV sensor not in registry: %s", sensor_key)
            continue

        registry_entry = entity_registry.entities[entity_id]

        if has_pv:
            # Only clear our own disablement, never a deliberate user choice.
            if registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
                entity_registry.async_update_entity(entity_id, disabled_by=None)
        elif registry_entry.disabled_by is None:
            entity_registry.async_update_entity(
                entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
            )


async def async_unload_entry(hass: HomeAssistant, entry: EatonConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the data persisted for the entry when it is deleted."""
    await Store(hass, 1, token_store_key(entry.entry_id)).async_remove()
    await Store(hass, 1, number_store_key(entry.entry_id)).async_remove()
