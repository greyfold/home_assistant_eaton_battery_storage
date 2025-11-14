"""Number platform constants for Eaton Battery Storage."""

from __future__ import annotations

from typing import TypedDict

# Number entity keys
CHARGE_DURATION = "charge_duration"
CHARGE_END_SOC = "charge_end_soc"
CHARGE_POWER = "charge_power"
CHARGE_POWER_WATT = "charge_power_watt"
DISCHARGE_DURATION = "discharge_duration"
DISCHARGE_END_SOC = "discharge_end_soc"
DISCHARGE_POWER = "discharge_power"
DISCHARGE_POWER_WATT = "discharge_power_watt"
RUN_DURATION = "run_duration"


class NumberEntityDefinition(TypedDict):
    """Type definition for number entity configuration."""

    key: str
    name: str
    min: int
    max: int
    step: int
    unit: str
    device_class: str


NUMBER_ENTITIES: list[NumberEntityDefinition] = [
    {
        "key": CHARGE_DURATION,
        "name": "Charge Duration",
        "min": 1,
        "max": 12,
        "step": 1,
        "unit": "h",
        "device_class": "duration",
        "default": 1,
    },
    {
        "key": CHARGE_END_SOC,
        "name": "Charge Target SOC",
        "min": 0,
        "max": 100,
        "step": 1,
        "unit": "%",
        "device_class": "battery",
        "default": 80,
    },
    {
        "key": CHARGE_POWER,
        "name": "Charge Power (%)",
        "min": 5,
        "max": 100,
        "step": 1,
        "unit": "%",
        "device_class": "power",
        "default": 20,
    },
    {
        "key": CHARGE_POWER_WATT,
        "name": "Charge Power (Watt)",
        "min": 180,
        "max": 3600,
        "step": 1,
        "unit": "W",
        "device_class": "power",
        # No default for watt, will be set by percent
    },
    {
        "key": DISCHARGE_DURATION,
        "name": "Discharge Duration",
        "min": 1,
        "max": 12,
        "step": 1,
        "unit": "h",
        "device_class": "duration",
        "default": 1,
    },
    {
        "key": DISCHARGE_END_SOC,
        "name": "Discharge Target SOC",
        "min": 0,
        "max": 100,
        "step": 1,
        "unit": "%",
        "device_class": "battery",
        "default": 20,
    },
    {
        "key": DISCHARGE_POWER,
        "name": "Discharge Power (%)",
        "min": 5,
        "max": 100,
        "step": 1,
        "unit": "%",
        "device_class": "power",
        "default": 20,
    },
    {
        "key": DISCHARGE_POWER_WATT,
        "name": "Discharge Power (Watt)",
        "min": 180,
        "max": 3600,
        "step": 1,
        "unit": "W",
        "device_class": "power",
        # No default for watt, will be set by percent
    },
    {
        "key": RUN_DURATION,
        "name": "Run Duration",
        "min": 1,
        "max": 12,
        "step": 1,
        "unit": "h",
        "device_class": "duration",
        "default": 1,
    },
]
