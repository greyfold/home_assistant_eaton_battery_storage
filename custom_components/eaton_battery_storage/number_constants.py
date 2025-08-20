# Number platform constants for Eaton Battery Storage

CHARGE_END_SOC = "charge_end_soc"
CHARGE_POWER = "charge_power"
CHARGE_POWER_WATT = "charge_power_watt"
CHARGE_DURATION = "charge_duration"
DISCHARGE_END_SOC = "discharge_end_soc"
DISCHARGE_POWER = "discharge_power"
DISCHARGE_POWER_WATT = "discharge_power_watt"
DISCHARGE_DURATION = "discharge_duration"
RUN_DURATION = "run_duration"

NUMBER_ENTITIES = [
    {"key": CHARGE_END_SOC, "name": "Chg SOC", "min": 0, "max": 100, "step": 1, "unit": "%", "device_class": "battery"},
    {"key": CHARGE_POWER, "name": "Chg Pwr (%)", "min": 5, "max": 100, "step": 1, "unit": "%", "device_class": "power"},
    {"key": CHARGE_POWER_WATT, "name": "Chg Pwr (W)", "min": 180, "max": 3600, "step": 1, "unit": "W", "device_class": "power"},
    {"key": CHARGE_DURATION, "name": "Chg Dur", "min": 1, "max": 12, "step": 1, "unit": "h", "device_class": "duration"},
    {"key": DISCHARGE_END_SOC, "name": "Dischg SOC", "min": 0, "max": 100, "step": 1, "unit": "%", "device_class": "battery"},
    {"key": DISCHARGE_POWER, "name": "Dischg Pwr (%)", "min": 5, "max": 100, "step": 1, "unit": "%", "device_class": "power"},
    {"key": DISCHARGE_POWER_WATT, "name": "Dischg Pwr (W)", "min": 180, "max": 3600, "step": 1, "unit": "W", "device_class": "power"},
    {"key": DISCHARGE_DURATION, "name": "Dischg Dur", "min": 1, "max": 12, "step": 1, "unit": "h", "device_class": "duration"},
    {"key": RUN_DURATION, "name": "Run Dur", "min": 1, "max": 12, "step": 1, "unit": "h", "device_class": "duration"},
]
