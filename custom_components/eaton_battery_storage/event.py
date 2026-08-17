"""Eaton battery storage event platform."""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import EatonConfigEntry, EatonXstorageHomeCoordinator
from .entity import EatonEntity

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

# Number of alert IDs remembered to suppress repeat events.
SEEN_ALERTS_LIMIT = 500


def _alert_id(alert: dict[str, Any]) -> str:
    """Return the identifier of an alert, empty when it carries none."""
    return str(alert.get("alertId") or alert.get("alert_id") or "")


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: EatonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up event entities."""
    async_add_entities([EatonXStorageNotificationEvent(entry.runtime_data)])


class EatonXStorageNotificationEvent(EatonEntity, EventEntity):
    """Event entity that emits an event when new unread notifications are detected."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_event_types = ["notification"]
    _attr_translation_key = "notifications_event"

    def __init__(self, coordinator: EatonXstorageHomeCoordinator) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_notifications_event"
        )
        self._seen: deque[str] = deque(maxlen=SEEN_ALERTS_LIMIT)
        self._seen_ids: set[str] = set()
        self._primed = False
        # Keep track of the last emitted event type to expose a friendly state
        self._last_event_type: str | None = None

    def _remember(self, alert_id: str) -> None:
        """Record an alert as seen, evicting the oldest once the cap is hit."""
        if len(self._seen) == SEEN_ALERTS_LIMIT:
            self._seen_ids.discard(self._seen[0])
        self._seen.append(alert_id)
        self._seen_ids.add(alert_id)

    def _extract_alerts(self) -> list[dict[str, Any]]:
        """Extract alerts from coordinator data."""
        data = (self.coordinator.data or {}).get("notifications", {})
        results = data.get("results", [])
        # Normalize to list of dicts with alertId
        return [item for item in results if isinstance(item, dict) and _alert_id(item)]

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to hass."""
        await super().async_added_to_hass()
        # Prime seen set on first add to avoid a burst of historical events
        for alert in self._extract_alerts():
            self._remember(_alert_id(alert))
        self._primed = True

    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        for alert in self._extract_alerts():
            aid = _alert_id(alert)
            if aid in self._seen_ids:
                continue
            self._remember(aid)
            if self._primed:
                self._trigger_event("notification", {"alert": alert})
                self._last_event_type = "notification"
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        # Provide friendly status information as attributes instead of overriding state
        unread_data = (self.coordinator.data or {}).get(
            "unread_notifications_count", {}
        )
        # unread endpoint returns {"total": <int>}
        unread_count = int(unread_data.get("total", 0) or 0)

        status = "has_unread" if unread_count > 0 else self._last_event_type or "idle"

        return {
            "status": status,
            "unread_count": unread_count,
            "last_event_type": self._last_event_type,
        }
