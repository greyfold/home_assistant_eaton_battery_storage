"""Tests for the Eaton xStorage Home data update coordinator."""

from datetime import timedelta
from typing import Any

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.eaton_battery_storage.const import DOMAIN, sensor_unique_id

from .conftest import (
    BASE_URL,
    JSON_HEADERS,
    MINOR_VERSION,
    SERIAL,
    STATUS_RESULT,
    TECH_INPUT,
    USER_INPUT,
    VERSION,
    mock_device,
)

# The coordinator polls once a minute; overshoot it so the timer is due.
PAST_THE_UPDATE_INTERVAL = timedelta(minutes=1, seconds=1)
BATTERY_STATUS_KEY = "status.energyFlow.batteryStatus"


async def setup_entry(
    hass: HomeAssistant, data: dict[str, Any] = TECH_INPUT
) -> MockConfigEntry:
    """Set up a config entry and return it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data=data,
        version=VERSION,
        minor_version=MINOR_VERSION,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def trigger_refresh(hass: HomeAssistant) -> None:
    """Let the coordinator's polling timer fire.

    The refresh runs as a background task, which the default block does not wait
    for, and the next poll is only scheduled once it finishes.
    """
    async_fire_time_changed(hass, dt_util.utcnow() + PAST_THE_UPDATE_INTERVAL)
    await hass.async_block_till_done(wait_background_tasks=True)


def entity_id_for(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str:
    """Return the entity ID of the sensor for a coordinator data key."""
    return er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, sensor_unique_id(entry.entry_id, key)
    )


async def test_data_is_refreshed_on_the_update_interval(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The coordinator polls the device without being asked to."""
    mock_device(aioclient_mock)
    entry = await setup_entry(hass)
    entity_id = entity_id_for(hass, entry, BATTERY_STATUS_KEY)
    assert hass.states.get(entity_id).state == "Idle"

    aioclient_mock.clear_requests()
    mock_device(
        aioclient_mock,
        status={**STATUS_RESULT, "energyFlow": {"batteryStatus": "BAT_CHARGING"}},
    )
    await trigger_refresh(hass)

    assert hass.states.get(entity_id).state == "Charging"


async def test_an_optional_endpoint_failure_is_tolerated(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """One failing endpoint must not take the whole integration down."""
    aioclient_mock.get(f"{BASE_URL}/api/settings", status=500, text="")
    mock_device(aioclient_mock)
    entry = await setup_entry(hass)

    assert entry.runtime_data.last_update_success
    assert entry.runtime_data.data["settings"] == {}


async def test_a_customer_account_skips_the_technician_endpoints(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Technical data is only read for accounts that are allowed to see it."""
    mock_device(aioclient_mock)
    entry = await setup_entry(hass, USER_INPUT)

    assert entry.runtime_data.data["technical_status"] == {}
    assert not any(
        url.path == "/api/technical/status"
        for _, url, _, _ in aioclient_mock.mock_calls
    )


async def test_entities_go_unavailable_and_recover(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A device that stops answering marks its entities unavailable until it returns."""
    mock_device(aioclient_mock)
    entry = await setup_entry(hass)
    entity_id = entity_id_for(hass, entry, BATTERY_STATUS_KEY)
    assert hass.states.get(entity_id).state == "Idle"

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE_URL}/api/device/status", status=500, text="")
    mock_device(aioclient_mock)
    await trigger_refresh(hass)

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert "is unavailable" in caplog.text

    aioclient_mock.clear_requests()
    mock_device(
        aioclient_mock,
        status={**STATUS_RESULT, "energyFlow": {"batteryStatus": "BAT_CHARGING"}},
    )
    await trigger_refresh(hass)

    assert hass.states.get(entity_id).state == "Charging"
    assert "is available again" in caplog.text


async def test_an_expired_session_starts_a_reauth_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Credentials that stop working ask the user to sign in again."""
    mock_device(aioclient_mock)
    entry = await setup_entry(hass)

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"{BASE_URL}/api/auth/signin",
        json={"error": {"errCode": "3", "description": "Wrong credentials"}},
        headers=JSON_HEADERS,
    )
    # The held token has to be rejected before the client signs in again.
    aioclient_mock.get(f"{BASE_URL}/api/device/status", status=401, text="")
    await trigger_refresh(hass)

    assert list(entry.async_get_active_flows(hass, {"reauth"}))


async def test_an_optional_endpoint_losing_access_starts_a_reauth_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A technician account downgraded to customer must not fail silently.

    The required endpoints keep answering, so only the technician-only ones are
    refused. Tolerating that would leave every technical sensor unknown with
    nothing above debug level to explain it.
    """
    mock_device(aioclient_mock)
    entry = await setup_entry(hass)

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"{BASE_URL}/api/auth/signin",
        json={"error": {"errCode": "3", "description": "Wrong credentials"}},
        headers=JSON_HEADERS,
    )
    aioclient_mock.get(f"{BASE_URL}/api/technical/status", status=401, text="")
    mock_device(aioclient_mock)
    await trigger_refresh(hass)

    # async_get_active_flows returns a generator, which is truthy even when empty.
    assert list(entry.async_get_active_flows(hass, {"reauth"}))
