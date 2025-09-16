"""Sensor entities for Eaton xStorage Home battery integration.

IMPORTANT ACCURACY WARNING:
The built-in inverter energy monitoring has poor accuracy and typically reports
power output/consumption values approximately 30% higher than actual values.
This affects all power-related data in Home Assistant including:
- Grid power values
- Load consumption values
- PV production metrics
- Self-consumption calculations
- All 30-day and daily metrics

Users should rely on external power monitoring devices for accurate energy data.
Do not rely on consumption and production metrics from the inverter for accurate
energy calculations. This affects all power-related sensors including:
- Grid power values
- Load consumption values
- PV production metrics
- Self-consumption calculations
- All 30-day and daily metrics

Sensors with accuracy issues are marked with accuracy_warning=True in SENSOR_TYPES.
30-day metrics are disabled by default due to these accuracy concerns.
"""

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BMS_STATE_MAP,
    CURRENT_MODE_ACTION_MAP,
    CURRENT_MODE_COMMAND_MAP,
    CURRENT_MODE_RECURRENCE_MAP,
    CURRENT_MODE_TYPE_MAP,
    DOMAIN,
    OPERATION_MODE_MAP,
    POWER_ACCURACY_WARNING,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    # status endpoint
    "status.currentMode.command": {
        "name": "Current Mode Command",
        "unit": None,
        "device_class": None,
        "entity_category": None,
    },
    "status.currentMode.duration": {
        "name": "Current Mode Duration",
        "unit": None,
        "device_class": None,
        "entity_category": None,
    },
    "status.currentMode.startTime": {
        "name": "Current Mode Start Time",
        "unit": None,
        "device_class": None,
        "entity_category": None,
    },
    "status.currentMode.endTime": {
        "name": "Current Mode End Time",
        "unit": None,
        "device_class": None,
        "entity_category": None,
    },
    "status.currentMode.recurrence": {
        "name": "Current Mode Recurrence",
        "unit": None,
        "device_class": None,
        "entity_category": None,
    },
    "status.currentMode.type": {
        "name": "Current Mode Type",
        "unit": None,
        "device_class": None,
        "entity_category": None,
    },
    "status.currentMode.parameters.action": {
        "name": "Current Mode Action",
        "unit": None,
        "device_class": None,
        "entity_category": None,
    },
    "status.currentMode.parameters.power": {
        "name": "Current Mode Power",
        "unit": None,
        "device_class": None,
        "entity_category": None,
    },
    "status.currentMode.parameters.soc": {
        "name": "Current Mode SOC",
        "unit": PERCENTAGE,
        "device_class": "battery",
        "entity_category": None,
    },
    "status.energyFlow.acPvRole": {
        "name": "AC PV Role",
        "unit": None,
        "device_class": None,
        "entity_category": None,
        "pv_related": True,
    },
    # WARNING: Inverter power measurements are typically 30% higher than actual values - accuracy is poor
    "status.energyFlow.acPvValue": {
        "name": "AC PV Value",
        "unit": UnitOfPower.WATT,
        "device_class": "power",
        "entity_category": None,
        "pv_related": True,
        "accuracy_warning": True,
    },
    "status.energyFlow.batteryBackupLevel": {
        "name": "Battery Backup Level",
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
    },
    "status.energyFlow.batteryStatus": {
        "name": "Battery Status",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "status.energyFlow.batteryEnergyFlow": {
        "name": "Battery Power",
        "unit": UnitOfPower.WATT,
        "device_class": "power",
        "entity_category": None,
    },
    "status.energyFlow.criticalLoadRole": {
        "name": "Critical Load Role",
        "unit": None,
        "device_class": None,
        "entity_category": None,
    },
    # WARNING: Inverter power measurements are typically 30% higher than actual values - accuracy is poor
    "status.energyFlow.criticalLoadValue": {
        "name": "Critical Load Value",
        "unit": UnitOfPower.WATT,
        "device_class": "power",
        "entity_category": None,
        "accuracy_warning": True,
    },
    "status.energyFlow.dcPvRole": {
        "name": "DC PV Role",
        "unit": None,
        "device_class": None,
        "entity_category": None,
        "pv_related": True,
    },
    # WARNING: Inverter power measurements are typically 30% higher than actual values - accuracy is poor
    "status.energyFlow.dcPvValue": {
        "name": "DC PV Value",
        "unit": UnitOfPower.WATT,
        "device_class": "power",
        "entity_category": None,
        "pv_related": True,
        "accuracy_warning": True,
    },
    "status.energyFlow.gridRole": {
        "name": "Grid Role",
        "unit": None,
        "device_class": None,
        "entity_category": None,
    },
    # WARNING: Inverter power measurements are typically 30% higher than actual values - accuracy is poor
    "status.energyFlow.gridValue": {
        "name": "Grid Power",
        "unit": UnitOfPower.WATT,
        "device_class": "power",
        "entity_category": None,
        "accuracy_warning": True,
    },
    "status.energyFlow.nonCriticalLoadRole": {
        "name": "Non-Critical Load Role",
        "unit": None,
        "device_class": None,
        "entity_category": None,
    },
    # WARNING: Inverter power measurements are typically 30% higher than actual values - accuracy is poor
    "status.energyFlow.nonCriticalLoadValue": {
        "name": "Non-Critical Load Value",
        "unit": UnitOfPower.WATT,
        "device_class": "power",
        "entity_category": None,
        "accuracy_warning": True,
    },
    "status.energyFlow.operationMode": {
        "name": "Operation Mode",
        "unit": None,
        "device_class": None,
        "entity_category": None,
    },
    # WARNING: Inverter power measurements are typically 30% higher than actual values - accuracy is poor
    "status.energyFlow.selfConsumption": {
        "name": "Self Consumption",
        "unit": UnitOfPower.WATT,
        "device_class": "power",
        "entity_category": None,
        "accuracy_warning": True,
    },
    "status.energyFlow.selfSufficiency": {
        "name": "Self Sufficiency",
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": None,
    },
    "status.energyFlow.stateOfCharge": {
        "name": "Battery State of Charge",
        "unit": PERCENTAGE,
        "device_class": "battery",
        "entity_category": None,
    },
    "status.energyFlow.energySavingModeEnabled": {
        "name": "Energy Saving Mode Enabled",
        "unit": None,
        "device_class": None,
        "entity_category": None,
    },
    "status.energyFlow.energySavingModeActivated": {
        "name": "Energy Saving Mode Activated",
        "unit": None,
        "device_class": None,
        "entity_category": None,
    },
    # WARNING: 30-day metrics disabled by default - inverter measurements are typically 30% higher than actual values
    "status.last30daysEnergyFlow.gridConsumption": {
        "name": "30 Days Grid Consumption",
        "unit": UnitOfPower.WATT,
        "device_class": "power",
        "entity_category": None,
        "disabled_by_default": True,
        "accuracy_warning": True,
    },
    "status.last30daysEnergyFlow.photovoltaicProduction": {
        "name": "30 Days PV Production",
        "unit": UnitOfPower.WATT,
        "device_class": "power",
        "entity_category": None,
        "pv_related": True,
        "disabled_by_default": True,
        "accuracy_warning": True,
    },
    "status.last30daysEnergyFlow.selfConsumption": {
        "name": "30 Days Self Consumption",
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": None,
        "disabled_by_default": True,
        "accuracy_warning": True,
    },
    "status.last30daysEnergyFlow.selfSufficiency": {
        "name": "30 Days Self Sufficiency",
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": None,
        "disabled_by_default": True,
        "accuracy_warning": True,
    },
    # WARNING: Today's metrics also affected by inverter accuracy issues
    "status.today.gridConsumption": {
        "name": "Today's Grid Consumption",
        "unit": UnitOfPower.WATT,
        "device_class": "power",
        "entity_category": None,
        "disabled_by_default": True,
        "accuracy_warning": True,
    },
    "status.today.photovoltaicProduction": {
        "name": "Today's PV Production",
        "unit": UnitOfPower.WATT,
        "device_class": "power",
        "entity_category": None,
        "pv_related": True,
        "accuracy_warning": True,
    },
    "status.today.selfConsumption": {
        "name": "Today's Self Consumption",
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": None,
        "disabled_by_default": True,
        "accuracy_warning": True,
    },
    "status.today.selfSufficiency": {
        "name": "Today's Self Sufficiency",
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": None,
        "disabled_by_default": True,
        "accuracy_warning": True,
    },
    # device endpoint
    "device.firmwareVersion": {
        "name": "Firmware Version",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "device.inverterFirmwareVersion": {
        "name": "Inverter Firmware Version",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "device.bmsFirmwareVersion": {
        "name": "BMS Firmware Version",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "device.energySavingMode.houseConsumptionThreshold": {
        "name": "House Consumption Threshold",
        "unit": UnitOfPower.WATT,
        "device_class": "power",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "device.inverterManufacturer": {
        "name": "Inverter Manufacturer",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "device.inverterModelName": {
        "name": "Inverter Model Name",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "device.inverterVaRating": {
        "name": "Inverter VA Rating",
        "unit": "VA",
        "device_class": "apparent_power",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "device.inverterSerialNumber": {
        "name": "Inverter Serial Number",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "device.inverterNominalVpv": {
        "name": "Inverter Nominal VPV",
        "unit": "V",
        "device_class": "voltage",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
    },
    "device.bmsCapacity": {
        "name": "BMS Capacity",
        "unit": "kWh",
        "device_class": "energy_storage",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "device.bmsSerialNumber": {
        "name": "BMS Serial Number",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "device.bmsModel": {
        "name": "BMS Model",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "device.bundleVersion": {
        "name": "Bundle Version",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "device.localPortalRemoteId": {
        "name": "Local Portal Remote ID",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "device.dns": {
        "name": "DNS Server",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "device.timezone.name": {
        "name": "Device Timezone",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    # technical status endpoint - requires technician account
    "technical_status.operationMode": {
        "name": "Technical Operation Mode",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.gridVoltage": {
        "name": "Grid Voltage",
        "unit": "V",
        "device_class": "voltage",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.gridFrequency": {
        "name": "Grid Frequency",
        "unit": "Hz",
        "device_class": "frequency",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.currentToGrid": {
        "name": "Current To Grid",
        "unit": "A",
        "device_class": "current",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.inverterPower": {
        "name": "Inverter Power",
        "unit": UnitOfPower.WATT,
        "device_class": "power",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.inverterTemperature": {
        "name": "Inverter Temperature",
        "unit": "°C",
        "device_class": "temperature",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.busVoltage": {
        "name": "Bus Voltage",
        "unit": "V",
        "device_class": "voltage",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.gridCode": {
        "name": "Grid Code",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.dcCurrentInjectionR": {
        "name": "DC Current Injection R",
        "unit": "A",
        "device_class": "current",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
    },
    "technical_status.dcCurrentInjectionS": {
        "name": "DC Current Injection S",
        "unit": "A",
        "device_class": "current",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
    },
    "technical_status.dcCurrentInjectionT": {
        "name": "DC Current Injection T",
        "unit": "A",
        "device_class": "current",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
    },
    "technical_status.inverterModel": {
        "name": "Technical Inverter Model",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.inverterPowerRating": {
        "name": "Technical Inverter Power Rating",
        "unit": UnitOfPower.WATT,
        "device_class": "power",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.pv1Voltage": {
        "name": "PV1 Voltage",
        "unit": "V",
        "device_class": "voltage",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
    },
    "technical_status.pv1Current": {
        "name": "PV1 Current",
        "unit": "A",
        "device_class": "current",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
    },
    "technical_status.pv2Voltage": {
        "name": "PV2 Voltage",
        "unit": "V",
        "device_class": "voltage",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
    },
    "technical_status.pv2Current": {
        "name": "PV2 Current",
        "unit": "A",
        "device_class": "current",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
    },
    "technical_status.bmsVoltage": {
        "name": "BMS Voltage",
        "unit": "V",
        "device_class": "voltage",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsCurrent": {
        "name": "BMS Current",
        "unit": "A",
        "device_class": "current",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsTemperature": {
        "name": "BMS Temperature",
        "unit": "°C",
        "device_class": "temperature",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsAvgTemperature": {
        "name": "BMS Average Temperature",
        "unit": "°C",
        "device_class": "temperature",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsMaxTemperature": {
        "name": "BMS Max Temperature",
        "unit": "°C",
        "device_class": "temperature",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsMinTemperature": {
        "name": "BMS Min Temperature",
        "unit": "°C",
        "device_class": "temperature",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsTotalCharge": {
        "name": "BMS Total Charge",
        "unit": "kWh",
        "device_class": "energy",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsTotalDischarge": {
        "name": "BMS Total Discharge",
        "unit": "kWh",
        "device_class": "energy",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsStateOfCharge": {
        "name": "Technical BMS State of Charge",
        "unit": PERCENTAGE,
        "device_class": "battery",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsState": {
        "name": "BMS State",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsFaultCode": {
        "name": "BMS Fault Code",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsHighestCellVoltage": {
        "name": "BMS Highest Cell Voltage",
        "unit": "mV",
        "device_class": "voltage",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsLowestCellVoltage": {
        "name": "BMS Lowest Cell Voltage",
        "unit": "mV",
        "device_class": "voltage",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsCellVoltageDelta": {
        "name": "BMS Cell Voltage Delta",
        "unit": "mV",
        "device_class": "voltage",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.tidaProtocolVersion": {
        "name": "TIDA Protocol Version",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.invBootloaderVersion": {
        "name": "Inverter Bootloader Version",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    # maintenance diagnostics endpoint - requires technician account
    "maintenance_diagnostics.ramUsage.total": {
        "name": "System RAM Total",
        "unit": "MB",
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "maintenance_diagnostics.ramUsage.used": {
        "name": "System RAM Used",
        "unit": "MB",
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "maintenance_diagnostics.cpuUsage.used": {
        "name": "System CPU Usage",
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    # notification endpoints
    "unread_notifications_count.total": {
        "name": "Unread Notifications Count",
        "unit": None,
        "device_class": None,
        "entity_category": None,
    },
    "notifications.total": {
        "name": "Total Notifications Count",
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN]["coordinator"]
    has_pv = config_entry.data.get("has_pv", False)

    # Create sensors based on PV configuration
    entities = []
    for key, description in SENSOR_TYPES.items():
        # Skip PV-related sensors if has_pv is False
        if description.get("pv_related", False) and not has_pv:
            continue
        entities.append(EatonXStorageSensor(coordinator, key, description, has_pv))

    # Add the notifications array sensor
    entities.append(EatonXStorageNotificationsSensor(coordinator))

    async_add_entities(entities)


class EatonXStorageNotificationsSensor(CoordinatorEntity, SensorEntity):
    """Sensor for displaying notifications array."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    @property
    def name(self):
        return "Notifications"

    @property
    def unique_id(self):
        return "eaton_xstorage_notifications"

    @property
    def state(self):
        """Return the number of notifications as the state."""
        try:
            notifications_data = self.coordinator.data.get("notifications", {})
            results = notifications_data.get("results", [])
            return len(results)
        except Exception as e:
            _LOGGER.error(f"Error retrieving notifications state: {e}")
            return 0

    @property
    def extra_state_attributes(self):
        """Return notifications as attributes."""
        try:
            notifications_data = self.coordinator.data.get("notifications", {})
            results = notifications_data.get("results", [])

            # Format notifications for better readability
            formatted_notifications = []
            for notification in results:
                formatted_notifications.append(
                    {
                        "alert_id": notification.get("alertId"),
                        "level": notification.get("level"),
                        "type": notification.get("type"),
                        "sub_type": notification.get("subType"),
                        "status": notification.get("status"),
                        "created_at": notification.get("createdAt"),
                        "updated_at": notification.get("updatedAt"),
                    }
                )

            return {
                "notifications": formatted_notifications,
                "total": notifications_data.get("total", 0),
                "start": notifications_data.get("start", 0),
                "size": notifications_data.get("size", 0),
            }
        except Exception as e:
            _LOGGER.error(f"Error retrieving notifications attributes: {e}")
            return {}

    @property
    def device_info(self):
        return self.coordinator.device_info

    @property
    def should_poll(self):
        return False


class EatonXStorageSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, key, description, has_pv):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._key = key
        self._name = description["name"]
        self._unit = description["unit"]
        self._device_class = description["device_class"]
        self._entity_category = description["entity_category"]
        self._disabled_by_default = description.get("disabled_by_default", False)
        self._accuracy_warning = description.get("accuracy_warning", False)
        self._precision = description.get("precision", None)

    @property
    def entity_category(self):
        return self._entity_category

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added.

        This only applies when first added to the entity registry.
        """
        # Disable TIDA Protocol Version by default as it's rarely useful
        if self._key == "technical_status.tidaProtocolVersion":
            return False

        # Disable entities marked with disabled_by_default flag (e.g., 30-day metrics)
        if self._disabled_by_default:
            return False

        return True

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"eaton_xstorage_{self._key}"

    @property
    def state(self):
        try:
            # Log accuracy warning for sensors with known accuracy issues
            if self._accuracy_warning:
                _LOGGER.debug(
                    f"Sensor {self._name} ({self._key}) - {POWER_ACCURACY_WARNING}"
                )

            # Calculate BMS cell voltage delta first (before normal data extraction)
            if self._key == "technical_status.bmsCellVoltageDelta":
                try:
                    tech_status = self.coordinator.data.get("technical_status", {})
                    highest = tech_status.get("bmsHighestCellVoltage")
                    lowest = tech_status.get("bmsLowestCellVoltage")

                    # Filter out values below 1000mV before calculation
                    if highest is not None and highest < 1000:
                        _LOGGER.error(
                            f"BMS highest cell voltage below 1000mV threshold: {highest}mV - delta calculation not possible"
                        )
                        return None
                    if lowest is not None and lowest < 1000:
                        _LOGGER.error(
                            f"BMS lowest cell voltage below 1000mV threshold: {lowest}mV - delta calculation not possible"
                        )
                        return None

                    if highest is not None and lowest is not None:
                        delta = float(highest) - float(lowest)
                        result = round(delta, 1)
                        return result
                    _LOGGER.debug(
                        f"Delta calculation failed - missing values. Highest: {highest}, Lowest: {lowest}"
                    )
                    return None
                except (ValueError, TypeError) as e:
                    _LOGGER.error(f"Error calculating BMS cell voltage delta: {e}")
                    return None

            # Normal data extraction for other sensors
            keys = self._key.split(".")
            value = self.coordinator.data
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k, {})
                else:
                    value = {}
            # If value is still a dict, return None
            if isinstance(value, dict):
                return None

            # Handle null/None values that should display as "None" instead of "Unknown"
            if value is None:
                return None

            # Debug logging for technical status sensors to help troubleshoot formatting issues
            if self._key.startswith("technical_status.") and value is not None:
                _LOGGER.debug(
                    f"Technical Status Sensor '{self._key}' - Raw value: '{value}' (type: {type(value).__name__})"
                )

            # Filter out values below 1000mV for BMS cell voltage sensors
            if self._key in [
                "technical_status.bmsHighestCellVoltage",
                "technical_status.bmsLowestCellVoltage",
            ]:
                if isinstance(value, (int, float)) and value < 1000:
                    _LOGGER.error(
                        f"BMS cell voltage {self._key} below 1000mV threshold: {value}mV - treating as error"
                    )
                    return None

            # Format Current Mode Command to human-readable format
            if self._key == "status.currentMode.command" and isinstance(value, str):
                return CURRENT_MODE_COMMAND_MAP.get(value, value)

            # Format Current Mode Action to human-readable format
            if self._key == "status.currentMode.parameters.action" and isinstance(
                value, str
            ):
                return CURRENT_MODE_ACTION_MAP.get(value, value)

            # Format Current Mode Type to human-readable format
            if self._key == "status.currentMode.type" and isinstance(value, str):
                return CURRENT_MODE_TYPE_MAP.get(value, value)

            # Format Current Mode Recurrence to human-readable format
            if self._key == "status.currentMode.recurrence" and isinstance(value, str):
                return CURRENT_MODE_RECURRENCE_MAP.get(value, value)

            # Format Operation Mode to human-readable format
            if self._key == "status.energyFlow.operationMode" and isinstance(
                value, str
            ):
                return OPERATION_MODE_MAP.get(value, value)

            # Format Technical Operation Mode to human-readable format
            if self._key == "technical_status.operationMode" and isinstance(value, str):
                # Add debug logging to help troubleshoot
                _LOGGER.debug(
                    f"Technical Operation Mode - Raw value: '{value}', Mapped value: '{OPERATION_MODE_MAP.get(value, value)}'"
                )
                return OPERATION_MODE_MAP.get(value, value)

            # Format BMS State to human-readable format
            if self._key == "technical_status.bmsState" and isinstance(value, str):
                return BMS_STATE_MAP.get(value, value)

            # Format Battery Status to human-readable format (uses same mapping as BMS State)
            if self._key == "status.energyFlow.batteryStatus" and isinstance(
                value, str
            ):
                return BMS_STATE_MAP.get(value, value)

            # Round temperature values to 1 decimal place
            if self._device_class == "temperature" and isinstance(value, (int, float)):
                return round(value, 1)

            # Format startTime and endTime to 12-hour format
            if self._key.endswith("startTime") or self._key.endswith("endTime"):
                if isinstance(value, int) or (
                    isinstance(value, str) and value.isdigit()
                ):
                    # Accept both int and string representations
                    time_val = int(value)
                    hour = time_val // 100
                    minute = time_val % 100
                    if 0 <= hour < 24 and 0 <= minute < 60:
                        suffix = " am" if hour < 12 or hour == 24 else " pm"
                        hour12 = hour % 12
                        if hour12 == 0:
                            hour12 = 12
                        return f"{hour12}:{minute:02d}{suffix}"
            # Convert RAM usage from bytes to megabytes
            if "ramUsage" in self._key and isinstance(value, (int, float)):
                return round(value / 1024 / 1024, 2)
            # Round CPU usage to 2 decimal places
            if "cpuUsage.used" in self._key and isinstance(value, (int, float)):
                return round(value, 2)
            return value
        except Exception as e:
            _LOGGER.error(f"Error retrieving state for {self._key}: {e}")
            return None

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def device_class(self):
        return self._device_class

    @property
    def suggested_display_precision(self):
        """Return the suggested number of decimal places for display."""
        # Use sensor-specific precision if defined
        if self._precision is not None:
            return self._precision

        # Temperature sensors: 1 decimal place
        if self._device_class == "temperature" or self._device_class == "voltage":
            return 1
        # Current sensors: 2 decimal places
        if self._device_class == "current" or self._device_class == "frequency":
            return 2
        # Power sensors: 0 decimal places (whole watts)
        if self._device_class == "power":
            return 0
        # Energy sensors: 1 decimal place
        if self._device_class == "energy" or self._device_class == "energy_storage":
            return 1
        # Apparent power (VA): 0 decimal places
        if (
            self._device_class == "apparent_power"
            or self._unit == PERCENTAGE
            or "ramUsage" in self._key
        ):
            return 0
        # CPU usage: 1 decimal place
        if "cpuUsage" in self._key:
            return 1
        # Cell voltage sensors (mV): 0 decimal places (already in millivolts)
        if "CellVoltage" in self._key or "VoltageDelta" in self._key:
            return 0
        # Default: no specific precision
        return None

    @property
    def extra_state_attributes(self):
        """Return extra state attributes for entities with accuracy warnings."""
        if self._accuracy_warning:
            return {
                "accuracy_warning": POWER_ACCURACY_WARNING,
                "measurement_note": "Values typically 30% higher than actual",
            }
        return None

    @property
    def device_info(self):
        return self.coordinator.device_info

    @property
    def should_poll(self):
        return False
