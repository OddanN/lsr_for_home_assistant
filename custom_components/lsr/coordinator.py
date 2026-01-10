# Version: 1.1.2
"""Custom component for LSR integration, managing data updates and authentication."""

from datetime import timedelta, datetime
import logging
import uuid
import re
import asyncio
from typing import Dict
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, NAMESPACE
from custom_components.lsr.api_client import authenticate, get_accounts, get_account_data, get_cameras, get_communal_requests, get_meters, get_meter_history, get_camera_stream_url

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
            _LOGGER.debug("accounts_data: %s", accounts_data)
            detailed_data = {}
            for account in accounts_data:
                _LOGGER.debug("account: %s", account)
                account_id = account["objectId"]["id"]

                # Сохраняем важные поля из списка аккаунтов
                original_data = {
                    "notification_count": account.get("notificationCount", 999),
                }

                # Извлекаем адрес и л/с прямо здесь
                try:
                    addr_match = re.search(
                        r'<span[^>]*>(.*?)</span>',
                        account["customFields"]["rows"][0]["cells"][0]["value"],
                        re.DOTALL
                    )
                    ls_match = re.search(r"Л/с №(\d+)", account["objectId"]["title"])
                    
                    parsed_address = addr_match.group(1).strip() if addr_match else "Адрес не распознан"
                    parsed_personal_account = ls_match.group(1) if ls_match else "Л/с не найден"
                    
                    _LOGGER.debug("Извлечено в цикле: Адрес=%s | Л/с=%s", parsed_address, parsed_personal_account)
                
                except Exception as e:
                    _LOGGER.warning("Ошибка парсинга адреса/л/с для %s: %s", account_id, e)
                    parsed_address = "Ошибка"
                    parsed_personal_account = "Ошибка"

                account_data = await self.async_fetch_account_data(account_id, include_cameras=True, include_main_pass=True, include_guest_passes=True)
                
                # Добавляем сохранённые поля в результат
                account_data.update(original_data)

                # Добавляем спарсенные значения в результат
                account_data["address"] = parsed_address
                account_data["personal_account"] = parsed_personal_account
                
                detailed_data[account_id] = account_data
            _LOGGER.debug("Fetched data: %s", detailed_data)
            return detailed_data
        except Exception as err:
            _LOGGER.error("Error communicating with API: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_force_update_sensors(self) -> None:
        """Force update of sensor data (excluding cameras) by re-authenticating and fetching new data."""
        try:
            await self._authenticate()
            accounts_data = await get_accounts(self.session, self.access_token)
            _LOGGER.debug("accounts_data: %s", accounts_data)
            detailed_data = {}
            for account in accounts_data:
                _LOGGER.debug("account: %s", account)
                account_id = account["objectId"]["id"]

                # Сохраняем важные поля из списка аккаунтов
                original_data = {
                    "notification_count": account.get("notificationCount", 999),
                }

                # Извлекаем адрес и л/с прямо здесь
                try:
                    addr_match = re.search(
                        r'<span[^>]*>(.*?)</span>',
                        account["customFields"]["rows"][0]["cells"][0]["value"],
                        re.DOTALL
                    )
                    ls_match = re.search(r"Л/с №(\d+)", account["objectId"]["title"])
                    
                    parsed_address = addr_match.group(1).strip() if addr_match else "Адрес не распознан"
                    parsed_personal_account = ls_match.group(1) if ls_match else "Л/с не найден"
                    
                    _LOGGER.debug("Извлечено в цикле: Адрес=%s | Л/с=%s", parsed_address, parsed_personal_account)
                
                except Exception as e:
                    _LOGGER.warning("Ошибка парсинга адреса/л/с для %s: %s", account_id, e)
                    parsed_address = "Ошибка"
                    parsed_personal_account = "Ошибка"

                account_data = await self.async_fetch_account_data(account_id, include_cameras=False, include_main_pass=False, include_guest_passes=False)

                # Добавляем сохранённые поля в результат
                account_data.update(original_data)
                
                # Добавляем спарсенные значения в результат
                account_data["address"] = parsed_address
                account_data["personal_account"] = parsed_personal_account

                detailed_data[account_id] = account_data
            self.data = detailed_data
            _LOGGER.debug("Force updated sensor data: %s", self.data)
        except Exception as err:
            _LOGGER.error("Error during force update of sensor data: %s", err)
            raise UpdateFailed(f"Error during force update: {err}") from err

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

    async def async_get_main_pass_data(self, account_id: str) -> Dict:
        """Fetch main pass data for the given account."""
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        payload = {
            "data": {"communalAccountId": account_id},
            "method": "GetMainPassData",
            "namespace": NAMESPACE,
            "operation": "REQUEST",
            "parameters": {"Authorization": f"Bearer {self.access_token}"}
        }
        try:
            async with self.session.post("https://mp.lsr.ru/api/rpc", json=payload, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("statusCode") == 200:
                        return data["data"]
                _LOGGER.error("Failed to fetch main pass data for account %s: HTTP %s", account_id, resp.status)
                return {}
        except Exception as err:
            _LOGGER.error("Error fetching main pass data for account %s: %s", account_id, err)
            return {}

    async def async_get_guest_passes(self, account_id: str) -> Dict:
        """Fetch guest passes data for the given account."""
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        payload = {
            "data": {
                "type": "GuestPass",
                "query": {
                    "conditions": [
                        {
                            "property": "communalAccountId",
                            "value": [account_id],
                            "comparisonOperator": "="
                        }
                    ],
                    "sort": [],
                    "lastEditedPropertyType": None
                },
                "pageQuery": None
            },
            "method": "GetObjectList",
            "namespace": NAMESPACE,
            "operation": "REQUEST",
            "parameters": {"Authorization": f"Bearer {self.access_token}"}
        }
        try:
            async with self.session.post("https://mp.lsr.ru/api/rpc", json=payload, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("statusCode") == 200:
                        return data["data"]
                _LOGGER.error("Failed to fetch guest passes data for account %s: HTTP %s", account_id, resp.status)
                return {}
        except Exception as err:
            _LOGGER.error("Error fetching guest passes data for account %s: %s", account_id, err)
            return {}

    async def async_fetch_account_data(
        self,
        account_id: str,
        include_cameras: bool = False,
        include_main_pass: bool = False,
        include_guest_passes: bool = False,
    ) -> Dict:
        """Fetch account data with optional inclusions."""

        account_data = await get_account_data(self.session, self.access_token, account_id)
        communal_requests = await get_communal_requests(self.session, self.access_token, account_id)
        meters_data = await get_meters(self.session, self.access_token, account_id)

        # -------- МЕТРЫ --------
        meters_history = {}

        for meter in meters_data:
            _LOGGER.debug("meter: %s", meter)

            object_id = meter.get("objectId")
            if not object_id:
                _LOGGER.warning("Meter without objectId skipped: %s", meter)
                continue

            meter_id = object_id.get("id")
            if not meter_id:
                _LOGGER.warning("Meter without id skipped: %s", meter)
                continue

            history_items = await get_meter_history(self.session, self.access_token, meter_id)

            history_dict = {}

            for history_item in history_items:
                value_raw = history_item.get("value1", {}).get("value")
                date_str = history_item.get("dateList")

                if value_raw and date_str:
                    history_dict[date_str] = float(value_raw.replace(",", "."))

            last_value_raw = meter.get("lastMeterValue", {}).get("listValue")
            last_date = meter.get("lastMeterValue", {}).get("dateList")

            if last_value_raw and last_date:
                history_dict[last_date] = float(last_value_raw.replace(",", "."))

            meters_history[meter_id] = {
                "title": object_id.get("title", "Unknown"),
                "type_id": meter.get("type", {}).get("id"),
                "type_title": meter.get("type", {}).get("title"),
                "history": sorted(
                    history_dict.items(),
                    key=lambda x: datetime.strptime(x[0], "%d.%m.%Y"),
                ),
            }

        # -------- НАЧИСЛЕНИЯ / ЛИЦЕВОЙ СЧЁТ --------
        items = account_data.get("items", [])

        valid_items = [
            item for item in items
            if item.get("communalAccount", {}).get("title")
        ]

        communal_account = next(
            (item["communalAccount"] for item in valid_items),
            None
        )

        if not communal_account:
            _LOGGER.warning(
                "No valid accrual items with communalAccount.title for account %s",
                account_id,
            )

        # # -------- АДРЕС --------
        # _LOGGER.debug("account_data: %s", account_data)
        # address_raw = (
        #     account_data
        #     .get("optionalObject", {})
        #     .get("rows", [{}])[0]
        #     .get("cells", [{}])[0]
        #     .get("value")
        # )

        # _LOGGER.debug("address_raw: %s", address_raw)
        # match = re.search(r"Л/с №(\d+)", address_raw or "")
        # address = match.group(1) if match else "Unknown"
        # _LOGGER.debug("address: %s", address)

        # -------- КАМЕРЫ --------
        cameras = []
        if include_cameras:
            cameras = await get_cameras(self.session, self.access_token, account_id)

        # -------- РЕЗУЛЬТАТ --------
        result = {
            "id": communal_account.get("id", account_id) if communal_account else account_id,
            "number": communal_account.get("title", f"Л/с №{account_id}") if communal_account else f"Л/с №{account_id}",
            "payment_status": self._extract_payment_status(account_data.get("optionalObject", {})),
            "notification_count": account_data.get("notificationCount", 0),
            "camera_count": len(cameras),
            "cameras": cameras,
            "accruals": valid_items,
            "communal_requests": communal_requests,
            "meters": meters_history,
            "main_pass": {} if not include_main_pass else await self.async_get_main_pass_data(account_id),
            "guest_passes": {} if not include_guest_passes else await self.async_get_guest_passes(account_id),
        }

        return result
