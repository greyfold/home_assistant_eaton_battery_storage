import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
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
        try:
            return self.data.get("status", {}).get("energyFlow", {}).get("stateOfCharge")
        except Exception:
            return None

    @property
    def device_info(self):
        device_data = self.data.get("device", {}) if self.data else {}
        info = {
            "identifiers": {(DOMAIN, self.api.host)},
            "name": "Eaton xStorage Home",
            "manufacturer": "Eaton",
            "model": "xStorage Home",
            "entry_type": "service",
            "configuration_url": f"https://{self.api.host}",
        }
        if device_data:
            if "firmwareVersion" in device_data:
                info["sw_version"] = device_data["firmwareVersion"]
            if "inverterModelName" in device_data:
                info["model"] = f"xStorage Home ({device_data['inverterModelName']})"
            if "inverterSerialNumber" in device_data:
                info["serial_number"] = device_data["inverterSerialNumber"]
                info["identifiers"].add((DOMAIN, device_data["inverterSerialNumber"]))
            if "bmsFirmwareVersion" in device_data:
                info["hw_version"] = device_data["bmsFirmwareVersion"]
        return info

    async def _async_update_data(self):
        try:
            # Fetch multiple endpoints; tolerate failures for tech-only ones
            results = {}
            status = await self.api.get_status()
            device = None
            config_state = None
            settings = None
            metrics = None
            metrics_daily = None
            schedule = None
            technical_status = None
            maintenance_diagnostics = None

            try:
                device = await self.api.get_device()
            except Exception:
                pass
            try:
                config_state = await self.api.get_config_state()
            except Exception:
                pass
            try:
                settings = await self.api.get_settings()
            except Exception:
                pass
            try:
                metrics = await self.api.get_metrics()
            except Exception:
                pass
            try:
                metrics_daily = await self.api.get_metrics_daily()
            except Exception:
                pass
            try:
                schedule = await self.api.get_schedule()
            except Exception:
                pass
            try:
                technical_status = await self.api.get_technical_status()
            except Exception:
                pass
            try:
                maintenance_diagnostics = await self.api.get_maintenance_diagnostics()
            except Exception:
                pass

            # Build combined data; keep legacy compatibility where possible
            results["status"] = status.get("result", {}) if status else {}
            results["device"] = device.get("result", {}) if device else {}
            results["config_state"] = config_state if config_state else {}
            results["settings"] = settings.get("result", {}) if settings else {}
            results["metrics"] = metrics if metrics else {}
            results["metrics_daily"] = metrics_daily if metrics_daily else {}
            results["schedule"] = schedule if schedule else {}
            results["technical_status"] = technical_status.get("result", {}) if technical_status else {}
            results["maintenance_diagnostics"] = maintenance_diagnostics.get("result", {}) if maintenance_diagnostics else {}

            # Notifications
            try:
                notifications = await self.api.get_notifications()
                unread_count = await self.api.get_unread_notifications_count()
            except Exception:
                notifications = None
                unread_count = None
            results["notifications"] = notifications.get("result", {}) if notifications else {}
            results["unread_notifications_count"] = unread_count.get("result", {}) if unread_count else {}

            # Legacy compatibility: expose some status keys at root for sensors using top-level access
            try:
                if isinstance(results.get("status"), dict):
                    # Merge selected subtrees for backward-compat sensors that expect root keys
                    for key in ("energyFlow", "today", "last30daysEnergyFlow"):
                        if key in results["status"] and key not in results:
                            results[key] = results["status"][key]
            except Exception:
                pass

            return results
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}")