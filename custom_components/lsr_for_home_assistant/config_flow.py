# Version: 1.3.0
# pylint: disable=import-error,wrong-import-order,ungrouped-imports,mixed-line-endings,too-few-public-methods
"""Config flow for LSR integration."""

import uuid
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import selector

from .const import DOMAIN
from .api_client import authenticate

_LOGGER = logging.getLogger(__name__)

def _build_user_schema(default_scan_interval=12):
    return vol.Schema({
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=default_scan_interval): selector({
            "number": {
                "min": 1,
                "max": 12,
                "step": 1,
                "mode": "box",
                "unit_of_measurement": "ч",
            }
        }),
    })

async def validate_input(hass: HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    try:
        login = data[CONF_USERNAME].lstrip("+")
        password = data[CONF_PASSWORD]
        app_instance_id = str(uuid.uuid4().hex[:16])
        auth_data = await authenticate(session, login, password, app_instance_id)
        if auth_data.get("accessToken"):
            return {"title": data[CONF_USERNAME]}
        raise ValueError("Invalid credentials")
    except (ValueError, ConfigEntryAuthFailed) as err:
        _LOGGER.error("Validation error: %s", str(err))
        raise

class LSRConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LSR integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=_build_user_schema(12),
                errors={},
            )

        errors = {}
        try:
            info = await validate_input(self.hass, user_input)
            return self.async_create_entry(title=info["title"], data=user_input)
        except (ValueError, ConfigEntryAuthFailed):
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
            return self.async_show_form(
                step_id="user",
                data_schema=_build_user_schema(12),
                errors=errors,
            )

    async def async_step_import(self, user_input=None):
        """Handle import from configuration.yaml."""
        if user_input is None:
            return self.async_abort(reason="not_supported")
        return await self.async_step_user(user_input)

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return LSROptionsFlow(config_entry)


class LSROptionsFlow(config_entries.OptionsFlow):
    """Handle LSR options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self._config_entry.data.get(CONF_SCAN_INTERVAL, 12),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_SCAN_INTERVAL, default=current): selector({
                    "number": {
                        "min": 1,
                        "max": 12,
                        "step": 1,
                        "mode": "box",
                        "unit_of_measurement": "ч",
                    }
                }),
            }),
        )
