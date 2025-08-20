# Constants
DOMAIN = "eaton_battery_storage"

# Accuracy warning message for power measurements
POWER_ACCURACY_WARNING = (
    "WARNING: Inverter power measurements are typically 30% higher than actual values. "
    "Do not rely on this data for accurate energy calculations."
)

# Current Mode Command mapping for human-readable display
CURRENT_MODE_COMMAND_MAP = {
    "SET_CHARGE": "Charge",
    "SET_BASIC_MODE": "Basic Mode",
    "SET_DISCHARGE": "Discharge", 
    "SET_MAXIMIZE_AUTO_CONSUMPTION": "Maximize Auto Consumption",
    "SET_VARIABLE_GRID_INJECTION": "Variable Grid Injection",
    "SET_FREQUENCY_REGULATION": "Frequency Regulation",
    "SET_PEAK_SHAVING": "Peak Shaving"
}

# Current Mode Action mapping for human-readable display
CURRENT_MODE_ACTION_MAP = {
    "ACTION_CHARGE": "Charge",
    "ACTION_DISCHARGE": "Discharge"
}

# Current Mode Type mapping for human-readable display  
CURRENT_MODE_TYPE_MAP = {
    "MANUAL": "Manual",
    "SCHEDULE": "Scheduled"
}

# Current Mode Recurrence mapping for human-readable display
CURRENT_MODE_RECURRENCE_MAP = {
    "MANUAL_EVENT": "Manual Event",
    "DAILY": "Daily",
    "WEEKLY": "Weekly"
}

# Operation Mode mapping for human-readable display
OPERATION_MODE_MAP = {
    "CHARGING": "Charging",
    "DISCHARGING": "Discharging",
    "IDLE": "Idle",
    "STANDBY": "Standby",
    "MAXIMIZE_AUTO_CONSUMPTION": "Maximize Auto Consumption",
    # Additional possible values that might appear in technical status
    "BAT_CHARGING": "Charging",
    "BAT_DISCHARGING": "Discharging", 
    "BAT_IDLE": "Idle",
    "UNKNOWN": "Unknown",
    "OFF": "Off",
    "FAULT": "Fault"
}

# BMS State mapping for human-readable display
BMS_STATE_MAP = {
    "BAT_CHARGING": "Charging",
    "BAT_DISCHARGING": "Discharging", 
    "BAT_IDLE": "Idle"
}
