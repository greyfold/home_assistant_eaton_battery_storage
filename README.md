# Home Assistant Eaton xStorage Home Battery Integration

A Home Assistant custom component for integrating Eaton xStorage Home battery systems.

## Credits

- Original author and maintainer: [greyfold](https://github.com/greyfold)
- Major enhancements and API documentation: [genestealer](https://github.com/genestealer)

## Features

- Real-time monitoring of battery status and energy flow
- Control charging/discharging modes
- Monitor PV production and grid consumption
- Energy saving mode configuration
- Notifications and alerts management
- Technical status monitoring

## API Documentation

This integration is based on the reverse-engineered REST API of the Eaton xStorage Home system done by @genestealer. For detailed API documentation including all endpoints, authentication, and response formats, see:

**xStorage Home REST API Unofficial Documentation:** <https://github.com/genestealer/eaton-xstorage-home-api-doc/>

## Important Accuracy Warning

> ⚠️ Inverter Power Measurement Accuracy: The built-in inverter energy monitoring has poor accuracy and typically reports power output/consumption values approximately 30% higher than actual values. Do not rely on consumption and production metrics from the inverter for accurate energy calculations. This affects all power-related sensors including grid power, load values, PV production, and consumption metrics.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/greyfold/home_assistant_eaton_battery_storage`
6. Select "Integration" as the category
7. Click "Add"
8. Click "Install"
9. Restart Home Assistant

---

## Pre-requisite

- A Home Assistant Gateway
- An Eaton xStorage Home (Tiida)
- A local network
- A GitHub account

Please make sure to setup all your devices on the same network.

### Useful links

- [Get started with home assistant](https://www.home-assistant.io/installation/)
- [xStorage Home User Manual](https://www.eaton.com/content/dam/eaton/products/energy-storage/xstorage-home/en-gb/eaton-xstorage-home-user-interface-manual-en-gb.pdf)

## Documentation

The available documentation provides 4 steps to setup an Eaton xStorage Hybrid unit with a Home Assistant device through local APIs.

- xStorage Home setup
- Setup Home Assistant
- HACS installation and configuration
- Eaton Battery Storage installation and configuration

[Read the documentation ➜](https://genestealer.github.io/home_assistant_eaton_battery_storage/)

## Entities provided by this integration

| Type | Key | Name | Unit |
|------|-----|------|------|
| sensor | `currentMode.command` | Current Mode Command | - |
| sensor | `energyFlow.acPvRole` | AC PV Role | - |
| sensor | `energyFlow.acPvValue` | AC PV Value | W |
| sensor | `energyFlow.batteryBackupLevel` | Battery Backup Level | % |
| sensor | `energyFlow.batteryStatus` | Battery Status | - |
| sensor | `energyFlow.batteryEnergyFlow` | Battery Power | W |
| sensor | `energyFlow.criticalLoadRole` | Critical Load Role | - |
| sensor | `energyFlow.criticalLoadValue` | Critical Load Value | W |
| sensor | `energyFlow.dcPvRole` | DC PV Role | - |
| sensor | `energyFlow.dcPvValue` | DC PV Value | W |
| sensor | `energyFlow.gridRole` | Grid Role | - |
| sensor | `energyFlow.gridValue` | Grid Power | W |
| sensor | `energyFlow.nonCriticalLoadRole` | Non-Critical Load Role | - |
| sensor | `energyFlow.nonCriticalLoadValue` | Non-Critical Load Value | W |
| sensor | `energyFlow.operationMode` | Operation Mode | - |
| sensor | `energyFlow.selfConsumption` | Self Consumption | W |
| sensor | `energyFlow.selfSufficiency` | Self Sufficiency | % |
| sensor | `energyFlow.stateOfCharge` | Battery State of Charge | % |
| sensor | `energyFlow.energySavingModeEnabled` | Energy Saving Mode Enabled | - |
| sensor | `energyFlow.energySavingModeActivated` | Energy Saving Mode Activated | - |
| sensor | `last30daysEnergyFlow.gridConsumption` | 30 Days Grid Consumption | W |
| sensor | `last30daysEnergyFlow.photovoltaicProduction` | 30 Days PV Production | W |
| sensor | `last30daysEnergyFlow.selfConsumption` | 30 Days Self Consumption | % |
| sensor | `last30daysEnergyFlow.selfSufficiency` | 30 Days Self Sufficiency | % |
| sensor | `today.gridConsumption` | Today's Grid Consumption | W |
| sensor | `today.photovoltaicProduction` | Today's PV Production | W |
| sensor | `today.selfConsumption` | Today's Self Consumption | % |
| sensor | `today.selfSufficiency` | Today's Self Sufficiency | % |
| binary_sensor | `status.energyFlow.batteryStatus_charging` | Battery Charging | - |
| binary_sensor | `status.energyFlow.batteryStatus_discharging` | Battery Discharging | - |
| binary_sensor | `device.powerState` | Inverter Power State | - |
| binary_sensor | `notifications.has_unread` | Has Unread Notifications | - |
| switch | - | Inverter Power | - |
| switch | - | Energy Saving Mode | - |
| select | - | Default Operation Mode | - |
| select | - | Current Operation Mode | - |
| number | `charge_end_soc` | Charge end state of charge | % |
| number | `charge_power` | Charge power | % |
| number | `charge_power_watt` | Charge power | W |
| number | `charge_duration` | Charge duration | h |
| number | `discharge_end_soc` | Discharge end state of charge | % |
| number | `discharge_power` | Discharge power | % |
| number | `discharge_power_watt` | Discharge power | W |
| number | `discharge_duration` | Discharge duration | h |
| number | `run_duration` | Run duration | h |
| number | - | Set House Consumption Threshold | W |
| number | - | Set Battery Backup Level | % |
| button | - | Mark All Notifications Read | - |
| button | - | Stop Current Operation | - |

### Notifications sensor

The integration exposes a sensor named "Notifications" (entity_id typically `sensor.notifications`).

- State: the number of notifications currently returned by the inverter
- Attributes: a notifications array with entries containing `alert_id`, `level`, `type`, `sub_type`, `status`, `created_at`, and `updated_at` (plus `total`, `start`, and `size` for pagination)

Example (attributes in Home Assistant):

```yaml
notifications:
	- alert_id: 5d1b55e4-1e3b-403f-86dc-564e5b1a2191
		level: INFO
		type: DEVICES
		sub_type: BATTERY_VOLTAGE_HIGH
		status: NORMAL
		created_at: 1754724228000
		updated_at: 1754724228000
	- alert_id: 84221498-96aa-4e0c-9649-d7a4d71bf5c7
		level: CRITICAL
		type: DEVICES
		sub_type: BATTERY_VOLTAGE_HIGH
		status: READ
		created_at: 1754656076000
		updated_at: 1754692437000
total: 2
start: 0
size: 2
```

## Examples

Example Home Assistant automations are provided in the `examples/` folder:

- `examples/example_home_assistant_automation_meter_emulator.yaml` — publish real-time meter data to the inverter (MQTT) with safety limits and accuracy warning
- `examples/example_home_assistant_automation_octopus_go_intelligent_dispatching.yaml` — smart daytime charging driven by Octopus Intelligent Go dispatch windows
- `examples/example_home_assistant_automation_notifications_event.yaml` — react to new inverter alerts via EventEntity and mark notifications read

These examples use registry `device_id` and `entity_id` values for stability across renames; update them to match your setup and see inline comments for guidance.
