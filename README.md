# Home Assistant Eaton Battery Storage Integration

A Home Assistant custom component for integrating Eaton's xStorage Home battery storage system.

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

Responses that the documentation does not cover, and that this integration has
to work around, are recorded in
[docs/device-api-behaviour.md](docs/device-api-behaviour.md).

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

> **Note:** This integration provides different entities based on your account type (Customer vs Technician) and configuration (PV enabled). See [Account Types](#account-types) for more details.

### Core Entities (Available to all account types)

| Type          | Name                            | Unit | Default  | Comment                                                  |
| ------------- | ------------------------------- | ---- | -------- | -------------------------------------------------------- |
| sensor        | Battery State of Charge         | %    | Enabled  | Current battery charge level                             |
| sensor        | Battery Status                  | -    | Enabled  | Charging/Discharging/Idle state                          |
| sensor        | Battery Power                   | W    | Enabled  | Positive=discharge, negative=charge                      |
| sensor        | Battery Backup Level            | %    | Disabled | Minimum SOC reserved for backup power                    |
| sensor        | Grid Power                      | W    | Enabled  | Grid consumption/injection (⚠️ accuracy warning applies) |
| sensor        | Grid Role                       | -    | Enabled  | Producing/Consuming/Disconnected/Idle                                 |
| sensor        | Operation Mode                  | -    | Disabled | Current operation mode (duplicates the Current Operation Mode select) |
| sensor        | Self Consumption                | %    | Enabled  | Percentage of PV energy used directly                    |
| sensor        | Self Sufficiency                | %    | Enabled  | Percentage of energy needs met by PV                     |
| sensor        | Critical Load Role              | -    | Enabled  | Critical loads status                                    |
| sensor        | Critical Load Value             | W    | Enabled  | Power to critical loads                                  |
| sensor        | Non-Critical Load Role          | -    | Enabled  | Non-critical loads status                                |
| sensor        | Non-Critical Load Value         | W    | Enabled  | Power to non-critical loads                              |
| sensor        | Energy Saving Mode Enabled      | -    | Disabled | Duplicates the Energy Saving Mode switch                 |
| sensor        | Energy Saving Mode Activated    | -    | Disabled | Duplicates the Energy Saving Mode Activated binary sensor |
| sensor        | Current Mode Command            | -    | Enabled  | Active operation mode command                            |
| sensor        | Current Mode Duration           | h    | Enabled  | Duration of current mode                                 |
| sensor        | Current Mode Type               | -    | Enabled  | Manual or Scheduled                                      |
| sensor        | Current Mode Recurrence         | -    | Enabled  | Daily/Weekly/Manual Event                                |
| sensor        | Current Mode Power              | %    | Enabled  | Power setting for current mode                           |
| sensor        | Current Mode SOC                | %    | Enabled  | Target SOC for current mode                              |
| sensor        | Current Mode Action             | -    | Enabled  | Charge/Discharge action                                  |
| sensor        | Current Mode Start Time         | -    | Enabled  | Start time of current mode (24-hour `HH:MM`)             |
| sensor        | Current Mode End Time           | -    | Enabled  | End time of current mode (24-hour `HH:MM`)               |
| sensor        | Today's Grid Consumption        | Wh   | Disabled | Grid energy consumed today                               |
| sensor        | Today's Self Consumption        | %    | Disabled | Self-consumption percentage today                        |
| sensor        | Today's Self Sufficiency        | %    | Disabled | Self-sufficiency percentage today                        |
| sensor        | 30 Days Grid Consumption        | Wh   | Disabled | Grid consumption last 30 days                            |
| sensor        | 30 Days Self Consumption        | %    | Disabled | Self-consumption last 30 days                            |
| sensor        | 30 Days Self Sufficiency        | %    | Disabled | Self-sufficiency last 30 days                            |
| sensor        | Total Notifications Count       | -    | Enabled  | Number of system notifications                           |
| sensor        | Unread Notifications Count      | -    | Enabled  | Number of unread notifications                           |
| sensor        | Latest Notification             | -    | Enabled  | Readable description of the most recent notification (see [Notifications sensor](#notifications-sensors)) |
| sensor        | BMS Capacity                    | kWh  | Disabled | Folded into the BMS Info sensor's attributes              |
| sensor        | BMS Firmware Version            | -    | Disabled | Battery management system version (duplicates device `hw_version`) |
| sensor        | BMS Model                       | -    | Disabled | Folded into the BMS Info sensor's attributes              |
| sensor        | BMS Serial Number               | -    | Disabled | Folded into the BMS Info sensor's attributes              |
| sensor        | Firmware Version                | -    | Disabled | Duplicates device `sw_version`                            |
| sensor        | Inverter Firmware Version       | -    | Disabled | Folded into the Inverter Info sensor's state               |
| sensor        | Inverter Manufacturer           | -    | Disabled | Duplicates device manufacturer                             |
| sensor        | Inverter Model Name             | -    | Disabled | Duplicates device `model`                                  |
| sensor        | Inverter Serial Number          | -    | Disabled | Duplicates device `serial_number`                          |
| sensor        | Inverter VA Rating              | VA   | Disabled | Folded into the Inverter Info sensor's attributes           |
| sensor        | Bundle Version                  | -    | Disabled | Folded into the Device Info sensor's state                 |
| sensor        | Device Timezone                 | -    | Disabled | Folded into the Device Info sensor's attributes             |
| sensor        | DNS Server                      | -    | Disabled | DNS server address                                       |
| sensor        | House Consumption Threshold     | W    | Disabled | Duplicates the Set House Consumption Threshold number      |
| sensor        | Local Portal Remote ID          | -    | Disabled | Folded into the Device Info sensor's attributes             |
| sensor        | Inverter Info                   | -    | Enabled  | State = inverter firmware version; attributes: `va_rating`, `nominal_vpv` (PV installs) |
| sensor        | BMS Info                        | -    | Enabled  | State = BMS model; attributes: `serial_number`, `capacity_kwh` |
| sensor        | Device Info                     | -    | Enabled  | State = bundle version; attributes: `local_portal_remote_id`, `timezone` |
| binary_sensor | Battery Charging                | -    | Enabled  | True when battery is charging                            |
| binary_sensor | Battery Discharging             | -    | Enabled  | True when battery is discharging                         |
| binary_sensor | Inverter Power State            | -    | Disabled | Duplicates the Inverter Power switch                       |
| binary_sensor | Energy Saving Mode Activated    | -    | Enabled  | True while energy saving mode is actively reducing consumption |
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
| sensor | Inverter Nominal VPV   | V    | Disabled | Folded into the Inverter Info sensor's attributes (PV installs) |
| sensor | Today's PV Production  | Wh   | Enabled | PV energy generated today                          |
| sensor | 30 Days PV Production  | Wh   | Disabled | PV energy generated last 30 days                   |
| sensor | PV1 Voltage            | V    | Enabled | PV string 1 voltage (technician account required)  |
| sensor | PV1 Current            | A    | Enabled | PV string 1 current (technician account required)  |
| sensor | PV2 Voltage            | V    | Enabled | PV string 2 voltage (technician account required)  |
| sensor | PV2 Current            | A    | Enabled | PV string 2 current (technician account required)  |
| sensor | DC Current Injection R | A    | Enabled | DC injection R phase (technician account required) |
| sensor | DC Current Injection S | A    | Enabled | DC injection S phase (technician account required) |
| sensor | DC Current Injection T | A    | Enabled | DC injection T phase (technician account required) |

### Technician Account Only Entities (Require technician login credentials)

| Type   | Name                            | Unit | Default | Comment                                     |
| ------ | ------------------------------- | ---- | ------- | ------------------------------------------- |
| sensor | Grid Voltage                    | V    | Enabled | AC grid voltage                             |
| sensor | Grid Frequency                  | Hz   | Enabled | AC grid frequency                           |
| sensor | Grid Code                       | -    | Disabled | Folded into the Technical Info sensor's state       |
| sensor | Current To Grid                 | A    | Enabled | Current flow to/from grid                   |
| sensor | Inverter Power                  | W    | Enabled | Inverter power output                       |
| sensor | Inverter Temperature            | °C   | Enabled | Inverter operating temperature              |
| sensor | Bus Voltage                     | V    | Enabled | DC bus voltage                              |
| sensor | Technical Inverter Model        | -    | Disabled | Duplicates the Inverter Model Name sensor   |
| sensor | Technical Inverter Power Rating | W    | Disabled | Folded into the Technical Info sensor's attributes |
| sensor | Inverter Bootloader Version     | -    | Disabled | Folded into the Technical Info sensor's attributes |
| sensor | TIDA Protocol Version           | -    | Disabled | Rarely useful                               |
| sensor | Technical Operation Mode        | -    | Disabled | Duplicates the Current Operation Mode select |
| sensor | BMS Voltage                     | V    | Enabled | Battery pack voltage                        |
| sensor | BMS Current                     | A    | Enabled | Battery pack current                        |
| sensor | BMS Temperature                 | °C   | Enabled | Battery temperature                         |
| sensor | BMS Average Temperature         | °C   | Enabled | Average battery cell temperature            |
| sensor | BMS Max Temperature             | °C   | Enabled | Maximum battery cell temperature            |
| sensor | BMS Min Temperature             | °C   | Enabled | Minimum battery cell temperature            |
| sensor | BMS State                       | -    | Enabled | Battery state (charging/discharging/idle)   |
| sensor | Technical BMS State of Charge   | %    | Disabled | Duplicates the Battery State of Charge sensor |
| sensor | BMS Total Charge                | Ah   | Enabled | Lifetime energy charged                     |
| sensor | BMS Total Discharge             | Ah   | Enabled | Lifetime energy discharged                  |
| sensor | BMS Highest Cell Voltage        | mV   | Enabled | Highest individual cell voltage             |
| sensor | BMS Lowest Cell Voltage         | mV   | Enabled | Lowest individual cell voltage              |
| sensor | BMS Cell Voltage Delta          | mV   | Enabled | Difference between highest and lowest cells |
| sensor | BMS Fault Code                  | -    | Enabled | Readable fault text (`No fault` when healthy); raw codes in the `fault_codes` attribute |
| sensor | System CPU Usage                | %    | Enabled | Controller CPU utilization                  |
| sensor | System RAM Total                | MiB  | Enabled | Total system memory (also available as `system_ram_total_mb` on the Technical Info sensor) |
| sensor | System RAM Used                 | MiB  | Enabled | Used system memory                          |
| sensor | Technical Info                  | -    | Enabled | State = grid code; attributes: `inverter_power_rating`, `bootloader_version`, `system_ram_total_mb` |
| binary_sensor | BMS Fault                | -    | Enabled | Problem sensor, on when `BMS Fault Code` reports a fault |

### Notifications sensors

The integration exposes two sensors backed by the same notifications feed:

**`sensor.eaton_xstorage_home_notifications`**

- State: the total number of notifications reported by the inverter (not just the current page)
- Attributes: a `notifications` array (most recent page) with entries containing `alert_id`, `level`, `type`, `sub_type`, `status`, `created_at`, and `updated_at` (plus `total`, `start`, and `size` for pagination)

**`sensor.eaton_xstorage_home_latest_notification`**

- State: a human-readable description of the most recent notification (e.g. `The battery voltage is too high.`), derived from `sub_type`
- Attributes: `raw_sub_type` (the original API value, e.g. `BATTERY_VOLTAGE_HIGH`), `remedy` (suggested action), plus `alert_id`, `level`, `type`, `status`, `created_at`, `updated_at`
- Note: 5 of the 51 documented `sub_type` descriptions are reworded from the [xStorage Home API documentation](https://github.com/genestealer/eaton-xstorage-home-api-doc) (`BATTERY_VOLTAGE_HIGH`/`LOW` and `BUS_FAIL`/`BUS_HIGH_FAIL`/`BUS_LOW_FAIL`), because Eaton's own translation bundle reuses one string per opposing pair, which would make the sensor state unable to distinguish e.g. over-voltage from under-voltage

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

## Actions

The integration provides the following action.

### Action: Reload

`eaton_battery_storage.reload` reloads every configured inverter: the connection is rebuilt,
the stored access token is re-read and all entities are recreated. Use it after power-cycling
the inverter or updating its firmware, rather than restarting Home Assistant.

- **Data attributes**: none.
- **Permissions**: administrators only.

## Configuration

### Setup parameters

The form shown when you add the integration, and again when you reconfigure or re-authenticate
it, asks for:

| Field | Required | Description |
| --- | --- | --- |
| **Host** | Yes | The IP address or hostname of the inverter, optionally with a port (`192.168.1.10` or `xstorage.local:8443`). Do not include `https://` or a path. |
| **Account type** | Yes | **Customer** or **Technician**. See [Account Types](#account-types). |
| **Username** | Yes | The account name used to sign in to the inverter's web interface. |
| **Password** | Yes | The password for that account. It is stored in Home Assistant's configuration and never shown again. |
| **Inverter serial number** | For technician accounts | Required to sign in as a technician. For customer accounts, leave it empty unless the device fails to report its own serial, in which case type it in so the entry can be keyed on it. |
| **PV installed** | No | Turn on if the inverter has solar panels attached. This creates the PV entities listed above; turning it off later disables them again. |
| **Verify SSL certificate** | No | See [Verify SSL certificate](#verify-ssl-certificate). Off by default. |

### Account Types

This integration supports two account types:

- **Customer Account** (Default: user/user)
  - Basic monitoring and control
  - All core entities available
  - PV sensors (if enabled)

- **Technician Account** (Default: admin/jlwgK41G)
  - All Customer features plus:
  - Advanced technical diagnostics
  - BMS voltage/current/temperature sensors
  - System CPU/RAM monitoring
  - Requires inverter serial number

### Verify SSL certificate

The inverter serves its web API over HTTPS with a self-signed certificate, so **Verify SSL
certificate** is off by default and Home Assistant accepts whatever certificate the device
presents. Anything on the same network segment could therefore intercept the credentials.
Enable the option if you have installed a certificate that Home Assistant trusts.

### Reconfiguration

You can change settings after installation:
1. Go to **Settings** → **Devices & Services**
2. Find **Eaton xStorage Home Battery**
3. Open the ⋮ menu on the entry and choose **Reconfigure**
4. Update credentials, account type, or PV settings

The integration reloads itself when you save. If the device reports a different serial number
from the one the entry was set up with, the change is refused, so reconfiguring cannot
silently move an entry onto another inverter.

## Removing the integration

1. Go to **Settings** → **Devices & Services**
2. Find **Eaton xStorage Home Battery**
3. Open the ⋮ menu on the entry and choose **Delete**
4. In HACS, open the integration and choose **Remove**, otherwise the files stay installed and
   HACS keeps offering updates for it
5. Restart Home Assistant

Deleting the entry removes the device and all its entities, and deletes the stored access
token and the charge and discharge helper values, so no credentials are left behind.

**The inverter keeps whatever you last told it to do.** The integration writes the default
operation mode, battery backup level, energy saving mode and its house consumption threshold
to the device itself, and none of that is reverted on removal. A manual charge or discharge
also runs to the end of its duration, because the inverter carries it out on its own. If you
are removing the integration part way through a command, or you changed the default mode
through Home Assistant, set the inverter back to the mode you want in its own web interface
at `https://<device-ip>` first.

Two things survive removal by design:

- Recorded history and long-term statistics for the entities, until Home Assistant purges
  them.
- `.storage/eaton_battery_storage_number_values.json`, but only on installations that ran a
  version before 1.0.0. Newer versions store these values per config entry and delete them
  with the entry. The old shared file is left alone because a second inverter may still be
  reading it; delete it by hand once no entries remain.

## Troubleshooting

### Account Locked (Error 10)
If you see "Error during authentication: 10", your account was locked due to failed login attempts. Wait 10 minutes before trying again.

### Enable Debug Logging
Add to `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    custom_components.eaton_battery_storage: debug
```
