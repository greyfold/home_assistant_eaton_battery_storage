"""Base entity for the Eaton xStorage Home battery integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import EatonXstorageHomeCoordinator


class EatonEntity(CoordinatorEntity[EatonXstorageHomeCoordinator]):
    """Base entity for every Eaton xStorage Home platform."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information, which follows the data the device reports."""
        return self.coordinator.device_info
