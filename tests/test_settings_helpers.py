"""Tests for the settings transformation helpers."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from custom_components.eaton_battery_storage.api import EatonResponseError
from custom_components.eaton_battery_storage.settings_helpers import (
    async_get_and_transform_settings,
    transform_settings_for_put,
)


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        pytest.param(
            {
                "country": {"geonameId": 2635167, "name": "United Kingdom"},
                "city": {"geonameId": 2643743, "name": "London"},
                "timezone": {"id": "Europe/London", "offset": 0},
            },
            {
                "country": 2635167,
                "city": 2643743,
                "timezone": "Europe/London",
            },
            id="composite_objects_are_flattened",
        ),
        pytest.param(
            {"country": 2635167, "city": 2643743, "timezone": "Europe/London"},
            {"country": 2635167, "city": 2643743, "timezone": "Europe/London"},
            id="primitive_values_are_left_alone",
        ),
        pytest.param(
            {"country": {}, "city": {}, "timezone": {}},
            {"country": "", "city": "", "timezone": ""},
            id="missing_ids_become_empty_strings",
        ),
        pytest.param(
            {"bmsBackupLevel": 30},
            {"bmsBackupLevel": 30},
            id="unrelated_keys_are_preserved",
        ),
        pytest.param({}, {}, id="empty_settings"),
    ],
)
def test_transform_settings_for_put(
    settings: dict[str, Any], expected: dict[str, Any]
) -> None:
    """Composite GET values are converted to the primitives the PUT API wants."""
    assert transform_settings_for_put(settings) == expected


def test_transform_settings_for_put_does_not_mutate_input() -> None:
    """The caller's settings document is left untouched."""
    settings = {"country": {"geonameId": 1}}

    transform_settings_for_put(settings)

    assert settings == {"country": {"geonameId": 1}}


async def test_async_get_and_transform_settings() -> None:
    """The API response payload is unwrapped and transformed."""
    api = AsyncMock()
    api.get_settings.return_value = {
        "successful": True,
        "result": {"timezone": {"id": "Europe/London"}, "bmsBackupLevel": 30},
    }

    assert await async_get_and_transform_settings(api) == {
        "timezone": "Europe/London",
        "bmsBackupLevel": 30,
    }


@pytest.mark.parametrize(
    "response",
    [
        pytest.param({}, id="no_result_key"),
        pytest.param({"result": {}}, id="empty_result"),
        pytest.param({"result": None}, id="null_result"),
        pytest.param({"result": "nope"}, id="non_dict_result"),
    ],
)
async def test_async_get_and_transform_settings_raises(
    response: dict[str, Any],
) -> None:
    """A response without usable settings raises instead of returning None."""
    api = AsyncMock()
    api.get_settings.return_value = response

    with pytest.raises(EatonResponseError):
        await async_get_and_transform_settings(api)
