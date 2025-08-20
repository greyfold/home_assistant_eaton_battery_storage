import logging
import asyncio
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Eaton xStorage Home switches from a config entry."""
    coordinator = hass.data[DOMAIN]["coordinator"]
    entities = [
        EatonXStoragePowerSwitch(coordinator),
        EatonXStorageEnergySavingModeSwitch(coordinator)
    ]
    async_add_entities(entities)

class EatonXStoragePowerSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to control the power state of the Eaton xStorage Home device."""
    
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_entity_category = EntityCategory.CONFIG
        self._optimistic_state = None  # For optimistic updates

    @property
    def name(self):
        """Return the name of the switch."""
        return "Inverter Power"

    @property
    def unique_id(self):
        """Return the unique ID of the switch."""
        return "eaton_xstorage_inverter_power"

    @property
    def icon(self):
        """Return the icon for the switch."""
        return "mdi:power"

    @property
    def device_info(self):
        """Return device information."""
        return self.coordinator.device_info

    @property
    def is_on(self):
        """Return true if the device is on."""
        # If we have an optimistic state from a recent command, use that
        if self._optimistic_state is not None:
            return self._optimistic_state
            
        try:
            # Otherwise, check the powerState from device data
            device_data = self.coordinator.data.get("device", {}) if self.coordinator.data else {}
            return device_data.get("powerState", False)
        except (AttributeError, TypeError, KeyError):
            return False

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        try:
            # Set optimistic state immediately for responsive UI
            self._optimistic_state = True
            self.async_write_ha_state()
            
            result = await self.coordinator.api.set_device_power(True)
            
            if result.get("successful"):
                _LOGGER.info("Successfully turned on Eaton xStorage Home device")
                # Wait a bit for the device to actually change state
                await asyncio.sleep(3)
            else:
                _LOGGER.warning(f"API call completed but may not have succeeded: {result}")
                # Still wait a bit in case it worked despite the response
                await asyncio.sleep(2)
            
            # Always refresh the coordinator data after attempting to change power state
            await self.coordinator.async_request_refresh()
            
            # Clear optimistic state so we use real data
            self._optimistic_state = None
            
        except Exception as e:
            _LOGGER.error(f"Error turning on device: {e}")
            # Clear optimistic state and refresh to get current state
            self._optimistic_state = None
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        try:
            # Set optimistic state immediately for responsive UI
            self._optimistic_state = False
            self.async_write_ha_state()
            
            result = await self.coordinator.api.set_device_power(False)
            
            if result.get("successful"):
                _LOGGER.info("Successfully turned off Eaton xStorage Home device")
                # Wait a bit for the device to actually change state
                await asyncio.sleep(3)
            else:
                _LOGGER.warning(f"API call completed but may not have succeeded: {result}")
                # Still wait a bit in case it worked despite the response
                await asyncio.sleep(2)
            
            # Always refresh the coordinator data after attempting to change power state
            await self.coordinator.async_request_refresh()
            
            # Clear optimistic state so we use real data
            self._optimistic_state = None
            
        except Exception as e:
            _LOGGER.error(f"Error turning off device: {e}")
            # Clear optimistic state and refresh to get current state
            self._optimistic_state = None
            await self.coordinator.async_request_refresh()

    @property
    def should_poll(self):
        """No polling needed since we use coordinator."""
        return False

    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        # Clear optimistic state when we get real data from coordinator
        if self._optimistic_state is not None:
            self._optimistic_state = None
        super()._handle_coordinator_update()


class EatonXStorageEnergySavingModeSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to control the Energy Saving Mode of the Eaton xStorage Home device."""
    
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_entity_category = EntityCategory.CONFIG
        self._optimistic_state = None  # For optimistic updates

    @property
    def name(self):
        """Return the name of the switch."""
        return "Energy Saving Mode"

    @property
    def unique_id(self):
        """Return the unique ID of the switch."""
        return "eaton_xstorage_energy_saving_mode"

    @property
    def icon(self):
        """Return the icon for the switch."""
        return "mdi:leaf"

    @property
    def device_info(self):
        """Return device information."""
        return self.coordinator.device_info

    @property
    def is_on(self):
        """Return true if energy saving mode is enabled."""
        # If we have an optimistic state from a recent command, use that
        if self._optimistic_state is not None:
            return self._optimistic_state
            
        try:
            # Get energy saving mode from settings data
            settings_data = self.coordinator.data.get("settings", {}) if self.coordinator.data else {}
            energy_saving_mode = settings_data.get("energySavingMode", {})
            enabled_value = energy_saving_mode.get("enabled", False)
            
            # API returns boolean values
            return bool(enabled_value)
        except (AttributeError, TypeError, KeyError):
            return False

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_turn_on(self, **kwargs):
        """Turn energy saving mode on."""
        try:
            # Set optimistic state immediately for responsive UI
            self._optimistic_state = True
            self.async_write_ha_state()
            
            # First, get the current settings from the API (not cached data)
            current_settings_response = await self.coordinator.api.get_settings()
            if not current_settings_response or not current_settings_response.get("result"):
                _LOGGER.error("Failed to get current settings from API")
                self._optimistic_state = None
                return
            
            # Get the current settings data
            current_settings = current_settings_response.get("result", {})
            
            # Transform the settings data to match PUT API expectations
            # The GET API returns objects, but PUT API expects strings/primitives
            if "country" in current_settings and isinstance(current_settings["country"], dict):
                current_settings["country"] = current_settings["country"].get("geonameId", "")
            
            if "city" in current_settings and isinstance(current_settings["city"], dict):
                current_settings["city"] = current_settings["city"].get("geonameId", "")
            
            if "timezone" in current_settings and isinstance(current_settings["timezone"], dict):
                current_settings["timezone"] = current_settings["timezone"].get("id", "")
            
            # Update only the energySavingMode.enabled field
            if "energySavingMode" not in current_settings:
                current_settings["energySavingMode"] = {}
            current_settings["energySavingMode"]["enabled"] = True
            
            # API expects data wrapped in "settings" object
            payload = {"settings": current_settings}
            
            result = await self.coordinator.api.update_settings(payload)
            
            if result.get("successful", result.get("result") is not None):
                _LOGGER.info("Successfully enabled energy saving mode")
                await asyncio.sleep(2)
            else:
                _LOGGER.warning(f"API call completed but may not have succeeded: {result}")
                await asyncio.sleep(1)
            
            # Always refresh the coordinator data
            await self.coordinator.async_request_refresh()
            
            # Clear optimistic state so we use real data
            self._optimistic_state = None
            
        except Exception as e:
            _LOGGER.error(f"Error enabling energy saving mode: {e}")
            # Clear optimistic state and refresh to get current state
            self._optimistic_state = None
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn energy saving mode off."""
        try:
            # Set optimistic state immediately for responsive UI
            self._optimistic_state = False
            self.async_write_ha_state()
            
            # First, get the current settings from the API (not cached data)
            current_settings_response = await self.coordinator.api.get_settings()
            if not current_settings_response or not current_settings_response.get("result"):
                _LOGGER.error("Failed to get current settings from API")
                self._optimistic_state = None
                return
            
            # Get the current settings data
            current_settings = current_settings_response.get("result", {})
            
            # Transform the settings data to match PUT API expectations
            # The GET API returns objects, but PUT API expects strings/primitives
            if "country" in current_settings and isinstance(current_settings["country"], dict):
                current_settings["country"] = current_settings["country"].get("geonameId", "")
            
            if "city" in current_settings and isinstance(current_settings["city"], dict):
                current_settings["city"] = current_settings["city"].get("geonameId", "")
            
            if "timezone" in current_settings and isinstance(current_settings["timezone"], dict):
                current_settings["timezone"] = current_settings["timezone"].get("id", "")
            
            # Update only the energySavingMode.enabled field
            if "energySavingMode" not in current_settings:
                current_settings["energySavingMode"] = {}
            current_settings["energySavingMode"]["enabled"] = False
            
            # API expects data wrapped in "settings" object
            payload = {"settings": current_settings}
            
            result = await self.coordinator.api.update_settings(payload)
            
            if result.get("successful", result.get("result") is not None):
                _LOGGER.info("Successfully disabled energy saving mode")
                await asyncio.sleep(2)
            else:
                _LOGGER.warning(f"API call completed but may not have succeeded: {result}")
                await asyncio.sleep(1)
            
            # Always refresh the coordinator data
            await self.coordinator.async_request_refresh()
            
            # Clear optimistic state so we use real data
            self._optimistic_state = None
            
        except Exception as e:
            _LOGGER.error(f"Error disabling energy saving mode: {e}")
            # Clear optimistic state and refresh to get current state
            self._optimistic_state = None
            await self.coordinator.async_request_refresh()

    @property
    def should_poll(self):
        """No polling needed since we use coordinator."""
        return False

    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        # Clear optimistic state when we get real data from coordinator
        if self._optimistic_state is not None:
            self._optimistic_state = None
        super()._handle_coordinator_update()
