# Version: 1.1.2
"""Config flow for LSR integration."""

import logging
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol
import uuid
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DOMAIN
from .api_client import authenticate

_LOGGER = logging.getLogger(__name__)

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
                data_schema=vol.Schema({
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_SCAN_INTERVAL, default=12): vol.Coerce(float),
                }),
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
                data_schema=vol.Schema({
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_SCAN_INTERVAL, default=12): vol.Coerce(float),
                }),
                errors=errors,
            )

    async def async_step_import(self, user_input=None):
        """Handle import from configuration.yaml."""
        if user_input is None:
            return self.async_abort(reason="not_supported")
        return await self.async_step_user(user_input)