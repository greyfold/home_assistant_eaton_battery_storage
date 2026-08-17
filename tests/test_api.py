"""Tests for the Eaton xStorage Home API client."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from aiohttp import ClientConnectionError
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from yarl import URL

from custom_components.eaton_battery_storage.api import (
    EatonAuthError,
    EatonBatteryAPI,
    EatonCommandError,
    EatonConnectionError,
    EatonResponseError,
    token_store_key,
)

from .conftest import BASE_URL, HOST, JSON_HEADERS, SERIAL, mock_signin

ENTRY_ID = "an-entry"
STORE_KEY = token_store_key(ENTRY_ID)


def make_api(hass: HomeAssistant, **kwargs: Any) -> EatonBatteryAPI:
    """Return an API client for the mocked device."""
    return EatonBatteryAPI(
        hass,
        HOST,
        "admin",
        "secret",
        SERIAL,
        "anything@anything.com",
        "com.eaton.xstoragehome",
        "Eaton xStorage Home",
        "Eaton",
        entry_id=ENTRY_ID,
        **kwargs,
    )


def signin_count(aioclient_mock: AiohttpClientMocker) -> int:
    """Return how many times the client authenticated."""
    return sum(1 for _, url, _, _ in aioclient_mock.mock_calls if "signin" in url.path)


def stored_token(hass_storage: dict[str, Any]) -> dict[str, Any]:
    """Return the persisted token data."""
    return hass_storage[STORE_KEY]["data"]


async def test_a_token_is_persisted_and_reused(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """One sign-in serves every request until the token expires."""
    mock_signin(aioclient_mock)
    aioclient_mock.get(f"{BASE_URL}/api/device", json={}, headers=JSON_HEADERS)
    api = make_api(hass)

    await api.get_device()
    await api.get_device()

    assert signin_count(aioclient_mock) == 1
    assert stored_token(hass_storage)["access_token"] == "test-token"


async def test_a_naive_stored_expiry_is_read_as_utc(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """Tokens written by older versions carry no timezone and must not re-authenticate."""
    naive_expiry = (datetime.now(UTC) + timedelta(minutes=30)).replace(tzinfo=None)
    hass_storage[STORE_KEY] = {
        "version": 1,
        "data": {
            "access_token": "stored-token",
            "token_expiration": naive_expiry.isoformat(),
        },
    }
    mock_signin(aioclient_mock)
    aioclient_mock.get(f"{BASE_URL}/api/device", json={}, headers=JSON_HEADERS)
    api = make_api(hass)

    await api.get_device()

    assert api.token_expiration == naive_expiry.replace(tzinfo=UTC)
    assert signin_count(aioclient_mock) == 0


async def test_an_expired_stored_token_is_replaced(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """A token that is past its expiry triggers a fresh sign-in."""
    hass_storage[STORE_KEY] = {
        "version": 1,
        "data": {
            "access_token": "stale-token",
            "token_expiration": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        },
    }
    mock_signin(aioclient_mock)
    aioclient_mock.get(f"{BASE_URL}/api/device", json={}, headers=JSON_HEADERS)
    api = make_api(hass)

    await api.get_device()

    assert api.access_token == "test-token"
    assert signin_count(aioclient_mock) == 1


async def test_the_token_is_removed_on_request(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """Removing the token clears it from storage."""
    mock_signin(aioclient_mock)
    api = make_api(hass)
    await api.connect()

    await api.remove_token()
    await hass.async_block_till_done()

    assert STORE_KEY not in hass_storage


async def test_a_config_flow_probe_persists_nothing(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """A client without a config entry has nowhere to store its token."""
    mock_signin(aioclient_mock)
    api = EatonBatteryAPI(
        hass,
        HOST,
        "admin",
        "secret",
        SERIAL,
        "anything@anything.com",
        "com.eaton.xstoragehome",
        "Eaton xStorage Home",
        "Eaton",
    )

    await api.connect()
    await api.load_token()
    await api.remove_token()

    assert api.access_token == "test-token"
    assert STORE_KEY not in hass_storage


async def test_a_rejected_token_is_renewed_once(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 401 costs one re-authentication and the request is then retried."""
    mock_signin(aioclient_mock)
    url = URL(f"{BASE_URL}/api/device")
    answers = iter(
        [
            AiohttpClientMockResponse("GET", url, status=401, text=""),
            AiohttpClientMockResponse(
                "GET", url, json={"result": {"id": 1}}, headers=JSON_HEADERS
            ),
        ]
    )

    async def answer(method: str, url: URL, data: Any) -> AiohttpClientMockResponse:
        return next(answers)

    aioclient_mock.get(f"{BASE_URL}/api/device", side_effect=answer)
    api = make_api(hass)
    api.access_token = "rejected-token"
    api.token_expiration = datetime.now(UTC) + timedelta(minutes=30)

    assert await api.get_device() == {"result": {"id": 1}}
    assert signin_count(aioclient_mock) == 1


async def test_an_empty_body_counts_as_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Write endpoints answer 200 with no body."""
    mock_signin(aioclient_mock)
    aioclient_mock.post(f"{BASE_URL}/api/device/power", text="")
    api = make_api(hass)

    assert await api.set_device_power(True) == {}


async def test_a_non_json_body_raises(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 200 carrying an HTML page is not a usable answer."""
    mock_signin(aioclient_mock)
    aioclient_mock.get(f"{BASE_URL}/api/device", text="<html>nope</html>")
    api = make_api(hass)

    with pytest.raises(EatonResponseError, match="Non-JSON response"):
        await api.get_device()


@pytest.mark.parametrize("status", [403, 404, 500])
async def test_an_error_status_raises_even_with_a_json_body(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, status: int
) -> None:
    """An error payload must not be mistaken for device data."""
    mock_signin(aioclient_mock)
    aioclient_mock.get(
        f"{BASE_URL}/api/device",
        status=status,
        json={"result": {"id": 1}},
        headers=JSON_HEADERS,
    )
    api = make_api(hass)

    with pytest.raises(EatonResponseError, match=f"HTTP {status}"):
        await api.get_device()


async def test_an_error_status_fails_a_write(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The power endpoint has no success flag, so only the status can fail it."""
    mock_signin(aioclient_mock)
    aioclient_mock.post(
        f"{BASE_URL}/api/device/power",
        status=500,
        json={"error": "nope"},
        headers=JSON_HEADERS,
    )
    api = make_api(hass)

    with pytest.raises(EatonResponseError, match="HTTP 500"):
        await api.set_device_power(True)


async def test_a_401_that_survives_reauthentication_is_an_auth_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A fresh token that is still refused means the account lost access."""
    mock_signin(aioclient_mock)
    aioclient_mock.get(f"{BASE_URL}/api/device", status=401, text="")
    api = make_api(hass)

    with pytest.raises(EatonAuthError):
        await api.get_device()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(ClientConnectionError, id="network_error"),
    ],
)
async def test_an_unreachable_device_raises_a_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, error: type[Exception]
) -> None:
    """Transport failures are reported as connection errors."""
    mock_signin(aioclient_mock)
    aioclient_mock.get(f"{BASE_URL}/api/device", exc=error)
    api = make_api(hass)

    with pytest.raises(EatonConnectionError):
        await api.get_device()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(ClientConnectionError, id="network_error"),
    ],
)
async def test_an_unreachable_device_fails_authentication(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, error: type[Exception]
) -> None:
    """Sign-in reports transport failures as connection errors too."""
    aioclient_mock.post(f"{BASE_URL}/api/auth/signin", exc=error)
    api = make_api(hass)

    with pytest.raises(EatonConnectionError):
        await api.connect()


async def test_an_auth_error_carries_the_device_code(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The error code drives the message the config flow shows."""
    aioclient_mock.post(
        f"{BASE_URL}/api/auth/signin",
        json={"successful": False, "error": {"errCode": "10", "description": "Locked"}},
        headers=JSON_HEADERS,
    )
    api = make_api(hass)

    with pytest.raises(EatonAuthError) as err:
        await api.connect()

    assert err.value.err_code == "10"
    assert err.value.message == "Locked"


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(
            {"json": {"successful": False}, "headers": JSON_HEADERS},
            id="unexpected_payload",
        ),
        pytest.param({"text": "<html>login</html>"}, id="html"),
    ],
)
async def test_an_uninterpretable_sign_in_is_a_connection_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
) -> None:
    """A response the device does not explain is a reachability problem.

    Raising an auth error here would send the user through reauth for what is
    usually a reboot or a proxy in front of the inverter.
    """
    aioclient_mock.post(f"{BASE_URL}/api/auth/signin", **response)
    api = make_api(hass)

    with pytest.raises(EatonConnectionError):
        await api.connect()


async def test_a_customer_account_signs_in_without_a_serial(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Only technician accounts send the inverter serial and email."""
    mock_signin(aioclient_mock)
    api = make_api(hass, user_type="customer")

    await api.connect()

    _, _, payload, _ = aioclient_mock.mock_calls[0]
    assert payload == {"username": "admin", "pwd": "secret", "userType": "customer"}


async def test_notifications_are_filtered_by_the_device(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Paging and status filters are passed to the device as query parameters."""
    mock_signin(aioclient_mock)
    aioclient_mock.get(
        f"{BASE_URL}/api/notifications/", json={"result": {}}, headers=JSON_HEADERS
    )
    api = make_api(hass)

    await api.get_notifications(status="UNREAD", size=10, offset=0)

    _, url, _, _ = aioclient_mock.mock_calls[-1]
    assert dict(url.query) == {"status": "UNREAD", "size": "10", "offset": "0"}


@pytest.mark.parametrize(
    "response",
    [
        pytest.param({"successful": False}, id="rejected"),
        pytest.param({}, id="empty"),
    ],
)
async def test_a_rejected_write_raises(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, response: dict[str, Any]
) -> None:
    """Writes that the device does not confirm are surfaced as errors."""
    mock_signin(aioclient_mock)
    aioclient_mock.post(
        f"{BASE_URL}/api/notifications/read/all", json=response, headers=JSON_HEADERS
    )
    api = make_api(hass)

    with pytest.raises(EatonCommandError):
        await api.mark_all_notifications_read()
