"""Button platform for Eaton Battery Storage integration."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import EatonBatteryStorageCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    coordinator: EatonBatteryStorageCoordinator = config_entry.runtime_data
    entities = [
        EatonXStorageMarkNotificationsReadButton(coordinator),
        EatonXStorageStopCurrentOperationButton(coordinator),
    ]
    async_add_entities(entities)


class EatonXStorageMarkNotificationsReadButton(CoordinatorEntity, ButtonEntity):
    """Button to mark all notifications as read."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:email-mark-as-unread"

    def __init__(self, coordinator: EatonBatteryStorageCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_mark_notifications_read"
        )
        self._attr_name = "Mark all notifications read"

    @property
    def device_info(self):
        """Return device information."""
        return self.coordinator.device_info

    async def async_press(self) -> None:
        """Mark all notifications as read."""
        try:
            result = await self.coordinator.api.mark_all_notifications_read()
            if result.get("successful"):
                _LOGGER.info("Successfully marked all notifications as read")
                # Trigger coordinator update to refresh notification data
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to mark notifications as read: %s", result)
        except Exception as e:
            _LOGGER.error("Error marking notifications as read: %s", e)


class EatonXStorageStopCurrentOperationButton(CoordinatorEntity, ButtonEntity):
    """Button to stop/cancel current operation by setting to basic mode."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:stop-circle"

    def __init__(self, coordinator: EatonBatteryStorageCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_stop_current_operation"
        )
        self._attr_name = "Stop current operation"

    @property
    def device_info(self):
        """Return device information."""
        return self.coordinator.device_info

    async def async_press(self) -> None:
        """Stop current operation by setting to basic mode."""
        try:
            # Send SET_BASIC_MODE command with minimal duration (1 hour)
            result = await self.coordinator.api.send_device_command(
                "SET_BASIC_MODE", 1, {}
            )

            if result.get("successful", result.get("result") is not None):
                _LOGGER.info(
                    "Successfully stopped current operation - set to basic mode"
                )
                await asyncio.sleep(1)
            else:
                _LOGGER.warning(
                    "Stop operation API call may not have succeeded: %s", result
                )
                await asyncio.sleep(1)

            # Trigger coordinator update to refresh current mode data
            await self.coordinator.async_request_refresh()

        except Exception as e:
            _LOGGER.error("Error stopping current operation: %s", e)
            # Still refresh to get current state
            await self.coordinator.async_request_refresh()
