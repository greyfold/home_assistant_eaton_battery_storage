"""Config flow for Eaton xStorage Home integration."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector as sel

from .api import EatonAuthError, EatonBatteryAPI, EatonError
from .const import (
    ACCOUNT_TYPE_CUSTOMER,
    ACCOUNT_TYPE_TECHNICIAN,
    API_EMAIL,
    APP_ID,
    CONF_EMAIL,
    CONF_HAS_PV,
    CONF_INVERTER_SN,
    CONF_USER_TYPE,
    CONF_VERIFY_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Hostname, IPv4 address or bracketed IPv6 address, with an optional port.
HOST_PATTERN = re.compile(
    r"^(?:\[[0-9a-fA-F:]+\]|[A-Za-z0-9._-]+)(?::(?P<port>\d{1,5}))?$"
)

# Error codes reported by the device, mapped to translation keys.
AUTH_ERROR_CODES = {
    "10": "auth_error_locked",
}


async def _async_test_connection(
    hass: HomeAssistant,
    user_input: dict[str, Any],
) -> str | None:
    """Test the connection and return the inverter serial if the device reports it.

    Shared helper used by the user, reconfigure and reauth steps.
    """
    api = EatonBatteryAPI(
        hass=hass,
        host=user_input[CONF_HOST],
        username=user_input[CONF_USERNAME],
        password=user_input[CONF_PASSWORD],
        inverter_sn=user_input[CONF_INVERTER_SN],
        email=API_EMAIL,
        app_id=APP_ID,
        name="Eaton xStorage Home",
        manufacturer="Eaton",
        user_type=user_input[CONF_USER_TYPE],
        verify_ssl=user_input[CONF_VERIFY_SSL],
    )

    await api.connect()

    try:
        device = await api.get_device()
    except EatonError as err:
        _LOGGER.debug("Failed to retrieve device serial number: %s", err)
        return None

    result = device.get("result")
    return result.get("inverterSerialNumber") if isinstance(result, dict) else None


def _is_valid_host(host: str) -> bool:
    """Return True for a bare address or hostname with an optional usable port."""
    match = HOST_PATTERN.match(host)
    if match is None:
        return False
    port = match["port"]
    return port is None or 1 <= int(port) <= 65535


def _classify_auth_error(err: EatonAuthError) -> str:
    """Map an authentication failure to a translation error key."""
    if translation_key := AUTH_ERROR_CODES.get(err.err_code):
        return translation_key

    # Older firmware only reports a description, so fall back to its wording.
    message = err.message.lower()
    if "wrong credentials" in message:
        return "err_wrong_credentials"
    if "invalid inverter" in message:
        return "err_invalid_inverter_sn"
    return "invalid_auth"


def _build_user_schema(
    user_type: str = ACCOUNT_TYPE_CUSTOMER,
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build the data schema for user/options/reauth forms."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST, default=defaults.get(CONF_HOST, "")
            ): sel.TextSelector(),
            vol.Required(CONF_USER_TYPE, default=user_type): sel.SelectSelector(
                sel.SelectSelectorConfig(
                    options=[
                        sel.SelectOptionDict(
                            value=ACCOUNT_TYPE_CUSTOMER, label="Customer"
                        ),
                        sel.SelectOptionDict(
                            value=ACCOUNT_TYPE_TECHNICIAN, label="Technician"
                        ),
                    ],
                    mode=sel.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")
            ): sel.TextSelector(),
            # Never prefill the password: it would be sent to the browser.
            vol.Required(CONF_PASSWORD): sel.TextSelector(
                sel.TextSelectorConfig(type=sel.TextSelectorType.PASSWORD)
            ),
            vol.Optional(
                CONF_INVERTER_SN, default=defaults.get(CONF_INVERTER_SN, "")
            ): sel.TextSelector(),
            vol.Optional(
                CONF_HAS_PV, default=defaults.get(CONF_HAS_PV, False)
            ): sel.BooleanSelector(),
            vol.Optional(
                CONF_VERIFY_SSL,
                default=defaults.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            ): sel.BooleanSelector(),
        }
    )


async def _async_validate_input(
    hass: HomeAssistant, user_input: dict[str, Any], errors: dict[str, str]
) -> str | None:
    """Validate the form input, filling errors and returning the device serial."""
    if not _is_valid_host(user_input[CONF_HOST]):
        errors[CONF_HOST] = "invalid_host"
        return None

    if (
        user_input[CONF_USER_TYPE] == ACCOUNT_TYPE_TECHNICIAN
        and not user_input[CONF_INVERTER_SN]
    ):
        errors[CONF_INVERTER_SN] = "required_inverter_sn"
        return None

    try:
        return await _async_test_connection(hass, user_input)
    except EatonAuthError as err:
        errors["base"] = _classify_auth_error(err)
    except EatonError as err:
        _LOGGER.debug("Connection test failed: %s", err)
        errors["base"] = "cannot_connect"
    return None


class EatonXStorageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eaton xStorage Home."""

    VERSION = 2
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step (single-step flow with conditional validation)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            serial = await _async_validate_input(self.hass, user_input, errors)
            unique_id = serial or user_input[CONF_INVERTER_SN]
            if not errors and not unique_id:
                # The host is the only other candidate and it moves with DHCP,
                # which would orphan every entity. Better to ask for a retry.
                errors["base"] = "unknown_serial"
            if not errors:
                host = user_input[CONF_HOST]
                # Key the entry on the serial so a device that moves to another
                # address updates its host instead of being added a second time.
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})

                return self.async_create_entry(
                    title="Eaton xStorage Home",
                    data={**user_input, CONF_EMAIL: API_EMAIL},
                )

        defaults = user_input or {}

        return self.async_show_form(
            step_id="user",
            data_schema=_build_user_schema(
                user_type=defaults.get(CONF_USER_TYPE, ACCOUNT_TYPE_CUSTOMER),
                defaults=defaults,
            ),
            errors=errors,
        )

    async def async_step_reauth(self, _entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauth when credentials expire."""
        return await self.async_step_reauth_confirm()

    async def _async_check_identity(
        self, entry: ConfigEntry, serial: str | None
    ) -> None:
        """Refuse a flow that points the entry at a different inverter."""
        if not serial or serial == entry.unique_id:
            return
        if entry.unique_id == entry.data[CONF_HOST]:
            # Entries created before the serial was readable were keyed on the
            # host; this is the only chance to give them a stable identity.
            return
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_mismatch()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation step."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            serial = await _async_validate_input(self.hass, user_input, errors)
            if not errors:
                await self._async_check_identity(reauth_entry, serial)
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    unique_id=serial or reauth_entry.unique_id,
                    data_updates={**user_input, CONF_EMAIL: API_EMAIL},
                )

        defaults = user_input or dict(reauth_entry.data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_build_user_schema(
                user_type=defaults.get(CONF_USER_TYPE, ACCOUNT_TYPE_CUSTOMER),
                defaults=defaults,
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the connection settings of an existing entry."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            serial = await _async_validate_input(self.hass, user_input, errors)
            if not errors:
                await self._async_check_identity(reconfigure_entry, serial)
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    unique_id=serial or reconfigure_entry.unique_id,
                    data_updates={**user_input, CONF_EMAIL: API_EMAIL},
                )

        defaults = user_input or dict(reconfigure_entry.data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_user_schema(
                user_type=defaults.get(CONF_USER_TYPE, ACCOUNT_TYPE_CUSTOMER),
                defaults=defaults,
            ),
            errors=errors,
        )
