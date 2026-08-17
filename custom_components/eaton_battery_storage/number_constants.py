"""Number platform constants for Eaton Battery Storage."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from homeassistant.components.number import NumberDeviceClass
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTime

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
    translation_key: str
    min: int
    max: int
    step: int
    unit: str
    device_class: NumberDeviceClass | None
    default: NotRequired[int]


NUMBER_ENTITIES: list[NumberEntityDefinition] = [
    {
        "key": CHARGE_DURATION,
        "translation_key": "charge_duration",
        "min": 1,
        "max": 12,
        "step": 1,
        "unit": UnitOfTime.HOURS,
        "device_class": NumberDeviceClass.DURATION,
        "default": 1,
    },
    {
        "key": CHARGE_END_SOC,
        "translation_key": "charge_end_soc",
        "min": 0,
        "max": 100,
        "step": 1,
        "unit": PERCENTAGE,
        "device_class": NumberDeviceClass.BATTERY,
        "default": 80,
    },
    {
        "key": CHARGE_POWER,
        "translation_key": "charge_power",
        "min": 5,
        "max": 100,
        "step": 1,
        "unit": PERCENTAGE,
        # A share of the inverter rating, which no power device class accepts.
        "device_class": None,
        "default": 20,
    },
    {
        "key": CHARGE_POWER_WATT,
        "translation_key": "charge_power_watt",
        # Baseline for a 3.6 kW inverter; the platform replaces these bounds
        # with the rating the device reports (the range spans 3.6 kW to 6 kW).
        "min": 180,
        "max": 3600,
        "step": 1,
        "unit": UnitOfPower.WATT,
        "device_class": NumberDeviceClass.POWER,
        # No default for watt, will be set by percent
    },
    {
        "key": DISCHARGE_DURATION,
        "translation_key": "discharge_duration",
        "min": 1,
        "max": 12,
        "step": 1,
        "unit": UnitOfTime.HOURS,
        "device_class": NumberDeviceClass.DURATION,
        "default": 1,
    },
    {
        "key": DISCHARGE_END_SOC,
        "translation_key": "discharge_end_soc",
        "min": 0,
        "max": 100,
        "step": 1,
        "unit": PERCENTAGE,
        "device_class": NumberDeviceClass.BATTERY,
        "default": 20,
    },
    {
        "key": DISCHARGE_POWER,
        "translation_key": "discharge_power",
        "min": 5,
        "max": 100,
        "step": 1,
        "unit": PERCENTAGE,
        "device_class": None,
        "default": 20,
    },
    {
        "key": DISCHARGE_POWER_WATT,
        "translation_key": "discharge_power_watt",
        # Baseline for a 3.6 kW inverter; the platform replaces these bounds
        # with the rating the device reports (the range spans 3.6 kW to 6 kW).
        "min": 180,
        "max": 3600,
        "step": 1,
        "unit": UnitOfPower.WATT,
        "device_class": NumberDeviceClass.POWER,
        # No default for watt, will be set by percent
    },
    {
        "key": RUN_DURATION,
        "translation_key": "run_duration",
        "min": 1,
        "max": 12,
        "step": 1,
        "unit": UnitOfTime.HOURS,
        "device_class": NumberDeviceClass.DURATION,
        "default": 1,
    },
]
