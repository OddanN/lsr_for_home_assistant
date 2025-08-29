# Version: 1.0.3
"""Custom component for LSR integration, managing data updates and authentication."""

from datetime import timedelta
import logging
import uuid
import re
import asyncio
from typing import Dict, List
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN
from .api_client import authenticate, get_accounts, get_account_data, get_cameras, get_communal_requests, get_meters, get_meter_history, get_camera_stream_url

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(hours=12)

class LSRDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching LSR data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        self.session = async_get_clientsession(hass)
        self.access_token = None
        self.refresh_token = None
        self.accounts = []
        self.app_instance_id = str(uuid.uuid4().hex[:16])
        scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        if isinstance(scan_interval, (int, float)):
            scan_interval = timedelta(hours=scan_interval)
        _LOGGER.debug("Scan interval: %s", scan_interval)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=scan_interval)

    async def _async_update_data(self) -> Dict:
        """Update data via API."""
        try:
            await self._authenticate()
            accounts_data = await get_accounts(self.session, self.access_token)
            detailed_data = {}
            for account in accounts_data:
                account_id = account["objectId"]["id"]
                account_data = await get_account_data(self.session, self.access_token, account_id)
                communal_requests = await get_communal_requests(self.session, self.access_token, account_id)
                cameras_data = await get_cameras(self.session, self.access_token, account_id)
                meters_data = await get_meters(self.session, self.access_token, account_id)

                # Fetch meter history
                meters_history = {}
                for meter in meters_data:
                    meter_id = meter["objectId"]["id"]
                    history_items = await get_meter_history(self.session, self.access_token, meter_id)
                    history_dict = {}
                    for history_item in history_items:
                        if history_item["value1"]["value"]:
                            date_str = history_item["dateList"]
                            value = float(history_item["value1"]["value"].replace(",", "."))
                            history_dict[date_str] = value
                    last_value_raw = meter.get("lastMeterValue", {}).get("listValue")
                    last_date = meter.get("lastMeterValue", {}).get("dateList")
                    if last_value_raw and last_date:
                        history_dict[last_date] = float(last_value_raw.replace(",", "."))
                    meters_history[meter_id] = {
                        "title": meter["objectId"]["title"],
                        "type_id": meter["type"]["id"],
                        "type_title": meter["type"]["title"],
                        "history": sorted([(date_str, value) for date_str, value in history_dict.items()], key=lambda x: datetime.strptime(x[0], "%d.%m.%Y"))
                    }

                # Fetch camera stream URLs
                headers = {"Authorization": f"Bearer {self.access_token}"}
                tasks = [self._get_camera_stream_url(camera, headers) for camera in cameras_data]
                await asyncio.gather(*tasks)

                address = account_data.get("optionalObject", {}).get("rows", [{}])[0].get("cells", [{}])[0].get("value", "Unknown")
                address = re.search(r"Л/с №(\d+)", address).group(1) if address and re.search(r"Л/с №(\d+)", address) else "Unknown"
                if not address or address.strip() == "":
                    _LOGGER.warning("Address for account %s is empty or invalid, setting to 'Unknown'", account_id)
                    address = "Unknown"
                detailed_data[account_id] = {
                    "id": account_id,
                    "address": address,
                    "payment_status": self._extract_payment_status(account_data.get("optionalObject", {})),
                    "number": account["objectId"]["title"],
                    "notification_count": account_data.get("notificationCount", 0),
                    "camera_count": len(cameras_data),
                    "cameras": cameras_data,
                    "accruals": account_data.get("items", []),  # Данные начислений
                    "communal_requests": communal_requests,  # Данные коммунальных запросов
                    "meters": meters_history  # Данные метров и их истории
                }
            _LOGGER.debug("Fetched data: %s", detailed_data)
            return detailed_data
        except Exception as err:
            _LOGGER.error("Error communicating with API: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def _authenticate(self) -> None:
        """Authenticate and get access token."""
        max_attempts = 5
        attempt = 1

        while attempt <= max_attempts:
            try:
                login = self.entry.data[CONF_USERNAME].lstrip("+")
                password = self.entry.data[CONF_PASSWORD]
                auth_data = await authenticate(self.session, login, password, self.app_instance_id)
                self.access_token = auth_data["accessToken"]
                self.refresh_token = auth_data["refreshToken"]
                _LOGGER.debug("Authentication successful, access_token: %s, refresh_token: %s", self.access_token, self.refresh_token)
                break
            except Exception as err:
                _LOGGER.error("Authentication error: %s", str(err))
                if attempt == max_attempts:
                    _LOGGER.error("Max retry attempts reached, giving up.")
                    raise ConfigEntryAuthFailed(f"Authentication error after {max_attempts} attempts: {err}")
                _LOGGER.warning("Retrying authentication (attempt %d of %d) in 15 seconds...", attempt, max_attempts)
                await asyncio.sleep(15)
                attempt += 1

    @staticmethod
    def _extract_payment_status(title_custom_fields: Dict) -> str:
        """Extract payment status from titleCustomFields.

        Args:
            title_custom_fields (dict): The dictionary containing custom fields from the API response.

        Returns:
            str: The extracted payment status or 'Unknown' if not found.
        """
        for row in title_custom_fields.get("rows", []):
            if row.get("isVisible") is True:
                value = row["cells"][0]["value"]
                match = re.search(r'<span[^>]*>(.*?)</span>', value)
                if match:
                    return match.group(1).strip()
                return value.strip()
        return "Unknown"

    async def _get_camera_stream_url(self, camera: Dict, headers: Dict) -> None:
        """Fetch stream URL for a single camera asynchronously."""
        await get_camera_stream_url(self.session, camera, headers)