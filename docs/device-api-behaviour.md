# Observed device API behaviour

Recorded on 2026-08-12 by probing a live inverter, because these responses are
not described in the [xStorage Home API
documentation](https://github.com/genestealer/eaton-xstorage-home-api-doc) and
the integration previously guessed at them.

| Field | Value |
| --- | --- |
| Model | `XSTH1P036P048V01` (3.6 kW) |
| Bundle version | `v1.17` |
| Device firmware | `00.01.0017-0-g72006700` |
| Inverter firmware | `00.06.0069` |
| BMS firmware | `4004` |

Behaviour may still differ on the 4.6 kW and 6 kW models, and on units left on
an older bundle version. It will not change on this one: the xStorage Home is
discontinued and no further firmware is expected, so what is recorded here is
fixed for this build rather than a snapshot. Add findings from other models
below rather than replacing these.

## Write endpoints answer in three different shapes

| Endpoint | Status | Content-Type | Body |
| --- | --- | --- | --- |
| `POST /api/device/power` | `200` | `application/json` | `""` |
| `POST /api/device/command` | `200` | `application/json` | `{"successful": true, "result": {…}}` |
| `PUT /api/settings` | `307` → `/api/settings/` → `200` | `application/json` | `{"successful": true, "result": {…}}` |

`POST /api/device/power` returns a bare JSON empty string rather than a result
object, so it cannot be checked for success. `api.set_device_power` therefore
does not call `_require_success`, and `make_request` treats a 2xx with no usable
body as success. The other two return a normal result object and are checked.

`PUT /api/settings` redirects to the trailing-slash path. aiohttp follows a 307
while preserving the method, so the client sees the final `200` and no special
handling is needed. It does cost two round trips per settings write. Note that
`GET /api/settings` does **not** redirect.

## An accepted command answers with the stored mode record

Captured from the device web interface on 2026-08-16. Request:

```json
{
  "command": "SET_CHARGE",
  "duration": 4,
  "parameters": { "power": 100, "soc": 95, "action": "ACTION_CHARGE" }
}
```

Response:

```json
{
  "successful": true,
  "message": "Content Ready",
  "result": {
    "id": "0def3bdb-f021-484e-a1d8-22cebaa391a1",
    "command": "SET_CHARGE",
    "createdAt": 1786919563000,
    "updatedAt": 1786919563000,
    "duration": 4,
    "startTime": 2332,
    "endTime": 332,
    "recurrence": "MANUAL_EVENT",
    "type": "MANUAL",
    "parameters": { "action": "ACTION_CHARGE", "power": 100, "soc": 95 },
    "user": { "id": "00000000-0000-0000-0000-000000000000", "firstName": "Local", "lastName": "User" }
  }
}
```

The result is the mode record the device stored, in the same shape that
`status.currentMode` reports, so a caller can read the accepted command back
without a second request. Everything except `command`, `duration` and
`parameters` is filled in by the device:

- `startTime` and `endTime` are HHMM integers derived from the time of the
  request and its duration. Here 23:32 plus four hours gives `332`, which is
  03:32 the next day: the pair wraps past midnight with no date to say so.
- `recurrence` is `MANUAL_EVENT` and `type` is `MANUAL` for a command sent to
  this endpoint. The other values either field can take are listed under
  [Values missing from the documented enumerations](#values-missing-from-the-documented-enumerations);
  which combinations a scheduled or default-mode record uses has not been
  captured.
- `user` is a placeholder for a locally issued command, with an all-zero
  identifier and the fixed name `Local User`.

### The status takes a few seconds to report the accepted command

`status.currentMode` still describes the previous mode for a moment after the
command has been accepted. Polling the status every two seconds after each of
three commands sent to a 3.6 kW unit, the new record appeared after 0.4 s, 2.7 s
and 2.8 s, and never changed again afterwards. Anything that reads the mode back
immediately therefore gets the old one; the response above is the reliable
answer, and the integration shows it until a poll agrees with it.

## Rejections arrive as an error status with a JSON body

A refused request answers with a non-2xx status, and the body may still be JSON:

| Request | Status | Body |
| --- | --- | --- |
| `GET /api/definitely-not-a-real-endpoint` | `404` | `404 page not found` (plain text) |
| `POST /api/device` (a GET-only endpoint) | `404` | `404 page not found` (plain text) |
| `POST /api/device/command` with `{}` | `400` | `{"error": {"step": "set_manual_command", "errCode": "Key: 'ManualCommandReq…"}}` |

The JSON case is why `make_request` checks the status before it looks at the
body. Returning a parsed error payload to the caller would leave
`set_device_power` — the one write with no success flag to check — reporting a
refused command as applied.

## Every settings write stores a new record

`PUT /api/settings` does not update the stored document in place. Reading the
settings back after writing them returns identical values with a fresh `id`,
`createdAt` and `updatedAt`, so those three fields cannot be used to tell
whether a write changed anything. Nested records the write did not touch, such
as `defaultMode`, keep their own original identifier and timestamps.

## Record timestamps are seconds in some places and milliseconds in others

`createdAt` and `updatedAt` do not carry the same unit everywhere:

| Record | Unit | Example |
| --- | --- | --- |
| `GET /api/device`, `GET /api/settings`, `GET /api/device/maintenance/diagnostics` | seconds | `1786919104` |
| `status.currentMode`, the result of `POST /api/device/command`, notification records | milliseconds | `1786919563000` |

Both refer to the same instant, so the digit count is the only way to tell them
apart. The integration passes the notification values through untouched as the
`created_at` and `updated_at` attributes, which are therefore milliseconds.

`startTime` and `endTime` on a mode record are neither: they are HHMM integers,
so a mode running from 23:32 to 03:32 reads `2332` and `332`.

## The inverter power rating can be zero

`technical_status.inverterPowerRating` reads `0` on this unit, while
`device.inverterVaRating` reads `3600` and matches the model number. The
xStorage Home range spans 3.6 kW to 6 kW, so the percentage to watt conversion
for the charge and discharge helpers cannot assume 3600.

`number._full_scale_power` therefore prefers `inverterPowerRating` only when it
is greater than zero, then falls back to `inverterVaRating`, then to
`DEFAULT_INVERTER_POWER_RATING`. Removing the greater-than-zero guard would
collapse the watt entities to a 0 W scale on this hardware.

## The status totals are energy in watt hours

`status.today` and `status.last30daysEnergyFlow` carry no unit in the API
documentation, and the sample response there has every field at zero. A live
reading at 20:55 local resolves it:

| Field | Value |
| --- | --- |
| `energyFlow.gridValue` | `1337` |
| `today.gridConsumption` | `13748.699` |
| `last30daysEnergyFlow.gridConsumption` | `411518.78` |

`today.gridConsumption` cannot be power: 13.7 kW is beyond the 3600 VA inverter,
and the instantaneous grid reading at the same moment was 1337 W. As energy it is
13.7 kWh of grid import in a day, which is an ordinary house. The 30-day figure is
29.9 times the daily one, or 411.5 kWh over 30 days for the same 13.7 kWh a day.
So both blocks are watt hours, `today` resetting daily and the 30-day block
rolling.

Note that `/api/metrics` is *not* in the same unit, despite the API documentation
saying its values are Wh. Over the same day its 250 samples averaged 574.75 with a
maximum of 3688.8; summing them gives 143.7 kWh against an actual 13.7 kWh day.
Those samples are watts.

## The BMS totals are ampere hours, not kWh

`bmsTotalCharge` reads `17005` and `bmsTotalDischarge` `15847` on a 4.2 kWh pack
whose records start 2025-07-12. Read as kWh that is 4048 full cycles in about 396
days, or ten cycles a day, which the hardware cannot do. Read as Wh it is four
cycles in thirteen months, which is too few for a battery that cycles daily.

At the observed `bmsVoltage` of 98.5 V the pack is roughly 42.6 Ah, so 17005 Ah is
399 cycles, or 1.008 a day. That is what a home battery does, and a coulomb counter
in Ah is the BMS convention. The charge to discharge ratio of 93 % is a plausible
coulombic efficiency.

Home Assistant has no device class or unit constant for charge, so these sensors
declare the unit `Ah` with no device class.

## Values missing from the documented enumerations

Seen live but absent from the API documentation, so they reach Home Assistant
unmapped and render as the raw string:

| Field | Value seen | Documented values |
| --- | --- | --- |
| `energyFlow.gridRole` | `PRODUCER` | `NONE`, `SUPPLYING`, `CONSUMING` |
| `energyFlow.nonCriticalLoadRole` | `CONSUMER` | as above |
| `energyFlow.operationMode` | `BASIC` | `CHARGING`, `DISCHARGING`, `IDLE` |
| `currentMode.recurrence` | `DEFAULT_EVENT` | `DAILY`, `WEEKLY`, `MANUAL_EVENT` |
| `currentMode.type` | `DEFAULT` | `MANUAL`, `SCHEDULE` |

`currentMode` also returns `null` for `duration`, `startTime`, `endTime` and
`parameters` while the device is running its default mode.

## Sign-in errors

Still unverified. `_classify_auth_error` maps the documented `errCode` `10`
(account locked) and the two synthetic codes the client raises itself, then
falls back to matching the English `description` for wrong credentials and an
invalid inverter serial. Capturing the real codes needs deliberately failed
logins, which risk a ten minute account lockout.

Because the firmware is frozen, that prose fallback cannot be broken by an
update, which makes this low priority. The remaining risk is a device set to a
non-English language returning a localised `description`, which would fall
through to the generic `invalid_auth` message.

## Which zero readings are real

`technical/status` zeroes some fields when it cannot take the reading, so the
integration drops those. Deciding which ones needed evidence rather than
guesswork, because suppressing a genuine zero hides information just as badly as
showing a false one.

Read from the test unit while it was healthy: `bmsAvgTemperature` 23.2,
`bmsMaxTemperature` 46.1, `bmsMinTemperature` 43.7, `bmsVoltage` 90.4,
`bmsTotalCharge` 17142, `bmsTotalDischarge` 15999, `gridFrequency` 49.97.

- Temperatures are dropped at zero. The API documentation's own sample shows
  `bmsAvgTemperature: 0` next to a max of 35.5 and a min of 32.8, which is not a
  battery at freezing point, it is an absent reading.
- `bmsVoltage` is dropped at zero. The pack reads around 90 to 99 V whenever the
  BMS answers at all, so nothing connected can report 0 V.
- `bmsTotalCharge` and `bmsTotalDischarge` are dropped at zero even though a new
  pack legitimately starts there. They only ever climb, so a return to zero is a
  read error, and letting it through would put a reset into the `TOTAL`
  statistic and add a spurious lifetime of charge to its sum. The cost is that a
  brand new battery reads unknown until the first amp hour flows.
- `gridFrequency` is **not** dropped. 0 Hz is what an outage looks like, which is
  the moment the reading matters most, and it agrees with the `NO_UTILITY`
  notification. Hiding it was the one case where the suppression removed the
  signal it was supposed to protect.

## Reproducing

`temp/probe_device.py` in this repository performs these probes. It reads the
credentials from a local Home Assistant config entry so no password is typed or
stored, and it redacts the access token from its output. The command probe
replays whatever mode the device is already running rather than forcing a new
one, but it still replaces the running session, so avoid it mid-charge.

`temp/probe_units.py` collects the readings behind the two unit sections above.
It only issues GETs, so it is safe to run at any time.
