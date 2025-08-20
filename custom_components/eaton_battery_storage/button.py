import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN]["coordinator"]
    entities = [
        EatonXStorageMarkNotificationsReadButton(coordinator),
        EatonXStorageStopCurrentOperationButton(coordinator)
    ]
    async_add_entities(entities)

class EatonXStorageMarkNotificationsReadButton(CoordinatorEntity, ButtonEntity):
    """Button to mark all notifications as read."""
    
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator

    @property
    def name(self):
        return "Mark All Notifications Read"

    @property
    def unique_id(self):
        return "eaton_xstorage_mark_notifications_read"

    @property
    def icon(self):
        return "mdi:email-mark-as-unread"

    @property
    def entity_category(self):
        return EntityCategory.CONFIG

    @property
    def device_info(self):
        return self.coordinator.device_info

    async def async_press(self):
        """Mark all notifications as read."""
        try:
            result = await self.coordinator.api.mark_all_notifications_read()
            if result.get("successful"):
                _LOGGER.info("Successfully marked all notifications as read")
                # Trigger coordinator update to refresh notification data
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Failed to mark notifications as read: {result}")
        except Exception as e:
            _LOGGER.error(f"Error marking notifications as read: {e}")

    @property
    def should_poll(self):
        return False


class EatonXStorageStopCurrentOperationButton(CoordinatorEntity, ButtonEntity):
    """Button to stop/cancel current operation by setting to basic mode."""
    
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator

    @property
    def name(self):
        return "Stop Current Operation"

    @property
    def unique_id(self):
        return "eaton_xstorage_stop_current_operation"

    @property
    def icon(self):
        return "mdi:stop-circle"

    @property
    def entity_category(self):
        return EntityCategory.CONFIG

    @property
    def device_info(self):
        return self.coordinator.device_info

    async def async_press(self):
        """Stop current operation by setting to basic mode."""
        try:
            import asyncio
            
            # Send SET_BASIC_MODE command with minimal duration (1 hour)
            result = await self.coordinator.api.send_device_command("SET_BASIC_MODE", 1, {})
            
            if result.get("successful", result.get("result") is not None):
                _LOGGER.info("Successfully stopped current operation - set to basic mode")
                await asyncio.sleep(1)
            else:
                _LOGGER.warning(f"Stop operation API call may not have succeeded: {result}")
                await asyncio.sleep(1)
            
            # Trigger coordinator update to refresh current mode data
            await self.coordinator.async_request_refresh()
            
        except Exception as e:
            _LOGGER.error(f"Error stopping current operation: {e}")
            # Still refresh to get current state
            await self.coordinator.async_request_refresh()

    @property
    def should_poll(self):
        return False