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

> ⚠️ Inverter Power Measurement Accuracy: The built-in inverter energy monitoring has poor accuracy and typically reports power output/consumption values approximately 10%-30% higher than actual values. Do not rely on consumption and production metrics from the inverter for accurate energy calculations. This affects all power-related sensors including grid power, load values, PV production, and consumption metrics.

## Installation

### HACS (Recommended)

1. Install HACS following the [installation guide](https://hacs.xyz/docs/use/download/download/).
2. Open Home Assistant and click "HACS" in the sidebar.
3. In HACS, click "Integrations", then click the three dots (⋯) in the top-right corner.
4. Select "Custom repositories"
5. Add this repository URL.
6. Select "Integration" as the category
7. Click "Add"
8. Click "Install"
9. Restart Home Assistant

---

## Pre-requisite

- A Home Assistant Gateway
- An Eaton xStorage Battery Storage System
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

[Read the documentation ➜](https://greyfold.github.io/home_assistant_eaton_battery_storage/)

## Entities provided by this integration

> **Note:** This integration provides different entities based on your account type (Customer vs Technician) and configuration (PV enabled). See [Account Type Support](ACCOUNT_TYPE_SUPPORT.md) for more details.

### Core Entities (Available to all account types)

| Type          | Name                            | Unit | Default  | Comment                                                  |
| ------------- | ------------------------------- | ---- | -------- | -------------------------------------------------------- |
| sensor        | Battery State of Charge         | %    | Enabled  | Current battery charge level                             |
| sensor        | Battery Status                  | -    | Enabled  | Charging/Discharging/Idle state                          |
| sensor        | Battery Power                   | W    | Enabled  | Positive=discharge, negative=charge                      |
| sensor        | Battery Backup Level            | %    | Disabled | Minimum SOC reserved for backup power                    |
| sensor        | Grid Power                      | W    | Enabled  | Grid consumption/injection (⚠️ accuracy warning applies) |
| sensor        | Grid Role                       | -    | Enabled  | Supplying/Consuming/None                                 |
| sensor        | Operation Mode                  | -    | Enabled  | Current operation mode                                   |
| sensor        | Self Consumption                | %    | Enabled  | Percentage of PV energy used directly                    |
| sensor        | Self Sufficiency                | %    | Enabled  | Percentage of energy needs met by PV                     |
| sensor        | Critical Load Role              | -    | Enabled  | Critical loads status                                    |
| sensor        | Critical Load Value             | W    | Enabled  | Power to critical loads                                  |
| sensor        | Non-Critical Load Role          | -    | Enabled  | Non-critical loads status                                |
| sensor        | Non-Critical Load Value         | W    | Enabled  | Power to non-critical loads                              |
| sensor        | Energy Saving Mode Enabled      | -    | Enabled  | Energy saving mode configuration                         |
| sensor        | Energy Saving Mode Activated    | -    | Enabled  | Energy saving mode active status                         |
| sensor        | Current Mode Command            | -    | Enabled  | Active operation mode command                            |
| sensor        | Current Mode Duration           | h    | Enabled  | Duration of current mode                                 |
| sensor        | Current Mode Type               | -    | Enabled  | Manual or Scheduled                                      |
| sensor        | Current Mode Recurrence         | -    | Enabled  | Daily/Weekly/Manual Event                                |
| sensor        | Current Mode Power              | %    | Enabled  | Power setting for current mode                           |
| sensor        | Current Mode SOC                | %    | Enabled  | Target SOC for current mode                              |
| sensor        | Current Mode Action             | -    | Enabled  | Charge/Discharge action                                  |
| sensor        | Current Mode Start Time         | -    | Enabled  | Start time of current mode                               |
| sensor        | Current Mode End Time           | -    | Enabled  | End time of current mode                                 |
| sensor        | Today's Grid Consumption        | kWh  | Disabled | Grid energy consumed today                               |
| sensor        | Today's Self Consumption        | %    | Disabled | Self-consumption percentage today                        |
| sensor        | Today's Self Sufficiency        | %    | Disabled | Self-sufficiency percentage today                        |
| sensor        | 30 Days Grid Consumption        | kWh  | Disabled | Grid consumption last 30 days                            |
| sensor        | 30 Days Self Consumption        | %    | Disabled | Self-consumption last 30 days                            |
| sensor        | 30 Days Self Sufficiency        | %    | Disabled | Self-sufficiency last 30 days                            |
| sensor        | Total Notifications Count       | -    | Enabled  | Number of system notifications                           |
| sensor        | Unread Notifications Count      | -    | Enabled  | Number of unread notifications                           |
| sensor        | BMS Capacity                    | kWh  | Enabled  | Total battery capacity                                   |
| sensor        | BMS Firmware Version            | -    | Enabled  | Battery management system version                        |
| sensor        | BMS Model                       | -    | Enabled  | Battery model designation                                |
| sensor        | BMS Serial Number               | -    | Enabled  | Battery serial number                                    |
| sensor        | Firmware Version                | -    | Enabled  | System firmware version                                  |
| sensor        | Inverter Firmware Version       | -    | Enabled  | Inverter firmware version                                |
| sensor        | Inverter Manufacturer           | -    | Enabled  | Inverter manufacturer                                    |
| sensor        | Inverter Model Name             | -    | Enabled  | Inverter model                                           |
| sensor        | Inverter Serial Number          | -    | Enabled  | Inverter serial number                                   |
| sensor        | Inverter VA Rating              | VA   | Enabled  | Inverter power rating                                    |
| sensor        | Bundle Version                  | -    | Enabled  | Software bundle version                                  |
| sensor        | Device Timezone                 | -    | Enabled  | System timezone setting                                  |
| sensor        | DNS Server                      | -    | Disabled | DNS server address                                       |
| sensor        | House Consumption Threshold     | W    | Enabled  | Energy saving mode threshold                             |
| sensor        | Local Portal Remote ID          | -    | Enabled  | Remote portal identifier                                 |
| binary_sensor | Battery Charging                | -    | Enabled  | True when battery is charging                            |
| binary_sensor | Battery Discharging             | -    | Enabled  | True when battery is discharging                         |
| binary_sensor | Inverter Power State            | -    | Enabled  | Inverter on/off state                                    |
| binary_sensor | Has Unread Notifications        | -    | Enabled  | True if unread notifications exist                       |
| switch        | Inverter Power                  | -    | Enabled  | Control inverter power on/off                            |
| switch        | Energy Saving Mode              | -    | Enabled  | Enable/disable energy saving mode                        |
| select        | Default Operation Mode          | -    | Enabled  | Set default operation mode                               |
| select        | Current Operation Mode          | -    | Enabled  | Change current operation mode                            |
| number        | Charge Target SOC               | %    | Enabled  | Target SOC for manual charge                             |
| number        | Charge Power (%)                | %    | Enabled  | Charging power percentage (5-100%)                       |
| number        | Charge Power (Watts)            | W    | Enabled  | Charging power in watts                                  |
| number        | Charge Duration                 | h    | Enabled  | Duration for manual charge (1-12h)                       |
| number        | Discharge Target SOC            | %    | Enabled  | Target SOC for manual discharge                          |
| number        | Discharge Power (%)             | %    | Enabled  | Discharge power percentage (5-100%)                      |
| number        | Discharge Power (Watts)         | W    | Enabled  | Discharge power in watts                                 |
| number        | Discharge Duration              | h    | Enabled  | Duration for manual discharge (1-12h)                    |
| number        | Run Duration                    | h    | Enabled  | Duration for basic mode (1-12h)                          |
| number        | Set House Consumption Threshold | W    | Enabled  | Configure energy saving threshold (300-1000W)            |
| number        | Set Battery Backup Level        | %    | Enabled  | Configure minimum backup SOC (0-100%)                    |
| button        | Mark All Notifications Read     | -    | Enabled  | Mark all notifications as read                           |
| button        | Stop Current Operation          | -    | Enabled  | Stop current manual operation                            |
| event         | Notification Event              | -    | Enabled  | Fires when new notifications are detected                |

### PV-Related Entities (Only created when PV is enabled during setup)

| Type   | Name                   | Unit | Default | Comment                                            |
| ------ | ---------------------- | ---- | ------- | -------------------------------------------------- |
| sensor | AC PV Role             | -    | Enabled | AC-coupled PV status                               |
| sensor | AC PV Value            | W    | Enabled | AC-coupled PV power (⚠️ accuracy warning applies)  |
| sensor | DC PV Role             | -    | Enabled | DC-coupled PV status                               |
| sensor | DC PV Value            | W    | Enabled | DC-coupled PV power (⚠️ accuracy warning applies)  |
| sensor | Inverter Nominal VPV   | V    | Enabled | Nominal PV voltage                                 |
| sensor | Today's PV Production  | kWh  | Enabled | PV energy generated today                          |
| sensor | 30 Days PV Production  | kWh  | Enabled | PV energy generated last 30 days                   |
| sensor | PV1 Voltage            | V    | Enabled | PV string 1 voltage (technician account required)  |
| sensor | PV1 Current            | A    | Enabled | PV string 1 current (technician account required)  |
| sensor | PV2 Voltage            | V    | Enabled | PV string 2 voltage (technician account required)  |
| sensor | PV2 Current            | A    | Enabled | PV string 2 current (technician account required)  |
| sensor | DC Current Injection R | mA   | Enabled | DC injection R phase (technician account required) |
| sensor | DC Current Injection S | mA   | Enabled | DC injection S phase (technician account required) |
| sensor | DC Current Injection T | mA   | Enabled | DC injection T phase (technician account required) |

### Technician Account Only Entities (Require technician login credentials)

| Type   | Name                            | Unit | Default | Comment                                     |
| ------ | ------------------------------- | ---- | ------- | ------------------------------------------- |
| sensor | Grid Voltage                    | V    | Enabled | AC grid voltage                             |
| sensor | Grid Frequency                  | Hz   | Enabled | AC grid frequency                           |
| sensor | Grid Code                       | -    | Enabled | Grid connection standard                    |
| sensor | Current To Grid                 | A    | Enabled | Current flow to/from grid                   |
| sensor | Inverter Power                  | W    | Enabled | Inverter power output                       |
| sensor | Inverter Temperature            | °C   | Enabled | Inverter operating temperature              |
| sensor | Bus Voltage                     | V    | Enabled | DC bus voltage                              |
| sensor | Technical Inverter Model        | -    | Enabled | Detailed inverter model                     |
| sensor | Technical Inverter Power Rating | W    | Enabled | Inverter power rating                       |
| sensor | Inverter Bootloader Version     | -    | Enabled | Inverter bootloader version                 |
| sensor | TIDA Protocol Version           | -    | Enabled | TIDA protocol version                       |
| sensor | Technical Operation Mode        | -    | Enabled | Detailed operation mode                     |
| sensor | BMS Voltage                     | V    | Enabled | Battery pack voltage                        |
| sensor | BMS Current                     | A    | Enabled | Battery pack current                        |
| sensor | BMS Temperature                 | °C   | Enabled | Battery temperature                         |
| sensor | BMS Average Temperature         | °C   | Enabled | Average battery cell temperature            |
| sensor | BMS Max Temperature             | °C   | Enabled | Maximum battery cell temperature            |
| sensor | BMS Min Temperature             | °C   | Enabled | Minimum battery cell temperature            |
| sensor | BMS State                       | -    | Enabled | Battery state (charging/discharging/idle)   |
| sensor | Technical BMS State of Charge   | %    | Enabled | Technical SOC reading                       |
| sensor | BMS Total Charge                | kWh  | Enabled | Lifetime energy charged                     |
| sensor | BMS Total Discharge             | kWh  | Enabled | Lifetime energy discharged                  |
| sensor | BMS Highest Cell Voltage        | mV   | Enabled | Highest individual cell voltage             |
| sensor | BMS Lowest Cell Voltage         | mV   | Enabled | Lowest individual cell voltage              |
| sensor | BMS Cell Voltage Delta          | mV   | Enabled | Difference between highest and lowest cells |
| sensor | BMS Fault Code                  | -    | Enabled | Battery fault code (if any)                 |
| sensor | System CPU Usage                | %    | Enabled | Controller CPU utilization                  |
| sensor | System RAM Total                | MB   | Enabled | Total system memory                         |
| sensor | System RAM Used                 | MB   | Enabled | Used system memory                          |

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
