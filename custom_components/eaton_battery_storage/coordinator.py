"""
Data update coordinator for Eaton xStorage Home battery integration.

IMPORTANT ACCURACY WARNING:
Power measurement data retrieved by this coordinator from the xStorage Home API
has poor accuracy. Energy flow values (consumption, production, grid power, 
load values) are typically 30% higher than actual measurements. This affects
all power-related data in the coordinator's data structure under energyFlow,
today, and last30daysEnergyFlow sections.
"""
import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class EatonXstorageHomeCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api):
        super().__init__(
            hass,
            _LOGGER,
            name="Eaton xStorage Home",
            update_interval=timedelta(minutes=1),
        )
        self.api = api

    @property
    def battery_level(self):
        """Return the current battery level as a percentage."""
        try:
            return self.data.get("status", {}).get("energyFlow", {}).get("stateOfCharge")
        except Exception:
            return None

    @property
    def device_info(self):
        """Return device information for this coordinator."""
        device_data = self.data.get("device", {}) if self.data else {}
        
        device_info = {
            "identifiers": {(DOMAIN, self.api.host)},
            "name": "Eaton xStorage Home",
            "manufacturer": "Eaton",
            "model": "xStorage Home",
            "entry_type": "service",
            "configuration_url": f"https://{self.api.host}",
        }
        
        # Add detailed device information if available
        if device_data:
            # Add firmware version (software version)
            if "firmwareVersion" in device_data:
                device_info["sw_version"] = device_data["firmwareVersion"]
            
            # Add more specific model name if available
            if "inverterModelName" in device_data:
                device_info["model"] = f"xStorage Home ({device_data['inverterModelName']})"
            
            # Add serial number if available (inverter serial as primary identifier)
            if "inverterSerialNumber" in device_data:
                device_info["serial_number"] = device_data["inverterSerialNumber"]
                # Also add as an additional identifier
                device_info["identifiers"].add((DOMAIN, device_data["inverterSerialNumber"]))
            
            # Add hardware version (BMS firmware version)
            if "bmsFirmwareVersion" in device_data:
                device_info["hw_version"] = device_data["bmsFirmwareVersion"]
        
        return device_info

    async def _async_update_data(self):
        try:
            # Fetch all endpoints in parallel
            results = {}
            status = await self.api.get_status()
            device = await self.api.get_device()
            config_state = await self.api.get_config_state()
            settings = await self.api.get_settings()
            metrics = await self.api.get_metrics()
            metrics_daily = await self.api.get_metrics_daily()
            schedule = await self.api.get_schedule()
            # The following may require technician account, handle errors gracefully
            try:
                technical_status = await self.api.get_technical_status()
            except Exception:
                technical_status = None
            try:
                maintenance_diagnostics = await self.api.get_maintenance_diagnostics()
            except Exception:
                maintenance_diagnostics = None

            results["status"] = status.get("result", {}) if status else {}
            results["device"] = device.get("result", {}) if device else {}
            results["config_state"] = config_state if config_state else {}
            results["settings"] = settings.get("result", {}) if settings else {}
            results["metrics"] = metrics if metrics else {}
            results["metrics_daily"] = metrics_daily if metrics_daily else {}
            results["schedule"] = schedule if schedule else {}
            results["technical_status"] = technical_status.get("result", {}) if technical_status else {}
            results["maintenance_diagnostics"] = maintenance_diagnostics.get("result", {}) if maintenance_diagnostics else {}

            # Fetch notification data
            try:
                notifications = await self.api.get_notifications()
                unread_count = await self.api.get_unread_notifications_count()
            except Exception:
                notifications = None
                unread_count = None
            
            results["notifications"] = notifications.get("result", {}) if notifications else {}
            results["unread_notifications_count"] = unread_count.get("result", {}) if unread_count else {}

            return results
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}")