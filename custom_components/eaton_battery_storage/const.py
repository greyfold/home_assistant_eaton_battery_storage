"""Constants for Eaton Battery Storage integration."""

from __future__ import annotations

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
