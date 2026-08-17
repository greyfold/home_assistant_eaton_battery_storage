"""Select entities for Eaton battery storage system operation modes."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EatonError
from .const import DOMAIN, resolve_mode_command
from .coordinator import EatonConfigEntry, EatonXstorageHomeCoordinator
from .entity import EatonEntity
from .number_constants import (
    CHARGE_DURATION,
    CHARGE_END_SOC,
    CHARGE_POWER,
    DISCHARGE_DURATION,
    DISCHARGE_END_SOC,
    DISCHARGE_POWER,
    RUN_DURATION,
)

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)

# Option keys are the device command in snake_case, so the mapping back to the
# API stays obvious; the labels live in strings.json. Names follow the operation
# modes reference in the eaton-xstorage-home-api-doc repository.
DEFAULT_MODE_OPTIONS: dict[str, str] = {
    "basic_mode": "SET_BASIC_MODE",
    "maximize_auto_consumption": "SET_MAXIMIZE_AUTO_CONSUMPTION",
    "variable_grid_injection": "SET_VARIABLE_GRID_INJECTION",
    "frequency_regulation": "SET_FREQUENCY_REGULATION",
    "peak_shaving": "SET_PEAK_SHAVING",
}

# The dashboard can also drive the two manual modes, which settings cannot.
MANUAL_MODE_OPTIONS: dict[str, str] = {
    "manual_charge": "SET_CHARGE",
    "manual_discharge": "SET_DISCHARGE",
}

# Fallback state of charge used by frequency regulation when the device does
# not report a backup level.
DEFAULT_OPTIMAL_SOC = 28
DEFAULT_HOUSE_PEAK_CONSUMPTION = 1000


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: EatonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            EatonXStorageDefaultOperationModeSelect(coordinator),
            EatonXStorageCurrentOperationModeSelect(coordinator),
        ]
    )


class EatonXStorageBaseSelect(EatonEntity, SelectEntity):
    """Common behavior for the operation mode selects."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: EatonXstorageHomeCoordinator, options: dict[str, str]
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._option_to_cmd = options
        self._cmd_to_option = {cmd: option for option, cmd in options.items()}
        self._attr_options = list(options)

    def _optimal_soc(self, settings: dict[str, Any]) -> int:
        """Return the state of charge frequency regulation should hold."""
        energy_flow = (
            (self.coordinator.data or {}).get("status", {}).get("energyFlow", {})
        )
        for candidate in (
            settings.get("bmsBackupLevel"),
            energy_flow.get("batteryBackupLevel"),
        ):
            if isinstance(candidate, (int, float)):
                return int(candidate)
        return DEFAULT_OPTIMAL_SOC

    def _mode_parameters(
        self, command: str, settings: dict[str, Any]
    ) -> dict[str, Any]:
        """Build the parameters the device expects for an intelligent mode."""
        if command == "SET_PEAK_SHAVING":
            threshold = settings.get("energySavingMode", {}).get(
                "houseConsumptionThreshold"
            )
            if not isinstance(threshold, (int, float)):
                threshold = DEFAULT_HOUSE_PEAK_CONSUMPTION
            return {"maxHousePeakConsumption": int(threshold)}
        if command == "SET_VARIABLE_GRID_INJECTION":
            return {"maximumPower": 0}
        if command == "SET_FREQUENCY_REGULATION":
            return {"powerAllocation": 0, "optimalSoc": self._optimal_soc(settings)}
        return {}


class EatonXStorageDefaultOperationModeSelect(EatonXStorageBaseSelect):
    """Select entity to configure Default Operation Mode in settings.defaultMode."""

    _attr_icon = "mdi:transmission-tower"
    _attr_translation_key = "default_operation_mode"

    def __init__(self, coordinator: EatonXstorageHomeCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, DEFAULT_MODE_OPTIONS)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_default_operation_mode"
        )

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        settings = (self.coordinator.data or {}).get("settings", {})
        default_mode = settings.get("defaultMode", {})
        return self._cmd_to_option.get(default_mode.get("command"))

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        command = self._option_to_cmd[option]

        def mutate(settings: dict) -> None:
            settings["defaultMode"] = {
                "command": command,
                "parameters": self._mode_parameters(command, settings),
            }

        try:
            await self.coordinator.async_patch_settings(mutate)
        except EatonError as err:
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_default_operation_mode_failed",
                translation_placeholders={"mode": option},
            ) from err


class EatonXStorageCurrentOperationModeSelect(EatonXStorageBaseSelect):
    """Select entity to send immediate operation mode commands.

    Commands sent via /api/device/command.
    """

    _attr_icon = "mdi:battery-clock"
    _attr_translation_key = "current_operation_mode"

    def __init__(self, coordinator: EatonXstorageHomeCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, DEFAULT_MODE_OPTIONS | MANUAL_MODE_OPTIONS)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_current_operation_mode"
        )

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        status = (self.coordinator.data or {}).get("status", {})
        current_mode = status.get("currentMode", {})
        return self._cmd_to_option.get(resolve_mode_command(current_mode))

    def _command_duration(self, command: str, helper_values: dict) -> int:
        """Return the run duration in hours configured for this command."""
        if command == "SET_CHARGE":
            return int(helper_values.get(CHARGE_DURATION, 1))
        if command == "SET_DISCHARGE":
            return int(helper_values.get(DISCHARGE_DURATION, 1))
        # All intelligent modes use the shared run_duration
        return int(helper_values.get(RUN_DURATION, 2))

    def _command_parameters(self, command: str, helper_values: dict) -> dict[str, Any]:
        """Build the parameters the device expects for the selected command."""
        settings = (self.coordinator.data or {}).get("settings", {})

        if command == "SET_CHARGE":
            return {
                "action": "ACTION_CHARGE",
                "power": int(helper_values.get(CHARGE_POWER, 15)),
                "soc": int(helper_values.get(CHARGE_END_SOC, 90)),
            }
        if command == "SET_DISCHARGE":
            return {
                "action": "ACTION_DISCHARGE",
                "power": int(helper_values.get(DISCHARGE_POWER, 15)),
                "soc": int(helper_values.get(DISCHARGE_END_SOC, 10)),
            }
        return self._mode_parameters(command, settings)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        command = self._option_to_cmd[option]
        helper_values = self.coordinator.number_values
        duration = self._command_duration(command, helper_values)

        try:
            response = await self.coordinator.api.send_device_command(
                command, duration, self._command_parameters(command, helper_values)
            )
        except EatonError as err:
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_operation_mode_failed",
                translation_placeholders={"mode": option},
            ) from err

        await self.coordinator.async_apply_command_result(response)

        _LOGGER.debug("Current operation mode set to %s for %d hours", option, duration)
