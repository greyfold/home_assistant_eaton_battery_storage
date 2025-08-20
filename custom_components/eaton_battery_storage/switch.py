import logging
import asyncio
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN]["coordinator"]
    entities = [
        EatonXStoragePowerSwitch(coordinator),
        EatonXStorageEnergySavingModeSwitch(coordinator),
    ]
    async_add_entities(entities)

class EatonXStoragePowerSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_entity_category = EntityCategory.CONFIG
        self._optimistic_state = None

    @property
    def name(self):
        return "Inverter Power"

    @property
    def unique_id(self):
        return "eaton_xstorage_inverter_power"

    @property
    def icon(self):
        return "mdi:power"

    @property
    def device_info(self):
        return getattr(self.coordinator, "device_info", None) or {
            "identifiers": {(DOMAIN, self.coordinator.api.host)},
            "name": "Eaton xStorage Home",
            "manufacturer": "Eaton",
            "model": "xStorage Home",
            "entry_type": "service",
            "configuration_url": f"https://{self.coordinator.api.host}",
        }

    @property
    def is_on(self):
        if self._optimistic_state is not None:
            return self._optimistic_state
        try:
            device_data = self.coordinator.data.get("device", {}) if self.coordinator.data else {}
            return device_data.get("powerState", False)
        except Exception:
            return False

    @property
    def available(self):
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_turn_on(self, **kwargs):
        try:
            self._optimistic_state = True
            self.async_write_ha_state()
            result = await self.coordinator.api.set_device_power(True)
            if result.get("successful"):
                _LOGGER.info("Turned on device")
                await asyncio.sleep(3)
            else:
                _LOGGER.warning(f"Power on may not have succeeded: {result}")
                await asyncio.sleep(2)
            await self.coordinator.async_request_refresh()
            self._optimistic_state = None
        except Exception as e:
            _LOGGER.error(f"Error turning on device: {e}")
            self._optimistic_state = None
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        try:
            self._optimistic_state = False
            self.async_write_ha_state()
            result = await self.coordinator.api.set_device_power(False)
            if result.get("successful"):
                _LOGGER.info("Turned off device")
                await asyncio.sleep(3)
            else:
                _LOGGER.warning(f"Power off may not have succeeded: {result}")
                await asyncio.sleep(2)
            await self.coordinator.async_request_refresh()
            self._optimistic_state = None
        except Exception as e:
            _LOGGER.error(f"Error turning off device: {e}")
            self._optimistic_state = None
            await self.coordinator.async_request_refresh()

    @property
    def should_poll(self):
        return False

    def _handle_coordinator_update(self):
        if self._optimistic_state is not None:
            self._optimistic_state = None
        super()._handle_coordinator_update()


class EatonXStorageEnergySavingModeSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_entity_category = EntityCategory.CONFIG
        self._optimistic_state = None

    @property
    def name(self):
        return "Energy Saving Mode"

    @property
    def unique_id(self):
        return "eaton_xstorage_energy_saving_mode"

    @property
    def icon(self):
        return "mdi:leaf"

    @property
    def device_info(self):
        return getattr(self.coordinator, "device_info", None) or {
            "identifiers": {(DOMAIN, self.coordinator.api.host)},
            "name": "Eaton xStorage Home",
            "manufacturer": "Eaton",
            "model": "xStorage Home",
            "entry_type": "service",
            "configuration_url": f"https://{self.coordinator.api.host}",
        }

    @property
    def is_on(self):
        if self._optimistic_state is not None:
            return self._optimistic_state
        try:
            settings_data = self.coordinator.data.get("settings", {}) if self.coordinator.data else {}
            energy_saving_mode = settings_data.get("energySavingMode", {})
            enabled_value = energy_saving_mode.get("enabled", False)
            return bool(enabled_value)
        except Exception:
            return False

    @property
    def available(self):
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_turn_on(self, **kwargs):
        try:
            self._optimistic_state = True
            self.async_write_ha_state()
            current_settings_response = await self.coordinator.api.get_settings()
            if not current_settings_response or not current_settings_response.get("result"):
                _LOGGER.error("Failed to get settings from API")
                self._optimistic_state = None
                return
            current_settings = current_settings_response.get("result", {})
            if "country" in current_settings and isinstance(current_settings["country"], dict):
                current_settings["country"] = current_settings["country"].get("geonameId", "")
            if "city" in current_settings and isinstance(current_settings["city"], dict):
                current_settings["city"] = current_settings["city"].get("geonameId", "")
            if "timezone" in current_settings and isinstance(current_settings["timezone"], dict):
                current_settings["timezone"] = current_settings["timezone"].get("id", "")
            if "energySavingMode" not in current_settings:
                current_settings["energySavingMode"] = {}
            current_settings["energySavingMode"]["enabled"] = True
            payload = {"settings": current_settings}
            result = await self.coordinator.api.update_settings(payload)
            if result.get("successful", result.get("result") is not None):
                _LOGGER.info("Enabled energy saving mode")
                await asyncio.sleep(2)
            else:
                _LOGGER.warning(f"Enable ESM may not have succeeded: {result}")
                await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()
            self._optimistic_state = None
        except Exception as e:
            _LOGGER.error(f"Error enabling energy saving mode: {e}")
            self._optimistic_state = None
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        try:
            self._optimistic_state = False
            self.async_write_ha_state()
            current_settings_response = await self.coordinator.api.get_settings()
            if not current_settings_response or not current_settings_response.get("result"):
                _LOGGER.error("Failed to get settings from API")
                self._optimistic_state = None
                return
            current_settings = current_settings_response.get("result", {})
            if "country" in current_settings and isinstance(current_settings["country"], dict):
                current_settings["country"] = current_settings["country"].get("geonameId", "")
            if "city" in current_settings and isinstance(current_settings["city"], dict):
                current_settings["city"] = current_settings["city"].get("geonameId", "")
            if "timezone" in current_settings and isinstance(current_settings["timezone"], dict):
                current_settings["timezone"] = current_settings["timezone"].get("id", "")
            if "energySavingMode" not in current_settings:
                current_settings["energySavingMode"] = {}
            current_settings["energySavingMode"]["enabled"] = False
            payload = {"settings": current_settings}
            result = await self.coordinator.api.update_settings(payload)
            if result.get("successful", result.get("result") is not None):
                _LOGGER.info("Disabled energy saving mode")
                await asyncio.sleep(2)
            else:
                _LOGGER.warning(f"Disable ESM may not have succeeded: {result}")
                await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()
            self._optimistic_state = None
        except Exception as e:
            _LOGGER.error(f"Error disabling energy saving mode: {e}")
            self._optimistic_state = None
            await self.coordinator.async_request_refresh()

    @property
    def should_poll(self):
        return False

    def _handle_coordinator_update(self):
        if self._optimistic_state is not None:
            self._optimistic_state = None
        super()._handle_coordinator_update()
