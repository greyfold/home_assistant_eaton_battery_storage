"""Sensor entities for Eaton xStorage Home battery integration.

IMPORTANT ACCURACY WARNING:
The built-in inverter energy monitoring has poor accuracy and typically reports
power output/consumption values approximately 10%-30% higher than actual values.
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

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    ACCOUNT_TYPE_TECHNICIAN,
    BMS_FAULT_CODE_MAP,
    BMS_NO_FAULT,
    BMS_STATE_MAP,
    CONF_HAS_PV,
    CONF_USER_TYPE,
    CURRENT_MODE_ACTION_MAP,
    CURRENT_MODE_COMMAND_MAP,
    CURRENT_MODE_RECURRENCE_MAP,
    CURRENT_MODE_TYPE_MAP,
    ENERGY_FLOW_ROLE_MAP,
    NOTIFICATION_SUBTYPE_MAP,
    OPERATION_MODE_MAP,
    POWER_ACCURACY_WARNING,
    TECHNICIAN_ONLY_SENSORS,
    resolve_mode_command,
    sensor_unique_id,
)
from .coordinator import EatonConfigEntry, EatonXstorageHomeCoordinator
from .entity import EatonEntity

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

CELL_VOLTAGE_DELTA_KEY = "technical_status.bmsCellVoltageDelta"
BMS_FAULT_CODE_KEY = "technical_status.bmsFaultCode"
CURRENT_MODE_COMMAND_KEY = "status.currentMode.command"

# The BMS reports cell voltages in mV; a lower reading is a sensor error.
MIN_CELL_VOLTAGE_MV = 1000
CELL_VOLTAGE_KEYS = frozenset(
    {
        "technical_status.bmsHighestCellVoltage",
        "technical_status.bmsLowestCellVoltage",
    }
)

# Readings the device zeroes when it cannot take them. A connected pack is never
# at 0 V, and the API documentation shows bmsAvgTemperature reading 0 alongside a
# max of 35.5 and a min of 32.8, so 0 there is an absent reading rather than a
# freezing battery. The lifetime counters stay here because they only ever climb:
# a return to 0 is a read error, and letting it through would land a reset in the
# TOTAL statistic and a spurious lifetime's worth of charge in its sum.
ZERO_IS_INVALID_KEYS = frozenset(
    {
        "technical_status.bmsMaxTemperature",
        "technical_status.bmsMinTemperature",
        "technical_status.bmsAvgTemperature",
        "technical_status.bmsTotalCharge",
        "technical_status.bmsTotalDischarge",
        "technical_status.bmsVoltage",
    }
)

# Sensor keys whose raw string value has a human-readable label.
VALUE_MAPS: dict[str, dict[str, str]] = {
    "status.currentMode.command": CURRENT_MODE_COMMAND_MAP,
    "status.currentMode.parameters.action": CURRENT_MODE_ACTION_MAP,
    "status.currentMode.type": CURRENT_MODE_TYPE_MAP,
    "status.currentMode.recurrence": CURRENT_MODE_RECURRENCE_MAP,
    "status.energyFlow.operationMode": OPERATION_MODE_MAP,
    "technical_status.operationMode": OPERATION_MODE_MAP,
    "technical_status.bmsState": BMS_STATE_MAP,
    "status.energyFlow.batteryStatus": BMS_STATE_MAP,
    "status.energyFlow.acPvRole": ENERGY_FLOW_ROLE_MAP,
    "status.energyFlow.dcPvRole": ENERGY_FLOW_ROLE_MAP,
    "status.energyFlow.gridRole": ENERGY_FLOW_ROLE_MAP,
    "status.energyFlow.criticalLoadRole": ENERGY_FLOW_ROLE_MAP,
    "status.energyFlow.nonCriticalLoadRole": ENERGY_FLOW_ROLE_MAP,
}


def _value_at(data: dict[str, Any], key: str) -> Any:
    """Return the scalar at a dotted key path, or None if there is none."""
    value: Any = data
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return None if isinstance(value, dict) else value


def _format_fault_codes(value: Any) -> Any:
    """Render the BMS fault codes, which arrive as a list or null when healthy."""
    if value is None:
        return BMS_NO_FAULT
    if not isinstance(value, list):
        return value
    return (
        ", ".join(BMS_FAULT_CODE_MAP.get(code, str(code)) for code in value)[:255]
        or BMS_NO_FAULT
    )


def _is_number(value: str) -> bool:
    """Return True when a string reading can be used as a number."""
    try:
        float(value)
    except ValueError:
        return False
    return True


def _notification_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the notifications the device listed, ignoring malformed entries."""
    results = data.get("notifications", {}).get("results", [])
    return [item for item in results if isinstance(item, dict)]


def _notification_time(value: Any) -> datetime | None:
    """Return a notification timestamp, which the device reports in milliseconds."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return dt_util.utc_from_timestamp(value / 1000)


def _cell_voltage_delta(technical_status: dict[str, Any]) -> float | None:
    """Return the spread between the highest and lowest cell voltage."""
    highest = technical_status.get("bmsHighestCellVoltage")
    lowest = technical_status.get("bmsLowestCellVoltage")
    if highest is None or lowest is None:
        _LOGGER.debug(
            "Cell voltage delta needs both readings, got %s and %s", highest, lowest
        )
        return None

    try:
        highest, lowest = float(highest), float(lowest)
    except (TypeError, ValueError):
        # The device reports "n/a" for a reading it cannot take, every poll.
        _LOGGER.debug("Cell voltages are not numeric: %s and %s", highest, lowest)
        return None

    if min(highest, lowest) < MIN_CELL_VOLTAGE_MV:
        _LOGGER.debug(
            "Cell voltage below %smV, delta not calculated: %s and %s",
            MIN_CELL_VOLTAGE_MV,
            highest,
            lowest,
        )
        return None

    return round(highest - lowest, 1)


def _is_device_time(value: Any) -> bool:
    """Return True when the value looks like the HHMM the API reports."""
    return (isinstance(value, int) and not isinstance(value, bool)) or (
        isinstance(value, str) and value.isdigit()
    )


def _format_device_time(value: int | str) -> str | None:
    """Format an HHMM reading as HH:MM, or None when it is out of range."""
    hour, minute = divmod(int(value), 100)
    if 0 <= hour < 24 and 0 <= minute < 60:
        return f"{hour:02d}:{minute:02d}"
    return None


def _translation_key_from_key(key: str) -> str:
    """Build a stable translation key from a sensor data key."""
    return key.replace(".", "_").replace("-", "_").lower()


# Every device class Home Assistant accepts a state class for. Core maps each
# device class to the set of state classes it permits; this picks one default
# per class. Sensors with a device class not listed here, and sensors with none
# at all, need an explicit "state_class" in SENSOR_TYPES.
DEVICE_CLASS_STATE_CLASSES: dict[SensorDeviceClass, SensorStateClass] = {
    SensorDeviceClass.APPARENT_POWER: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.BATTERY: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.CURRENT: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.DATA_SIZE: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.ENERGY: SensorStateClass.TOTAL_INCREASING,
    SensorDeviceClass.ENERGY_STORAGE: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.FREQUENCY: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.POWER: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.TEMPERATURE: SensorStateClass.MEASUREMENT,
    SensorDeviceClass.VOLTAGE: SensorStateClass.MEASUREMENT,
}

# Decimal places to display, by device class. Anything not listed, and any
# sensor needing something else, carries "precision" in SENSOR_TYPES.
DEVICE_CLASS_PRECISIONS: dict[SensorDeviceClass, int] = {
    SensorDeviceClass.APPARENT_POWER: 0,
    SensorDeviceClass.CURRENT: 2,
    SensorDeviceClass.ENERGY: 1,
    SensorDeviceClass.ENERGY_STORAGE: 1,
    SensorDeviceClass.FREQUENCY: 2,
    SensorDeviceClass.POWER: 0,
    SensorDeviceClass.TEMPERATURE: 1,
    SensorDeviceClass.VOLTAGE: 1,
}

# The BMS reports its coulomb counters in ampere hours. Home Assistant has no
# device class or unit constant for charge, so these carry neither.
AMPERE_HOUR = "Ah"


def _display_precision(
    key: str, description: dict[str, Any], device_class: SensorDeviceClass | None
) -> int | None:
    """Return the decimal places a sensor should be displayed with."""
    if (precision := description.get("precision")) is not None:
        return precision
    if device_class is not None:
        precision = DEVICE_CLASS_PRECISIONS.get(device_class)
        if precision is not None:
            return precision
    if "cpuUsage" in key:
        return 1
    if "ramUsage" in key or description.get("unit") == PERCENTAGE:
        return 0
    return None


SENSOR_TYPES: dict[str, dict[str, Any]] = {
    # status endpoint
    "status.currentMode.command": {
        "unit": None,
        "device_class": None,
        "entity_category": None,
        "icon": "mdi:gesture-tap-button",
    },
    "status.currentMode.duration": {
        "unit": UnitOfTime.HOURS,
        "device_class": SensorDeviceClass.DURATION,
        "entity_category": None,
        "icon": "mdi:timer-outline",
    },
    "status.currentMode.startTime": {
        "unit": None,
        "device_class": None,
        "entity_category": None,
        "icon": "mdi:clock-start",
    },
    "status.currentMode.endTime": {
        "unit": None,
        "device_class": None,
        "entity_category": None,
        "icon": "mdi:clock-end",
    },
    "status.currentMode.recurrence": {
        "unit": None,
        "device_class": None,
        "entity_category": None,
        "icon": "mdi:calendar-refresh",
    },
    "status.currentMode.type": {
        "unit": None,
        "device_class": None,
        "entity_category": None,
        "icon": "mdi:format-list-bulleted-type",
    },
    "status.currentMode.parameters.action": {
        "unit": None,
        "device_class": None,
        "entity_category": None,
        "icon": "mdi:play-outline",
    },
    "status.currentMode.parameters.power": {
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": None,
        "state_class": None,
        "icon": "mdi:flash",
    },
    "status.currentMode.parameters.soc": {
        "unit": PERCENTAGE,
        "device_class": SensorDeviceClass.BATTERY,
        "entity_category": None,
        "state_class": None,
    },
    "status.energyFlow.acPvRole": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
        "icon": "mdi:solar-power",
    },
    # WARNING: Inverter power measurements are typically 10%-30% higher than actual values - accuracy is poor
    "status.energyFlow.acPvValue": {
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "entity_category": None,
        "pv_related": True,
        "accuracy_warning": True,
    },
    "status.energyFlow.batteryBackupLevel": {
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:battery-heart-outline",
    },
    "status.energyFlow.batteryStatus": {
        "unit": None,
        "device_class": None,
        "entity_category": None,
        "icon": "mdi:battery",
    },
    "status.energyFlow.batteryEnergyFlow": {
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "entity_category": None,
    },
    "status.energyFlow.criticalLoadRole": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "icon": "mdi:alert-octagon-outline",
    },
    # WARNING: Inverter power measurements are typically 10%-30% higher than actual values - accuracy is poor
    "status.energyFlow.criticalLoadValue": {
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "entity_category": None,
        "accuracy_warning": True,
    },
    "status.energyFlow.dcPvRole": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
        "icon": "mdi:solar-power",
    },
    # WARNING: Inverter power measurements are typically 10%-30% higher than actual values - accuracy is poor
    "status.energyFlow.dcPvValue": {
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "entity_category": None,
        "pv_related": True,
        "accuracy_warning": True,
    },
    "status.energyFlow.gridRole": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "icon": "mdi:transmission-tower",
    },
    # WARNING: Inverter power measurements are typically 10%-30% higher than actual values - accuracy is poor
    "status.energyFlow.gridValue": {
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "entity_category": None,
        "accuracy_warning": True,
    },
    "status.energyFlow.nonCriticalLoadRole": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "icon": "mdi:power-socket",
    },
    # WARNING: Inverter power measurements are typically 10%-30% higher than actual values - accuracy is poor
    "status.energyFlow.nonCriticalLoadValue": {
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "entity_category": None,
        "accuracy_warning": True,
    },
    "status.energyFlow.operationMode": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:cog-outline",
    },
    # WARNING: Inverter power measurements are typically 10%-30% higher than actual values - accuracy is poor
    # The API reports this as a percentage of generated energy used directly,
    # not as a power reading.
    "status.energyFlow.selfConsumption": {
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "accuracy_warning": True,
        "icon": "mdi:home-lightning-bolt",
    },
    "status.energyFlow.selfSufficiency": {
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:gauge",
    },
    "status.energyFlow.stateOfCharge": {
        "unit": PERCENTAGE,
        "device_class": SensorDeviceClass.BATTERY,
        "entity_category": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "status.energyFlow.energySavingModeEnabled": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:leaf",
    },
    "status.energyFlow.energySavingModeActivated": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:leaf-circle",
    },
    # WARNING: 30-day metrics disabled by default - inverter measurements are typically 10%-30% higher than actual values
    # A rolling window's absolute value is what matters, not its growth, so TOTAL
    # is wrong; MEASUREMENT is barred for the energy device class, hence none.
    "status.last30daysEnergyFlow.gridConsumption": {
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "state_class": None,
        "accuracy_warning": True,
    },
    "status.last30daysEnergyFlow.photovoltaicProduction": {
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
        "disabled_by_default": True,
        "state_class": None,
        "accuracy_warning": True,
    },
    "status.last30daysEnergyFlow.selfConsumption": {
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "state_class": SensorStateClass.MEASUREMENT,
        "accuracy_warning": True,
        "icon": "mdi:calendar-clock",
    },
    "status.last30daysEnergyFlow.selfSufficiency": {
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "state_class": SensorStateClass.MEASUREMENT,
        "accuracy_warning": True,
        "icon": "mdi:calendar-gauge",
    },
    # WARNING: Today's metrics also affected by inverter accuracy issues
    "status.today.gridConsumption": {
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "accuracy_warning": True,
    },
    "status.today.photovoltaicProduction": {
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "entity_category": None,
        "pv_related": True,
        "accuracy_warning": True,
    },
    "status.today.selfConsumption": {
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "state_class": SensorStateClass.MEASUREMENT,
        "accuracy_warning": True,
        "icon": "mdi:clock-outline",
    },
    "status.today.selfSufficiency": {
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "state_class": SensorStateClass.MEASUREMENT,
        "accuracy_warning": True,
        "icon": "mdi:clock-check-outline",
    },
    # device endpoint
    "device.firmwareVersion": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:chip",
    },
    "device.inverterFirmwareVersion": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:chip",
    },
    "device.bmsFirmwareVersion": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:chip",
    },
    "device.energySavingMode.houseConsumptionThreshold": {
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
    },
    "device.inverterManufacturer": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:factory",
    },
    "device.inverterModelName": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:identifier",
    },
    "device.inverterVaRating": {
        "unit": UnitOfApparentPower.VOLT_AMPERE,
        "device_class": SensorDeviceClass.APPARENT_POWER,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "state_class": None,
    },
    "device.inverterSerialNumber": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:barcode",
    },
    "device.inverterNominalVpv": {
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
        "disabled_by_default": True,
        "state_class": None,
    },
    "device.bmsCapacity": {
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY_STORAGE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
    },
    "device.bmsSerialNumber": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:barcode",
    },
    "device.bmsModel": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:identifier",
    },
    "device.bundleVersion": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:package-variant",
    },
    "device.localPortalRemoteId": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:remote-desktop",
    },
    "device.dns": {
        "unit": None,
        "device_class": None,
        "disabled_by_default": True,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "icon": "mdi:dns",
    },
    "device.timezone.name": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:earth",
    },
    # technical status endpoint - requires technician account
    "technical_status.operationMode": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:cog-outline",
    },
    "technical_status.gridVoltage": {
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.gridFrequency": {
        "unit": UnitOfFrequency.HERTZ,
        "device_class": SensorDeviceClass.FREQUENCY,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.currentToGrid": {
        "unit": UnitOfElectricCurrent.AMPERE,
        "device_class": SensorDeviceClass.CURRENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.inverterPower": {
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.inverterTemperature": {
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.busVoltage": {
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.gridCode": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:code-tags",
    },
    "technical_status.dcCurrentInjectionR": {
        "unit": UnitOfElectricCurrent.AMPERE,
        "device_class": SensorDeviceClass.CURRENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
    },
    "technical_status.dcCurrentInjectionS": {
        "unit": UnitOfElectricCurrent.AMPERE,
        "device_class": SensorDeviceClass.CURRENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
    },
    "technical_status.dcCurrentInjectionT": {
        "unit": UnitOfElectricCurrent.AMPERE,
        "device_class": SensorDeviceClass.CURRENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
    },
    "technical_status.inverterModel": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:identifier",
    },
    # Reads a constant 0 on at least the 3.6kW unit, so it is not a statistic.
    "technical_status.inverterPowerRating": {
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "state_class": None,
    },
    "technical_status.pv1Voltage": {
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
    },
    "technical_status.pv1Current": {
        "unit": UnitOfElectricCurrent.AMPERE,
        "device_class": SensorDeviceClass.CURRENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
    },
    "technical_status.pv2Voltage": {
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
    },
    "technical_status.pv2Current": {
        "unit": UnitOfElectricCurrent.AMPERE,
        "device_class": SensorDeviceClass.CURRENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "pv_related": True,
    },
    "technical_status.bmsVoltage": {
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsCurrent": {
        "unit": UnitOfElectricCurrent.AMPERE,
        "device_class": SensorDeviceClass.CURRENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsTemperature": {
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsAvgTemperature": {
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsMaxTemperature": {
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsMinTemperature": {
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    # Lifetime counters that never reset, so TOTAL rather than TOTAL_INCREASING.
    "technical_status.bmsTotalCharge": {
        "unit": AMPERE_HOUR,
        "device_class": None,
        "precision": 0,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "state_class": SensorStateClass.TOTAL,
    },
    "technical_status.bmsTotalDischarge": {
        "unit": AMPERE_HOUR,
        "device_class": None,
        "precision": 0,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "state_class": SensorStateClass.TOTAL,
    },
    "technical_status.bmsStateOfCharge": {
        "unit": PERCENTAGE,
        "device_class": SensorDeviceClass.BATTERY,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "technical_status.bmsState": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "icon": "mdi:battery",
    },
    "technical_status.bmsFaultCode": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "icon": "mdi:alert-circle-outline",
    },
    "technical_status.bmsHighestCellVoltage": {
        "unit": UnitOfElectricPotential.MILLIVOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "precision": 0,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsLowestCellVoltage": {
        "unit": UnitOfElectricPotential.MILLIVOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "precision": 0,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.bmsCellVoltageDelta": {
        "unit": UnitOfElectricPotential.MILLIVOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "precision": 0,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "technical_status.tidaProtocolVersion": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:protocol",
    },
    "technical_status.invBootloaderVersion": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "disabled_by_default": True,
        "icon": "mdi:chip",
    },
    # maintenance diagnostics endpoint - requires technician account
    "maintenance_diagnostics.ramUsage.total": {
        "unit": UnitOfInformation.MEBIBYTES,
        "device_class": SensorDeviceClass.DATA_SIZE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:memory",
    },
    "maintenance_diagnostics.ramUsage.used": {
        "unit": UnitOfInformation.MEBIBYTES,
        "device_class": SensorDeviceClass.DATA_SIZE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:memory",
    },
    "maintenance_diagnostics.cpuUsage.used": {
        "unit": PERCENTAGE,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:cpu-64-bit",
    },
    # notification endpoints
    "unread_notifications_count.total": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:bell-badge-outline",
    },
    "notifications.total": {
        "unit": None,
        "device_class": None,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:bell-outline",
    },
}


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: EatonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Eaton xStorage Home sensor platform."""
    coordinator = config_entry.runtime_data
    has_pv = config_entry.data.get(CONF_HAS_PV, False)
    is_technician = (
        config_entry.data.get(CONF_USER_TYPE, ACCOUNT_TYPE_TECHNICIAN)
        == ACCOUNT_TYPE_TECHNICIAN
    )

    # Create sensors based on account type and PV configuration
    entities: list[
        EatonXStorageSensor
        | EatonXStorageNotificationsSensor
        | EatonXStorageLatestNotificationSensor
        | EatonXStorageInverterInfoSensor
        | EatonXStorageBmsInfoSensor
        | EatonXStorageDeviceInfoSensor
        | EatonXStorageTechnicalInfoSensor
    ] = []
    for key, description in SENSOR_TYPES.items():
        # Skip PV-related sensors if has_pv is False
        if description.get("pv_related", False) and not has_pv:
            continue

        # Skip technician-only sensors for customer accounts
        if key in TECHNICIAN_ONLY_SENSORS and not is_technician:
            continue

        entities.append(EatonXStorageSensor(coordinator, key, description))

    # Add the notifications array sensor
    entities.append(EatonXStorageNotificationsSensor(coordinator))
    entities.append(EatonXStorageLatestNotificationSensor(coordinator))

    # Static identity fields grouped into a few sensors instead of one each. Home
    # Assistant normally wants a separate entity per value rather than attributes,
    # but these never change, so the recorder stores each attribute set once. The
    # same fields remain available as individual sensors, disabled by default.
    entities.append(EatonXStorageInverterInfoSensor(coordinator, has_pv))
    entities.append(EatonXStorageBmsInfoSensor(coordinator))
    entities.append(EatonXStorageDeviceInfoSensor(coordinator))
    if is_technician:
        entities.append(EatonXStorageTechnicalInfoSensor(coordinator))

    async_add_entities(entities)


class EatonXStorageNotificationsSensor(EatonEntity, SensorEntity):
    """Sensor for displaying notifications array."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "notifications"
    _unrecorded_attributes = frozenset({"notifications", "start", "size"})

    def __init__(self, coordinator: EatonXstorageHomeCoordinator) -> None:
        """Initialize the notifications sensor."""
        super().__init__(coordinator)
        # Scope unique ID to config entry for multi-device support
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_notifications"

    def _notifications(self) -> dict[str, Any]:
        """Return the notifications section of the coordinator data."""
        return (self.coordinator.data or {}).get("notifications", {})

    @property
    def native_value(self) -> int:
        """Return the total number of notifications as the state."""
        return self._notifications().get("total", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return notifications as attributes."""
        notifications_data = self._notifications()
        return {
            "notifications": [
                {
                    "alert_id": notification.get("alertId"),
                    "level": notification.get("level"),
                    "type": notification.get("type"),
                    "sub_type": notification.get("subType"),
                    "status": notification.get("status"),
                    "created_at": _notification_time(notification.get("createdAt")),
                    "updated_at": _notification_time(notification.get("updatedAt")),
                }
                for notification in _notification_results(self.coordinator.data or {})
            ],
            "total": notifications_data.get("total", 0),
            "start": notifications_data.get("start", 0),
            "size": notifications_data.get("size", 0),
        }


class EatonXStorageLatestNotificationSensor(EatonEntity, SensorEntity):
    """Sensor exposing the most recent notification's type as its state."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "latest_notification"

    def __init__(self, coordinator: EatonXstorageHomeCoordinator) -> None:
        """Initialize the latest notification sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_latest_notification"
        )

    def _latest_notification(self) -> dict[str, Any] | None:
        """Return the most recent notification, if any."""
        results = _notification_results(self.coordinator.data or {})
        return results[0] if results else None

    @property
    def native_value(self) -> str | None:
        """Return the most recent notification's description as the state."""
        notification = self._latest_notification()
        if not notification:
            return None
        sub_type = notification.get("subType") or notification.get("type")
        if not sub_type:
            return None
        mapped = NOTIFICATION_SUBTYPE_MAP.get(sub_type)
        return mapped["description"] if mapped else sub_type

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the remaining notification details as attributes."""
        notification = self._latest_notification()
        if not notification:
            return None
        sub_type = notification.get("subType")
        mapped = NOTIFICATION_SUBTYPE_MAP.get(sub_type or "", {})
        return {
            "raw_sub_type": sub_type,
            "remedy": mapped.get("remedy"),
            "alert_id": notification.get("alertId"),
            "level": notification.get("level"),
            "type": notification.get("type"),
            "status": notification.get("status"),
            "created_at": _notification_time(notification.get("createdAt")),
            "updated_at": _notification_time(notification.get("updatedAt")),
        }


class EatonXStorageInverterInfoSensor(EatonEntity, SensorEntity):
    """Sensor grouping static inverter identity fields as attributes."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "inverter_info"
    _unrecorded_attributes = frozenset({"va_rating", "nominal_vpv"})

    def __init__(self, coordinator: EatonXstorageHomeCoordinator, has_pv: bool) -> None:
        """Initialize the inverter info sensor."""
        super().__init__(coordinator)
        self._has_pv = has_pv
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_inverter_info"

    @property
    def native_value(self) -> str | None:
        """Return the inverter firmware version as the state."""
        device = (self.coordinator.data or {}).get("device", {})
        return device.get("inverterFirmwareVersion")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the remaining static inverter fields as attributes."""
        device = (self.coordinator.data or {}).get("device", {})
        attributes = {"va_rating": device.get("inverterVaRating")}
        if self._has_pv:
            attributes["nominal_vpv"] = device.get("inverterNominalVpv")
        return attributes


class EatonXStorageBmsInfoSensor(EatonEntity, SensorEntity):
    """Sensor grouping static BMS identity fields as attributes."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "bms_info"
    _unrecorded_attributes = frozenset({"serial_number", "capacity_kwh"})

    def __init__(self, coordinator: EatonXstorageHomeCoordinator) -> None:
        """Initialize the BMS info sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_bms_info"

    @property
    def native_value(self) -> str | None:
        """Return the BMS model as the state."""
        device = (self.coordinator.data or {}).get("device", {})
        return device.get("bmsModel")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the remaining static BMS fields as attributes."""
        device = (self.coordinator.data or {}).get("device", {})
        return {
            "serial_number": device.get("bmsSerialNumber"),
            "capacity_kwh": device.get("bmsCapacity"),
        }


class EatonXStorageDeviceInfoSensor(EatonEntity, SensorEntity):
    """Sensor grouping static device/network identity fields as attributes."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "device_info"
    _unrecorded_attributes = frozenset({"local_portal_remote_id", "timezone"})

    def __init__(self, coordinator: EatonXstorageHomeCoordinator) -> None:
        """Initialize the device info sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_device_info"

    @property
    def native_value(self) -> str | None:
        """Return the bundle version as the state."""
        device = (self.coordinator.data or {}).get("device", {})
        return device.get("bundleVersion")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the remaining static device fields as attributes."""
        device = (self.coordinator.data or {}).get("device", {})
        return {
            "local_portal_remote_id": device.get("localPortalRemoteId"),
            "timezone": (device.get("timezone") or {}).get("name"),
        }


class EatonXStorageTechnicalInfoSensor(EatonEntity, SensorEntity):
    """Sensor grouping static technician-only identity fields as attributes."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "technical_info"
    _unrecorded_attributes = frozenset(
        {"inverter_power_rating", "bootloader_version", "system_ram_total_mib"}
    )

    def __init__(self, coordinator: EatonXstorageHomeCoordinator) -> None:
        """Initialize the technical info sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_technical_info"

    @property
    def native_value(self) -> str | None:
        """Return the grid code as the state."""
        technical_status = (self.coordinator.data or {}).get("technical_status", {})
        return technical_status.get("gridCode")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the remaining static technical fields as attributes."""
        technical_status = (self.coordinator.data or {}).get("technical_status", {})
        maintenance_diagnostics = (self.coordinator.data or {}).get(
            "maintenance_diagnostics", {}
        )
        ram_total = maintenance_diagnostics.get("ramUsage", {}).get("total")
        return {
            "inverter_power_rating": technical_status.get("inverterPowerRating"),
            "bootloader_version": technical_status.get("invBootloaderVersion"),
            "system_ram_total_mib": (
                round(ram_total / 1024 / 1024, 2) if ram_total is not None else None
            ),
        }


class EatonXStorageSensor(EatonEntity, SensorEntity):
    """Eaton xStorage Home sensor entity."""

    def __init__(
        self,
        coordinator: EatonXstorageHomeCoordinator,
        key: str,
        description: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        # Be robust to missing fields in description
        self._attr_translation_key = _translation_key_from_key(self._key)
        self._attr_native_unit_of_measurement = description.get("unit")
        self._attr_device_class = description.get("device_class")
        self._attr_entity_category = description.get("entity_category")
        self._attr_entity_registry_enabled_default = not description.get(
            "disabled_by_default", False
        )
        self._accuracy_warning = description.get("accuracy_warning", False)
        # Ensure per-entry unique IDs to avoid collisions across multiple devices
        self._attr_unique_id = sensor_unique_id(coordinator.config_entry.entry_id, key)

        # Apply icon from description if provided
        if description.get("icon"):
            self._attr_icon = description["icon"]

        # An explicit state_class wins, including an explicit None for setpoints
        # and static ratings that would otherwise be recorded as statistics.
        device_class = description["device_class"]
        if "state_class" in description:
            state_class = description["state_class"]
        elif device_class is not None:
            state_class = DEVICE_CLASS_STATE_CLASSES.get(device_class)
        else:
            state_class = None
        self._attr_state_class = state_class
        self._attr_suggested_display_precision = _display_precision(
            key, description, device_class
        )

        # Declaring any of these commits the sensor to a numeric state.
        self._numeric = any((description.get("unit"), state_class, device_class))

    @property
    def native_value(self) -> str | int | float | None:
        """Return the current value of the sensor."""
        data = self.coordinator.data or {}

        if self._key == CELL_VOLTAGE_DELTA_KEY:
            return _cell_voltage_delta(data.get("technical_status", {}))

        if self._key == CURRENT_MODE_COMMAND_KEY:
            value = resolve_mode_command(data.get("status", {}).get("currentMode", {}))
        else:
            value = _value_at(data, self._key)

        if self._key == BMS_FAULT_CODE_KEY:
            return _format_fault_codes(value)

        if value is None:
            return None

        if self._numeric and isinstance(value, str) and not _is_number(value):
            # The device answers "n/a" for readings it cannot take. Home
            # Assistant refuses to add a numeric sensor holding that, so the
            # entity would never appear at all.
            _LOGGER.debug(
                "Sensor %s returned the non-numeric reading %r", self._key, value
            )
            return None

        if (
            self._key in CELL_VOLTAGE_KEYS
            and isinstance(value, (int, float))
            and value < MIN_CELL_VOLTAGE_MV
        ):
            _LOGGER.debug(
                "Cell voltage %s below %smV, treating as a read error: %smV",
                self._key,
                MIN_CELL_VOLTAGE_MV,
                value,
            )
            return None

        if (
            self._key in ZERO_IS_INVALID_KEYS
            and isinstance(value, (int, float))
            and value == 0
        ):
            _LOGGER.debug("Sensor %s returned invalid value 0 - ignoring", self._key)
            return None

        if (labels := VALUE_MAPS.get(self._key)) is not None and isinstance(value, str):
            return labels.get(value, value)

        if self._attr_device_class is SensorDeviceClass.TEMPERATURE and isinstance(
            value, (int, float)
        ):
            return round(value, 1)

        if self._key.endswith(("startTime", "endTime")) and _is_device_time(value):
            return _format_device_time(value) or value

        if "ramUsage" in self._key and isinstance(value, (int, float)):
            return round(value / 1024 / 1024, 2)

        if "cpuUsage.used" in self._key and isinstance(value, (int, float)):
            return round(value, 2)

        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes for entities with accuracy warnings."""
        if self._key == BMS_FAULT_CODE_KEY:
            technical_status = (self.coordinator.data or {}).get("technical_status", {})
            codes = technical_status.get("bmsFaultCode")
            return {"fault_codes": codes if isinstance(codes, list) else []}
        if self._accuracy_warning:
            return {
                "accuracy_warning": POWER_ACCURACY_WARNING,
                "measurement_note": "Values typically 10%-30% higher than actual",
            }
        return None
