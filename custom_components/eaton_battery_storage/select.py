"""Select entities for Eaton battery storage system operation modes."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import EatonBatteryStorageCoordinator

_LOGGER = logging.getLogger(__name__)

# Supported default modes and their command codes
DEFAULT_MODE_OPTIONS: list[tuple[str, str]] = [
    ("Basic Mode", "SET_BASIC_MODE"),
    ("Maximize Auto Consumption", "SET_MAXIMIZE_AUTO_CONSUMPTION"),
    ("Variable Grid Injection", "SET_VARIABLE_GRID_INJECTION"),
    ("Frequency Regulation", "SET_FREQUENCY_REGULATION"),
    ("Peak Shaving", "SET_PEAK_SHAVING"),
]


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    coordinator: EatonBatteryStorageCoordinator = config_entry.runtime_data
    async_add_entities(
        [
            EatonXStorageDefaultOperationModeSelect(coordinator),
            EatonXStorageCurrentOperationModeSelect(coordinator),
        ]
    )


class EatonXStorageDefaultOperationModeSelect(CoordinatorEntity, SelectEntity):
    """Select entity to configure Default Operation Mode in settings.defaultMode."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:transmission-tower"

    def __init__(self, coordinator: EatonBatteryStorageCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_default_operation_mode"
        )
        self._attr_name = "Default operation mode"
        self._options = [label for (label, _) in DEFAULT_MODE_OPTIONS]
        self._option_to_cmd = {label: cmd for (label, cmd) in DEFAULT_MODE_OPTIONS}
        self._cmd_to_label = {cmd: label for (label, cmd) in DEFAULT_MODE_OPTIONS}

    @property
    def device_info(self):
        """Return device information."""
        return self.coordinator.device_info

    @property
    def options(self) -> list[str]:
        """Return list of available options."""
        return self._options

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        try:
            settings = (
                self.coordinator.data.get("settings", {})
                if self.coordinator.data
                else {}
            )
            default_mode = (
                settings.get("defaultMode", {}) if isinstance(settings, dict) else {}
            )
            cmd = default_mode.get("command")
            if cmd and cmd in self._cmd_to_label:
                return self._cmd_to_label[cmd]
        except Exception:
            pass
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if option not in self._option_to_cmd:
            _LOGGER.error("Invalid operation mode option: %s", option)
            return

        try:
            # Always fetch the latest settings
            current_settings_response = await self.coordinator.api.get_settings()
            if not current_settings_response or not current_settings_response.get(
                "result"
            ):
                _LOGGER.error("Failed to get current settings from API")
                return
            current_settings = current_settings_response.get("result", {})

            # Transform composite objects expected as strings on PUT
            if "country" in current_settings and isinstance(
                current_settings["country"], dict
            ):
                current_settings["country"] = current_settings["country"].get(
                    "geonameId", ""
                )
            if "city" in current_settings and isinstance(
                current_settings["city"], dict
            ):
                current_settings["city"] = current_settings["city"].get("geonameId", "")
            if "timezone" in current_settings and isinstance(
                current_settings["timezone"], dict
            ):
                current_settings["timezone"] = current_settings["timezone"].get(
                    "id", ""
                )

            # Determine parameters based on selected mode and available helper/settings values
            command = self._option_to_cmd[option]
            parameters = {}

            try:
                if command == "SET_PEAK_SHAVING":
                    # Use energySavingMode.houseConsumptionThreshold if available
                    esm = (
                        current_settings.get("energySavingMode", {})
                        if isinstance(current_settings, dict)
                        else {}
                    )
                    max_peak = None
                    if isinstance(esm, dict):
                        max_peak = esm.get("houseConsumptionThreshold")
                    if isinstance(max_peak, (int, float)):
                        parameters = {"maxHousePeakConsumption": int(max_peak)}
                elif command == "SET_VARIABLE_GRID_INJECTION":
                    # Default to 0W unless a helper is added later
                    parameters = {"maximumPower": 0}
                elif command == "SET_FREQUENCY_REGULATION":
                    # Use current backup level as a reasonable default for optimal SOC
                    optimal_soc = current_settings.get("bmsBackupLevel")
                    if not isinstance(optimal_soc, (int, float)):
                        # fallback from status if present
                        status = (
                            self.coordinator.data.get("status", {})
                            if self.coordinator.data
                            else {}
                        )
                        energy_flow = (
                            status.get("energyFlow", {})
                            if isinstance(status, dict)
                            else {}
                        )
                        optimal_soc = energy_flow.get("batteryBackupLevel", 28)
                    parameters = {"powerAllocation": 0, "optimalSoc": int(optimal_soc)}
                else:
                    parameters = {}
            except Exception:
                parameters = {}

            # Set defaultMode with chosen command and computed parameters
            current_settings["defaultMode"] = {
                "command": command,
                "parameters": parameters,
            }

            payload = {"settings": current_settings}
            result = await self.coordinator.api.update_settings(payload)
            if result.get("successful", result.get("result") is not None):
                _LOGGER.info("Default operation mode set to %s", option)
                # Give device time to apply the change
                await asyncio.sleep(2)
            else:
                _LOGGER.warning(
                    "Default mode API call may not have succeeded: %s", result
                )
                await asyncio.sleep(1)
            
            # Refresh to get the latest state from device
            await self.coordinator.async_request_refresh()
            
        except Exception as e:
            _LOGGER.error("Error setting default operation mode: %s", e)
            await self.coordinator.async_request_refresh()

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        asyncio.create_task(self.async_select_option(option))


class EatonXStorageCurrentOperationModeSelect(CoordinatorEntity, SelectEntity):
    """Select entity to send immediate operation mode commands.

    Commands sent via /api/device/command.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:battery-clock"

    def __init__(self, coordinator: EatonBatteryStorageCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_current_operation_mode"
        )
        self._attr_name = "Current operation mode"
        self._options = [label for (label, _) in DEFAULT_MODE_OPTIONS] + [
            "Manual Charge",
            "Manual Discharge",
        ]
        self._option_to_cmd = {label: cmd for (label, cmd) in DEFAULT_MODE_OPTIONS}
        self._option_to_cmd.update(
            {"Manual Charge": "SET_CHARGE", "Manual Discharge": "SET_DISCHARGE"}
        )
        self._cmd_to_label = {cmd: label for (label, cmd) in DEFAULT_MODE_OPTIONS}
        self._cmd_to_label.update(
            {"SET_CHARGE": "Manual Charge", "SET_DISCHARGE": "Manual Discharge"}
        )

    @property
    def device_info(self):
        """Return device information."""
        return self.coordinator.device_info

    @property
    def options(self) -> list[str]:
        """Return list of available options."""
        return self._options

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        try:
            status = (
                self.coordinator.data.get("status", {}) if self.coordinator.data else {}
            )
            current_mode = (
                status.get("currentMode", {}) if isinstance(status, dict) else {}
            )
            cmd = current_mode.get("command")
            if cmd and cmd in self._cmd_to_label:
                return self._cmd_to_label[cmd]
        except Exception:
            pass
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if option not in self._option_to_cmd:
            _LOGGER.error("Invalid current operation mode option: %s", option)
            return

        try:
            command = self._option_to_cmd[option]

            # Get helper values from coordinator storage
            helper_values = getattr(self.coordinator, "number_values", {})

            # Determine duration based on command type
            duration = 1  # default fallback
            if command in ["SET_CHARGE"]:
                duration = helper_values.get("charge_duration", 1)
                _LOGGER.debug("Using charge_duration: %s for %s", duration, command)
            elif command in ["SET_DISCHARGE"]:
                duration = helper_values.get("discharge_duration", 1)
                _LOGGER.debug("Using discharge_duration: %s for %s", duration, command)
            else:
                # All intelligent modes use the shared run_duration
                duration = helper_values.get("run_duration", 2)
                _LOGGER.debug(
                    "Using run_duration: %s for intelligent mode %s (available helpers: %s)",
                    duration,
                    command,
                    list(helper_values.keys()),
                )

            # Build parameters based on command type
            parameters = {}

            if command == "SET_CHARGE":
                parameters = {
                    "action": "ACTION_CHARGE",
                    "power": int(helper_values.get("charge_power", 15)),  # percentage
                    "soc": int(helper_values.get("charge_end_soc", 90)),
                }
            elif command == "SET_DISCHARGE":
                parameters = {
                    "action": "ACTION_DISCHARGE",
                    "power": int(
                        helper_values.get("discharge_power", 15)
                    ),  # percentage
                    "soc": int(helper_values.get("discharge_end_soc", 10)),
                }
            elif command == "SET_PEAK_SHAVING":
                # Get current settings for house consumption threshold
                settings = (
                    self.coordinator.data.get("settings", {})
                    if self.coordinator.data
                    else {}
                )
                esm = (
                    settings.get("energySavingMode", {})
                    if isinstance(settings, dict)
                    else {}
                )
                max_peak = (
                    esm.get("houseConsumptionThreshold", 1000)
                    if isinstance(esm, dict)
                    else 1000
                )
                parameters = {"maxHousePeakConsumption": int(max_peak)}
            elif command == "SET_VARIABLE_GRID_INJECTION":
                parameters = {
                    "maximumPower": 0
                }  # Could be extended with helper value later
            elif command == "SET_FREQUENCY_REGULATION":
                # Use backup level as optimal SOC
                settings = (
                    self.coordinator.data.get("settings", {})
                    if self.coordinator.data
                    else {}
                )
                optimal_soc = (
                    settings.get("bmsBackupLevel", 28)
                    if isinstance(settings, dict)
                    else 28
                )
                parameters = {"powerAllocation": 0, "optimalSoc": int(optimal_soc)}

            result = await self.coordinator.api.send_device_command(
                command, int(duration), parameters
            )

            if result.get("successful", result.get("result") is not None):
                _LOGGER.info(
                    "Current operation mode set to %s for %d hours", option, duration
                )
                # Give device time to apply the change
                await asyncio.sleep(2)
            else:
                _LOGGER.warning(
                    "Current mode API call may not have succeeded: %s", result
                )
                await asyncio.sleep(1)

            # Refresh to get the latest state from device
            await self.coordinator.async_request_refresh()

        except Exception as e:
            _LOGGER.error("Error setting current operation mode: %s", e)
            await self.coordinator.async_request_refresh()
