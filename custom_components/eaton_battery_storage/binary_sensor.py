"""Binary sensors for Eaton Battery Storage integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ACCOUNT_TYPE_TECHNICIAN, CONF_USER_TYPE
from .coordinator import EatonConfigEntry, EatonXstorageHomeCoordinator
from .entity import EatonEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EatonBatteryStorageBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Eaton Battery Storage binary sensor entities."""

    is_on_fn: Callable[[dict[str, Any]], bool | None]
    technician_only: bool = False


DESCRIPTIONS = [
    EatonBatteryStorageBinarySensorEntityDescription(
        key="battery_charging",
        translation_key="battery_charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on_fn=lambda data: (
            data.get("status", {}).get("energyFlow", {}).get("batteryStatus")
            == "BAT_CHARGING"
        ),
    ),
    EatonBatteryStorageBinarySensorEntityDescription(
        key="battery_discharging",
        translation_key="battery_discharging",
        device_class=BinarySensorDeviceClass.POWER,
        is_on_fn=lambda data: (
            data.get("status", {}).get("energyFlow", {}).get("batteryStatus")
            == "BAT_DISCHARGING"
        ),
    ),
    EatonBatteryStorageBinarySensorEntityDescription(
        key="inverter_power_state",
        translation_key="inverter_power_state",
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda data: bool(data.get("device", {}).get("powerState")),
    ),
    EatonBatteryStorageBinarySensorEntityDescription(
        key="energy_saving_mode_activated",
        translation_key="energy_saving_mode_activated",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: bool(
            data.get("status", {})
            .get("energyFlow", {})
            .get("energySavingModeActivated")
        ),
    ),
    EatonBatteryStorageBinarySensorEntityDescription(
        key="bms_fault",
        translation_key="bms_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        technician_only=True,
        is_on_fn=lambda data: bool(
            data.get("technical_status", {}).get("bmsFaultCode")
        ),
    ),
    EatonBatteryStorageBinarySensorEntityDescription(
        key="has_unread_notifications",
        translation_key="has_unread_notifications",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: (
            (data.get("unread_notifications_count", {}).get("total") or 0) > 0
        ),
    ),
]


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: EatonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Eaton Battery Storage binary sensor platform."""
    coordinator = entry.runtime_data
    is_technician = (
        entry.data.get(CONF_USER_TYPE, ACCOUNT_TYPE_TECHNICIAN)
        == ACCOUNT_TYPE_TECHNICIAN
    )
    async_add_entities(
        EatonBatteryStorageBinarySensorEntity(coordinator, description)
        for description in DESCRIPTIONS
        if is_technician or not description.technician_only
    )


class EatonBatteryStorageBinarySensorEntity(EatonEntity, BinarySensorEntity):
    """Eaton Battery Storage binary sensor entity."""

    entity_description: EatonBatteryStorageBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: EatonXstorageHomeCoordinator,
        description: EatonBatteryStorageBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        # Ensure unique IDs are scoped to the config entry to support multiple devices
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.is_on_fn(self.coordinator.data or {})
