"""Tests for the Eaton xStorage Home config flow."""

from typing import Any

import aiohttp
import pytest
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.eaton_battery_storage.const import DOMAIN

from .conftest import (
    BASE_URL,
    ENTRY_DATA,
    HOST,
    JSON_HEADERS,
    MINOR_VERSION,
    SERIAL,
    TECH_INPUT,
    USER_INPUT,
    VERSION,
    mock_device,
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


def mock_signin_failure(
    aioclient_mock: AiohttpClientMocker, **response: Any
) -> AiohttpClientMocker:
    """Answer the sign-in request with a failure."""
    aioclient_mock.post(f"{BASE_URL}/api/auth/signin", **response)
    return aioclient_mock


@pytest.mark.usefixtures("mock_connected_device")
async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """A valid customer configuration creates an entry keyed on the serial."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Eaton xStorage Home"
    assert result["data"] == {**USER_INPUT, "email": "anything@anything.com"}
    assert result["result"].unique_id == SERIAL
    # Anything older than this has to be handled by async_migrate_entry.
    assert (result["result"].version, result["result"].minor_version) == (
        VERSION,
        MINOR_VERSION,
    )


async def test_user_flow_falls_back_to_configured_serial(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The configured serial is used when the device does not report one."""
    mock_device(aioclient_mock, device={})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TECH_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL


async def test_user_flow_refuses_an_unknown_serial(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Without a serial there is no identity that survives a DHCP change."""
    aioclient_mock.get(f"{BASE_URL}/api/device", exc=aiohttp.ClientConnectionError())
    mock_device(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown_serial"}


@pytest.mark.usefixtures("mock_connected_device")
async def test_user_flow_aborts_on_duplicate_and_updates_host(
    hass: HomeAssistant,
) -> None:
    """A device that moved to another address updates the existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=SERIAL, data={**USER_INPUT, "host": "10.0.0.1"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["host"] == HOST


async def test_user_flow_requires_inverter_serial_for_technician(
    hass: HomeAssistant, mock_connected_device: AiohttpClientMocker
) -> None:
    """Technician accounts must supply an inverter serial number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**TECH_INPUT, "inverter_sn": ""}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"inverter_sn": "required_inverter_sn"}
    assert mock_connected_device.call_count == 0

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TECH_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "host",
    [
        pytest.param("https://192.168.1.10", id="scheme"),
        pytest.param("192.168.1.10/api", id="path"),
        pytest.param("../../etc", id="traversal"),
        pytest.param("192.168.1.10 ", id="trailing_space"),
        pytest.param("192.168.1.10:0", id="port_zero"),
        pytest.param("192.168.1.10:99999", id="port_out_of_range"),
    ],
)
async def test_user_flow_rejects_invalid_host(
    hass: HomeAssistant, mock_connected_device: AiohttpClientMocker, host: str
) -> None:
    """Hosts that are not a bare address or hostname are rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, "host": host}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"host": "invalid_host"}
    assert mock_connected_device.call_count == 0


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        pytest.param(
            {
                "json": {"error": {"errCode": "10", "description": "Account locked"}},
                "headers": JSON_HEADERS,
            },
            "auth_error_locked",
            id="locked_account_code",
        ),
        pytest.param(
            {
                "json": {"error": {"errCode": "3", "description": "Wrong credentials"}},
                "headers": JSON_HEADERS,
            },
            "err_wrong_credentials",
            id="wrong_credentials_description",
        ),
        pytest.param(
            {
                "json": {
                    "error": {
                        "errCode": "4",
                        "description": "Invalid inverter serial number",
                    }
                },
                "headers": JSON_HEADERS,
            },
            "err_invalid_inverter_sn",
            id="invalid_inverter_description",
        ),
        pytest.param(
            {
                "json": {"error": {"errCode": "99", "description": "Something else"}},
                "headers": JSON_HEADERS,
            },
            "invalid_auth",
            id="unmapped_code",
        ),
        pytest.param(
            {"json": {"successful": False}, "headers": JSON_HEADERS},
            "cannot_connect",
            id="no_error_details",
        ),
        pytest.param(
            {"text": "<html>Gateway timeout</html>"},
            "cannot_connect",
            id="non_json_response",
        ),
        pytest.param(
            {"exc": aiohttp.ClientConnectionError()},
            "cannot_connect",
            id="connection_refused",
        ),
        pytest.param(
            {"exc": TimeoutError()},
            "cannot_connect",
            id="timeout",
        ),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    expected: str,
) -> None:
    """Failures map to the matching form error and the flow stays recoverable."""
    mock_signin_failure(aioclient_mock, **response)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    # The second registration answers successfully, so a retry now works.
    aioclient_mock.clear_requests()
    mock_device(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_connected_device")
async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Reauth updates the stored credentials."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=SERIAL, data=USER_INPUT)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, "password": "new-secret"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "new-secret"


@pytest.mark.usefixtures("mock_connected_device")
async def test_reauth_refuses_a_different_inverter(hass: HomeAssistant) -> None:
    """Reauth must not silently re-point an entry at another device."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="SN-OTHER", data=USER_INPUT)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.unique_id == "SN-OTHER"


@pytest.mark.usefixtures("mock_connected_device")
async def test_reauth_rekeys_a_host_based_entry(hass: HomeAssistant) -> None:
    """Entries the migration could not repair adopt the serial on reauth."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=HOST, data=USER_INPUT)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.unique_id == SERIAL


async def test_reauth_flow_recovers_from_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A failed reauth shows an error and can be retried."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=SERIAL, data=USER_INPUT)
    entry.add_to_hass(hass)
    mock_signin_failure(
        aioclient_mock,
        json={"error": {"errCode": "3", "description": "Wrong credentials"}},
        headers=JSON_HEADERS,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "err_wrong_credentials"}

    aioclient_mock.clear_requests()
    mock_device(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("mock_connected_device")
async def test_reconfigure_flow_updates_the_entry(hass: HomeAssistant) -> None:
    """Reconfiguring writes the connection settings back to the entry data."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=SERIAL, data=ENTRY_DATA)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, "has_pv": True}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["has_pv"] is True
    # data_updates merges, so the key the form does not collect is not dropped.
    assert entry.data["email"] == "anything@anything.com"
    assert entry.options == {}


@pytest.mark.usefixtures("mock_connected_device")
async def test_reconfigure_flow_refuses_a_different_inverter(
    hass: HomeAssistant,
) -> None:
    """Reconfiguring must not silently re-point an entry at another device."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="SN-OTHER", data=ENTRY_DATA)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.unique_id == "SN-OTHER"


async def test_reconfigure_flow_shows_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A connection failure keeps the reconfigure form open."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=SERIAL, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    mock_signin_failure(aioclient_mock, exc=aiohttp.ClientConnectionError())

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data == ENTRY_DATA
