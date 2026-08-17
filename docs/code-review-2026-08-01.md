# Code review — Eaton xStorage Home integration

**Date**: 2026-08-01
**Reviewed revision**: `main` @ `3ba945d` ("Bump minimum Home Assistant version to 2024.1.0")
**Reviewer**: GitHub Copilot (Claude Opus 5), acting as senior engineer reviewer

---

## What was used to perform this review

### Review instructions

The review followed the repository's own review prompt,
[.github/prompts/review-code-nikiforovall.prompt.md](../.github/prompts/review-code-nikiforovall.prompt.md),
which defines the focus areas (security, runtime correctness, performance, code
quality, maintainability), the required output structure, and the priority /
type emoji conventions used throughout this document.

Project coding standards were taken from three sources:

1. [AGENTS.md](../AGENTS.md) in this repository.
2. The Home Assistant **integrations skill**
   (`.claude/skills/integrations/SKILL.md` in `home-assistant/core`, mirrored
   into `.github/copilot-instructions.md` and `AGENTS.md`) — async I/O rules,
   exception-type selection, entity naming, unique-ID sourcing, device registry
   rules, coordinator patterns.
3. The Home Assistant **quality scale system**, verified directly against the
   machine validators in `script/hassfest/quality_scale_validation/` and the
   rule/tier table in `script/hassfest/quality_scale.py` of a checked-out
   `home-assistant/core` at branch `dev`, following the
   `ha-quality-scale-verify` skill.

### Scope

Three passes were performed:

1. **Delta review** of the changes on `main` since the merge of PR #28
   (`68986b0..HEAD`) — the work described by PR #32, "Fix system health crash,
   PV sensor migration, and cell-voltage precision".
2. **Whole-project review** of the full integration source.
3. **Quality scale verification** against Home Assistant core's own rule
   definitions and validators (Part 3).

Everything under `custom_components/eaton_battery_storage/` was read in full
(≈4,400 lines across 16 modules), plus `hacs.json`,
`.github/workflows/main.yml`, `quality_scale.yaml` and `services.yaml`.

### Commands and tooling used

| Purpose | Command / tool |
| --- | --- |
| Delta identification | `git diff --stat 68986b0..HEAD` |
| Delta inspection | `git --no-pager diff --no-prefix --unified=10 --minimal 68986b0..HEAD` |
| Repository state | `git log --oneline`, `git status --short`, `git branch -a` |
| Module sizing | `wc -l custom_components/eaton_battery_storage/*` |
| Cross-module fact checks | workspace text search (exact + regex) for `unique_id`, `load_token`, `ConfigEntryAuthFailed`, `PARALLEL_UPDATES`, `last_update_success_time`, `CellVoltage` |
| Source reading | full-file reads of every module in the component |
| Test / CI discovery | `find . -name "test_*.py" -o -name "conftest.py"`, inspection of `.github/workflows/main.yml` |
| Quality scale grounding | reads of `script/hassfest/quality_scale.py` (`ALL_RULES`, tier table, `validate_iqs_file`) and `script/hassfest/quality_scale_validation/*.py` in `home-assistant/core` |

No code was executed, no linter or test suite was run (none exist in the
repository — see finding 10), and no changes were made to the integration as
part of this review. Every finding below was verified by reading the source; no
finding is inferred from naming alone.

**Methodology note**: Parts 1 and 2 were produced using the general Home
Assistant integration guidelines only. Part 3 was added afterwards, when it
became clear that the quality scale rules had not been checked against core's
authoritative definitions. It is kept as a separate section rather than merged
backwards, so the provenance of each finding stays clear.

---

# Part 1 — Review of PR #32 (delta)

The change set is small and well-targeted:

- [coordinator.py](../custom_components/eaton_battery_storage/coordinator.py)
  switches to `TimestampDataUpdateCoordinator` so `last_update_success_time`
  exists (fixes an `AttributeError` in `system_health.py`).
- [__init__.py](../custom_components/eaton_battery_storage/__init__.py) resolves
  PV entities by `unique_id` instead of guessing the `entity_id` slug.
- [sensor.py](../custom_components/eaton_battery_storage/sensor.py) moves the
  cell-voltage precision rule ahead of the generic `voltage` rule.
- [number_constants.py](../custom_components/eaton_battery_storage/number_constants.py)
  adds the missing `default: NotRequired[int]` key.
- [hacs.json](../hacs.json) raises the minimum HA version to `2024.1.0`.

## 👍 Correct root-cause fix for the system health crash

* **Priority**: 🟢
* **File**: `custom_components/eaton_battery_storage/coordinator.py`
* **Details**: Using `TimestampDataUpdateCoordinator` instead of hand-rolling a
  `last_update_success_time` attribute is the idiomatic HA fix, and it is a
  drop-in superclass of `DataUpdateCoordinator`. Bumping the HACS minimum
  version alongside it is the right diligence.

## 🔧 System health still crashes when the entry is not loaded

* **Priority**: 🔥
* **File**: `custom_components/eaton_battery_storage/system_health.py`
* **Details**: The PR title claims the system health crash is fixed, but
  `entries[0].runtime_data` raises `AttributeError` whenever the first entry is
  disabled or in `SETUP_RETRY` — the exact situation in which a user opens the
  system health panel. It also arbitrarily picks `entries[0]` even though the
  config flow now supports multiple devices via per-device unique IDs.
* **Suggested change**:

  ```python
  entry = next(
      (
          e
          for e in hass.config_entries.async_entries(DOMAIN)
          if e.state is ConfigEntryState.LOADED
      ),
      None,
  )
  if entry is None:
      return {"device_reachable": False, "last_successful_update": "Never"}

  coordinator = entry.runtime_data
  ```

## 🔧 PV migration re-enables entities the user disabled on purpose

* **Priority**: ⚠️
* **File**: `custom_components/eaton_battery_storage/__init__.py`
* **Details**: `disabled_by=None if has_pv else er.RegistryEntryDisabler.INTEGRATION`
  unconditionally clears the disabled flag when `has_pv` is true. If a user
  manually disabled a PV sensor (`disabled_by=USER`), this silently re-enables
  it on every setup. Only the integration's own disablement should be cleared.
* **Suggested change**:

  ```python
  entry_obj = entity_registry.async_get(entity_id)
  if has_pv:
      if entry_obj.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
          entity_registry.async_update_entity(entity_id, disabled_by=None)
  elif entry_obj.disabled_by is None:
      entity_registry.async_update_entity(
          entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION
      )
  ```

## ♻️ The unique-ID format is now duplicated in two modules

* **Priority**: ⚠️
* **File**: `custom_components/eaton_battery_storage/__init__.py`
* **Details**: `f"{entry.entry_id}_{key.replace('.', '_')}"` is constructed here
  and independently in `sensor.py`. If either side ever changes, the migration
  silently becomes a no-op — there is no `else` branch, so nothing is logged
  when the lookup misses.
* **Suggested change** (in `const.py`, used by both):

  ```python
  def sensor_unique_id(entry_id: str, key: str) -> str:
      """Build the per-entry unique ID for a sensor key."""
      return f"{entry_id}_{key.replace('.', '_')}"
  ```

  …and add an `else: _LOGGER.debug("PV sensor not in registry: %s", sensor_key)`
  so a future mismatch is diagnosable.

## ♻️ Prefer declarative precision over substring matching on the key

* **Priority**: 🟡
* **File**: `custom_components/eaton_battery_storage/sensor.py`
* **Details**: The reorder is correct, but
  `"CellVoltage" in self._key or "VoltageDelta" in self._key` is order-dependent
  string matching that has already caused one bug — and the fix re-introduces
  the same class of fragility one rule higher. The class already supports
  `description.get("precision")` via `self._precision`, which is checked first
  and is explicit.
* **Suggested change**:

  ```python
  "technical_status.bmsHighestCellVoltage": {
      "name": "BMS Highest Cell Voltage",
      "unit": "mV",
      "device_class": "voltage",
      "precision": 0,
      "entity_category": EntityCategory.DIAGNOSTIC,
  },
  ```

## ❓ No migration for entities created before per-entry unique IDs

* **Priority**: 🟡
* **File**: `custom_components/eaton_battery_storage/__init__.py`
* **Details**: The lookup assumes every existing install already has
  `{entry_id}_{key}` unique IDs. For installs predating that change, the lookup
  returns `None` and the PV migration quietly does nothing — the same symptom
  this PR is fixing. Was an `async_migrate_entry` / `er.async_migrate_entries`
  pass considered, or is the pre-per-entry scheme confirmed to be unreleased?

## ⛏ `hacs.json` has no trailing newline

* **Priority**: 🟢
* **File**: `hacs.json`
* **Details**: The diff reports `\ No newline at end of file`. Worth fixing
  while touching the file so future diffs stay clean.

---

# Part 2 — Whole-project review

**Architecture**: a standard HA hub integration — `api.py` (aiohttp client +
bearer token), `coordinator.py` (`TimestampDataUpdateCoordinator`, 60 s polling,
fans out to ~11 endpoints), and seven entity platforms driven from a large
`SENSOR_TYPES` map. The shape is right and recent work (per-entry unique IDs,
`runtime_data`, redacted diagnostics) is solid. The issues below are
concentrated in the transport layer, the settings write path, and the complete
absence of tests.

## 1. 🔧 TLS certificate verification is disabled for every request, including the credential POST

* **Priority**: 🔥
* **File**: `custom_components/eaton_battery_storage/api.py`
* **Details**: `ssl=False` is passed to the sign-in request and hardcoded in
  `make_request`. The username, password and inverter serial are sent over a TLS
  channel with no certificate validation, and the bearer token is returned the
  same way — any host on the LAN segment can MITM and harvest inverter admin
  credentials (OWASP A02/A07). Worse, `async_get_clientsession(self.hass)`
  returns HA's *verifying* shared session and the per-request `ssl=False`
  silently overrides it, so the disablement is invisible at the session level.
* **Suggested change**: use HA's explicit non-verifying session so the choice is
  visible and centralized, and expose it as a user decision rather than a hidden
  default:

  ```python
  self._session = async_get_clientsession(hass, verify_ssl=verify_ssl)
  ...
  async with self._session.post(url, json=payload, timeout=...) as response:
  ```

  Add a `verify_ssl` option to the config flow (default `True`), and document
  that the device ships a self-signed certificate. If verification can never
  work, at minimum pin the certificate fingerprint via `aiohttp.Fingerprint`.

## 2. 🔧 Token storage key is built from unsanitized user input and is not domain-namespaced

* **Priority**: 🔥
* **File**: `custom_components/eaton_battery_storage/api.py`
* **Details**: `Store(hass, 1, f"{host}_token")` writes to `.storage/<host>_token`
  using a value typed by the user in the config flow with no validation. A host
  string containing `../` escapes the `.storage` directory; a host containing
  `/` breaks the write. It also collides across config entries on the same host,
  is not prefixed with the domain, and is never cleaned up on entry removal.
* **Suggested change**:

  ```python
  self.store = Store(hass, 1, f"{DOMAIN}.{entry_id}_token")
  ```

  and remove the file in `async_remove_entry`. Independently, validate `host` in
  the config flow with `vol.Match` or a `cv.url`-style check rather than a bare
  `TextSelector`.

## 3. 🔧 `load_token()` is dead code and `ConfigEntryAuthFailed` is never raised — the reauth flow is unreachable

* **Priority**: ⚠️
* **File**: `custom_components/eaton_battery_storage/api.py`
* **Details**: Two related gaps found by searching the whole component:
  1. `load_token` has no callers, so the token persisted by `store_token` is
     written on every auth and never read. Every restart triggers a fresh
     sign-in — the `Store` is pure overhead (and pure risk, per finding 2).
  2. `ConfigEntryAuthFailed` appears nowhere in the codebase.
     `async_step_reauth` / `async_step_reauth_confirm` are fully implemented in
     `config_flow.py` but nothing ever starts the flow — a changed password just
     produces `UpdateFailed` and entities go unavailable forever with no repair
     prompt. `quality_scale.yaml` marks `reauthentication-flow: done`, which is
     not accurate today.
* **Suggested change**: in `_async_update_data`, distinguish auth failure from
  connectivity failure:

  ```python
  except AuthenticationError as err:
      raise ConfigEntryAuthFailed(str(err)) from err
  except Exception as err:
      raise UpdateFailed(f"Error communicating with API: {err}") from err
  ```

  This needs `api.connect()` to raise a dedicated exception type instead of a
  generic `ValueError` — see finding 4.

## 4. 🔧 The API layer signals errors three different ways, and callers guess

* **Priority**: ⚠️
* **File**: `custom_components/eaton_battery_storage/api.py`
* **Details**: `connect()` raises `ValueError`/`ConnectionError`, while
  `make_request()` catches everything and returns
  `{"successful": False, "error": ...}`. The consequences ripple outward:
  `config_flow.py` has to classify failures by **substring-matching English
  error text** (`"wrong credentials" in ...`, `"Cannot connect to host" in ...`),
  which breaks the moment the firmware changes its wording or a locale differs.
  Callers then re-guess success with
  `result.get("successful", result.get("result") is not None)` — repeated
  verbatim in eight places across `switch.py`, `select.py`, `number.py` and
  `button.py`.
* **Suggested change**: define a small exception hierarchy in `api.py` and let
  it propagate:

  ```python
  class EatonError(HomeAssistantError): ...
  class EatonConnectionError(EatonError): ...
  class EatonAuthError(EatonError):
      def __init__(self, err_code: str, message: str) -> None:
          self.err_code = err_code  # classify on the code, not the prose
  ```

  `_classify_auth_error` then becomes a dict lookup on `err.err_code`, and the
  eight duplicated success checks collapse into "no exception means success".

## 5. 🔧 Concurrent settings writes silently overwrite each other

* **Priority**: ⚠️
* **File**: `custom_components/eaton_battery_storage/settings_helpers.py`
* **Details**: Five entities perform an unguarded read-modify-write of the
  *entire* settings document: both switches, both API-backed numbers, and the
  default-mode select. Each does `GET /api/settings` → mutate one field → `PUT`
  the whole object. Two automations firing in the same second (e.g. set backup
  level + enable energy saving) interleave their GETs and the second PUT reverts
  the first change — a classic lost update. With `PARALLEL_UPDATES` unset in
  `switch.py`/`select.py`, nothing serializes them.
* **Suggested change**: put the read-modify-write behind one coordinator-owned
  helper with a lock, and have every caller use it:

  ```python
  self._settings_lock = asyncio.Lock()

  async def async_patch_settings(self, mutate: Callable[[dict], None]) -> None:
      """Apply a mutation to the device settings atomically."""
      async with self._settings_lock:
          settings = await async_get_and_transform_settings(self.api)
          if settings is None:
              raise HomeAssistantError("Could not read current settings")
          mutate(settings)
          await self.api.update_settings({"settings": settings})
      await self.async_request_refresh()
  ```

  Then the energy-saving switch becomes ~4 lines instead of ~50, and
  `PARALLEL_UPDATES = 1` should be declared in `switch.py`, `select.py` and
  `button.py`.

## 6. 🔧 Every command handler sleeps 1–3 seconds inside the service call

* **Priority**: ⚠️
* **File**: `custom_components/eaton_battery_storage/switch.py`
* **Details**: `await asyncio.sleep(3)` (power switch), `sleep(2)` / `sleep(1)`
  (energy saving, both API numbers, both selects, stop-operation button) run on
  the service-call path. A script that turns the inverter on and then sets a
  mode stalls for 5+ seconds, and HA logs "Update of switch.x is taking over 10
  seconds" under load.
* **Suggested change**: replace the sleep + `async_request_refresh()` pair with a
  debounced or delayed refresh that does not block the caller:

  ```python
  await self.coordinator.api.set_device_power(True)
  self.async_write_ha_state()          # optimistic value already set
  async_call_later(self.hass, 3, lambda _now: self.coordinator.async_refresh())
  ```

## 7. 🔧 The coordinator serializes ~11 HTTP round trips every minute

* **Priority**: ⚠️
* **File**: `custom_components/eaton_battery_storage/coordinator.py`
* **Details**: `_async_update_data` awaits `get_status`, `get_device`, then five
  optional endpoints in a `for` loop, then two technical endpoints, then two
  notification endpoints — all sequentially. With a 15 s per-request timeout the
  worst case is ~165 s for a 60 s poll interval, so a degraded device produces
  permanently overlapping refreshes. HA's own guidance is explicit: *avoid
  awaiting in loops — use `gather` instead*.
* **Suggested change**: keep the two mandatory calls sequential (they gate
  `UpdateFailed`), then gather the rest:

  ```python
  optional = {
      "config_state": self.api.get_config_state,
      "settings": self.api.get_settings,
      "metrics": self.api.get_metrics,
      ...
  }
  responses = await asyncio.gather(
      *(fn() for fn in optional.values()), return_exceptions=True
  )
  for name, response in zip(optional, responses, strict=True):
      results[name] = {} if isinstance(response, Exception) else _unwrap(response)
  ```

## 8. 🔧 Device identity is keyed on the host, with a second identifier bolted on

* **Priority**: ⚠️
* **File**: `custom_components/eaton_battery_storage/coordinator.py`
* **Details**: `identifiers={(DOMAIN, self.api.host)}` uses an IP/hostname as the
  device identifier, which HA explicitly forbids (IPs, hostnames and URLs must
  never be used) — a DHCP lease change orphans the device and all its entities.
  The code then *adds* the serial as a second identifier, which does not fix the
  problem: the host tuple persists in the registry, and a device carrying two
  identifiers can absorb an unrelated entry later. The same weakness exists in
  the config entry unique ID, `f"{host}_{serial}"` — after an IP change, the same
  physical inverter can be added twice.
* **Suggested change**: use the serial as the sole identifier and fall back to
  `entry_id` only when the serial is genuinely unavailable; set the config entry
  `unique_id` to the bare serial and use
  `_abort_if_unique_id_configured(updates={CONF_HOST: host})` so a moved device
  updates its host instead of duplicating.

## 9. 🔧 `select.py` swallows every failure — the user never learns the command failed

* **Priority**: ⚠️
* **File**: `custom_components/eaton_battery_storage/select.py`
* **Details**: Both `async_select_option` implementations end in
  `except Exception as e: _LOGGER.error(...)` with no re-raise, so a failed mode
  change looks successful in the UI until the next poll reverts the dropdown.
  `current_option` goes further with a bare `except Exception: pass`, and
  `extra_state_attributes` in `event.py` does the same. This is the one platform
  that does *not* raise `HomeAssistantError`, unlike `switch.py` and `number.py`,
  so the inconsistency is likely an oversight rather than a decision.
* **Suggested change**: raise a translated error and drop the bare handlers:

  ```python
  except EatonError as err:
      raise HomeAssistantError(
          translation_domain=DOMAIN,
          translation_key="set_operation_mode_failed",
          translation_placeholders={"mode": option},
      ) from err
  ```

## 10. 🔧 No tests, and CI runs no linter or type checker

* **Priority**: ⚠️
* **File**: `.github/workflows/main.yml`
* **Details**: The repository has no test or quality tooling of any kind. A
  directory listing confirms all of the following are absent:

  | Expected | Present? |
  | --- | --- |
  | `tests/` directory, any `test_*.py`, any `conftest.py` | ❌ none |
  | `pyproject.toml` / `setup.cfg` | ❌ none |
  | `requirements_test.txt` / any requirements file | ❌ none |
  | `.ruff.toml` / ruff or pylint config | ❌ none |
  | `.pre-commit-config.yaml` | ❌ none |
  | CI job that executes integration code | ❌ none |

  The single workflow runs HACS validation and hassfest. Neither imports or
  executes a line of the integration — HACS validation checks repository
  structure and `hacs.json`, and hassfest checks manifest/translation metadata
  (and, per finding 14, skips quality scale validation entirely for custom
  components). Ruff, Pylint and MyPy are all absent despite being the standards
  this project's own `AGENTS.md` points at.

  The practical consequence: for a 4,400-line integration that writes to a
  battery inverter, **no automated check would catch a syntax error, an unused
  import, a broken type contract, or a regression in the settings PUT path**
  before it reaches users via HACS. Every finding in this review was found by
  reading, because there was no other way to find it. `quality_scale.yaml`
  already flags `config-flow-test-coverage: todo`, which is one of the five
  rules blocking the declared Bronze tier (finding 15).
* **Suggested change**: this is the highest-leverage item in the review, because
  it is what makes every other item safe to act on. A minimal viable setup:

  1. `requirements_test.txt` pinning `pytest-homeassistant-custom-component`,
     `ruff` and `mypy`.
  2. A `pyproject.toml` with ruff and mypy configuration.
  3. A CI job that actually runs them:

     ```yaml
     - run: pip install -r requirements_test.txt
     - run: ruff check custom_components/
     - run: mypy custom_components/eaton_battery_storage
     - run: pytest tests/ --cov=custom_components.eaton_battery_storage
     ```

  4. First tests targeting the highest-risk, lowest-effort surfaces: the config
     flow (Bronze requires 100 % coverage there) and
     `settings_helpers.transform_settings_for_put` (pure function, no mocking
     required).

  Adding step 3 alone — with zero tests written — already catches an entire
  class of defect on every pull request.

## 11. ♻️ Options flow writes twice and triggers two reloads

* **Priority**: 🟡
* **File**: `custom_components/eaton_battery_storage/config_flow.py`
* **Details**: `async_step_init` calls
  `async_update_entry(self.config_entry, data=entry_data)` — which fires the
  update listener, and therefore `async_update_options` →
  `async_migrate_pv_sensors` → `async_reload` — and then returns
  `async_create_entry(title="", data={})`, which writes empty options and fires
  the listener a second time. The entry reloads twice per settings save, racing
  the PV migration against platform teardown. Separately, the schema prefills
  `CONF_PASSWORD` with the stored password, sending the plaintext secret to the
  browser on every options/reauth form open; HA convention is to leave password
  fields empty.
* **Suggested change**: drop the `async_update_entry` call and let
  `async_create_entry(data=user_input)` write options normally, or keep the data
  write and return `self.async_abort(reason="reconfigure_successful")`. Also note
  `async_step_reauth`'s `entry_data` parameter is unused, and
  `EatonXStorageOptionsFlow.__init__` accepts a `config_entry` it deliberately
  discards — both can go.

## 12. ⛏ Smaller items worth batching

* **Priority**: 🟢
* **Details**:
  * `quality_scale.yaml` says
    `action-setup: exempt — Integration does not register custom service actions`,
    but `__init__.py` registers a `reload` service *inside* `async_setup_entry` —
    so it is re-registered per entry and never removed on unload. Move it to
    `async_setup` or drop it (HA provides reload natively).
  * `device_info` is annotated `-> dict[str, str]` in `switch.py` and `number.py`
    but returns `DeviceInfo`; elsewhere it is unannotated. `CoordinatorEntity` is
    used without its generic parameter everywhere except `sensor.py`, which
    discards `self.coordinator` typing across five platforms.
  * The `3600` watt full-scale conversion is hardcoded in six places in
    `number.py` — it should be a named constant, ideally derived from
    `technical_status.inverterPowerRating`.
  * `self._seen` in `event.py` grows without bound for the process lifetime;
    cap it (e.g. keep the last 500 alert IDs).
  * `services.yaml` contains only comments — either remove the file or the
    `action-setup` exemption becomes confusing.

## 13. 👍 What is working well

* **Priority**: 🟢
* **Details**: The accuracy caveat is documented at the top of `api.py`,
  `coordinator.py` and `sensor.py` *and* surfaced to users as an
  `accuracy_warning` state attribute — that is unusually honest engineering for a
  vendor-accuracy problem you cannot fix. `diagnostics.py` redacts the right set
  of fields including the nested `inverterSerialNumber`, `runtime_data` is used
  correctly instead of `hass.data`, and the recent move to per-entry unique IDs
  across all seven platforms was done consistently.

---

# Part 3 — Quality scale verification

This pass checks the integration against Home Assistant's Integration Quality
Scale as core actually defines and enforces it, rather than against the general
guidelines used in Parts 1 and 2. Every claim below is grounded in a specific
file in `home-assistant/core` (branch `dev`), cited inline.

`manifest.json` declares `"quality_scale": "bronze"` and the repository ships a
`quality_scale.yaml`, so the Bronze tier is being publicly asserted.

## 14. 🔧 Nothing validates the declared quality scale for a custom component

* **Priority**: 🔥
* **File**: `.github/workflows/main.yml`, `custom_components/eaton_battery_storage/quality_scale.yaml`
* **Details**: The CI workflow runs `home-assistant/actions/hassfest`, which
  looks like it validates the quality scale. It does not. `validate_iqs_file` in
  `script/hassfest/quality_scale.py` opens with:

  ```python
  def validate_iqs_file(config: Config, integration: Integration) -> None:
      """Validate quality scale file for integration."""
      if not integration.core:
          return
  ```

  Custom components return immediately. The declared Bronze tier is therefore
  entirely self-asserted, and every rule status in `quality_scale.yaml` is
  unverified by any automation. This is why findings 15–19 below have gone
  unnoticed.
* **Suggested change**: treat `quality_scale.yaml` as a manually maintained
  document and audit it on each release, or add a CI step that runs the core
  validators against the component path.

## 15. 🔧 The integration does not meet the Bronze tier it declares

* **Priority**: ⚠️
* **File**: `custom_components/eaton_battery_storage/quality_scale.yaml`
* **Details**: Five Bronze rules are marked `todo`: `brands`,
  `config-flow-test-coverage`, `docs-high-level-description`,
  `docs-installation-instructions`, `docs-removal-instructions`. Bronze requires
  **all** of its rules to be `done` or validly `exempt` — core enforces this in
  `quality_scale.py`:

  ```python
  required_rules = set(SCALE_RULES[scale])
  if missing_rules := (required_rules - rules_met):
      integration.add_error("quality_scale", f"...requires quality scale rules to be met:\n{...}")
  ```

  For a core integration this is a hard build failure.
* **Suggested change**: either complete the five rules or drop
  `"quality_scale": "bronze"` from `manifest.json` until they are done.
  `config-flow-test-coverage` is the only expensive one, and it is the same work
  as finding 10.

## 16. 🔧 The `action-setup` exemption is provably incorrect

* **Priority**: ⚠️
* **File**: `custom_components/eaton_battery_storage/quality_scale.yaml`, `custom_components/eaton_battery_storage/__init__.py`
* **Details**: The file states
  `action-setup: exempt — Integration does not register custom service actions`,
  but `__init__.py` calls `hass.services.async_register(DOMAIN, SERVICE_RELOAD, ...)`
  inside `async_setup_entry`. Core's validator
  (`script/hassfest/quality_scale_validation/action_setup.py`) detects exactly
  this shape — it walks `async_setup_entry` for any
  `hass.services.async_register` / `async_register_entity_service` call and
  reports *"Integration registers services in ... (async_setup_entry)"*.
  Registering per entry also means the service is re-registered for every
  config entry and never removed on unload.
* **Suggested change**: move the registration to `async_setup`, or drop it
  entirely — Home Assistant already provides reload for config-entry
  integrations. Then change the status from `exempt` to `done`.

## 17. 🔧 `parallel-updates` is unlisted and unmet across five platforms

* **Priority**: ⚠️
* **File**: `custom_components/eaton_battery_storage/`
* **Details**: `parallel-updates` is a Silver rule with its own validator
  (`quality_scale_validation/parallel_updates.py`) and is absent from
  `quality_scale.yaml`. Only `binary_sensor.py` and `number.py` declare
  `PARALLEL_UPDATES = 0`; `sensor.py`, `switch.py`, `select.py`, `button.py` and
  `event.py` declare nothing. This is not cosmetic — it is the missing guard
  that allows the concurrent settings writes described in finding 5.
* **Suggested change**: `PARALLEL_UPDATES = 0` on the read-only platforms
  (`sensor`, `binary_sensor`, `event`) and `PARALLEL_UPDATES = 1` on the
  command platforms (`switch`, `select`, `number`, `button`).

## 18. 🔧 `runtime-data` is marked done but fails the typed-entry requirement

* **Priority**: 🟡
* **File**: `custom_components/eaton_battery_storage/__init__.py`, `custom_components/eaton_battery_storage/diagnostics.py`
* **Details**: `quality_scale_validation/runtime_data.py` checks two things: that
  `async_setup_entry` assigns `entry.runtime_data` (the integration passes), and
  — once `strict-typing` is in play — that `async_setup_entry`,
  `async_unload_entry`, `async_migrate_entry` and
  `async_get_config_entry_diagnostics` are annotated with a custom
  `*ConfigEntry` alias matching `^[A-Za-z][A-Za-z0-9]+ConfigEntry$`.
  `__init__.py` and `diagnostics.py` both use a bare `ConfigEntry`; the alias
  exists only under `if TYPE_CHECKING` inside individual platform modules, where
  it is redefined five times.
* **Suggested change**: define the alias once in `coordinator.py` and import it
  everywhere:

  ```python
  type EatonConfigEntry = ConfigEntry[EatonXstorageHomeCoordinator]

  async def async_setup_entry(hass: HomeAssistant, entry: EatonConfigEntry) -> bool:
  ```

## 19. ⛏ `quality_scale.yaml` misfiles `diagnostics` and omits the whole Silver tier

* **Priority**: 🟢
* **File**: `custom_components/eaton_battery_storage/quality_scale.yaml`
* **Details**: `diagnostics` is listed under a `# Silver` comment, but it is a
  **Gold** rule per `ALL_RULES` in `quality_scale.py`. More importantly the
  Silver tier is almost entirely absent from the file: `action-exceptions`,
  `config-entry-unloading`, `docs-configuration-parameters`,
  `docs-installation-parameters`, `entity-unavailable`, `integration-owner`,
  `log-when-unavailable`, `parallel-updates` and `test-coverage` are all
  unlisted. Of these, `log-when-unavailable` has no implementation anywhere in
  the codebase — the coordinator logs an error on *every* failed refresh rather
  than once on loss and once on recovery.
* **Suggested change**: regenerate the file with every rule through the target
  tier listed explicitly as `done` / `todo` / `exempt`, and correct the tier
  comments. This is also the natural place to record finding 3 —
  `reauthentication-flow` is marked `done`, but the flow is unreachable because
  nothing raises `ConfigEntryAuthFailed`, so the status is aspirational rather
  than accurate.

---

# Summary

The integration is well-organized and the entity layer is idiomatic Home
Assistant, but three areas need attention before further feature work.

**Security first**: TLS verification is off for the credential exchange
(finding 1), and the token store key is derived from unvalidated user input
(finding 2). Both are small fixes with real exposure.

**Then the write path**: the settings read-modify-write is unserialized across
five entities (finding 5), errors are signalled three different ways and
classified by English substring matching (finding 4), and the reauth flow that
exists is unreachable because nothing raises `ConfigEntryAuthFailed`
(finding 3).

**Then the safety net**: with zero tests and no linting in CI (finding 10), none
of the above can be refactored with confidence. Adding
`pytest-homeassistant-custom-component` plus a ruff/mypy job is the
highest-leverage change in this list — it makes every other item on it safe to
do.

For PR #32 specifically, two items should be addressed before it is considered
complete: `system_health.py` still dereferences `runtime_data` on a
possibly-unloaded entry, so the advertised crash fix is incomplete; and the PV
migration will stomp on user-disabled entities.

**On the quality scale claim**: the Bronze badge in `manifest.json` is currently
unearned (finding 15) and unverifiable by CI (finding 14), and two rules marked
`done`/`exempt` are inaccurate (findings 16 and 3). Correcting
`quality_scale.yaml` is cheap and makes the remaining gap honest; earning Bronze
for real needs only the five `todo` rules, of which config flow test coverage is
the only substantial one.
