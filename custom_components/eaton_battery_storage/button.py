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
        EatonXStorageStopCurrentOperationButton(coordinator),
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
        return getattr(self.coordinator, "device_info", None) or {
            "identifiers": {(DOMAIN, self.coordinator.api.host)},
            "name": "Eaton xStorage Home",
            "manufacturer": "Eaton",
            "model": "xStorage Home",
            "entry_type": "service",
            "configuration_url": f"https://{self.coordinator.api.host}",
        }

    async def async_press(self):
        try:
            result = await self.coordinator.api.mark_all_notifications_read()
            if result.get("successful"):
                _LOGGER.info("Marked all notifications as read")
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
        return getattr(self.coordinator, "device_info", None) or {
            "identifiers": {(DOMAIN, self.coordinator.api.host)},
            "name": "Eaton xStorage Home",
            "manufacturer": "Eaton",
            "model": "xStorage Home",
            "entry_type": "service",
            "configuration_url": f"https://{self.coordinator.api.host}",
        }

    async def async_press(self):
        try:
            import asyncio
            result = await self.coordinator.api.send_device_command("SET_BASIC_MODE", 1, {})
            if result.get("successful", result.get("result") is not None):
                _LOGGER.info("Stopped current operation (basic mode)")
                await asyncio.sleep(1)
            else:
                _LOGGER.warning(f"Stop operation may not have succeeded: {result}")
                await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()
        except Exception as e:
            _LOGGER.error(f"Error stopping current operation: {e}")
            await self.coordinator.async_request_refresh()

    @property
    def should_poll(self):
        return False
