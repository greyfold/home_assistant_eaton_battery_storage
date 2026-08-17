# Quality scale verification — 2026-08-16

Audit of every entry in `custom_components/eaton_battery_storage/quality_scale.yaml` against the
official rule documentation in
[developers.home-assistant.io](https://github.com/home-assistant/developers.home-assistant/tree/master/docs/core/integration-quality-scale/rules),
the integration source, and a real test run.

Rules already marked `todo` (`brands`, `docs-data-update`, `docs-examples`, `docs-supported-devices`,
`docs-use-cases`, `icon-translations`, `strict-typing`) were not re-litigated; only their comments
were checked for factual accuracy.

## Finding: `test-coverage` (Silver) is marked `done` but one module is below 95%

`python3 -m pytest tests/ --cov=custom_components.eaton_battery_storage --cov-report=term-missing`
gives 175 passed, 404 snapshots, **98% total**. Every module clears 95% except one:

| Module | Coverage | Missing lines |
| --- | --- | --- |
| `select.py` | **94%** | 104, 106, 110-115, 168, 183 |

The uncovered lines are:

- `_build_parameters` — the `SET_PEAK_SHAVING` fallback when `houseConsumptionThreshold` is missing
  or non-numeric, the `SET_VARIABLE_GRID_INJECTION` branch, and the whole
  `SET_FREQUENCY_REGULATION` branch including the `batteryBackupLevel` fallback.
- `_command_duration` — the `SET_DISCHARGE` branch.
- `_command_parameters` — the `SET_DISCHARGE` branch.

The rule states "There are no exceptions to this rule", so this cannot be downgraded to `exempt`.

**To close it:** add parametrized cases to `tests/test_select.py` that select the *Peak shaving*,
*Variable grid injection*, *Frequency regulation* and *Discharge* options and assert the command
payload sent to the API — including a peak-shaving case where
`settings["energySavingMode"]["houseConsumptionThreshold"]` is absent, and a frequency-regulation
case where `bmsBackupLevel` is absent so the `batteryBackupLevel` fallback is exercised.

## Claims re-checked and confirmed correct

These entries looked questionable on a first pass but hold up against the rule text. They are
recorded here so the same ground is not covered again in a later audit.

- **`entity-event-setup: done`** — `number.py` subscribes with `async_dispatcher_connect` inside
  `async_added_to_hass`, wrapped in `async_on_remove`. That is the simplified pattern the rule
  documents. The rule allows no exemptions, so re-marking it `exempt` because the integration is
  poll-based would be wrong.
- **`docs-configuration-parameters: done`** — the rule allows no exemptions. There is no options
  flow, so there are no configuration options left undocumented.
- **`async-dependency: done` / `inject-websession: done`** — `api.py` is fully async aiohttp and
  takes its session from `async_get_clientsession(hass, verify_ssl=...)`. `inject-websession` is
  only exempt when the integration makes no HTTP requests, which is not the case here. Having an
  empty `requirements` list does not make either rule inapplicable.
- **`action-setup: done` / `docs-actions: done`** — the `reload` action is registered once in
  `async_setup` through `async_register_admin_service`, declared in `services.yaml`, translated in
  `strings.json`, and documented in `README.md`.
- **`brands: todo`** — the comment is accurate. Core resolves `Path(integration.file_path) / "brand"`
  for custom integrations in `homeassistant/components/brands/__init__.py`, so a local `brand/`
  folder is genuinely all that is required now.
- All Gold `done` and `exempt` entries verified with no issues.
