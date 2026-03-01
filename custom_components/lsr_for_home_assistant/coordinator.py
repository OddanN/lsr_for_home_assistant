# Version: 1.3.0
# pylint: disable=import-error,too-many-locals,too-many-branches,too-many-statements
# pylint: disable=too-many-nested-blocks,line-too-long,mixed-line-endings
# pylint: disable=broad-exception-caught,raise-missing-from,too-many-arguments,too-many-positional-arguments
# pylint: disable=too-many-return-statements
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
from homeassistant.util import dt as dt_util

from .const import DOMAIN, NAMESPACE
from .api_client import (
    authenticate,
    get_accounts,
    get_account_data,
    get_cameras,
    get_communal_requests,
    get_meters,
    get_meter_history,
    get_camera_stream_url,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(hours=12)


def _coerce_scan_interval(raw_value) -> timedelta:
    """Normalize scan interval value to timedelta.

    Accepts timedelta, numbers in hours, or legacy seconds.
    """
    if raw_value is None:
        return DEFAULT_SCAN_INTERVAL
    if isinstance(raw_value, timedelta):
        return raw_value
    if isinstance(raw_value, str):
        try:
            raw_value = float(raw_value)
        except ValueError:
            return DEFAULT_SCAN_INTERVAL
    if isinstance(raw_value, (int, float)):
        # Legacy entries stored seconds (e.g. 43200). New config uses hours (1..12).
        if raw_value > 24:
            return timedelta(seconds=raw_value)
        return timedelta(hours=raw_value)
    return DEFAULT_SCAN_INTERVAL


def _parse_account_fields(account: Dict, account_id: str) -> Dict:
    """Parse address and account identifiers from account payload."""
    try:
        addr_match = re.search(
            r"<span[^>]*>(.*?)</span>",
            account["customFields"]["rows"][0]["cells"][0]["value"],
            re.DOTALL,
        )
        ls_match = re.search(r"Л/с №(\d+)", account["objectId"]["title"])

        parsed_address = addr_match.group(1).strip() if addr_match else "Адрес не распознан"
        parsed_personal_account = ls_match.group(1) if ls_match else "Л/с не найден"

        personal_account_number = (
            parsed_personal_account
            if parsed_personal_account != "Л/с не найден"
            else account_id[-8:]
        )

        account_title = account["objectId"]["title"]

        _LOGGER.debug(
            "Извлечено в цикле: Адрес=%s | Л/с=%s",
            parsed_address,
            parsed_personal_account,
        )
    except Exception as exc:
        _LOGGER.warning(
            "Ошибка парсинга адреса/л/с для %s: %s",
            account_id,
            exc,
        )
        parsed_address = "Ошибка"
        personal_account_number = account_id[-8:]
        account_title = f"Л/с №{account_id}"

    return {
        "address": parsed_address,
        "personal_account_number": personal_account_number,
        "account_title": account_title,
    }


def _extract_poverka_date(meter: Dict):
    """Extract verification date from meter payload."""
    rows = meter.get("dataTitleCustomFields", {}).get("rows", [])
    if len(rows) < 3:
        return None
    cells = rows[2].get("cells", [])
    if not cells:
        return None
    cell_value = cells[0].get("value", "")
    if not cell_value:
        return None
    clean_text = re.sub(r"<[^>]+>", "", cell_value).strip()
    if ":" not in clean_text:
        return None
    parts = clean_text.split(":", 1)
    if len(parts) != 2:
        return None
    date_part = parts[1].strip().rstrip(".")
    if re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_part):
        return date_part
    return None


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
        scan_interval = _coerce_scan_interval(
            entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL))
        )
        _LOGGER.debug("Scan interval: %s", scan_interval)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=scan_interval)

    async def _async_update_data(self) -> Dict:
        """Update data via API."""
        try:
            refreshed_at = dt_util.utcnow()
            await self._authenticate()
            accounts_data = await get_accounts(self.session, self.access_token)
            _LOGGER.debug("accounts_data: %s", accounts_data)
            detailed_data = {}
            for account in accounts_data:
                account_id, account_data, _ = await self._build_account_data(
                    account,
                    include_cameras=True,
                    include_main_pass=True,
                    include_guest_passes=True,
                    refreshed_at=refreshed_at,
                )
                detailed_data[account_id] = account_data
            _LOGGER.debug("Fetched data: %s", detailed_data)
            return detailed_data
        except Exception as err:
            _LOGGER.error("Error communicating with API: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_force_update_sensors(self) -> None:
        """Force update of sensor data (excluding cameras) by re-authenticating and fetching new data."""
        try:
            refreshed_at = dt_util.utcnow()
            await self._authenticate()
            accounts_data = await get_accounts(self.session, self.access_token)
            _LOGGER.debug("accounts_data: %s", accounts_data)
            detailed_data = {}
            for account in accounts_data:
                account_id, account_data, parsed_fields = await self._build_account_data(
                    account,
                    include_cameras=False,
                    include_main_pass=False,
                    include_guest_passes=False,
                    refreshed_at=refreshed_at,
                )
                account_data["personal_account"] = parsed_fields["personal_account_number"]
                detailed_data[account_id] = account_data
            self.async_set_updated_data(detailed_data)
            _LOGGER.debug("Force updated sensor data: %s", self.data)
        except Exception as err:
            _LOGGER.error("Error during force update of sensor data: %s", err)
            raise UpdateFailed(f"Error during force update: {err}") from err

    async def _build_account_data(
        self,
        account: Dict,
        include_cameras: bool,
        include_main_pass: bool,
        include_guest_passes: bool,
        refreshed_at,
    ):
        _LOGGER.debug("account: %s", account)
        account_id = account["objectId"]["id"]

        original_data = {
            "notification_count": account.get("notificationCount", 999),
        }

        parsed_fields = _parse_account_fields(account, account_id)

        account_data = await self.async_fetch_account_data(
            account_id,
            include_cameras=include_cameras,
            include_main_pass=include_main_pass,
            include_guest_passes=include_guest_passes,
        )

        account_data.update(original_data)
        account_data["address"] = parsed_fields["address"]
        account_data["personal_account_number"] = parsed_fields["personal_account_number"]
        account_data["account_title"] = parsed_fields["account_title"]
        account_data["last_refresh"] = refreshed_at

        return account_id, account_data, parsed_fields

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
                _LOGGER.debug("Authentication successful, access_token: %s, refresh_token: %s", self.access_token,
                              self.refresh_token)
                break
            except Exception as err:
                _LOGGER.error("Authentication error: %s", str(err))
                if attempt == max_attempts:
                    _LOGGER.error("Max retry attempts reached, giving up.")
                    raise ConfigEntryAuthFailed(f"Authentication error after {max_attempts} attempts: {err}")
                _LOGGER.warning("Retrying authentication (attempt %d of %d) in 15 seconds...", attempt, max_attempts)
                await asyncio.sleep(15)
                attempt += 1

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
            async with self.session.post("https://mp.lsr.ru/api/rpc", json=payload, headers=headers,
                                         timeout=10) as resp:
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
            async with self.session.post("https://mp.lsr.ru/api/rpc", json=payload, headers=headers,
                                         timeout=10) as resp:
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
            poverka_date = "Не указана"
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

            # Дата поверки
            poverka_date = _extract_poverka_date(meter) or poverka_date
            if poverka_date != "Не указана":
                _LOGGER.debug("Найдена дата поверки для %s: %s", meter_id, poverka_date)

            meters_history[meter_id] = {
                "title": object_id.get("title", "Unknown"),
                "type_id": meter.get("type", {}).get("id"),
                "type_title": meter.get("type", {}).get("title"),
                "history": sorted(
                    history_dict.items(),
                    key=lambda x: datetime.strptime(x[0], "%d.%m.%Y"),
                ),
                "poverka_date": poverka_date
            }

        # -------- НАЧИСЛЕНИЯ / ЛИЦЕВОЙ СЧЁТ --------
        accruals = [
            item for item in account_data.get("items", [])
            if item.get("communalAccount", {}).get("title")
        ]
        accruals.sort(key=lambda item: item.get("date", 0), reverse=True)

        communal_account = next(
            (item["communalAccount"] for item in accruals),
            None
        )

        if not communal_account:
            _LOGGER.warning("No valid accrual items for account %s", account_id)

        # Парсим payment_status из самого свежего начисления
        payment_status = "Unknown"
        if accruals:
            latest = accruals[0]  # самое свежее начисление
            rows = latest.get("listFields", {}).get("rows", [])
            for row in rows:
                if row.get("isVisible") is True:
                    cells = row.get("cells", [])
                    if cells and len(cells) > 0:
                        value = cells[0].get("value", "")
                        if value:
                            clean = re.sub(r"<[^>]+>", "", value).strip()
                            payment_status = clean
                            _LOGGER.debug("Найден payment_status: %s", payment_status)
                            break

        # -------- КАМЕРЫ --------
        cameras = []
        if include_cameras:
            try:
                cameras = await get_cameras(self.session, self.access_token, account_id) # сохраняем исходный список

                # Получаем реальные stream_url для каждой камеры
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
                    "Accept": "application/json",
                }

                for camera in cameras:
                    if "videoUrl" in camera and camera["videoUrl"]:
                        await get_camera_stream_url(self.session, camera, headers)
                        _LOGGER.debug(
                            "Camera %s (%s): videoUrl → stream_url = %s",
                            camera.get("id"),
                            camera.get("title"),
                            camera.get("stream_url", "<empty>")
                        )
                    else:
                        _LOGGER.warning("Camera %s has no videoUrl", camera.get("id"))

            except Exception as exc:
                _LOGGER.warning(
                    "Не удалось получить камеры для аккаунта %s: %s. Продолжаем без камер.",
                    account_id, exc
                )
                cameras = []  # Важно: пустой список, чтобы не было None и не падало дальше

        # -------- РЕЗУЛЬТАТ --------
        result = {
            "id": communal_account.get("id", account_id) if communal_account else account_id,
            "number": communal_account.get("title", f"Л/с №{account_id}") if communal_account else f"Л/с №{account_id}",
            "payment_status": payment_status,
            "notification_count": account_data.get("notificationCount", 0),
            "camera_count": len(cameras),
            "cameras": cameras,
            "accruals": accruals,
            "communal_requests": communal_requests,
            "meters": meters_history,
            "main_pass": {} if not include_main_pass else await self.async_get_main_pass_data(account_id),
            "guest_passes": {} if not include_guest_passes else await self.async_get_guest_passes(account_id),
        }

        return result
