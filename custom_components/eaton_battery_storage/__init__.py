import logging
from importlib.util import find_spec
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import EatonBatteryAPI
from .coordinator import EatonXstorageHomeCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    return True  # Not used for config flow-based setup


def _discover_platforms() -> list[str]:
    """Discover available platforms in this integration package.

    This avoids future edits to this file when adding new platforms.
    """
    candidates = ("sensor", "binary_sensor", "number", "button", "switch", "select")
    available = []
    for platform in candidates:
        # Module path relative to this package
        module_name = f"{__package__}.{platform}"
        if find_spec(module_name) is not None:
            available.append(platform)
    # Always keep sensor first for backward compatibility
    available.sort(key=lambda p: (p != "sensor", p))
    return available


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug("Setting up Eaton xStorage Home from config entry.")

    # Ensure our domain storage exists before use
    hass.data.setdefault(DOMAIN, {})

    api = EatonBatteryAPI(
        username=entry.data["username"],
        password=entry.data["password"],
        hass=hass,
        host=entry.data["host"],
        app_id="com.eaton.xstoragehome",
        name="Eaton xStorage Home",
        manufacturer="Eaton",
    )
    await api.connect()
    hass.data[DOMAIN]["api"] = api

    coordinator = EatonXstorageHomeCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN]["coordinator"] = coordinator

    # Dynamically forward setups for any available platforms in this package
    platforms = _discover_platforms()
    _LOGGER.debug("Discovered platforms: %s", platforms)
    if platforms:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setups(entry, platforms)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Attempt to unload all available platforms dynamically as well
    platforms = _discover_platforms()
    results = [
        await hass.config_entries.async_forward_entry_unload(entry, platform)
        for platform in platforms
    ]
    return all(results) if results else True
