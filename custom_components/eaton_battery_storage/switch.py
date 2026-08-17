"""Switch entities for Eaton xStorage Home battery integration."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EatonError
from .const import DOMAIN
from .coordinator import EatonConfigEntry, EatonXstorageHomeCoordinator
from .entity import EatonEntity

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: EatonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Eaton xStorage Home switches from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            EatonXStoragePowerSwitch(coordinator),
            EatonXStorageEnergySavingModeSwitch(coordinator),
        ]
    )


class EatonXStorageBaseSwitch(EatonEntity, SwitchEntity):
    """Common behavior for the Eaton xStorage Home switches."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: EatonXstorageHomeCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._optimistic_state: bool | None = None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._optimistic_state = None
        super()._handle_coordinator_update()


class EatonXStoragePowerSwitch(EatonXStorageBaseSwitch):
    """Switch to control the power state of the Eaton xStorage Home device."""

    _attr_icon = "mdi:power"
    _attr_translation_key = "inverter_power"

    def __init__(self, coordinator: EatonXstorageHomeCoordinator) -> None:
        """Initialize the power switch."""
        super().__init__(coordinator)
        # Scope unique ID to the config entry for multi-device setups
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_inverter_power"

    @property
    def is_on(self) -> bool | None:
        """Return true if the device is on."""
        if self._optimistic_state is not None:
            return self._optimistic_state

        device_data = (self.coordinator.data or {}).get("device", {})
        return device_data.get("powerState", False)

    async def _async_set_power(self, state: bool) -> None:
        """Send the power command and refresh."""
        self._optimistic_state = state
        self.async_write_ha_state()

        try:
            await self.coordinator.api.set_device_power(state)
        except EatonError as err:
            self._optimistic_state = None
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="power_command_failed"
            ) from err
        finally:
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **_kwargs: object) -> None:
        """Turn the device on."""
        await self._async_set_power(True)

    async def async_turn_off(self, **_kwargs: object) -> None:
        """Turn the device off."""
        await self._async_set_power(False)


class EatonXStorageEnergySavingModeSwitch(EatonXStorageBaseSwitch):
    """Switch to control the Energy Saving Mode of the Eaton xStorage Home device."""

    _attr_icon = "mdi:leaf"
    _attr_translation_key = "energy_saving_mode"

    def __init__(self, coordinator: EatonXstorageHomeCoordinator) -> None:
        """Initialize the energy saving mode switch."""
        super().__init__(coordinator)
        # Scope unique ID to the config entry for multi-device setups
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_energy_saving_mode"

    @property
    def is_on(self) -> bool | None:
        """Return true if energy saving mode is enabled."""
        if self._optimistic_state is not None:
            return self._optimistic_state

        settings = (self.coordinator.data or {}).get("settings", {})
        energy_saving_mode = settings.get("energySavingMode", {})
        return bool(energy_saving_mode.get("enabled", False))

    async def _async_set_enabled(self, enabled: bool) -> None:
        """Write the energy saving mode flag to the device settings."""
        self._optimistic_state = enabled
        self.async_write_ha_state()

        def mutate(settings: dict) -> None:
            settings.setdefault("energySavingMode", {})["enabled"] = enabled

        try:
            await self.coordinator.async_patch_settings(mutate)
        except EatonError as err:
            self._optimistic_state = None
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="energy_saving_mode_failed"
            ) from err

    async def async_turn_on(self, **_kwargs: object) -> None:
        """Turn energy saving mode on."""
        await self._async_set_enabled(True)

    async def async_turn_off(self, **_kwargs: object) -> None:
        """Turn energy saving mode off."""
        await self._async_set_enabled(False)
