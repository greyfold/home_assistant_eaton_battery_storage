import logging
from homeassistant.components.event import EventEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([EatonXStorageNotificationEvent(coordinator)])

class EatonXStorageNotificationEvent(CoordinatorEntity, EventEntity):
    """Event entity that emits an event when new unread notifications are detected."""

    _attr_event_types = {"notification"}

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._seen = set()
        self._primed = False
        # Keep track of the last emitted event type to expose a friendly state
        self._last_event_type = None

    @property
    def name(self):
        return "Notifications Event"

    @property
    def unique_id(self):
        return "eaton_xstorage_notifications_event"

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    @property
    def device_info(self):
        return self.coordinator.device_info

    def _extract_alerts(self):
        data = self.coordinator.data.get("notifications", {}) if self.coordinator.data else {}
        results = data.get("results", [])
        # Normalize to list of dicts with alertId
        alerts = []
        for item in results:
            if not isinstance(item, dict):
                continue
            alert_id = item.get("alertId") or item.get("alert_id")
            if alert_id:
                alerts.append(item)
        return alerts

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        # Prime seen set on first add to avoid a burst of historical events
        for alert in self._extract_alerts():
            aid = alert.get("alertId") or alert.get("alert_id")
            if aid:
                self._seen.add(aid)
        self._primed = True

    def _handle_coordinator_update(self) -> None:
        # On each data refresh, emit events for new unseen alerts
        try:
            for alert in self._extract_alerts():
                aid = alert.get("alertId") or alert.get("alert_id")
                if not aid or aid in self._seen:
                    continue
                self._seen.add(aid)
                if self._primed:
                    # Emit event with full alert payload in "event_data"
                    self._trigger_event("notification", {"alert": alert})
                    # Update the visible state to the last event type
                    self._last_event_type = "notification"
        except Exception as e:
            _LOGGER.error("Error processing notifications for events: %s", e)
        finally:
            # Ensure the entity state is updated in HA
            super()._handle_coordinator_update()

    @property
    def should_poll(self):
        return False

    @property
    def state(self):
        # Friendly state instead of Unknown before first event.
        # Priority:
        # 1) If there are unread notifications, show 'has_unread'
        # 2) Else show last event type if available
        # 3) Else 'idle'
        try:
            unread = 0
            if self.coordinator and self.coordinator.data:
                unread_data = self.coordinator.data.get("unread_notifications_count", {})
                # unread endpoint returns {"total": <int>}
                if isinstance(unread_data, dict):
                    unread = int(unread_data.get("total", 0) or 0)
            if unread > 0:
                return "Has Unread"
        except Exception:
            pass
        return self._last_event_type or "idle"
