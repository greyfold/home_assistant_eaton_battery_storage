"""Config flow for Eaton xStorage Home integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector as sel

from .api import EatonBatteryAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_INVERTER_SN = "inverter_sn"
CONF_HAS_PV = "has_pv"


class EatonXStorageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eaton xStorage Home."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> EatonXStorageOptionsFlow:
        """Create the options flow."""
        return EatonXStorageOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            inverter_sn = user_input[CONF_INVERTER_SN]
            # Hardcode the email address
            email = "anything@anything.com"

            # Set unique ID to prevent duplicates
            await self.async_set_unique_id(f"{host}_{inverter_sn}")
            self._abort_if_unique_id_configured()

            try:
                await self._test_connection(
                    host, username, password, inverter_sn, email
                )
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except ValueError as err:
                # Handle specific authentication error messages
                error_message = str(err)
                if "Error during authentication: 10" in error_message:
                    errors["base"] = "Error during authentication: 10"
                elif "wrong credentials" in error_message.lower():
                    errors["base"] = "err_wrong_credentials"
                elif "invalid inverter" in error_message.lower():
                    errors["base"] = "err_invalid_inverter_sn"
                elif "non-JSON response" in error_message:
                    errors["base"] = "Authentication failed: non-JSON response"
                elif "unexpected response" in error_message:
                    errors["base"] = "Authentication failed with unexpected response."
                else:
                    errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during connection test")
                errors["base"] = "unknown"
            else:
                # Save the hardcoded email in the config entry for consistency
                entry_data = dict(user_input)
                entry_data["email"] = email
                return self.async_create_entry(
                    title="Eaton xStorage Home", data=entry_data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): sel.TextSelector(),
                    vol.Required(CONF_USERNAME): sel.TextSelector(),
                    vol.Required(CONF_PASSWORD): sel.TextSelector(
                        sel.TextSelectorConfig(type=sel.TextSelectorType.PASSWORD)
                    ),
                    vol.Required(CONF_INVERTER_SN): sel.TextSelector(),
                    vol.Required(CONF_HAS_PV, default=False): sel.BooleanSelector(),
                }
            ),
            errors=errors,
        )

    async def _test_connection(
        self, host: str, username: str, password: str, inverter_sn: str, email: str
    ) -> None:
        """Test connection to the device."""
        api = EatonBatteryAPI(
            hass=self.hass,
            host=host,
            username=username,
            password=password,
            inverter_sn=inverter_sn,
            email=email,
            app_id="com.eaton.xstoragehome",
            name="Eaton xStorage Home",
            manufacturer="Eaton",
        )

        try:
            await api.connect()
        except ValueError as err:
            _LOGGER.warning("Authentication failed: %s", err)
            raise ValueError("Invalid credentials") from err
        except (ConnectionError, OSError) as err:
            _LOGGER.error("Connection failed: %s", err)
            raise ConnectionError("Cannot connect to device") from err
        except Exception as err:
            # Check if it's a connection-related error based on the message
            error_msg = str(err)
            if (
                "Cannot connect to host" in error_msg
                or "Connect call failed" in error_msg
            ):
                _LOGGER.error("Connection failed: %s", err)
                raise ConnectionError("Cannot connect to device") from err
            _LOGGER.error("Connection failed: %s", err)
            raise ConnectionError("Cannot connect to device") from err


class EatonXStorageOptionsFlow(OptionsFlow):
    """Handle options flow for Eaton xStorage Home."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Test connection with new credentials, use hardcoded email
                await self._test_connection(
                    user_input[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_INVERTER_SN],
                    "anything@anything.com",
                )
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except ValueError as err:
                # Handle specific authentication error messages
                error_message = str(err)
                if "Error during authentication: 10" in error_message:
                    errors["base"] = "Error during authentication: 10"
                elif "wrong credentials" in error_message.lower():
                    errors["base"] = "err_wrong_credentials"
                elif "invalid inverter" in error_message.lower():
                    errors["base"] = "err_invalid_inverter_sn"
                elif "non-JSON response" in error_message:
                    errors["base"] = "Authentication failed: non-JSON response"
                elif "unexpected response" in error_message:
                    errors["base"] = "Authentication failed with unexpected response."
                else:
                    errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during connection test")
                errors["base"] = "unknown"
            else:
                # Update the config entry with new data
                entry_data = dict(user_input)
                entry_data["email"] = "anything@anything.com"
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=entry_data
                )
                return self.async_create_entry(title="", data={})

        # Get current values from config entry
        current_data = self.config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=current_data.get(CONF_HOST, "")
                    ): sel.TextSelector(),
                    vol.Required(
                        CONF_USERNAME, default=current_data.get(CONF_USERNAME, "")
                    ): sel.TextSelector(),
                    vol.Required(
                        CONF_PASSWORD, default=current_data.get(CONF_PASSWORD, "")
                    ): sel.TextSelector(
                        sel.TextSelectorConfig(type=sel.TextSelectorType.PASSWORD)
                    ),
                    vol.Required(
                        CONF_INVERTER_SN, default=current_data.get(CONF_INVERTER_SN, "")
                    ): sel.TextSelector(),
                    vol.Required(
                        CONF_HAS_PV, default=current_data.get(CONF_HAS_PV, False)
                    ): sel.BooleanSelector(),
                }
            ),
            errors=errors,
        )

    async def _test_connection(
        self, host: str, username: str, password: str, inverter_sn: str, email: str
    ) -> None:
        """Test connection to the device."""
        api = EatonBatteryAPI(
            hass=self.hass,
            host=host,
            username=username,
            password=password,
            inverter_sn=inverter_sn,
            email=email,
            app_id="com.eaton.xstoragehome",
            name="Eaton xStorage Home",
            manufacturer="Eaton",
        )

        try:
            await api.connect()
        except ValueError as err:
            _LOGGER.warning("Authentication failed: %s", err)
            raise ValueError("Invalid credentials") from err
        except (ConnectionError, OSError) as err:
            # Handle connection errors - network issues, DNS, timeout, etc.
            error_str = str(err).lower()
            if any(
                conn_err in error_str
                for conn_err in [
                    "cannot connect",
                    "connect call failed",
                    "connection refused",
                    "timeout",
                    "unreachable",
                ]
            ):
                _LOGGER.warning("Connection failed to %s: %s", host, err)
                raise ConnectionError("Cannot connect to device") from err
            # Re-raise as generic error if not a clear connection issue
            _LOGGER.error("Unexpected error during connection: %s", err)
            raise Exception(f"Unexpected error: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected error during connection: %s", err)
            raise Exception(f"Unexpected error: {err}") from err
