"""Fixtures for the Eaton xStorage Home tests.

The device is mocked at the HTTP boundary so the tests exercise the real API
client, coordinator and entity platforms.
"""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from pytest_homeassistant_custom_component.syrupy import HomeAssistantSnapshotExtension
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

from custom_components.eaton_battery_storage.config_flow import (
    EatonXStorageConfigFlow,
)

HOST = "192.168.1.10"
BASE_URL = f"https://{HOST}"
SERIAL = "SN-12345"
JSON_HEADERS = {"Content-Type": "application/json"}
# Entity unique IDs embed the entry ID, so it is pinned for stable snapshots.
ENTRY_ID = "01JEAT0NXST0RAGEH0MEZZZZZZ"
# Taken from the flow so an entry a test builds is one the flow could create.
VERSION = EatonXStorageConfigFlow.VERSION
MINOR_VERSION = EatonXStorageConfigFlow.MINOR_VERSION

USER_INPUT = {
    "host": HOST,
    "user_type": "customer",
    "username": "user",
    "password": "secret",
    "inverter_sn": "",
    "has_pv": False,
    "verify_ssl": False,
}

TECH_INPUT = {
    **USER_INPUT,
    "user_type": "tech",
    "username": "admin",
    "inverter_sn": SERIAL,
}

# What the config flow actually stores on the entry.
ENTRY_DATA = {**USER_INPUT, "email": "anything@anything.com"}

DEVICE_RESULT = {
    "inverterSerialNumber": SERIAL,
    "firmwareVersion": "1.2.3",
    "inverterModelName": "xStorage Home 3.6",
    "bmsFirmwareVersion": "4.5.6",
    "powerState": True,
}

STATUS_RESULT = {
    "energyFlow": {"batteryStatus": "BAT_IDLE", "batteryBackupLevel": 30},
    "currentMode": {"command": "SET_BASIC_MODE"},
}

# The device nests country, city and timezone, which a write has to flatten.
SETTINGS_RESULT = {
    "country": {"geonameId": 2635167, "name": "United Kingdom"},
    "city": {"geonameId": 2643743, "name": "London"},
    "timezone": {"id": "Europe/London", "offset": 0},
    "bmsBackupLevel": 30,
    "energySavingMode": {"enabled": False, "houseConsumptionThreshold": 400},
}

# Coordinator data key to the endpoint it is read from.
ENDPOINT_PATHS = {
    "device": "/api/device",
    "status": "/api/device/status",
    "config_state": "/api/config/state",
    "settings": "/api/settings",
    "schedule": "/api/schedule/",
    "technical_status": "/api/technical/status",
    "maintenance_diagnostics": "/api/device/maintenance/diagnostics",
    "notifications": "/api/notifications/",
    "unread_notifications_count": "/api/notifications/unread",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading of the custom integration in every test."""


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Return a snapshot assertion that hides volatile registry fields."""
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Register entities that are disabled by default as enabled.

    Core ships this fixture in tests/components/conftest.py, which is not part
    of pytest-homeassistant-custom-component, so custom integrations need it.
    """
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        new_callable=PropertyMock,
        return_value=True,
    ):
        yield


def mock_signin(aioclient_mock: AiohttpClientMocker) -> None:
    """Answer the sign-in request with a bearer token."""
    aioclient_mock.post(
        f"{BASE_URL}/api/auth/signin",
        json={"successful": True, "result": {"token": "test-token"}},
        headers=JSON_HEADERS,
    )


def mock_settings(aioclient_mock: AiohttpClientMocker, *, successful: bool) -> None:
    """Answer the settings read and write of a read-modify-write cycle."""
    aioclient_mock.get(
        f"{BASE_URL}/api/settings",
        json={"successful": True, "result": SETTINGS_RESULT},
        headers=JSON_HEADERS,
    )
    aioclient_mock.put(
        f"{BASE_URL}/api/settings",
        json={"successful": successful},
        headers=JSON_HEADERS,
    )


def mock_device(aioclient_mock: AiohttpClientMocker, **results: dict[str, Any]) -> None:
    """Answer every endpoint the integration reads.

    Endpoints default to the payload of a healthy device; pass a coordinator
    data key to replace one. Registrations are matched in order, so a caller can
    also register its own override before calling this.
    """
    mock_signin(aioclient_mock)
    payloads: dict[str, Any] = {
        "device": DEVICE_RESULT,
        "status": STATUS_RESULT,
        **results,
    }
    for name, path in ENDPOINT_PATHS.items():
        aioclient_mock.get(
            f"{BASE_URL}{path}",
            json={"successful": True, "result": payloads.get(name, {})},
            headers=JSON_HEADERS,
        )


@pytest.fixture
def mock_connected_device(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock a device that answers every request successfully."""
    mock_device(aioclient_mock)
    return aioclient_mock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent the integration from being set up during config flow tests."""
    with patch(
        "custom_components.eaton_battery_storage.async_setup_entry",
        return_value=True,
    ) as setup_entry:
        yield setup_entry
