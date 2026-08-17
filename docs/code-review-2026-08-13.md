# Code review — 13 August 2026

Reviewed against the Home Assistant integration guidance and the integration
quality scale rules. Test suite is green at the time of review: 166 passed, 404
snapshots.

Working well: coordinator plus `runtime_data`, reauthentication flow, config
entry migration, `PARALLEL_UPDATES` declared on every platform, translated
exceptions, and tests that mock at the HTTP boundary rather than patching
internals.

## Bugs

### 1. The `reload` action does nothing

`__init__.py` calls `async_reload_integration_platforms`, which only re-reads
`configuration.yaml` and re-sets-up YAML platforms — its docstring names
template, stats and derivative. A config entry integration has no YAML platform
config, so the handler re-parses YAML and returns without touching anything.

It should iterate the domain's entries and call
`hass.config_entries.async_reload(entry.entry_id)`.

This also invalidates the `docs-actions: exempt` reasoning in
`quality_scale.yaml`, which claims the integration only registers "the standard
reload action".

### 2. Number helper state is global, not per config entry

The store key `f"{DOMAIN}_number_values.json"` and the dispatcher signal
`f"{DOMAIN}_number_update"` in `number.py` both omit the entry ID. Two inverters
share a single charge/discharge power file and cross-trigger each other's state
writes.

The store is also never cleaned up: `async_remove_entry` removes the token store
only.

### 3. `coordinator.number_values` is a race

It is declared as a class annotation on the coordinator but assigned by the
number platform's `async_setup_entry`. Platforms are forwarded concurrently, so
`select.py` reads `getattr(..., "number_values", {})` and can silently fall back
to hardcoded defaults (power 15, SOC 90) for a Manual Charge issued right after
startup.

Load the store and populate both attributes in `async_setup_entry` before
`async_forward_entry_setups`, then drop the `hasattr`/`getattr` guards in
`number.py`.

### 4. System health reports the wrong device

`system_health.py` takes the first loaded entry, so with two inverters one is
invisible and the panel silently shows the other's host and update time.

### 5. The unique ID falls back to the host

`async_step_user` in `config_flow.py` keys the entry on
`serial or inverter_sn or f"{host}_{username}"`. The comment above it states the
intent correctly — key on the serial so a device that moves address updates its
host rather than being added twice — but the third branch defeats it.

Home Assistant guidance is that a unique ID must be stable for the lifetime of
the device and must never be derived from network configuration: IP addresses,
hostnames, URLs, MAC addresses of the host, or anything else the user can change
without replacing the hardware. A DHCP lease change silently orphans every
entity and the device, and the user cannot recover the history.

The rest of the codebase already treats the host as unusable for identity. The
1 to 1.2 migration in `__init__.py` exists solely to strip a `{host}_` prefix
from unique IDs written by older versions, and `coordinator.device_info` carries
an explicit comment saying never to key the device on an IP or hostname. The
config flow is the one place that can still write a host-based ID, so the
migration is undone by the next fresh install that fails to read a serial.

A full audit of where the host reaches an identity value found two paths, and
only two. Everything else that touches the host is legitimate: the API base URL
in `api.py`, `configuration_url` in `device_info`, and `api_host` in the system
health panel are all display or transport, not identity. Entity unique IDs are
built from `entry_id`, and device identifiers fall back to `entry_id` rather
than the host.

**Path one, new installs.** The `f"{host}_{username}"` fallback described above.

**Path two, legacy entries.** The migration only strips a `{host}_` *prefix*.
When the old unique ID is the bare host, `__init__.py` logs a debug message and
leaves it, with the comment "the host stays until reauth". Reauthentication does
not in fact repair it: `async_step_reauth_confirm` calls
`async_update_reload_and_abort` without passing `unique_id`, so nothing ever
rewrites the value. Those entries keep an IP-based unique ID permanently. Since
reauth re-reads the device anyway, passing the serial through at that point
would close the gap.

While in there, reauth also never calls `_abort_if_unique_id_mismatch`, so
re-authenticating an entry against a different inverter silently keeps the old
serial.

The serial is read: `_async_test_connection` calls `GET /api/device` and returns
`inverterSerialNumber`. The fallback is reached only when that call raises,
because the `except EatonError` around it logs at debug level and returns `None`
rather than surfacing the failure. `test_user_flow_survives_unreadable_serial`
covers exactly this path and asserts `unique_id == f"{HOST}_user"`, so the
behaviour is currently pinned by a test rather than being an oversight. That
test needs to change with the code.

That path is not worth preserving. The coordinator treats the same endpoint as
required data — `_async_fetch_all` wraps it in `_unwrap_required`, and a failure
becomes `UpdateFailed` and therefore `ConfigEntryNotReady`. So an entry created
through the fallback either never loads at all, or loads a minute later once the
endpoint recovers, at which point the real serial was available and could have
been used. A host-based unique ID is never the correct outcome.

Treating an unreadable serial as `cannot_connect` and asking the user to retry
is both simpler and more honest: authentication has already succeeded at that
point, so `/api/device` failing immediately afterwards is transient, and the
integration cannot function without it regardless.

Concretely, the recommendation is to delete the `f"{host}_{username}"` branch
outright, leaving `serial or inverter_sn`. Both of those are hardware identity —
the serial the device reports, or the one the user typed in, which technician
accounts already require — and neither changes when the device moves address.
When both are empty, fail the step with `cannot_connect` instead of inventing an
identifier.

## Quality scale gaps

### 6. `entity-translations` is marked done but selects are not translatable

`DEFAULT_MODE_OPTIONS` in `select.py` uses display strings (`"Basic Mode"`) as
the option values. With a `translation_key` set, options must be snake_case keys
backed by an `entity.select.<key>.state.*` block in `strings.json`, which
currently defines only `name`.

Changing the option values is a breaking change for existing automations, so it
needs to be done deliberately.

### 7. `manifest.json` should not depend on `system_health`

No core integration lists it in `dependencies`; the platform is discovered via
`async_process_integration_platforms`. Drop it, or use `after_dependencies`.

### 8. `sensor.py` does not use entity descriptions

`SENSOR_TYPES` is a dict of dicts with raw device class strings, a hand
maintained `DEVICE_CLASS_STATE_CLASSES` copy of the core mapping, and a
`suggested_display_precision` if-chain. `binary_sensor.py` already uses the
frozen dataclass description pattern correctly.

Migrating to `SensorEntityDescription` with the `SensorDeviceClass` and
`SensorStateClass` enums removes the parallel mapping and restores type
checking.

### 9. `PV_SENSOR_KEYS` duplicates the `pv_related` flags

All 14 keys currently match the `pv_related: True` entries in `SENSOR_TYPES`,
but nothing enforces that and the two lists live in different files. Derive the
list from `SENSOR_TYPES`.

### 10. Over-broad exception handling

Several properties wrap their entire body in
`except (KeyError, TypeError, AttributeError)` — the notifications and latest
notification sensors in `sensor.py`, and `_handle_coordinator_update` in
`event.py` — around pure `.get()` chains that cannot raise. This contradicts the
"smallest possible try-clause" rule and hides real errors.

### 11. Recorder pressure

The notifications sensor stores the full alert list in attributes and the info
sensors store static fields. Consider `_unrecorded_attributes` so these are not
written to the database on every state change.

## Security and privacy

### 12. `strings.json` ships the vendor default technician password

The config flow `data_description` includes `admin/jlwgK41G`. Even though it is a
documented default, embedding credentials in the UI normalises it and puts them
into every translation export. A documentation link is preferable.

`verify_ssl` defaulting to off is fine and well explained given the self-signed
certificate.

## Minor

- `# pylint: disable=unexpected-keyword-arg` is repeated on every binary sensor
  description; fix it once through configuration instead.
- `_handle_external_update` uses `schedule_update_ha_state()`;
  `async_write_ha_state()` is the direct equivalent in a dispatcher callback.

## Suggested order

Items 1 to 5 are behavioural bugs and are all small, self-contained changes.
Item 5 also requires rewriting `test_user_flow_survives_unreadable_serial`,
which currently asserts the behaviour being removed, and covers two paths that
need fixing together — fixing only the config flow leaves existing IP-keyed
entries stranded.
