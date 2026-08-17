# Changelog

All notable changes to this integration are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - Unreleased

Implements the findings of [the 2026-08-01 code review](docs/code-review-2026-08-01.md)
and [the 2026-08-13 review](docs/code-review-2026-08-13.md).

0.2.2 is the last version published on `main`, and the 0.3.0 notes below were never released
either. Anyone upgrading from 0.2.2 gets both sets of changes at once, so read this entry and
the 0.3.0 one together.

### Breaking changes

Everything that needs something from you. Because 0.3.0 was never published, this covers the
0.2.2 to 1.0.0 upgrade, which is the only one anyone can make. The statistics clean-up is
described under [Upgrading](#upgrading).

- **The config entry format moves to version 2.** Existing entries migrate automatically on
  the first start, which re-keys them onto the inverter serial number and drops the
  host-based device identifier. Because Home Assistant refuses to load a config entry newer
  than the integration reading it, **downgrading to 0.3.x afterwards will not work**: the
  entry would have to be deleted and added again.
- **Settings have moved from Configure to Reconfigure.** Connection settings were edited
  through an options flow, which is not what an options flow is for. The entry's **Configure**
  button is replaced by **Reconfigure** in the ⋮ menu. Same form, same fields. Reconfiguring
  now also refuses a device whose serial number does not match the entry.
- **The operation mode select values changed.** `Basic Mode` → `basic_mode`,
  `Maximize Auto Consumption` → `maximize_auto_consumption`, `Variable Grid Injection` →
  `variable_grid_injection`, `Frequency Regulation` → `frequency_regulation`, `Peak Shaving`
  → `peak_shaving`, `Manual Charge` → `manual_charge`, `Manual Discharge` →
  `manual_discharge`. Update anything that calls `select.select_option` on **Default
  operation mode** or **Current operation mode**, and any template, condition or trigger
  comparing their state. The dropdown reads the same in the UI, because the labels are now
  translations rather than the values themselves.
- **Several sensors now report readable text instead of the raw API string.** The energy flow
  role sensors (**Grid Role**, **AC PV Role**, **DC PV Role**, **Critical Load Role**,
  **Non-Critical Load Role**) read Producing, Consuming, Disconnected or Idle instead of
  `PRODUCER`, `CONSUMER`, `DISCONNECTED` and `NONE`. **Operation Mode**, **Current Mode
  Recurrence** and **Current Mode Type** gained the values the device reports but the API
  documentation omits. Anything matching on the raw strings needs updating.
- **Sensor units were corrected, which invalidates their statistics.** **Self Consumption**
  (W → %), **BMS Total Charge** and **BMS Total Discharge** (kWh → Ah), and **Today's Grid
  Consumption**, **Today's PV Production** and their 30-day counterparts (W → Wh). The two
  30-day sensors are a rolling window rather than a total, so they no longer carry a state
  class and stop producing long-term statistics.
- **System RAM Total** and **System RAM Used** changed unit from MB to MiB and gained the
  `data_size` device class. The reading was always calculated in MiB, so the old label was
  simply wrong; expect a one-off step of about 5 % where the correction lands.
- **The `system_ram_total_mb` attribute is renamed `system_ram_total_mib`** on the
  **Technical Info** sensor. Templates reading it by name need updating.
- **Grid Frequency now reports `0` during a grid outage** rather than going unknown. Anything
  treating unknown as the outage signal should compare against 0 instead.
- **The `created_at` and `updated_at` attributes on Notifications and Latest Notification are
  now timestamps.** The device reports these in milliseconds, and the raw integer was passed
  straight through, so anything reading them had to divide by 1000 before converting. They
  are now datetimes; a template doing its own conversion needs updating.
- **Adding an inverter now requires its serial number.** If the device does not report one,
  type it into **Inverter Serial Number**. The old fallback keyed the entry on the IP
  address, which a DHCP change would orphan. Existing entries are unaffected.
- **Re-authentication refuses a different inverter.** It used to accept any device and keep
  the original identity, silently continuing one inverter's history with another's readings.
  An entry still keyed on its IP address adopts the serial at the next re-authentication.

Carried over from the unreleased 0.3.0, and therefore also new to anyone on 0.2.2:

- **BMS Fault Code** renders readable text such as `Over-voltage` instead of a stringified
  Python list, and reads `No fault` rather than `unknown` when there is none. The raw codes
  moved to the `fault_codes` attribute.
- **Current Mode Start Time** and **End Time** changed from 12-hour `11:54 am` to 24-hour
  `11:54`.
- **Notifications** reports the true total rather than the size of the current page, so the
  number changes.
- **Current Mode Duration** gained the `duration` device class and the unit `h`.

### Added

- **Verify SSL certificate** option in the config, reauth and options flows. It defaults to
  off, matching the previous hardcoded behaviour, because the inverter ships a self-signed
  certificate. Turning it on makes Home Assistant validate the certificate for every request,
  including the credential exchange.
- Host validation in the config flow: values containing a scheme, path or whitespace are now
  rejected instead of being used to build a storage filename.
- Reauthentication is now actually reachable — the coordinator raises `ConfigEntryAuthFailed`
  when the device rejects the credentials, so Home Assistant prompts for new ones instead of
  leaving every entity unavailable.
- Test scaffolding: `requirements_test.txt`, ruff/mypy/pytest configuration in
  `pyproject.toml`, a `tests/` suite and a CI job that runs ruff, mypy and pytest on every
  pull request. The device is mocked at the HTTP boundary, so the tests exercise the real
  API client, coordinator and entity platforms rather than stand-ins for them. Every module
  has its own test file and the suite covers 97 % of the integration.
  ([#31](https://github.com/greyfold/home_assistant_eaton_battery_storage/issues/31))
- `entity.py` with a shared `EatonEntity` base class, replacing the twelve copies of
  `device_info` and `has_entity_name` spread across the platforms.
- Syrupy snapshot coverage of every entity on all seven platforms, so an accidental change
  to a unit, device class, entity category or state shows up as a snapshot diff.

### Changed

- **The charge and discharge helper numbers moved to the Configuration section** of the
  device page. They configure this integration rather than reporting the inverter, so they
  are now diagnostic-style config entities. Entity IDs and history are unaffected.
- **Charge Power (%)** and **Discharge Power (%)** no longer carry the `power` device class.
  A percentage is not a power unit, and the pairing would have failed as soon as a unit
  override was applied. Their watt counterparts keep the device class.
- **Battery Backup Level** gained the `battery` device class and **House Consumption
  Threshold** the `power` device class, so both are recognised for what they are.
- **Adding an inverter now requires its serial number.** The config flow used to fall back to
  `{host}_{username}` when the device did not report one, which put the IP address back into
  the identity the rest of this release works to remove. When no serial is available the form
  now asks the user to retry or to type it in.
- **System RAM Total** and **System RAM Used** are reported in MiB with the `data_size` device
  class. They were labelled MB while dividing by 1024², so every reading was about 5 % out
  against its own unit. The **Technical Info** attribute is renamed to `system_ram_total_mib`
  to match.
- The config flow no longer displays the vendor's default technician password; it points at
  the documentation instead.
- The notification and static info sensors keep their bulky attributes out of the recorder,
  so the full alert list is no longer written to the database on every state change.
- **Device identity is now keyed on the inverter serial number.** The host-based identifier
  is removed from existing devices on upgrade, and the config entry unique ID is migrated
  from `{host}_{serial}` to the bare serial. A device that changes IP address now updates its
  host instead of appearing as a duplicate.
- The README documents the `reload` action: what it does, that it takes no data and that it
  needs an administrator.
- The README documents how to remove the integration, including that settings written to the
  inverter are not reverted and a running manual command finishes on its own.
- Settings writes (energy saving mode, backup level, house consumption threshold, default
  operation mode) go through a single lock-protected read-modify-write helper, so two
  automations firing at the same time can no longer overwrite each other's changes.
- The coordinator fetches the optional endpoints concurrently instead of serially, and logs
  loss of connectivity once rather than on every failed refresh.
- Command entities no longer sleep 1–3 seconds inside the service call; they schedule a
  debounced refresh instead.
- The API layer signals failures with a dedicated exception hierarchy
  (`EatonAuthError`, `EatonConnectionError`, `EatonResponseError`, `EatonCommandError`)
  instead of a mix of `ValueError`, `ConnectionError` and error dictionaries. The config flow
  classifies authentication failures on the device error code rather than on English text.
- Select entities now raise a translated error when a command fails, instead of logging and
  reporting success.
- The sensor value handling no longer wraps ~180 lines in a single `try`/`except`. The
  lookups, fault-code rendering, cell-voltage delta and HHMM time formatting are separate
  helpers with targeted guards, so a genuine bug surfaces instead of being swallowed as
  "Error retrieving state". Two debug logs that fired on every state read were removed;
  the same data is available in the diagnostics download.
- The access token is stored under `{domain}.{entry_id}_token`, is read back on restart
  instead of being written and never used, and is deleted when the entry is removed.
- The `reload` service is registered once in `async_setup` instead of per config entry, and
  now requires an administrator, matching Home Assistant's own reload helper. Automations
  run as a non-admin user can no longer call it.
- `PARALLEL_UPDATES` is declared on every platform: `0` for the read-only ones, `1` for the
  command platforms.
- Password fields are no longer prefilled in the reauth and options forms.
- Connection settings are changed through a reconfigure flow rather than an options flow.
  They were always written to the entry data rather than to its options, so the options flow
  was only ever a reconfigure flow with the wrong name and the wrong abort reason. The entry
  no longer registers a config entry update listener either: the reconfigure and reauth steps
  schedule their own reload, and Home Assistant warns that pairing the two with
  `async_update_reload_and_abort` stops working in 2026.12.
- `quality_scale.yaml` now lists every rule through Platinum with an accurate status. The
  `"quality_scale": "bronze"` claim was removed from `manifest.json` until the remaining
  Bronze rules (brands, removal instructions) are met, since it was self-asserted and
  unverifiable for a custom component.

### Removed

- The `examples/` folder and the README section linking to it. The automations in it had gone
  stale, and the quality scale asks for blueprints on the
  [blueprint exchange](https://community.home-assistant.io/c/blueprints-exchange) rather than
  YAML kept in the repository. Nothing that is already running is affected; only the copies
  in this repository are gone.

### Fixed

The unit, enum and `services.yaml` fixes below had no issue raised against them. They were
found while verifying the sensor platform against the API documentation, a live inverter and
the Home Assistant log, so there is nothing to link them to beyond this entry and the
readings recorded in [the device API behaviour notes](docs/device-api-behaviour.md).

- The **Reload** action did nothing. It called a helper meant for YAML-configured platforms,
  which re-read `configuration.yaml` and returned without touching the config entry, so the
  device was never re-polled and no entity was rebuilt.
- **An HTTP error from the inverter is now an error.** Only the status `401` was ever
  inspected, so a `403`, `404` or `500` carrying a JSON body was handed to the integration as
  if it had succeeded. The power switch was worst affected: it has no success flag to check,
  so a refused command was reported as applied. A `401` that survives a fresh token now asks
  for re-authentication instead of being retried forever.
- Numeric sensors whose reading comes back as `n/a` are now simply unknown. Home Assistant
  refuses to add a numeric sensor holding a non-numeric value, so **BMS Highest Cell
  Voltage** could vanish entirely rather than merely having no value.
- The charge and discharge helper values are stored per config entry. Two inverters shared a
  single file and overwrote each other's power, duration and target SOC. Values saved by an
  earlier version are adopted on upgrade rather than reset to the defaults.
- The helper values are loaded before the platforms start, so a mode command issued straight
  after startup no longer falls back to hardcoded defaults.
- A sign-in answered with an HTML page or an otherwise unexplained response is treated as the
  device being unreachable instead of as a rejected password, so a reboot or a proxy in front
  of the inverter no longer raises a spurious "re-authentication required" prompt.
- Re-authenticating now refuses a different inverter instead of silently re-pointing the
  entry at it, and re-keys entries that older versions left keyed on the IP address.
- The watt sliders follow the inverter rating even when it only arrives after setup, instead
  of staying capped at the 3600 W fallback until Home Assistant restarts.
- The notification sensors survive a malformed entry in the device's notification list rather
  than failing to write their state at all.
- Authentication failures on the optional endpoints are surfaced instead of being swallowed,
  which previously left every technician-only sensor unknown with nothing to explain it.
- System health covers every configured inverter rather than only the first one. The panel
  keeps its three translated rows, listing every host and reporting the reachability and
  update time of the worst-off inverter.

- A running manual discharge is no longer reported as a manual charge. The device echoes
  both directions back under the same command, so the direction is now read from the
  `action` parameter that distinguishes them. This affects the **Current operation mode**
  select and the **Current Mode Command** sensor; the discharge itself was always carried
  out correctly. ([#33](https://github.com/greyfold/home_assistant_eaton_battery_storage/issues/33))
- **Current operation mode** no longer springs back to the previous mode after a selection.
  The inverter takes a couple of seconds to report an accepted command in its status, and the
  refresh issued straight after the command beat it to it, read the old mode back and then
  left it on screen until the next poll a minute later. The mode the device echoes back when
  it accepts a command is now shown until a poll agrees with it, or for two minutes, whichever
  comes first. The **Stop current operation** button and the **Current Mode** sensors follow
  the same record. Measured on a 3.6 kW unit: the status caught up after 0.4 s to 2.8 s, and
  the entity held the selection across three polls where before it reverted after one.
- `sensor.eaton_xstorage_home_battery_state_of_charge` and the technical BMS state of charge
  now declare `state_class: measurement`, so they are recorded in long-term statistics.
  Sensor descriptions can now set `state_class` explicitly instead of only deriving it from
  the device class. ([#34](https://github.com/greyfold/home_assistant_eaton_battery_storage/issues/34))
- Every numeric sensor now declares a state class, so it reaches long-term statistics.
  Previously only the `power`, `energy` and `energy_storage` device classes derived one,
  which left the voltage, current, temperature, frequency and battery sensors, and the
  percentage and diagnostic counters, out of statistics entirely. String and enum sensors
  still declare none, as do the setpoints (**Current Mode SOC** and **Current Mode Power**)
  and the static ratings (**Inverter VA Rating**, **Inverter Nominal VPV** and **Technical
  Inverter Power Rating**, the last reading a constant 0 on at least the 3.6 kW model).
  This is the general form of the defect reported in
  [#34](https://github.com/greyfold/home_assistant_eaton_battery_storage/issues/34), which
  fixed the two state of charge sensors specifically.
- **Self Consumption** was reported in watts with the `power` device class, but the device
  reports it as a percentage of generated energy used directly. It is now a percentage,
  matching the 30-day and today's self-consumption sensors, which were already correct.
- **Current Mode Power** now declares its unit as a percentage. The device reports this
  parameter as 5–100 % of the inverter rating, which is what `number.py` already assumed
  when converting it to watts.
- **Today's Grid Consumption**, **Today's PV Production** and their 30-day counterparts
  were reported in watts with the `power` device class, but they are cumulative energy
  totals. Probing a live inverter gave `today.gridConsumption` 13748.699 against an
  instantaneous `gridValue` of 1337 W, and a 30-day figure almost exactly thirty times the
  daily one, so they are watt hours. The two today's sensors are now `total_increasing`
  energy and can be used in the Energy dashboard; the 30-day pair is a rolling window whose
  absolute value is what matters, so it carries no state class.
- **BMS Total Charge** and **BMS Total Discharge** were reported as energy in kWh. The
  device returns coulomb counts: 17005 on a 4.2 kWh battery would be 4048 full cycles in
  the ~13 months of records, whereas 17005 Ah over the pack's ~42.6 Ah works out at almost
  exactly one cycle a day. They are now reported in Ah with state class `total`.
- Values the device returns that were missing from the display maps no longer leak the raw
  API string to the dashboard. The five energy flow role sensors (**Grid Role**, **AC/DC PV
  Role**, **Critical** and **Non-Critical Load Role**) had no mapping at all and now read
  Producing, Consuming, Disconnected or Idle instead of `PRODUCER`, `CONSUMER`,
  `DISCONNECTED` and `NONE`. **Operation Mode** gained the eight modes the device's own web
  interface lists but the API documentation omits, including the `BASIC` it reports while
  running its default mode, and **Current Mode Recurrence** and **Current Mode Type** gained
  the `DEFAULT_EVENT` and `DEFAULT` they report at the same time. Automations matching on
  the raw strings for these seven sensors need updating.
- Loss of connectivity is logged at `info` rather than `warning`, which is the level the
  quality scale asks for. It is still logged once when the device goes away and once when it
  comes back, not on every failed refresh.
- `services.yaml` was missing, so Home Assistant logged "Failed to load services.yaml for
  integration: eaton_battery_storage" every time something asked for the service list. The
  `reload` service the integration registers is now described there and in the translations.

### Upgrading

The unit corrections above mean the recorder holds statistics for **Self Consumption**,
**BMS Total Charge** and **BMS Total Discharge** in the old units, and it will log
"cannot be converted to the unit of previously compiled statistics" and stop recording them
until that history is cleared. Those old readings were wrong, so delete them: go to
**Developer tools → Statistics**, find each of the three sensors, and use **Fix issue** to
remove the previously compiled statistics. Recording resumes on the next cycle.

**System RAM Total** and **System RAM Used** were labelled MB while being calculated in MiB,
so they now declare MiB and the `data_size` device class. The number they show is unchanged —
only the label was wrong. Home Assistant can convert between MB and MiB, so the recorder
carries the history over rather than refusing it, but the converted history for those two
sensors will be about 5 % out because it was recorded under the wrong label.

Adding a new inverter now requires the device to report its serial number, or the serial to
be typed into the **Inverter Serial Number** field. Existing entries are unaffected, and an
entry still keyed on its IP address is re-keyed to the serial the next time it
re-authenticates.
- System health no longer crashes when the first config entry is disabled or retrying setup.
- The PV sensor migration no longer re-enables sensors that the user disabled deliberately.
- Cell voltage sensors declare their display precision explicitly instead of relying on
  substring matching against the sensor key.
- The notification event entity no longer grows its "seen alerts" set without bound.
- The percentage/watt conversion for charge and discharge power now uses the inverter's
  reported power rating (`technical_status.inverterPowerRating`, falling back to
  `device.inverterVaRating` for customer accounts and to 3600 W if neither is available)
  instead of hardcoding 3600 W in six places. The watt sliders now span 5–100 % of that
  rating, so 4.6 kW and 6 kW models are no longer capped at 3600 W.

## [0.3.0] - Never released

This work was superseded by 1.0.0 before it was published. It is kept as its own entry
because it is a distinct body of changes, but there was never a 0.3.0 release to upgrade
from.

### Added

- `sensor.eaton_xstorage_home_latest_notification`: readable description of the most recent
  notification (e.g. "The battery voltage is too high."), with `raw_sub_type`, `remedy`,
  `alert_id`, `level`, `type`, `status`, `created_at`, and `updated_at` attributes. Covers all
  51 documented notification `sub_type` values.
- `binary_sensor.eaton_xstorage_home_bms_fault`: `problem` device class, on when
  `technical_status.bmsFaultCode` reports a fault. Technician account only.
- `binary_sensor.eaton_xstorage_home_energy_saving_mode_activated`: mirrors
  `status.energyFlow.energySavingModeActivated`.
- Grouped diagnostic sensors consolidating static identity fields into attributes instead of
  one sensor each:
  - `sensor.eaton_xstorage_home_inverter_info` (state = inverter firmware version;
    attributes: `va_rating`, `nominal_vpv` on PV installs)
  - `sensor.eaton_xstorage_home_bms_info` (state = BMS model; attributes: `serial_number`,
    `capacity_kwh`)
  - `sensor.eaton_xstorage_home_device_info` (state = bundle version; attributes:
    `local_portal_remote_id`, `timezone`)
  - `sensor.eaton_xstorage_home_technical_info` (state = grid code; attributes:
    `inverter_power_rating`, `bootloader_version`, `system_ram_total_mb`). Technician account
    only.

  Home Assistant normally asks for a separate entity per value rather than attributes,
  because when a sensor's state and its attributes both change often the recorder stores a
  new copy of the attributes on every update. That does not apply here: these are device
  identity fields — firmware versions, serial numbers, model names, ratings — that do not
  change while the integration is running, so the recorder stores each attribute set once
  and every later state row just points at it. Grouping them keeps four entities on the
  device page instead of a dozen that would each never move. Every one of these fields is
  still available as its own sensor if you prefer that; all except **System RAM Total** ship
  disabled by default, so enable them from the device page.
- `BMS_FAULT_CODE_MAP` and `NOTIFICATION_SUBTYPE_MAP` in `const.py`, sourced from the
  [xStorage Home API documentation](https://github.com/genestealer/eaton-xstorage-home-api-doc).

### Changed

- `sensor.eaton_xstorage_home_bms_fault_code`: now renders readable fault text (e.g.
  "Over-voltage") instead of a stringified Python list, and reads "No fault" instead of
  `unknown` when the API reports no fault (`bmsFaultCode: null`). Raw codes are preserved in
  the `fault_codes` attribute.
- `sensor.eaton_xstorage_home_current_mode_start_time` / `_end_time`: switched from 12-hour
  `"11:54 am"` to 24-hour `"11:54"` formatting.
- `sensor.eaton_xstorage_home_current_mode_duration`: now reports a `duration` device class
  with unit `h`, matching the existing charge/discharge/run duration numbers.
- `sensor.eaton_xstorage_home_notifications`: state now reflects the true total notification
  count instead of the current page size.
- The following sensors are now diagnostic and disabled by default on new installs, since
  they duplicate another entity or the device registry, or rarely change:
  `status.energyFlow.operationMode`, `technical_status.operationMode`,
  `device.energySavingMode.houseConsumptionThreshold`, `technical_status.bmsStateOfCharge`,
  `technical_status.inverterModel`, `status.energyFlow.energySavingModeEnabled`,
  `status.energyFlow.energySavingModeActivated`, `device.firmwareVersion`,
  `device.bmsFirmwareVersion`, `device.inverterSerialNumber`, `device.inverterManufacturer`,
  `device.inverterModelName`, `device.inverterFirmwareVersion`, `device.inverterVaRating`,
  `device.inverterNominalVpv`, `device.bmsCapacity`, `device.bmsSerialNumber`,
  `device.bmsModel`, `device.bundleVersion`, `device.localPortalRemoteId`,
  `device.timezone.name`, `technical_status.gridCode`, `technical_status.inverterPowerRating`,
  `technical_status.invBootloaderVersion`. Existing installs are unaffected; only entities
  registered for the first time are hidden.
  `binary_sensor.eaton_xstorage_home_inverter_power_state` is likewise now disabled by
  default (duplicates `switch.eaton_xstorage_home_inverter_power`).
- Active-fault detection (`binary_sensor.eaton_xstorage_home_bms_fault`) requires a
  technician account; it is not created for customer accounts.

### Removed

- `GET /api/metrics` and `GET /api/metrics/daily` polling. These calls omitted the required
  `from`/`to` parameters and returned `400 Bad Request` on every poll cycle; no entity
  consumed the data.

## [0.2.2] and earlier

The last version published on `main`. See git history prior to this file's creation.
