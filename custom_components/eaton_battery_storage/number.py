"""Number platform for Eaton Battery Storage integration.

This module provides number entities for controlling various settings of the Eaton
Battery Storage system, including:
- Charge and discharge power settings (both percentage and wattage)
- House consumption threshold for energy saving mode
- Battery backup level configuration
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .number_constants import NUMBER_ENTITIES

if TYPE_CHECKING:
    from .coordinator import EatonBatteryStorageCoordinator

    type EatonBatteryStorageConfigEntry = ConfigEntry[EatonBatteryStorageCoordinator]

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EatonBatteryStorageConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Eaton Battery Storage number platform."""
    coordinator = entry.runtime_data

    # Setup storage for local number values (for percentage/watt conversions)
    store = Store(hass, 1, f"{DOMAIN}_number_values.json")
    stored = await store.async_load() or {}

    # Store data directly on the coordinator for access by entities
    if not hasattr(coordinator, "number_values"):
        coordinator.number_values = stored
    if not hasattr(coordinator, "number_store"):
        coordinator.number_store = store

    entities: list[NumberEntity] = []

    # Add configurable number entities from constants
    entities.extend(
        EatonBatteryNumberEntity(coordinator, desc) for desc in NUMBER_ENTITIES
    )

    # Add API-controlled settings entities
    entities.extend(
        [
            EatonXStorageHouseConsumptionThresholdNumber(coordinator),
            EatonXStorageBatteryBackupLevelNumber(coordinator),
        ]
    )

    _LOGGER.debug("Adding %d number entities", len(entities))
    async_add_entities(entities)


class EatonBatteryNumberEntity(CoordinatorEntity, NumberEntity):
    """Number entity for Eaton Battery Storage configurable values."""

    _attr_mode = "box"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EatonBatteryStorageCoordinator,
        description: dict[str, str | int | float],
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._key = description["key"]
        self._attr_unique_id = f"eaton_battery_{description['key']}"
        self._attr_name = description["name"]
        self._attr_native_min_value = float(description["min"])
        self._attr_native_max_value = float(description["max"])
        self._attr_native_step = float(description["step"])
        self._attr_native_unit_of_measurement = description["unit"]
        self._attr_device_class = description["device_class"]

    async def async_added_to_hass(self) -> None:
        """Register for dispatcher updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{DOMAIN}_number_update", self._handle_external_update
            )
        )

    def _handle_external_update(self) -> None:
        """Handle external updates via dispatcher."""
        self.schedule_update_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, int] | None:
        """Return extra state attributes showing linked values."""
        native_val = self.native_value
        if native_val is None:
            return None

        if self._key == "charge_power":
            watts = int(round((native_val / 100) * 3600))
            return {"wattage": watts}
        elif self._key == "charge_power_watt":
            percent = int(round((native_val / 3600) * 100))
            return {"percent": percent}
        elif self._key == "discharge_power":
            watts = int(round((native_val / 100) * 3600))
            return {"wattage": watts}
        elif self._key == "discharge_power_watt":
            percent = int(round((native_val / 3600) * 100))
            return {"percent": percent}
        return None

    @property
    def native_value(self) -> float | None:
        """Return the current value from storage."""
        return getattr(self.coordinator, "number_values", {}).get(self._key)

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value and update linked entities."""
        # Ensure number_values exists on coordinator
        if not hasattr(self.coordinator, "number_values"):
            self.coordinator.number_values = {}
        if not hasattr(self.coordinator, "number_store"):
            store = Store(self.hass, 1, f"{DOMAIN}_number_values.json")
            self.coordinator.number_store = store

        # Store the value
        self.coordinator.number_values[self._key] = value

        # Calculate and store linked values
        linked_key = self._calculate_linked_value(value)

        # Save to persistent storage
        await self.coordinator.number_store.async_save(self.coordinator.number_values)

        # Update this entity
        self.async_write_ha_state()

        # Notify other entities via dispatcher
        if linked_key:
            async_dispatcher_send(self.hass, f"{DOMAIN}_number_update")

    def _calculate_linked_value(self, value: float) -> str | None:
        """Calculate and store linked value, return linked key if any."""
        if self._key == "charge_power":
            watts = int(round((value / 100) * 3600))
            self.coordinator.number_values["charge_power_watt"] = watts
            return "charge_power_watt"
        elif self._key == "charge_power_watt":
            percent = int(round((value / 3600) * 100))
            self.coordinator.number_values["charge_power"] = percent
            return "charge_power"
        elif self._key == "discharge_power":
            watts = int(round((value / 100) * 3600))
            self.coordinator.number_values["discharge_power_watt"] = watts
            return "discharge_power_watt"
        elif self._key == "discharge_power_watt":
            percent = int(round((value / 3600) * 100))
            self.coordinator.number_values["discharge_power"] = percent
            return "discharge_power"
        return None

    @property
    def device_info(self) -> dict[str, str]:
        """Return device information."""
        return self.coordinator.device_info


class EatonXStorageHouseConsumptionThresholdNumber(CoordinatorEntity, NumberEntity):
    """Number entity to control the House Consumption Threshold for Energy Saving Mode."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:home-lightning-bolt"
    _attr_native_unit_of_measurement = "W"
    _attr_native_min_value = 300
    _attr_native_max_value = 1000
    _attr_native_step = 25
    _attr_mode = "box"

    def __init__(self, coordinator: EatonBatteryStorageCoordinator) -> None:
        """Initialize the house consumption threshold number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = "eaton_xstorage_set_house_consumption_threshold"
        self._attr_name = "House consumption threshold"
        self._optimistic_value: int | None = None

    @property
    def device_info(self) -> dict[str, str]:
        """Return device information."""
        return self.coordinator.device_info

    @property
    def native_value(self) -> int | None:
        """Return the current house consumption threshold value."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        try:
            # Prefer device endpoint data (mirrors active runtime state)
            device = (
                self.coordinator.data.get("device", {}) if self.coordinator.data else {}
            )
            if isinstance(device, dict):
                es = device.get("energySavingMode", {})
                if isinstance(es, dict) and "houseConsumptionThreshold" in es:
                    return es.get("houseConsumptionThreshold")
            # Fallback to settings cache
            settings_data = (
                self.coordinator.data.get("settings", {})
                if self.coordinator.data
                else {}
            )
            es2 = (
                settings_data.get("energySavingMode", {})
                if isinstance(settings_data, dict)
                else {}
            )
            return es2.get("houseConsumptionThreshold", 300)
        except (KeyError, TypeError, AttributeError):
            return 300

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the house consumption threshold value."""
        try:
            # Set optimistic value immediately for responsive UI
            self._optimistic_value = int(value)
            self.async_write_ha_state()

            # First, get the current settings from the API (not cached data)
            current_settings_response = await self.coordinator.api.get_settings()
            if not current_settings_response or not current_settings_response.get(
                "result"
            ):
                _LOGGER.error("Failed to get current settings from API")
                self._optimistic_value = None
                return

            # Get the current settings data
            current_settings = current_settings_response.get("result", {})

            # Transform the settings data to match PUT API expectations
            # The GET API returns objects, but PUT API expects strings/primitives
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

            # Update only the energySavingMode.houseConsumptionThreshold field
            if "energySavingMode" not in current_settings:
                current_settings["energySavingMode"] = {}
            current_settings["energySavingMode"]["houseConsumptionThreshold"] = int(
                value
            )

            # API expects data wrapped in "settings" object
            payload = {"settings": current_settings}

            result = await self.coordinator.api.update_settings(payload)

            if result.get("successful", result.get("result") is not None):
                _LOGGER.info(
                    "Successfully set house consumption threshold to %dW", int(value)
                )
                await asyncio.sleep(2)
            else:
                _LOGGER.warning(
                    "API call completed but may not have succeeded: %s", result
                )
                await asyncio.sleep(1)

            # Always refresh the coordinator data
            await self.coordinator.async_request_refresh()

            # Clear optimistic value so we use real data
            self._optimistic_value = None

        except Exception as exc:
            _LOGGER.error("Error setting house consumption threshold: %s", exc)
            # Clear optimistic value and refresh to get current state
            self._optimistic_value = None
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(
                f"Failed to set house consumption threshold to {int(value)}W"
            ) from exc

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Clear optimistic value when we get real data from coordinator
        if self._optimistic_value is not None:
            self._optimistic_value = None
        super()._handle_coordinator_update()


class EatonXStorageBatteryBackupLevelNumber(CoordinatorEntity, NumberEntity):
    """Number entity to control the Battery Backup Level (bmsBackupLevel)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:battery-lock"
    _attr_native_unit_of_measurement = "%"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = "box"

    def __init__(self, coordinator: EatonBatteryStorageCoordinator) -> None:
        """Initialize the battery backup level number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = "eaton_xstorage_set_battery_backup_level"
        self._attr_name = "Battery backup level"
        self._optimistic_value: int | None = None

    @property
    def native_value(self) -> int | None:
        """Return the current battery backup level value."""
        if self._optimistic_value is not None:
            return self._optimistic_value
        try:
            # Prefer settings cache
            settings_data = (
                self.coordinator.data.get("settings", {})
                if self.coordinator.data
                else {}
            )
            if isinstance(settings_data, dict) and "bmsBackupLevel" in settings_data:
                return settings_data.get("bmsBackupLevel")
            # Fallback to status energyFlow if exposed
            status = (
                self.coordinator.data.get("status", {}) if self.coordinator.data else {}
            )
            energy_flow = (
                status.get("energyFlow", {}) if isinstance(status, dict) else {}
            )
            if "batteryBackupLevel" in energy_flow:
                return energy_flow.get("batteryBackupLevel")
            return 0
        except (KeyError, TypeError, AttributeError):
            return 0

    @property
    def device_info(self) -> dict[str, str]:
        """Return device information."""
        return self.coordinator.device_info

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the battery backup level value."""
        try:
            self._optimistic_value = int(value)
            self.async_write_ha_state()

            current_settings_response = await self.coordinator.api.get_settings()
            if not current_settings_response or not current_settings_response.get(
                "result"
            ):
                _LOGGER.error("Failed to get current settings from API")
                self._optimistic_value = None
                return
            current_settings = current_settings_response.get("result", {})

            # Transform composite objects
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

            current_settings["bmsBackupLevel"] = int(value)

            payload = {"settings": current_settings}
            result = await self.coordinator.api.update_settings(payload)
            if result.get("successful", result.get("result") is not None):
                _LOGGER.info(
                    "Successfully set battery backup level to %d%%", int(value)
                )
                await asyncio.sleep(2)
            else:
                _LOGGER.warning(
                    "API call completed but may not have succeeded: %s", result
                )
                await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()
            self._optimistic_value = None
        except Exception as exc:
            _LOGGER.error("Error setting battery backup level: %s", exc)
            self._optimistic_value = None
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(
                f"Failed to set battery backup level to {int(value)}%"
            ) from exc

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._optimistic_value is not None:
            self._optimistic_value = None
        super()._handle_coordinator_update()
