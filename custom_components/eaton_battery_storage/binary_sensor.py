"""Binary sensors for Eaton Battery Storage integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from .coordinator import EatonBatteryStorageCoordinator

    type EatonBatteryStorageConfigEntry = ConfigEntry[EatonBatteryStorageCoordinator]

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EatonBatteryStorageBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Eaton Battery Storage binary sensor entities."""

    is_on_fn: Callable[[dict[str, Any]], bool | None]


DESCRIPTIONS = [
    EatonBatteryStorageBinarySensorEntityDescription(  # pylint: disable=unexpected-keyword-arg
        key="battery_charging",
        translation_key="battery_charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on_fn=lambda data: (
            data.get("status", {}).get("energyFlow", {}).get("batteryStatus")
            == "BAT_CHARGING"
        ),
    ),
    EatonBatteryStorageBinarySensorEntityDescription(  # pylint: disable=unexpected-keyword-arg
        key="battery_discharging",
        translation_key="battery_discharging",
        device_class=BinarySensorDeviceClass.POWER,
        is_on_fn=lambda data: (
            data.get("status", {}).get("energyFlow", {}).get("batteryStatus")
            == "BAT_DISCHARGING"
        ),
    ),
    EatonBatteryStorageBinarySensorEntityDescription(  # pylint: disable=unexpected-keyword-arg
        key="inverter_power_state",
        translation_key="inverter_power_state",
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: bool(data.get("device", {}).get("powerState")),
    ),
    EatonBatteryStorageBinarySensorEntityDescription(  # pylint: disable=unexpected-keyword-arg
        key="has_unread_notifications",
        translation_key="has_unread_notifications",
        is_on_fn=lambda data: (
            data.get("unread_notifications_count", {}).get("total", 0) > 0
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    entry: EatonBatteryStorageConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Eaton Battery Storage binary sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        EatonBatteryStorageBinarySensorEntity(coordinator, description)
        for description in DESCRIPTIONS
    )


class EatonBatteryStorageBinarySensorEntity(CoordinatorEntity, BinarySensorEntity):
    """Eaton Battery Storage binary sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EatonBatteryStorageCoordinator,
        description: EatonBatteryStorageBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"eaton_xstorage_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        try:
            return self.entity_description.is_on_fn(self.coordinator.data or {})
        except (KeyError, ValueError, TypeError) as exc:
            _LOGGER.error(
                "Error retrieving binary state for %s: %s",
                self.entity_description.key,
                exc,
            )
            return None

    @property
    def device_info(self) -> dict[str, str]:
        """Return device information."""
        return self.coordinator.device_info
