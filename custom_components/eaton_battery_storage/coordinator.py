"""Data update coordinator for Eaton xStorage Home battery integration.

IMPORTANT ACCURACY WARNING:
Power measurement data retrieved by this coordinator from the xStorage Home API
has poor accuracy. Energy flow values (consumption, production, grid power,
load values) are typically 10%-30% higher than actual measurements. This affects
all power-related data in the coordinator's data structure under energyFlow,
today, and last30daysEnergyFlow sections.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .api import EatonAuthError, EatonBatteryAPI, EatonError, EatonResponseError
from .const import (
    ACCOUNT_TYPE_TECHNICIAN,
    CONF_USER_TYPE,
    DEFAULT_INVERTER_POWER_RATING,
    DOMAIN,
    resolve_mode_command,
)
from .number_constants import (
    CHARGE_POWER,
    CHARGE_POWER_WATT,
    DISCHARGE_POWER,
    DISCHARGE_POWER_WATT,
    NUMBER_ENTITIES,
)
from .settings_helpers import async_get_and_transform_settings

_LOGGER = logging.getLogger(__name__)

type EatonConfigEntry = ConfigEntry[EatonXstorageHomeCoordinator]

# Percentage entity to the watt entity holding the same setting.
LINKED_NUMBER_KEYS = (
    (CHARGE_POWER, CHARGE_POWER_WATT),
    (DISCHARGE_POWER, DISCHARGE_POWER_WATT),
)

# Before the helper values were scoped per entry they all shared this one store.
LEGACY_NUMBER_STORE_KEY = f"{DOMAIN}_number_values.json"

# How long an accepted mode is trusted over the one the device reports. Long
# enough to cover the lag, short enough that a mode changed on the device's own
# panel is not hidden for long.
PENDING_MODE_TIMEOUT = timedelta(minutes=2)


def number_store_key(entry_id: str) -> str:
    """Return the .storage key holding the local helper values for an entry."""
    return f"{DOMAIN}_{entry_id}_number_values"


def number_update_signal(entry_id: str) -> str:
    """Return the dispatcher signal linking an entry's paired number entities."""
    return f"{DOMAIN}_{entry_id}_number_update"


def _unwrap(response: dict[str, Any]) -> dict[str, Any]:
    """Return the payload of an optional API response."""
    result = response.get("result")
    return result if isinstance(result, dict) else {}


def _unwrap_required(response: dict[str, Any], name: str) -> dict[str, Any]:
    """Return the payload of an API response the integration cannot work without."""
    result = response.get("result")
    if not isinstance(result, dict) or not result:
        raise EatonResponseError(f"Device returned no {name} data: {response}")
    return result


class EatonXstorageHomeCoordinator(TimestampDataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Eaton xStorage Home API."""

    config_entry: EatonConfigEntry
    # Loaded by async_load_number_values before the platforms are forwarded; the
    # number platform writes them and the select platform reads them.
    number_values: dict[str, float]
    number_store: Store[dict[str, float]]

    def __init__(
        self,
        hass: HomeAssistant,
        api: EatonBatteryAPI,
        config_entry: EatonConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Eaton xStorage Home",
            update_interval=timedelta(minutes=1),
            config_entry=config_entry,
        )
        self.api = api
        self._settings_lock = asyncio.Lock()
        self._unavailable_logged = False
        self._pending_mode: dict[str, Any] | None = None
        self._pending_mode_until = dt_util.utcnow()

    @property
    def full_scale_power(self) -> int:
        """Return the inverter power rating used to convert percentages to watts.

        The range spans 3.6 kW to 6 kW, so the rating has to come from the
        device. inverterPowerRating needs a technician account and reads 0 on at
        least the 3.6 kW model, hence the greater-than-zero guard;
        inverterVaRating is the closest equivalent a customer account can read.
        """
        data = self.data or {}
        for rating in (
            data.get("technical_status", {}).get("inverterPowerRating"),
            data.get("device", {}).get("inverterVaRating"),
        ):
            if isinstance(rating, (int, float)) and rating > 0:
                return int(rating)
        return DEFAULT_INVERTER_POWER_RATING

    async def async_load_number_values(self) -> None:
        """Load the local helper values the number and select platforms share.

        Called before the platforms are forwarded, because they are set up
        concurrently and select reads these values to build its commands.
        """
        store: Store[dict[str, float]] = Store(
            self.hass, 1, number_store_key(self.config_entry.entry_id)
        )
        values: dict[str, float] = await store.async_load() or {}
        stored_count = len(values)

        if not values:
            # Adopt the shared store an earlier version wrote, so upgrading does
            # not reset the user's charge and discharge settings. It is left in
            # place because a second entry may not have migrated yet.
            legacy: Store[dict[str, float]] = Store(
                self.hass, 1, LEGACY_NUMBER_STORE_KEY
            )
            values = await legacy.async_load() or {}

        for description in NUMBER_ENTITIES:
            default = description.get("default")
            if default is not None and description["key"] not in values:
                values[description["key"]] = default

        for percent_key, watt_key in LINKED_NUMBER_KEYS:
            if watt_key not in values and percent_key in values:
                values[watt_key] = round(
                    values[percent_key] / 100 * self.full_scale_power
                )

        self.number_values = values
        self.number_store = store
        if len(values) != stored_count:
            await store.async_save(values)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this coordinator."""
        device_data = self.data.get("device", {}) if self.data else {}
        serial = device_data.get("inverterSerialNumber")

        device_info = DeviceInfo(
            # Never key the device on an IP/hostname: a DHCP change would orphan it.
            identifiers={(DOMAIN, serial or self.config_entry.entry_id)},
            name="Eaton xStorage Home",
            manufacturer="Eaton",
            model="xStorage Home",
            configuration_url=f"https://{self.api.host}",
        )

        if serial:
            device_info["serial_number"] = serial
        if "firmwareVersion" in device_data:
            device_info["sw_version"] = device_data["firmwareVersion"]
        if "inverterModelName" in device_data:
            device_info["model"] = f"xStorage Home ({device_data['inverterModelName']})"
        if "bmsFirmwareVersion" in device_data:
            device_info["hw_version"] = device_data["bmsFirmwareVersion"]

        return device_info

    async def async_patch_settings(
        self, mutate: Callable[[dict[str, Any]], None]
    ) -> None:
        """Apply a mutation to the device settings atomically.

        The device only accepts writes of the whole settings document, so the
        read-modify-write cycle is serialized to avoid lost updates.
        """
        async with self._settings_lock:
            settings = await async_get_and_transform_settings(self.api)
            mutate(settings)
            await self.api.update_settings({"settings": settings})
        await self.async_request_refresh()

    async def async_apply_command_result(self, response: dict[str, Any]) -> None:
        """Publish the mode record the device answered an accepted command with.

        The record has the shape of status.currentMode, which keeps reporting
        the previous mode for a while after the command is accepted, so it is
        held over the polled value until the device catches up.
        """
        mode = _unwrap(response)
        if not mode or not self.data:
            await self.async_request_refresh()
            return
        self._pending_mode = mode
        self._pending_mode_until = dt_util.utcnow() + PENDING_MODE_TIMEOUT
        status = {**self.data.get("status", {}), "currentMode": mode}
        self.async_set_updated_data({**self.data, "status": status})

    def _hold_pending_mode(self, status: dict[str, Any]) -> None:
        """Keep an accepted mode in the status until the device reports it."""
        if self._pending_mode is None:
            return
        if dt_util.utcnow() >= self._pending_mode_until or resolve_mode_command(
            status.get("currentMode", {})
        ) == resolve_mode_command(self._pending_mode):
            self._pending_mode = None
            return
        status["currentMode"] = self._pending_mode

    async def _async_fetch_all(self) -> dict[str, Any]:
        """Fetch every endpoint, tolerating failures of the optional ones."""
        # Core data: if these fail the device is considered offline.
        results: dict[str, Any] = {
            "status": _unwrap_required(await self.api.get_status(), "status"),
            "device": _unwrap_required(await self.api.get_device(), "device"),
        }

        optional: dict[str, Callable[[], Coroutine[Any, Any, dict[str, Any]]]] = {
            "config_state": self.api.get_config_state,
            "settings": self.api.get_settings,
            "schedule": self.api.get_schedule,
            "notifications": self.api.get_notifications,
            "unread_notifications_count": self.api.get_unread_notifications_count,
        }
        if (
            self.config_entry.data.get(CONF_USER_TYPE, ACCOUNT_TYPE_TECHNICIAN)
            == ACCOUNT_TYPE_TECHNICIAN
        ):
            optional["technical_status"] = self.api.get_technical_status
            optional["maintenance_diagnostics"] = self.api.get_maintenance_diagnostics
        else:
            results["technical_status"] = {}
            results["maintenance_diagnostics"] = {}

        responses = await asyncio.gather(
            *(fetch() for fetch in optional.values()), return_exceptions=True
        )
        for name, response in zip(optional, responses, strict=True):
            if isinstance(response, EatonAuthError):
                raise response
            if isinstance(response, BaseException):
                if not isinstance(response, Exception):
                    raise response
                _LOGGER.debug("Failed to fetch %s: %s", name, response)
                results[name] = {}
            else:
                results[name] = _unwrap(response)

        return results

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            results = await self._async_fetch_all()
        except EatonAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EatonError as err:
            if not self._unavailable_logged:
                self._unavailable_logged = True
                _LOGGER.info("Eaton xStorage Home is unavailable: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        if self._unavailable_logged:
            self._unavailable_logged = False
            _LOGGER.info("Eaton xStorage Home is available again")

        self._hold_pending_mode(results["status"])

        return results
