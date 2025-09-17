"""Data update coordinator for Eaton xStorage Home battery integration.

IMPORTANT ACCURACY WARNING:
Power measurement data retrieved by this coordinator from the xStorage Home API
has poor accuracy. Energy flow values (consumption, production, grid power,
load values) are typically 30% higher than actual measurements. This affects
all power-related data in the coordinator's data structure under energyFlow,
today, and last30daysEnergyFlow sections.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EatonBatteryAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EatonXstorageHomeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Eaton xStorage Home API."""

    def __init__(self, hass: HomeAssistant, api: EatonBatteryAPI, config_entry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Eaton xStorage Home",
            update_interval=timedelta(minutes=1),
            config_entry=config_entry,
        )
        self.api = api
        self.config_entry = config_entry

    @property
    def battery_level(self) -> int | None:
        """Return the current battery level as a percentage."""
        if not self.data:
            return None
        try:
            return (
                self.data.get("status", {}).get("energyFlow", {}).get("stateOfCharge")
            )
        except (AttributeError, KeyError):
            return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this coordinator."""
        device_data = self.data.get("device", {}) if self.data else {}

        device_info = DeviceInfo(
            identifiers={(DOMAIN, self.api.host)},
            name="Eaton xStorage Home",
            manufacturer="Eaton",
            model="xStorage Home",
            entry_type="device",
            configuration_url=f"https://{self.api.host}",
        )

        # Add detailed device information if available
        if device_data:
            # Add firmware version (software version)
            if "firmwareVersion" in device_data:
                device_info["sw_version"] = device_data["firmwareVersion"]

            # Add more specific model name if available
            if "inverterModelName" in device_data:
                device_info["model"] = (
                    f"xStorage Home ({device_data['inverterModelName']})"
                )

            # Add serial number if available (inverter serial as primary identifier)
            if "inverterSerialNumber" in device_data:
                device_info["serial_number"] = device_data["inverterSerialNumber"]
                # Also add as an additional identifier
                device_info["identifiers"].add(
                    (DOMAIN, device_data["inverterSerialNumber"])
                )

            # Add hardware version (BMS firmware version)
            if "bmsFirmwareVersion" in device_data:
                device_info["hw_version"] = device_data["bmsFirmwareVersion"]

        return device_info

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            # Fetch all endpoints, handling errors gracefully
            results: dict[str, Any] = {}

            # Core data that should always be available
            try:
                status = await self.api.get_status()
                results["status"] = status.get("result", {}) if status else {}
            except Exception as err:
                _LOGGER.warning("Failed to fetch status: %s", err)
                results["status"] = {}

            try:
                device = await self.api.get_device()
                results["device"] = device.get("result", {}) if device else {}
            except Exception as err:
                _LOGGER.warning("Failed to fetch device info: %s", err)
                results["device"] = {}

            # Additional data that may not always be available
            for endpoint, method in [
                ("config_state", self.api.get_config_state),
                ("settings", self.api.get_settings),
                ("metrics", self.api.get_metrics),
                ("metrics_daily", self.api.get_metrics_daily),
                ("schedule", self.api.get_schedule),
            ]:
                try:
                    data = await method()
                    results[endpoint] = (
                        data.get("result", {})
                        if data and isinstance(data, dict) and "result" in data
                        else data or {}
                    )
                except Exception as err:
                    _LOGGER.debug("Failed to fetch %s: %s", endpoint, err)
                    results[endpoint] = {}

            # Technical data that may require special permissions
            for endpoint, method in [
                ("technical_status", self.api.get_technical_status),
                ("maintenance_diagnostics", self.api.get_maintenance_diagnostics),
            ]:
                try:
                    data = await method()
                    results[endpoint] = data.get("result", {}) if data else {}
                except Exception as err:
                    _LOGGER.debug(
                        "Failed to fetch %s (may require technician account): %s",
                        endpoint,
                        err,
                    )
                    results[endpoint] = {}

            # Notification data
            try:
                notifications = await self.api.get_notifications()
                results["notifications"] = (
                    notifications.get("result", {}) if notifications else {}
                )
            except Exception as err:
                _LOGGER.debug("Failed to fetch notifications: %s", err)
                results["notifications"] = {}

            try:
                unread_count = await self.api.get_unread_notifications_count()
                results["unread_notifications_count"] = (
                    unread_count.get("result", {}) if unread_count else {}
                )
            except Exception as err:
                _LOGGER.debug("Failed to fetch unread notifications count: %s", err)
                results["unread_notifications_count"] = {}

            return results

        except Exception as err:
            _LOGGER.error("Error fetching data from Eaton xStorage Home: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err


# Alias for backward compatibility
EatonBatteryStorageCoordinator = EatonXstorageHomeCoordinator
