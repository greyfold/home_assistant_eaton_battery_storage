import logging
from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.storage import Store
from homeassistant.helpers.dispatcher import async_dispatcher_send, async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN
from .number_constants import NUMBER_ENTITIES

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coordinator = hass.data[DOMAIN]["coordinator"]
    store = Store(hass, 1, f"{DOMAIN}_number_values.json")
    stored = await store.async_load() or {}
    hass.data[DOMAIN]["number_values"] = stored
    hass.data[DOMAIN]["number_store"] = store
    entities = [EatonBatteryNumberEntity(hass, coordinator, desc) for desc in NUMBER_ENTITIES]
    entities.append(EatonXStorageHouseConsumptionThresholdNumber(coordinator))
    entities.append(EatonXStorageBatteryBackupLevelNumber(coordinator))
    logging.getLogger(__name__).debug("Adding %d number entities (incl. threshold + backup level)", len(entities))
    for entity in entities:
        if hasattr(entity, "_all_entities"):
            entity._all_entities = entities
    async_add_entities(entities)

class EatonBatteryNumberEntity(CoordinatorEntity, NumberEntity):
    @property
    def mode(self):
        return "box"
    def __init__(self, hass, coordinator, description):
        super().__init__(coordinator)
        self.hass = hass
        self.coordinator = coordinator
        self._key = description["key"]
        self._attr_unique_id = f"eaton_battery_{description['key']}"
        self._attr_name = description["name"]
        self._native_min_value = float(description["min"])
        self._native_max_value = float(description["max"])
        self._native_step = float(description["step"])
        self._native_unit_of_measurement = description["unit"]
        self._attr_device_class = description["device_class"]
        self._all_entities = None

    async def async_added_to_hass(self):
        async_dispatcher_connect(self.hass, f"{DOMAIN}_number_update", self._handle_external_update)

    def _handle_external_update(self):
        self.schedule_update_ha_state()

    @property
    def extra_state_attributes(self):
        if self._key == "charge_power":
            percent = self.native_value
            if percent is not None:
                watts = int(round((percent / 100) * 3600))
                return {"wattage": watts}
        elif self._key == "charge_power_watt":
            watts = self.native_value
            if watts is not None:
                percent = int(round((watts / 3600) * 100))
                return {"percent": percent}
        elif self._key == "discharge_power":
            percent = self.native_value
            if percent is not None:
                watts = int(round((percent / 100) * 3600))
                return {"wattage": watts}
        elif self._key == "discharge_power_watt":
            watts = self.native_value
            if watts is not None:
                percent = int(round((watts / 3600) * 100))
                return {"percent": percent}
        return None

    @property
    def native_min_value(self):
        return self._native_min_value

    @property
    def native_max_value(self):
        return self._native_max_value

    @property
    def native_step(self):
        return self._native_step

    @property
    def native_unit_of_measurement(self):
        return self._native_unit_of_measurement

    @property
    def native_value(self):
        return self.hass.data[DOMAIN]["number_values"].get(self._key)

    async def async_set_native_value(self, value: float) -> None:
        self.hass.data[DOMAIN]["number_values"][self._key] = value
        linked_key = None
        if self._key == "charge_power":
            watts = int(round((value / 100) * 3600))
            self.hass.data[DOMAIN]["number_values"]["charge_power_watt"] = watts
            linked_key = "charge_power_watt"
        elif self._key == "charge_power_watt":
            percent = int(round((value / 3600) * 100))
            self.hass.data[DOMAIN]["number_values"]["charge_power"] = percent
            linked_key = "charge_power"
        elif self._key == "discharge_power":
            watts = int(round((value / 100) * 3600))
            self.hass.data[DOMAIN]["number_values"]["discharge_power_watt"] = watts
            linked_key = "discharge_power_watt"
        elif self._key == "discharge_power_watt":
            percent = int(round((value / 3600) * 100))
            self.hass.data[DOMAIN]["number_values"]["discharge_power"] = percent
            linked_key = "discharge_power"
        await self.hass.data[DOMAIN]["number_store"].async_save(self.hass.data[DOMAIN]["number_values"])
        if linked_key and self._all_entities:
            for entity in self._all_entities:
                if hasattr(entity, "_key") and entity._key == linked_key:
                    entity.async_write_ha_state()
        async_dispatcher_send(self.hass, f"{DOMAIN}_number_update")
        self.async_write_ha_state()

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


class EatonXStorageHouseConsumptionThresholdNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_entity_category = EntityCategory.CONFIG
        self._optimistic_value = None

    @property
    def name(self):
        return "Set House Consumption Threshold"

    @property
    def unique_id(self):
        return "eaton_xstorage_set_house_consumption_threshold"

    @property
    def icon(self):
        return "mdi:home-lightning-bolt"

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
    def native_unit_of_measurement(self):
        return "W"

    @property
    def native_min_value(self):
        return 300

    @property
    def native_max_value(self):
        return 1000

    @property
    def native_step(self):
        return 25

    @property
    def mode(self):
        return "box"

    @property
    def native_value(self):
        if self._optimistic_value is not None:
            return self._optimistic_value
        try:
            device = self.coordinator.data.get("device", {}) if self.coordinator.data else {}
            if isinstance(device, dict):
                es = device.get("energySavingMode", {})
                if isinstance(es, dict) and "houseConsumptionThreshold" in es:
                    return es.get("houseConsumptionThreshold")
            settings_data = self.coordinator.data.get("settings", {}) if self.coordinator.data else {}
            es2 = settings_data.get("energySavingMode", {}) if isinstance(settings_data, dict) else {}
            return es2.get("houseConsumptionThreshold", 300)
        except Exception:
            return 300

    @property
    def available(self):
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_set_native_value(self, value: float) -> None:
        import asyncio
        _LOGGER = logging.getLogger(__name__)
        try:
            self._optimistic_value = int(value)
            self.async_write_ha_state()
            current_settings_response = await self.coordinator.api.get_settings()
            if not current_settings_response or not current_settings_response.get("result"):
                _LOGGER.error("Failed to get current settings from API")
                self._optimistic_value = None
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
            current_settings["energySavingMode"]["houseConsumptionThreshold"] = int(value)
            payload = {"settings": current_settings}
            result = await self.coordinator.api.update_settings(payload)
            if result.get("successful", result.get("result") is not None):
                _LOGGER.info(f"Set house consumption threshold to {int(value)}W")
                await asyncio.sleep(2)
            else:
                _LOGGER.warning(f"Set threshold may not have succeeded: {result}")
                await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()
            self._optimistic_value = None
        except Exception as e:
            _LOGGER.error(f"Error setting house consumption threshold: {e}")
            self._optimistic_value = None
            await self.coordinator.async_request_refresh()

    @property
    def should_poll(self):
        return False

    def _handle_coordinator_update(self):
        if self._optimistic_value is not None:
            self._optimistic_value = None
        super()._handle_coordinator_update()


class EatonXStorageBatteryBackupLevelNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_entity_category = EntityCategory.CONFIG
        self._optimistic_value = None

    @property
    def name(self):
        return "Set Battery Backup Level"

    @property
    def unique_id(self):
        return "eaton_xstorage_set_battery_backup_level"

    @property
    def icon(self):
        return "mdi:battery-lock"

    @property
    def native_unit_of_measurement(self):
        return "%"

    @property
    def native_min_value(self):
        return 0

    @property
    def native_max_value(self):
        return 100

    @property
    def native_step(self):
        return 1

    @property
    def mode(self):
        return "box"

    @property
    def native_value(self):
        if self._optimistic_value is not None:
            return self._optimistic_value
        try:
            settings_data = self.coordinator.data.get("settings", {}) if self.coordinator.data else {}
            if isinstance(settings_data, dict) and "bmsBackupLevel" in settings_data:
                return settings_data.get("bmsBackupLevel")
            status = self.coordinator.data.get("status", {}) if self.coordinator.data else {}
            energy_flow = status.get("energyFlow", {}) if isinstance(status, dict) else {}
            if "batteryBackupLevel" in energy_flow:
                return energy_flow.get("batteryBackupLevel")
            return 0
        except Exception:
            return 0

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
    def available(self):
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_set_native_value(self, value: float) -> None:
        import asyncio
        _LOGGER = logging.getLogger(__name__)
        try:
            self._optimistic_value = int(value)
            self.async_write_ha_state()
            current_settings_response = await self.coordinator.api.get_settings()
            if not current_settings_response or not current_settings_response.get("result"):
                _LOGGER.error("Failed to get current settings from API")
                self._optimistic_value = None
                return
            current_settings = current_settings_response.get("result", {})
            if "country" in current_settings and isinstance(current_settings["country"], dict):
                current_settings["country"] = current_settings["country"].get("geonameId", "")
            if "city" in current_settings and isinstance(current_settings["city"], dict):
                current_settings["city"] = current_settings["city"].get("geonameId", "")
            if "timezone" in current_settings and isinstance(current_settings["timezone"], dict):
                current_settings["timezone"] = current_settings["timezone"].get("id", "")
            current_settings["bmsBackupLevel"] = int(value)
            payload = {"settings": current_settings}
            result = await self.coordinator.api.update_settings(payload)
            if result.get("successful", result.get("result") is not None):
                _LOGGER.info(f"Set battery backup level to {int(value)}%")
                await asyncio.sleep(2)
            else:
                _LOGGER.warning(f"Set backup level may not have succeeded: {result}")
                await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()
            self._optimistic_value = None
        except Exception as e:
            _LOGGER.error(f"Error setting battery backup level: {e}")
            self._optimistic_value = None
            await self.coordinator.async_request_refresh()

    @property
    def should_poll(self):
        return False

    def _handle_coordinator_update(self):
        if self._optimistic_value is not None:
            self._optimistic_value = None
        super()._handle_coordinator_update()
