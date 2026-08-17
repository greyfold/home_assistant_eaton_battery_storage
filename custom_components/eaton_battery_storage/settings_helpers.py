"""Shared helpers for transforming Eaton xStorage Home settings."""

from __future__ import annotations

from typing import Any

from .api import EatonBatteryAPI, EatonResponseError


def transform_settings_for_put(settings: dict[str, Any]) -> dict[str, Any]:
    """Transform GET API settings response to match PUT API expectations.

    The GET API returns composite objects for country, city, and timezone,
    but the PUT API expects string/primitive values.
    """
    settings = dict(settings)
    if "country" in settings and isinstance(settings["country"], dict):
        settings["country"] = settings["country"].get("geonameId", "")

    if "city" in settings and isinstance(settings["city"], dict):
        settings["city"] = settings["city"].get("geonameId", "")

    if "timezone" in settings and isinstance(settings["timezone"], dict):
        settings["timezone"] = settings["timezone"].get("id", "")

    return settings


async def async_get_and_transform_settings(api: EatonBatteryAPI) -> dict[str, Any]:
    """Fetch current settings from the API and transform them for PUT."""
    response = await api.get_settings()
    current_settings = response.get("result")
    if not isinstance(current_settings, dict) or not current_settings:
        raise EatonResponseError("Device returned no settings")

    return transform_settings_for_put(current_settings)
