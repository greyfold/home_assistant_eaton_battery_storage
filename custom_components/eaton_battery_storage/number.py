"""Number platform for Eaton Battery Storage integration.

This module provides number entities for controlling various settings of the Eaton
Battery Storage system, including:
- Charge and discharge power settings (both percentage and wattage)
- House consumption threshold for energy saving mode
- Battery backup level configuration
"""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.number.const import NumberDeviceClass
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EatonError
from .const import DOMAIN
from .coordinator import (
    EatonConfigEntry,
    EatonXstorageHomeCoordinator,
    number_update_signal,
)
from .entity import EatonEntity
from .number_constants import (
    CHARGE_POWER,
    CHARGE_POWER_WATT,
    DISCHARGE_POWER,
    DISCHARGE_POWER_WATT,
    NUMBER_ENTITIES,
    NumberEntityDefinition,
)

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)

# The watt entities mirror the 5-100 % range of their paired percentage entity.
WATT_KEYS = (CHARGE_POWER_WATT, DISCHARGE_POWER_WATT)
PERCENT_KEYS = (CHARGE_POWER, DISCHARGE_POWER)
LINKED_KEYS = (
    (CHARGE_POWER, CHARGE_POWER_WATT),
    (DISCHARGE_POWER, DISCHARGE_POWER_WATT),
)
MIN_POWER_PERCENT = 5


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: EatonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Eaton Battery Storage number platform."""
    coordinator = entry.runtime_data

    entities: list[NumberEntity] = [
        EatonBatteryNumberEntity(coordinator, description)
        for description in NUMBER_ENTITIES
    ]
    entities.extend(
        [
            EatonXStorageHouseConsumptionThresholdNumber(coordinator),
            EatonXStorageBatteryBackupLevelNumber(coordinator),
        ]
    )

    _LOGGER.debug("Adding %d number entities", len(entities))
    async_add_entities(entities)


class EatonBatteryNumberEntity(EatonEntity, NumberEntity):
    """Number entity for Eaton Battery Storage configurable values."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: EatonXstorageHomeCoordinator,
        description: NumberEntityDefinition,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._key = description["key"]
        # Scope unique ID to config entry to support multiple devices
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{description['key']}"
        )
        self._attr_translation_key = description["translation_key"]
        self._attr_native_min_value = float(description["min"])
        self._attr_native_max_value = float(description["max"])
        self._attr_native_step = float(description["step"])
        self._attr_native_unit_of_measurement = description["unit"]
        self._attr_device_class = description["device_class"]

    @property
    def native_min_value(self) -> float:
        """Return the minimum, which for watts follows the inverter rating."""
        if self._key in WATT_KEYS:
            full_scale = self.coordinator.full_scale_power
            return float(round(full_scale * MIN_POWER_PERCENT / 100))
        return self._attr_native_min_value

    @property
    def native_max_value(self) -> float:
        """Return the maximum, which for watts follows the inverter rating."""
        if self._key in WATT_KEYS:
            return float(self.coordinator.full_scale_power)
        return self._attr_native_max_value

    async def async_added_to_hass(self) -> None:
        """Register for dispatcher updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                number_update_signal(self.coordinator.config_entry.entry_id),
                self._handle_external_update,
            )
        )

    @callback
    def _handle_external_update(self) -> None:
        """Handle the paired entity having written a new linked value."""
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, int] | None:
        """Return extra state attributes showing linked values."""
        native_val = self.native_value
        if native_val is None:
            return None

        full_scale = self.coordinator.full_scale_power
        if self._key in PERCENT_KEYS:
            return {"wattage": round((native_val / 100) * full_scale)}
        if self._key in WATT_KEYS:
            return {"percent": round((native_val / full_scale) * 100)}
        return None

    @property
    def native_value(self) -> float | None:
        """Return the current value from storage."""
        return self.coordinator.number_values.get(self._key)

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value and update linked entities."""
        self.coordinator.number_values[self._key] = value
        linked_key = self._calculate_linked_value(value)

        await self.coordinator.number_store.async_save(self.coordinator.number_values)
        self.async_write_ha_state()

        if linked_key:
            async_dispatcher_send(
                self.hass,
                number_update_signal(self.coordinator.config_entry.entry_id),
            )

    def _calculate_linked_value(self, value: float) -> str | None:
        """Calculate and store linked value, return linked key if any."""
        full_scale = self.coordinator.full_scale_power
        for percent_key, watt_key in LINKED_KEYS:
            if self._key == percent_key:
                self.coordinator.number_values[watt_key] = round(
                    (value / 100) * full_scale
                )
                return watt_key
            if self._key == watt_key:
                self.coordinator.number_values[percent_key] = round(
                    (value / full_scale) * 100
                )
                return percent_key
        return None


class EatonXStorageHouseConsumptionThresholdNumber(EatonEntity, NumberEntity):
    """Number entity to control the House Consumption Threshold.

    Used for Energy Saving Mode.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:home-lightning-bolt"
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 300
    _attr_native_max_value = 1000
    _attr_native_step = 25
    _attr_mode = NumberMode.BOX
    _attr_translation_key = "house_consumption_threshold"

    def __init__(self, coordinator: EatonXstorageHomeCoordinator) -> None:
        """Initialize the house consumption threshold number entity."""
        super().__init__(coordinator)
        # Scope unique ID to config entry for multi-device setups
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_set_house_consumption_threshold"
        )
        self._optimistic_value: int | None = None

    @property
    def native_value(self) -> int | None:
        """Return the current house consumption threshold value."""
        if self._optimistic_value is not None:
            return self._optimistic_value

        data = self.coordinator.data or {}
        # Prefer device endpoint data (mirrors active runtime state)
        device_esm = data.get("device", {}).get("energySavingMode", {})
        if "houseConsumptionThreshold" in device_esm:
            return device_esm["houseConsumptionThreshold"]

        settings_esm = data.get("settings", {}).get("energySavingMode", {})
        return settings_esm.get("houseConsumptionThreshold", 300)

    async def async_set_native_value(self, value: float) -> None:
        """Set the house consumption threshold value."""
        self._optimistic_value = int(value)
        self.async_write_ha_state()

        def mutate(settings: dict) -> None:
            settings.setdefault("energySavingMode", {})["houseConsumptionThreshold"] = (
                int(value)
            )

        try:
            await self.coordinator.async_patch_settings(mutate)
        except EatonError as err:
            self._optimistic_value = None
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_house_consumption_threshold_failed",
                translation_placeholders={"value": str(int(value))},
            ) from err

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._optimistic_value = None
        super()._handle_coordinator_update()


class EatonXStorageBatteryBackupLevelNumber(EatonEntity, NumberEntity):
    """Number entity to control the Battery Backup Level (bmsBackupLevel)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:battery-lock"
    _attr_device_class = NumberDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_translation_key = "battery_backup_level"

    def __init__(self, coordinator: EatonXstorageHomeCoordinator) -> None:
        """Initialize the battery backup level number entity."""
        super().__init__(coordinator)
        # Scope unique ID to config entry for multi-device setups
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_set_battery_backup_level"
        )
        self._optimistic_value: int | None = None

    @property
    def native_value(self) -> int | None:
        """Return the current battery backup level value."""
        if self._optimistic_value is not None:
            return self._optimistic_value

        data = self.coordinator.data or {}
        settings_data = data.get("settings", {})
        if "bmsBackupLevel" in settings_data:
            return settings_data["bmsBackupLevel"]

        energy_flow = data.get("status", {}).get("energyFlow", {})
        return energy_flow.get("batteryBackupLevel", 0)

    async def async_set_native_value(self, value: float) -> None:
        """Set the battery backup level value."""
        self._optimistic_value = int(value)
        self.async_write_ha_state()

        def mutate(settings: dict) -> None:
            settings["bmsBackupLevel"] = int(value)

        try:
            await self.coordinator.async_patch_settings(mutate)
        except EatonError as err:
            self._optimistic_value = None
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_battery_backup_level_failed",
                translation_placeholders={"value": str(int(value))},
            ) from err

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._optimistic_value = None
        super()._handle_coordinator_update()
