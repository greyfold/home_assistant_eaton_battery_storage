"""Constants for Eaton Battery Storage integration."""

from __future__ import annotations

# Account type constants
ACCOUNT_TYPE_CUSTOMER = "customer"
ACCOUNT_TYPE_TECHNICIAN = "tech"

# BMS State mapping for human-readable display
BMS_STATE_MAP: dict[str, str] = {
    "BAT_CHARGING": "Charging",
    "BAT_DISCHARGING": "Discharging",
    "BAT_IDLE": "Idle",
}

# Current Mode Action mapping for human-readable display
CURRENT_MODE_ACTION_MAP: dict[str, str] = {
    "ACTION_CHARGE": "Charge",
    "ACTION_DISCHARGE": "Discharge",
}

# Current Mode Command mapping for human-readable display
CURRENT_MODE_COMMAND_MAP: dict[str, str] = {
    "SET_BASIC_MODE": "Basic Mode",
    "SET_CHARGE": "Charge",
    "SET_DISCHARGE": "Discharge",
    "SET_FREQUENCY_REGULATION": "Frequency Regulation",
    "SET_MAXIMIZE_AUTO_CONSUMPTION": "Maximize Auto Consumption",
    "SET_PEAK_SHAVING": "Peak Shaving",
    "SET_VARIABLE_GRID_INJECTION": "Variable Grid Injection",
}

# Current Mode Recurrence mapping for human-readable display
CURRENT_MODE_RECURRENCE_MAP: dict[str, str] = {
    "DAILY": "Daily",
    "MANUAL_EVENT": "Manual Event",
    "WEEKLY": "Weekly",
}

# Current Mode Type mapping for human-readable display
CURRENT_MODE_TYPE_MAP: dict[str, str] = {"MANUAL": "Manual", "SCHEDULE": "Scheduled"}

# Integration domain
DOMAIN = "eaton_battery_storage"

# Operation Mode mapping for human-readable display
OPERATION_MODE_MAP: dict[str, str] = {
    "BAT_CHARGING": "Charging",
    "BAT_DISCHARGING": "Discharging",
    "BAT_IDLE": "Idle",
    "CHARGING": "Charging",
    "DISCHARGING": "Discharging",
    "FAULT": "Fault",
    "IDLE": "Idle",
    "MAXIMIZE_AUTO_CONSUMPTION": "Maximize Auto Consumption",
    "OFF": "Off",
    "STANDBY": "Standby",
    "UNKNOWN": "Unknown",
}

# Accuracy warning message for power measurements
POWER_ACCURACY_WARNING = (
    "WARNING: Inverter power measurements are typically 10%-30% higher than actual values. "
    "Do not rely on this data for accurate energy calculations."
)

# List of sensor keys that require technician account access
TECHNICIAN_ONLY_SENSORS = [
    "technical_status.operationMode",
    "technical_status.gridVoltage",
    "technical_status.gridFrequency",
    "technical_status.currentToGrid",
    "technical_status.inverterPower",
    "technical_status.inverterTemperature",
    "technical_status.busVoltage",
    "technical_status.gridCode",
    "technical_status.dcCurrentInjectionR",
    "technical_status.dcCurrentInjectionS",
    "technical_status.dcCurrentInjectionT",
    "technical_status.inverterModel",
    "technical_status.inverterPowerRating",
    "technical_status.pv1Voltage",
    "technical_status.pv1Current",
    "technical_status.pv2Voltage",
    "technical_status.pv2Current",
    "technical_status.bmsVoltage",
    "technical_status.bmsCurrent",
    "technical_status.bmsTemperature",
    "technical_status.bmsAvgTemperature",
    "technical_status.bmsMaxTemperature",
    "technical_status.bmsMinTemperature",
    "technical_status.bmsTotalCharge",
    "technical_status.bmsTotalDischarge",
    "technical_status.bmsStateOfCharge",
    "technical_status.bmsState",
    "technical_status.bmsFaultCode",
    "technical_status.bmsHighestCellVoltage",
    "technical_status.bmsLowestCellVoltage",
    "technical_status.bmsCellVoltageDelta",  # Calculated from highest/lowest
    "technical_status.tidaProtocolVersion",
    "technical_status.invBootloaderVersion",
    # Maintenance diagnostics sensors (also require technician account)
    "maintenance_diagnostics.ramUsage.total",
    "maintenance_diagnostics.ramUsage.used",
    "maintenance_diagnostics.cpuUsage.used",
]
