"""Eaton battery storage event platform."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.event import EventEntity
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
    """Set up event entities."""
    coordinator: EatonBatteryStorageCoordinator = config_entry.runtime_data
    async_add_entities([EatonXStorageNotificationEvent(coordinator)])


class EatonXStorageNotificationEvent(CoordinatorEntity, EventEntity):
    """Event entity that emits an event when new unread notifications are detected."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_event_types = ["notification"]

    def __init__(self, coordinator: EatonBatteryStorageCoordinator) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_notifications_event"
        )
        self._attr_name = "Notifications event"
        self._seen: set[str] = set()
        self._primed = False
        # Keep track of the last emitted event type to expose a friendly state
        self._last_event_type: str | None = None

    @property
    def device_info(self):
        """Return device information."""
        return self.coordinator.device_info

    def _extract_alerts(self) -> list[dict[str, Any]]:
        """Extract alerts from coordinator data."""
        data = (
            self.coordinator.data.get("notifications", {})
            if self.coordinator.data
            else {}
        )
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

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to hass."""
        await super().async_added_to_hass()
        # Prime seen set on first add to avoid a burst of historical events
        for alert in self._extract_alerts():
            aid = alert.get("alertId") or alert.get("alert_id")
            if aid:
                self._seen.add(aid)
        self._primed = True

    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
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
        except (KeyError, TypeError, AttributeError) as e:
            _LOGGER.error("Error processing notifications for events: %s", e)
        finally:
            # Ensure the entity state is updated in HA
            super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        # Provide friendly status information as attributes instead of overriding state
        # Priority:
        # 1) If there are unread notifications, show 'has_unread'
        # 2) Else show last event type if available
        # 3) Else 'idle'
        status = "idle"
        unread_count = 0

        try:
            if self.coordinator and self.coordinator.data:
                unread_data = self.coordinator.data.get(
                    "unread_notifications_count", {}
                )
                # unread endpoint returns {"total": <int>}
                if isinstance(unread_data, dict):
                    unread_count = int(unread_data.get("total", 0) or 0)

            if unread_count > 0:
                status = "has_unread"
            elif self._last_event_type:
                status = self._last_event_type
        except Exception:
            pass

        return {
            "status": status,
            "unread_count": unread_count,
            "last_event_type": self._last_event_type,
        }
