# Version: 1.0.0
"""Configuration flow for the LSR integration.

This module handles the configuration flow for setting up the LSR integration,
including user authentication and options management.
"""

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
import voluptuous as vol
import aiohttp
import logging
import uuid
from typing import Any, Dict, Optional
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, NAMESPACE
from .api_client import authenticate

_LOGGER = logging.getLogger(__name__)

class LSRConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LSR integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                app_instance_id = str(uuid.uuid4()).replace("-", "")[:16]
                auth_data = await authenticate(aiohttp.ClientSession(), user_input[CONF_USERNAME], user_input[CONF_PASSWORD], app_instance_id)
                scan_interval_seconds = user_input.get("scan_interval_hours", DEFAULT_SCAN_INTERVAL // 3600) * 3600
                return self.async_create_entry(
                    title=f"ЛСР {user_input[CONF_USERNAME]}",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        "scan_interval": scan_interval_seconds,
                        "app_instance_id": app_instance_id,
                        "access_token": auth_data["accessToken"],
                        "refresh_token": auth_data.get("refreshToken"),
                        "account_id": auth_data.get("accountId"),
                    },
                )
            except aiohttp.ClientError as err:
                _LOGGER.error("Error connecting to API: %s", err)
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.error("Authentication failed: %s", str(err))
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional("scan_interval_hours", default=DEFAULT_SCAN_INTERVAL // 3600): vol.All(vol.Coerce(int), vol.Range(min=1)),
                }
            ),
            errors=errors,
            description_placeholders={"scan_interval_unit": "часов"},
        )

    @staticmethod
    @callback
    def async_get_option_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the option flow for this handler."""
        return LSROptionFlowHandler(config_entry)

class LSROptionFlowHandler(config_entries.OptionsFlow):
    """Handle option flow for LSR integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize option flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Manage the option."""
        if user_input is not None:
            scan_interval_seconds = user_input.get("scan_interval_hours", DEFAULT_SCAN_INTERVAL // 3600) * 3600
            return self.async_create_entry(title="", data={"scan_interval": scan_interval_seconds})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "scan_interval_hours",
                        default=self.config_entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL) // 3600,
                    ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                }
            ),
            description_placeholders={"scan_interval_unit": "часов"},
        )