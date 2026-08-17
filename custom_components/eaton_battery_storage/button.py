"""Button platform for Eaton Battery Storage integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EatonError
from .const import DOMAIN
from .coordinator import EatonConfigEntry, EatonXstorageHomeCoordinator
from .entity import EatonEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: EatonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            EatonXStorageMarkNotificationsReadButton(coordinator),
            EatonXStorageStopCurrentOperationButton(coordinator),
        ]
    )


class EatonXStorageBaseButton(EatonEntity, ButtonEntity):
    """Common behavior for the Eaton xStorage Home buttons."""

    _attr_entity_category = EntityCategory.CONFIG


class EatonXStorageMarkNotificationsReadButton(EatonXStorageBaseButton):
    """Button to mark all notifications as read."""

    _attr_icon = "mdi:email-mark-as-unread"
    _attr_translation_key = "mark_notifications_read"

    def __init__(self, coordinator: EatonXstorageHomeCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_mark_notifications_read"
        )

    async def async_press(self) -> None:
        """Mark all notifications as read."""
        try:
            await self.coordinator.api.mark_all_notifications_read()
        except EatonError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="mark_notifications_read_failed",
            ) from err
        finally:
            await self.coordinator.async_request_refresh()


class EatonXStorageStopCurrentOperationButton(EatonXStorageBaseButton):
    """Button to stop/cancel current operation by setting to basic mode."""

    _attr_icon = "mdi:stop-circle"
    _attr_translation_key = "stop_current_operation"

    def __init__(self, coordinator: EatonXstorageHomeCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_stop_current_operation"
        )

    async def async_press(self) -> None:
        """Stop current operation by setting to basic mode."""
        try:
            response = await self.coordinator.api.send_device_command(
                "SET_BASIC_MODE", 1, {}
            )
        except EatonError as err:
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="stop_current_operation_failed",
            ) from err

        await self.coordinator.async_apply_command_result(response)
