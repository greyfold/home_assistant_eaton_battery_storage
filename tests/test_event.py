"""Tests for the Eaton xStorage Home notification event entity."""

from datetime import timedelta
from typing import Any

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.eaton_battery_storage.const import DOMAIN

from .conftest import MINOR_VERSION, SERIAL, TECH_INPUT, VERSION, mock_device

EVENT_ENTITY_ID = "event.eaton_xstorage_home_notifications_event"
PAST_THE_UPDATE_INTERVAL = timedelta(minutes=1, seconds=1)

FIRST_ALERT = {"alertId": "alert-1", "subType": "BMS_FAULT"}
SECOND_ALERT = {"alertId": "alert-2", "subType": "GRID_FAULT"}


def notifications(*alerts: dict[str, Any]) -> dict[str, Any]:
    """Return a notifications payload holding the given alerts."""
    return {"total": len(alerts), "results": list(alerts)}


async def setup_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, **payloads: Any
) -> MockConfigEntry:
    """Set up a config entry against a device serving the given payloads."""
    mock_device(aioclient_mock, **payloads)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data=TECH_INPUT,
        version=VERSION,
        minor_version=MINOR_VERSION,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def refresh_with(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, **payloads: Any
) -> None:
    """Serve new payloads and let the coordinator poll them."""
    aioclient_mock.clear_requests()
    mock_device(aioclient_mock, **payloads)
    async_fire_time_changed(hass, dt_util.utcnow() + PAST_THE_UPDATE_INTERVAL)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_alerts_present_at_startup_do_not_fire(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Existing alerts must not replay as events when the entity is added."""
    await setup_entry(hass, aioclient_mock, notifications=notifications(FIRST_ALERT))

    assert hass.states.get(EVENT_ENTITY_ID).state == STATE_UNKNOWN


async def test_a_new_alert_fires_an_event(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An alert the device has not reported before is emitted with its payload."""
    await setup_entry(hass, aioclient_mock, notifications=notifications(FIRST_ALERT))

    await refresh_with(
        hass,
        aioclient_mock,
        notifications=notifications(FIRST_ALERT, SECOND_ALERT),
    )

    state = hass.states.get(EVENT_ENTITY_ID)
    assert state.attributes["event_type"] == "notification"
    assert state.attributes["alert"] == SECOND_ALERT


async def test_a_known_alert_fires_only_once(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Repeated polls of the same alert must not keep firing events."""
    await setup_entry(hass, aioclient_mock, notifications=notifications())
    await refresh_with(hass, aioclient_mock, notifications=notifications(FIRST_ALERT))
    fired_at = hass.states.get(EVENT_ENTITY_ID).state

    await refresh_with(hass, aioclient_mock, notifications=notifications(FIRST_ALERT))

    assert hass.states.get(EVENT_ENTITY_ID).state == fired_at


async def test_alerts_without_an_id_are_ignored(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Entries that carry no identifier cannot be told apart and are skipped."""
    await setup_entry(hass, aioclient_mock, notifications=notifications())

    await refresh_with(
        hass,
        aioclient_mock,
        notifications={"total": 2, "results": [{"subType": "BMS_FAULT"}, "junk"]},
    )

    assert hass.states.get(EVENT_ENTITY_ID).state == STATE_UNKNOWN


async def test_unread_count_is_exposed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The entity reports how many notifications are still unread."""
    await setup_entry(
        hass,
        aioclient_mock,
        notifications=notifications(FIRST_ALERT),
        unread_notifications_count={"total": 3},
    )

    attributes = hass.states.get(EVENT_ENTITY_ID).attributes
    assert attributes["unread_count"] == 3
    assert attributes["status"] == "has_unread"
