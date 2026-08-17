"""Diagnostics support for Eaton xStorage Home Battery integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .coordinator import EatonConfigEntry

TO_REDACT = {
    "password",
    "pwd",
    "token",
    "access_token",
    "inverter_sn",
    "inverterSerialNumber",
    "email",
    "username",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EatonConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": async_redact_data(coordinator.data or {}, TO_REDACT),
    }
