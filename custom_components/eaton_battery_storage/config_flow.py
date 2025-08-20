import logging
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN
from .api import EatonBatteryAPI

_LOGGER = logging.getLogger(__name__)


class EatonXStorageConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eaton xStorage Home."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        """Create the options flow."""
        return EatonXStorageOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            host = user_input["host"]
            username = user_input["username"]
            password = user_input["password"]
            inverter_sn = user_input["inverter_sn"]
            email = user_input["email"]
            has_pv = user_input["has_pv"]

            # Validate credentials using current API (customer login).
            # Technician fields are stored and used by the expanded API in a separate PR.
            api = EatonBatteryAPI(
                hass=self.hass,
                host=host,
                username=username,
                password=password,
                app_id="com.eaton.xstoragehome",
                name="Eaton xStorage Home",
                manufacturer="Eaton",
            )

            try:
                await api.connect()
                # Store all fields including technician details and has_pv for later use
                return self.async_create_entry(
                    title="Eaton xStorage",
                    data={
                        "host": host,
                        "username": username,
                        "password": password,
                        "inverter_sn": inverter_sn,
                        "email": email,
                        "has_pv": has_pv,
                    },
                )
            except ValueError as e:
                _LOGGER.warning(f"Authentication failed: {e}")
                errors["base"] = "auth"
            except Exception as e:
                _LOGGER.error(f"Unexpected error: {e}")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("host"): str,
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Required("inverter_sn"): str,
                    vol.Required("email"): str,
                    vol.Required("has_pv", default=False): bool,
                }
            ),
            errors=errors,
        )


class EatonXStorageOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Eaton xStorage Home."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        if user_input is not None:
            # Validate connection with current API (customer login) for now
            api = EatonBatteryAPI(
                hass=self.hass,
                host=user_input["host"],
                username=user_input["username"],
                password=user_input["password"],
                app_id="com.eaton.xstoragehome",
                name="Eaton xStorage Home",
                manufacturer="Eaton",
            )

            try:
                await api.connect()
                # Update the config entry with new data (including technician fields)
                self.hass.config_entries.async_update_entry(self.config_entry, data=user_input)
                return self.async_create_entry(title="", data={})
            except ValueError as e:
                _LOGGER.warning(f"Authentication failed: {e}")
                errors["base"] = "auth"
            except Exception as e:
                _LOGGER.error(f"Unexpected error: {e}")
                errors["base"] = "cannot_connect"

        # Get current values from config entry
        current = self.config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("host", default=current.get("host", "")): str,
                    vol.Required("username", default=current.get("username", "")): str,
                    vol.Required("password", default=current.get("password", "")): str,
                    vol.Required("inverter_sn", default=current.get("inverter_sn", "")): str,
                    vol.Required("email", default=current.get("email", "")): str,
                    vol.Required("has_pv", default=current.get("has_pv", False)): bool,
                }
            ),
            errors=errors,
        )