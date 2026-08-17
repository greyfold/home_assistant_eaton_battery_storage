"""System health platform for Eaton xStorage Home Battery integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components import system_health
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the system health panel."""
    coordinators = [
        entry.runtime_data
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if not coordinators:
        return {"device_reachable": False, "last_successful_update": "Never"}

    # The panel can only translate a fixed set of keys, so several inverters are
    # folded into one entry each, reporting the worst case of the group.
    update_times = [
        coordinator.last_update_success_time
        for coordinator in coordinators
        if coordinator.last_update_success_time
    ]
    return {
        "device_reachable": all(
            coordinator.last_update_success for coordinator in coordinators
        ),
        "api_host": ", ".join(coordinator.api.host for coordinator in coordinators),
        "last_successful_update": str(min(update_times)) if update_times else "Never",
    }
