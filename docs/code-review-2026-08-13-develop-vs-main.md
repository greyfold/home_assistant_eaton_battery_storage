# Code review — `develop` vs `origin/main` (13 August 2026)

Reviewed `git diff $(git merge-base origin/main HEAD)` — 47 files, ~17k insertions
(11k of which are `.ambr` snapshots). Every finding below was double-checked by a
verification pass against the Home Assistant core sources in `/workspaces/core`.

This is a full-branch diff review and overlaps in places with
`code-review-2026-08-13.md`, which reviewed the working tree against the quality scale
rules. Where the two agree the finding is repeated here with the diff line numbers.

---

## `custom_components/eaton_battery_storage/__init__.py`

### [CRITICAL] Line 78 — the `reload` action does nothing

`async_reload_integration_platforms` is documented in `homeassistant/helpers/reload.py`
as being for integrations that expose YAML-configured platforms — its docstring names
template, stats and derivative. It re-reads `configuration.yaml` and re-sets-up entity
platforms that were registered through `async_setup_platform`.

This integration sets its platforms up via `async_forward_entry_setups`, so the handler
finds nothing in YAML and returns. Neither the config entry, the coordinator, the API
client nor any entity is reloaded — pressing "Reload" in the UI is a no-op.

This also means the `action-setup: done` and `docs-actions: exempt` entries in
`quality_scale.yaml` rest on a non-functional action.

#### Suggested fix

Reload the config entries, which is what the ~390 core integrations with a reload action
do. The service is registered in `async_setup`, before any entry exists, so the handler
has to look the entries up at call time:

```python
async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Set up the Eaton xStorage Home integration."""

    async def reload_service_handler(_call: ServiceCall) -> None:
        await asyncio.gather(
            *(
                hass.config_entries.async_reload(entry.entry_id)
                for entry in hass.config_entries.async_loaded_entries(DOMAIN)
            )
        )

    async_register_admin_service(
        hass, DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=vol.Schema({})
    )
    return True
```

Points to note when applying this:

- Use `async_loaded_entries(DOMAIN)` rather than `async_entries(DOMAIN)`. It skips
  entries that are disabled, failed or not yet set up, so a reload never tries to unload
  something that was never loaded.
- `asyncio.gather` keeps a two-inverter installation reloading in parallel; with a single
  entry it behaves identically to a plain `await`.
- `async_reload` tears the entry down and runs `async_setup_entry` again, so the API
  client is rebuilt, the token is re-read from `.storage`,
  `async_config_entry_first_refresh` re-polls the device, and every platform is
  re-created. That is the behaviour a user pressing "Reload" expects, and it is what
  makes the action useful after the inverter has been power-cycled or its firmware
  upgraded.
- The `from homeassistant.helpers.reload import async_reload_integration_platforms`
  import then becomes unused and should be removed. `asyncio` needs importing.
- The reload path already exists and is exercised elsewhere: `async_update_options`
  calls `hass.config_entries.async_reload(entry.entry_id)` for exactly this purpose, so
  the handler is reusing a code path that is known to work for this integration.
- Once the action genuinely reloads, `docs-actions: exempt` is defensible (the standard
  reload action needs no dedicated docs) and `action-setup: done` becomes accurate,
  because the action is still registered in `async_setup` rather than in
  `async_setup_entry`.
- Worth a test: set up two entries, call `eaton_battery_storage.reload`, and assert both
  coordinators re-polled — for example by comparing `aioclient_mock.call_count` before
  and after, or by asserting `last_update_success_time` moved. The current handler would
  pass any test that only asserts the service is registered, which is presumably how it
  survived this long.

### [SUGGESTION] Line 56 — `PV_SENSOR_KEYS` duplicates `"pv_related": True`

The two lists agree today (14 keys each, verified programmatically), but the next PV
sensor added to `SENSOR_TYPES` will silently not be migrated. Derive it instead:
`[k for k, d in SENSOR_TYPES.items() if d.get("pv_related")]`.

---

## `custom_components/eaton_battery_storage/number.py`

### [CRITICAL] Line 74 — the helper-value `Store` key is not scoped to the config entry

`f"{DOMAIN}_number_values.json"` is global, while every one of the 19 `unique_id`s in
this integration is deliberately scoped with `config_entry.entry_id` "to support multiple
devices". Two inverters would share one `.storage` file and overwrite each other's
charge/discharge power, duration and end-SOC. Worse, `_full_scale_power` differs per
inverter, so the percent-to-watt conversions cross-contaminate.

Key it `f"{DOMAIN}_{entry.entry_id}_number_values"`. The `.json` suffix is also
redundant — `Store` uses the key verbatim as the filename. The store is never removed in
`async_remove_entry` either, which only clears the token store.

### [PROBLEM] Lines 157 and 209 — the dispatcher signal is likewise unscoped

`f"{DOMAIN}_number_update"` carries no entry ID, so writing charge power on inverter A
wakes inverter B's entities. Same fix: include the entry ID in the signal name.

### [PROBLEM] Lines 71 and 146 — the watt entities' min/max are frozen at construction

If `technical_status` failed on the first refresh (it is an optional endpoint, and it is
unavailable to customer accounts), `_full_scale_power` falls back to
`DEFAULT_INVERTER_POWER_RATING = 3600` and a 6 kW inverter stays capped at 3600 W until
Home Assistant restarts — even though the rating arrives one minute later. Consider
computing the bounds in the `native_max_value` / `native_min_value` properties.

### [SUGGESTION] Lines 187-191 — dead defensive code

`async_setup_entry` unconditionally sets both `number_values` and `number_store` before
`async_add_entities`, so neither `hasattr` guard, nor the lazily-constructed `Store`
inside `async_set_native_value`, is reachable.

### [SUGGESTION] Line 163

`async_dispatcher_connect` callbacks run in the event loop, so `async_write_ha_state()`
is the idiomatic call rather than `schedule_update_ha_state()`.

---

## `custom_components/eaton_battery_storage/api.py`

### [PROBLEM] Lines 144 and 167 — transport failures are classified as auth failures

A non-JSON or otherwise unexpected sign-in response raises `EatonAuthError`, which both
`__init__.py:93` and `coordinator.py:101` catch *before* `EatonError` and turn into
`ConfigEntryAuthFailed`. An inverter serving an HTML page while rebooting, or a proxy
502, therefore raises a "reauthentication required" notification and asks the user for
credentials that were never wrong.

These two branches should raise `EatonConnectionError` (which becomes `UpdateFailed` /
`ConfigEntryNotReady`); reserve `EatonAuthError` for responses the device actually
identifies as credential failures.

### [SUGGESTION] Line 68 — document the empty-body contract of `_require_success`

`_require_success` treats the `{}` that `make_request` returns for an empty 2xx body as
a failure. `docs/device-api-behaviour.md` records that all three callers always return
`{"successful": true, ...}`, and `test_api.py` pins that expectation, so this is
currently correct. A one-line note that an empty body is deliberately a failure here
would help, since `set_device_power` deliberately bypasses `_require_success` for
exactly that reason.

### Verified as fine

The 401-retry at line 267 does send the refreshed token (`kwargs["headers"]` aliases the
mutated dict) and cannot loop. No credential or token is reachable by any `_LOGGER` call.

---

## `custom_components/eaton_battery_storage/config_flow.py`

### [PROBLEM] Line 227 — reauth does not check that it is still the same inverter

`_async_validate_input` returns the serial and the return value is discarded, then
`async_update_reload_and_abort` runs with no `self.async_set_unique_id(serial)` /
`self._abort_if_unique_id_mismatch()`. Because the reauth form exposes the whole schema
(host, serial, account type), a user can silently re-point an entry at a different
physical device while it keeps the old `unique_id` — the entity history of inverter A
then continues with inverter B's readings. This is the core convention for every reauth
flow and it undercuts `reauthentication-flow: done` in `quality_scale.yaml`.

### [SUGGESTION] Line 260 — the options flow is emulating a reconfigure flow

An `OptionsFlow` that writes to `entry.data` and aborts with `reconfigure_successful` is
a reconfigure flow in disguise. `quality_scale.yaml` honestly marks
`reconfiguration-flow: todo`, so this is a known gap, but `async_step_reconfigure` on the
`ConfigFlow` would remove the whole construct and the `CONF_EMAIL` re-injection that
exists only because `async_update_entry(data=...)` replaces the dict wholesale.

### Checked, not an issue

`HOST_PATTERN` cannot be used to inject a path, query, fragment or userinfo into
`f"https://{host}{endpoint}"`. It does accept `..` and ports above 65535, which are
harmless but could be tightened.

---

## `custom_components/eaton_battery_storage/sensor.py`

### [PROBLEM] Lines 858 and 866 — RAM sensors are labelled MB but computed in MiB

`native_value` divides by 1024², which yields mebibytes, so every reading is reported
about 4.9% low against its own unit. Use `UnitOfInformation.MEBIBYTES` (and the
`data_size` device class), or divide by 1000².
`EatonXStorageTechnicalInfoSensor.extra_state_attributes` has the same mismatch in
`system_ram_total_mb`.

### [PROBLEM] Line 1311 — the `cpuUsage` precision branch is unreachable

`maintenance_diagnostics.cpuUsage.used` carries `PERCENTAGE`, so the `== PERCENTAGE`
test at line 1306 returns 0 first. The intent (1 decimal) is also inconsistent with
`native_value` rounding CPU to 2 decimals.

### [SUGGESTION] Line 81 — `ZERO_IS_INVALID_KEYS` may suppress genuine zeroes

`bmsTotalCharge` / `bmsTotalDischarge` carry `state_class: TOTAL`; on a new battery 0 Ah
is a real reading and hiding it leaves the statistic unanchored. `gridFrequency` reading
0 Hz during a grid outage is arguably the single most interesting value that sensor can
report. If the device really only emits 0 as "no reading", a comment recording that
observation — as `docs/device-api-behaviour.md` does elsewhere — would justify it.

### [SUGGESTION] Line 199 — `SENSOR_TYPES` is an untyped `dict[str, dict[str, Any]]`

`binary_sensor.py:26` in the same integration already uses a frozen
`BinarySensorEntityDescription` subclass. A `SensorEntityDescription` subclass would give
mypy a chance to catch a misspelled `"device_class"` key (today it silently becomes
`None`) and would remove most of the `.get()` plumbing in `__init__`. This is the largest
file in the diff, so it is where the type safety would pay off most.

### [SUGGESTION] Raw string units and device classes

`"V"`, `"A"`, `"Hz"`, `"°C"`, `"mV"`, `"VA"`, `"kWh"`, `"Ah"`, `"h"`, `"power"`,
`"energy"`, `"voltage"` and so on, even though `UnitOfPower.WATT`,
`UnitOfEnergy.WATT_HOUR` and `PERCENTAGE` are imported and used in the same dict.
`UnitOfElectricPotential`, `UnitOfElectricCurrent`, `UnitOfFrequency`,
`UnitOfTemperature`, `UnitOfApparentPower`, `UnitOfTime` and `SensorDeviceClass` cover
all of them.

### [SUGGESTION] Line 1189 — unused `_has_pv` parameter

`EatonXStorageSensor.__init__` takes `_has_pv` and never uses it; `async_setup_entry`
still passes `has_pv`. Drop the parameter.

### [SUGGESTION] Line 182 — misleading comment on `DEVICE_CLASS_STATE_CLASSES`

The comment says the table mirrors Home Assistant's own, but core's maps each device
class to a *set of permitted* state classes, whereas this one picks a single default.
The comment reads as if the two are the same list and will mislead the next person
auditing for drift.

---

## `custom_components/eaton_battery_storage/coordinator.py`

### [SUGGESTION] Lines 122-123 — required endpoints fetched sequentially

The two required endpoints are awaited one after the other inside the dict literal while
the five optional ones run concurrently. Two serialized round trips per minute is minor,
but folding `get_status` / `get_device` into the same `gather` — keeping them in a
separate required group so their exceptions still propagate — is a small change.

### [SUGGESTION] Line 143 — `gather(return_exceptions=True)` swallows too much

The `isinstance(response, BaseException)` test swallows `EatonAuthError` and
`asyncio.CancelledError` alike, at debug level. A technician account downgraded to
customer would leave every `technical_status` / `maintenance_diagnostics` entity
permanently unknown with nothing above debug to explain it. Re-raising `EatonAuthError`
(and `CancelledError`) from the optional group would be cheap.

### Checked, not an issue

Setting failed optional sections to `{}` so entities report unknown while staying
available is exactly what the `entity-unavailable` rule asks for.

---

## `custom_components/eaton_battery_storage/event.py`

### [SUGGESTION] Line 86 — oversized `try`

The `try` wraps the whole loop and `_trigger_event`, catching
`KeyError, TypeError, AttributeError`. `_extract_alerts` already filters to dicts with a
non-empty alert id, so none of the three is reachable. `AGENTS.md` asks for the smallest
possible try-clause and no catching from functions that are not expected to raise.

### [SUGGESTION] Line 52 — O(n) membership test

`aid in self._seen` is a linear scan of a 500-element `deque` on every alert on every
refresh. Negligible at this scale, but a `set` alongside the deque, or an `OrderedDict`,
states the intent better.

---

## `system_health.py` and `manifest.json`

### [SUGGESTION] manifest.json line 6 — drop the `system_health` dependency

Every core integration shipping a `system_health.py` was checked (duco, spotify, ipma,
airly, isy994, cloud, network, gios, accuweather, lovelace): none declares it. The
platform is discovered, so the hard dependency only forces `system_health` to load.

### [SUGGESTION] system_health.py line 24 — only the first entry is reported

`next(...)` reports only the first loaded entry. Given how much effort the rest of this
diff spends on per-entry scoping, a second inverter silently vanishing from the health
panel is inconsistent; suffixing the keys per entry would cover it.

---

## `tests/`

Coverage is genuinely good — every module has a test file, the device is mocked at the
HTTP boundary so the real API client and coordinator are exercised, and the new PV
snapshot variant in `tests/test_entities.py` is exactly the kind of test that earns its
keep: it caught the `inverterNominalVpv` state class.

### [SUGGESTION] tests/conftest.py line 91 — misleading patch mechanics

**Correction:** an earlier draft of this review claimed the fixture was a redundant override of
one provided by `pytest_homeassistant_custom_component`. That is wrong, and removing it made
14 tests error with `fixture 'entity_registry_enabled_by_default' not found`. Core ships that
fixture in `tests/components/conftest.py`, which is not part of the custom-component package,
so a custom integration has to define its own.

The mechanics were still worth fixing: `patch(...)` replaced the
`entity_registry_enabled_default` property descriptor with a `MagicMock`, and attribute access
returned the mock object (truthy) without ever calling it, so `return_value=True` had no
effect. `new_callable=PropertyMock` makes it patch the property rather than shadow it.

---

## `quality_scale.yaml`

Most statuses hold up, and the `todo` / `exempt` comments are candid — the
`reconfiguration-flow` and `strict-typing` self-assessments are accurate. Three entries
are contradicted by the findings above:

- `action-setup: done` and `docs-actions: exempt` — the only registered action does not
  reload anything.
- `reauthentication-flow: done` — no `_abort_if_unique_id_mismatch` guard.
- `dependency-transparency: done` — `requirements` is empty and the client lives in-tree;
  this rule is about a published, versioned, licensed library, so `exempt` with a comment
  would be more accurate than `done`.

---

## Overall assessment: request changes

- [CRITICAL] `__init__.py:78` — `reload` action calls `async_reload_integration_platforms`,
  a YAML-platform helper; nothing is actually reloaded. Replace the handler with
  `asyncio.gather` over `hass.config_entries.async_reload(entry.entry_id)` for every
  `hass.config_entries.async_loaded_entries(DOMAIN)`, and drop the now-unused
  `homeassistant.helpers.reload` import.
- [CRITICAL] `number.py:74` — helper-value `Store` key omits the entry ID, so two
  inverters overwrite each other's power/duration/SOC settings.
- [PROBLEM] `number.py:157` — dispatcher signal is unscoped; cross-entry state writes.
- [PROBLEM] `number.py:146` — watt entity min/max frozen at construction; a 6 kW inverter
  stays capped at the 3600 W fallback if the rating arrives late.
- [PROBLEM] `api.py:144`, `api.py:167` — transient non-JSON/unexpected responses raise
  `EatonAuthError` and trigger a spurious reauth prompt; should be `EatonConnectionError`.
- [PROBLEM] `config_flow.py:227` — reauth never verifies the serial; an entry can be
  silently re-pointed at a different inverter.
- [PROBLEM] `sensor.py:858` — RAM sensors labelled `MB` but divided by 1024² (MiB),
  about 4.9% off.
- [PROBLEM] `sensor.py:1311` — `cpuUsage` precision branch unreachable behind the
  `PERCENTAGE` test.
- [SUGGESTION] `sensor.py:199` — convert `SENSOR_TYPES` to a `SensorEntityDescription`
  subclass; use `UnitOf*` / `SensorDeviceClass` constants instead of raw strings.
- [SUGGESTION] `sensor.py:81` — `ZERO_IS_INVALID_KEYS` hides a legitimate 0 Ah on a new
  battery and 0 Hz during a grid outage.
- [SUGGESTION] `sensor.py:1189` — unused `_has_pv` parameter.
- [SUGGESTION] `__init__.py:56` — derive `PV_SENSOR_KEYS` from the `pv_related` flags
  instead of maintaining a parallel list.
- [SUGGESTION] `coordinator.py:143` — `gather(return_exceptions=True)` swallows
  `EatonAuthError` and `CancelledError` from optional endpoints.
- [SUGGESTION] `coordinator.py:122` — the two required endpoints are fetched sequentially.
- [SUGGESTION] `event.py:86` — oversized `try` catching exceptions `_extract_alerts`
  already makes unreachable.
- [SUGGESTION] `manifest.json:6` / `system_health.py:24` — drop the `system_health`
  dependency; report all entries, not just the first.
- [SUGGESTION] `tests/conftest.py:91` — `entity_registry_enabled_by_default` patches a
  property with a plain `MagicMock`, so `return_value=True` is inert; use
  `new_callable=PropertyMock`. (The fixture itself is required, not redundant — see the
  correction above.)
- [SUGGESTION] `quality_scale.yaml` — `action-setup`, `reauthentication-flow` and
  `dependency-transparency` statuses are not supported by the code.
