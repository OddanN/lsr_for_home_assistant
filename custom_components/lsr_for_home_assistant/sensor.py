# Version: 1.2.0
"""Custom component for LSR integration, providing sensor entities."""

import logging
import re
from datetime import datetime
from typing import Union, Callable
# noinspection PyProtectedMember
from homeassistant.components.sensor import SensorEntity, EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass

from .const import DOMAIN
from .coordinator import LSRDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: Callable[[list], None],
) -> None:
    """Set up the LSR sensor platform.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (ConfigEntry): The configuration entry for the integration.
        async_add_entities (Callable[[list], None]): Callback to add entities to Home Assistant.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    sensor_types = {
        "address": {"name": "address", "friendly_name": "Адрес", "icon": "mdi:home", "state_class": None},
        "personal-account-number": {"name": "personal_account_number", "friendly_name": "№ л\с",
                             "icon": "mdi:card-account-details-outline", "state_class": None},
        "payment-status": {"name": "payment_status", "icon": "mdi:cash", "state_class": None},
        "notification-count": {"name": "notification_count", "friendly_name": "Уведомления", "icon": "mdi:bell",
                               "state_class": "measurement"},
        "camera-count": {"name": "camera_count", "icon": "mdi:camera", "state_class": "measurement"}
    }

    for account_id, account_data in coordinator.data.items():
        _LOGGER.debug("=== Данные аккаунта %s ===", account_id)
        _LOGGER.debug("Все доступные ключи: %s", sorted(account_data.keys()))
        _LOGGER.debug("address          → %s", account_data.get("address"))
        _LOGGER.debug("personal_account_number → %s", account_data.get("personal_account_number"))
        _LOGGER.debug("payment_status   → %s", account_data.get("payment_status"))
        _LOGGER.debug("notification_count → %s", account_data.get("notification_count"))
        _LOGGER.debug("Полный account_data (первые 1000 символов): %s", str(account_data))

        NUMERIC_DEFAULT = 999  # для всех счётчиков и числовых сенсоров — нормальный дефолт 0
        STRING_DEFAULT = "STRING_DEFAULT"

        personal_account_number = account_data.get("personal_account_number", "unknown")
        entity_suffix = personal_account_number if personal_account_number != "unknown" else account_id[-8:]

        for sensor_type, config in sensor_types.items():
            key = sensor_type.replace("-", "_")
            if sensor_type == "meter-count":
                # Специально считаем реальное количество из "meters"
                meters = account_data.get("meters", {})
                state = len(meters)
                _LOGGER.debug("Реальное количество счётчиков для %s: %d (найдено %d ключей в meters)",
                              account_id, state, len(meters))
            else:
                # Для остальных — обычный get с правильным дефолтом
                state = account_data.get(key, NUMERIC_DEFAULT if sensor_type in ["notification-count",
                                                                                 "camera-count"] else STRING_DEFAULT)

            entity_id = f"sensor.lsr_{entity_suffix}_{sensor_type}".lower().replace("-", "_")
            unique_id = entity_id
            entities.append(
                LSRSensor(
                    hass,
                    coordinator,
                    account_id,
                    sensor_type,
                    state,
                    config["name"],
                    config["icon"],
                    entity_id=entity_id,
                    unique_id=unique_id,
                    state_class=config.get("state_class"),
                    friendly_name=config.get("friendly_name", config["name"])
                )
            )

        # Sensors for meters
        meters = account_data.get("meters", {})
        meter_count = len(meters)

        # 1. Общий счётчик количества приборов
        meters = account_data.get("meters", {})
        meter_count = len(meters)

        # Собираем список названий всех счётчиков для атрибута
        all_meters_list = []
        for meter_id, meter_data in meters.items():
            title = meter_data.get("title", "Без названия")
            meter_type_title = meter_data.get("type_title", "Неизвестно")
            meter_str = f"{title} ({meter_type_title})"
            all_meters_list.append(meter_str)
        _LOGGER.debug("Собрано all_meters для %s: %s", account_id, all_meters_list)

        # Создаём сенсор количества
        meter_count_entity_id = f"sensor.lsr_{entity_suffix}_meter_count".lower().replace("-", "_")
        entities.append(
            LSRSensor(
                hass,
                coordinator,
                account_id,
                "meter-count",
                meter_count,
                "meter_count",
                "mdi:counter",
                entity_id=meter_count_entity_id,
                unique_id=meter_count_entity_id,
                state_class="measurement",
                friendly_name="Счётчиков всего",
                extra_attributes={
                    "all_meters": all_meters_list,
                    "count": meter_count,
                }
            )
        )

        # 2. По одному сенсору на каждый счётчик
        for meter_id, meter_data in meters.items():
            _LOGGER.debug("meter_id %s: %s", meter_id, meter_data)
            title = meter_data.get("title", "Без названия")

            # Извлекаем чистый номер и тип для имени
            meter_number_match = re.search(r"№(\d+)", title)
            meter_number = meter_number_match.group(1) if meter_number_match else meter_id[-8:]

            # Обрезаем всё после номера → получаем "ХВС на ГВС", "ХВС", "Отопление"
            prefix = re.sub(r"№\d+.*", "", title).strip()
            if not prefix:
                prefix = meter_data.get("type_title", "Счётчик").split()[-1]  # fallback

            # Имя: "Счётчик ХВС на ГВС №8358216"
            friendly_name = f"Счётчик {prefix} №{meter_number}"

            # Чистое значение (float)
            history = meter_data.get("history", [])
            current_value = history[-1][1] if history else 0.0

            # Единицы измерения — только стандартные для HA!
            unit = None
            device_class = None
            state_class = "total_increasing"

            type_id = meter_data.get("type_id")
            if type_id in ("HotWater", "ColdWater"):
                unit = "m³" # ← английская "m³"
                device_class = SensorDeviceClass.VOLUME
                state_class = "total_increasing"    # ← накопительное значение!
            elif type_id == "Heating":
                unit = "Gcal"   # ← стандартная для Гкал
                device_class = SensorDeviceClass.ENERGY
                state_class = "total_increasing"
            elif type_id == "Electricity":
                unit = "kWh"
                device_class = SensorDeviceClass.ENERGY
                state_class = "total_increasing"
            _LOGGER.debug("meter unit_of_measurement %s: type_id=%s, unit=%s, device_class=%s, state_class=%s", meter_id, type_id, unit, device_class, state_class)

            # Тип счётчика для атрибутов
            meter_type_title = meter_data.get("type_title", "Неизвестно")

            # Дата поверки
            poverka_date = "Не указана"
            rows = meter_data.get("dataTitleCustomFields", {}).get("rows", [])
            for row in rows:
                value = row.get("cells", [{}])[0].get("value", "")
                if "поверки" in value.lower():
                    poverka_text = re.sub(r"<[^>]+>", "", value)
                    if ": " in poverka_text:
                        poverka_date = poverka_text.split(": ", 1)[1].rstrip(".")
                    break

            # Дата последнего показания
            last_date = "Неизвестно"
            if history:
                last_date = history[-1][0]

            # Уникальное имя сущности
            base_entity_id = f"lsr_{entity_suffix}_meter_{meter_number}".lower().replace("-", "_")

            entities.append(
                LSRSensor(
                    hass,
                    coordinator,
                    account_id,
                    f"meter-{meter_id}-value",
                    current_value,  # ← только число!
                    f"meter_{meter_number}_value",
                    "mdi:gauge",
                    entity_id=f"sensor.{base_entity_id}_value",
                    unique_id=f"{base_entity_id}_value",
                    state_class=state_class,
                    unit_of_measurement=unit,  # ← единицы здесь!
                    device_class=device_class,
                    friendly_name=friendly_name,  # ← "Счётчик ХВС на ГВС №8358216"
                    extra_attributes={
                        "poverka_date": poverka_date,
                        "last_update": last_date,
                        "meter_type": meter_type_title,
                        "meter_id": meter_id,
                        "title": title,
                    }
                )
            )

        # Sensors for communal requests
        communal_requests = account_data.get("communal_requests", [])
        total_requests = len(communal_requests)

        # Считаем по статусам
        done_count = len([req for req in communal_requests if req.get("status", {}).get("id") == "Done"])
        atwork_count = len([req for req in communal_requests if req.get("status", {}).get("id") == "AtWork"])
        onhold_count = len([req for req in communal_requests if req.get("status", {}).get("id") == "OnHold"])
        waiting_count = len(
            [req for req in communal_requests if req.get("status", {}).get("id") == "WaitingForRegistration"])

        # Словарь с локализованными названиями и иконками
        request_sensors = [
            {
                "type": "communalrequest-count-total",
                "name": "communalrequest_count_total",
                "friendly_name": "Заявки всего",
                "icon": "mdi:playlist-check",
                "count": total_requests,
                "extra_attributes": {
                    "done": done_count,
                    "atwork": atwork_count,
                    "onhold": onhold_count,
                    "waiting": waiting_count,
                }
            },
            {
                "type": "communalrequest-count-done",
                "name": "communalrequest_count_done",
                "friendly_name": "Выполненные заявки",
                "icon": "mdi:check-circle",
                "count": done_count,
                "extra_attributes": None,
            },
            {
                "type": "communalrequest-count-atwork",
                "name": "communalrequest_count_atwork",
                "friendly_name": "Заявки в работе",
                "icon": "mdi:progress-clock",
                "count": atwork_count,
                "extra_attributes": None,
            },
            {
                "type": "communalrequest-count-onhold",
                "name": "communalrequest_count_onhold",
                "friendly_name": "Заявки на паузе",
                "icon": "mdi:pause-circle",
                "count": onhold_count,
                "extra_attributes": None,
            },
            {
                "type": "communalrequest-count-waitingforregistration",
                "name": "communalrequest_count_waitingforregistration",
                "friendly_name": "Заявки ожидают регистрации",
                "icon": "mdi:clock-outline",
                "count": waiting_count,
                "extra_attributes": None,
            }
        ]

        for req_sensor in request_sensors:
            entity_id = f"sensor.lsr_{entity_suffix}_{req_sensor['name']}".lower().replace("-", "_")
            entities.append(
                LSRSensor(
                    hass,
                    coordinator,
                    account_id,
                    req_sensor["type"],
                    req_sensor["count"],
                    req_sensor["name"],
                    req_sensor["icon"],
                    entity_id=entity_id,
                    unique_id=entity_id,
                    state_class="measurement",
                    friendly_name=req_sensor["friendly_name"],
                    extra_attributes=req_sensor.get("extra_attributes")
                )
            )

        # New sensor for payment due
        accruals = account_data.get("accruals", [])
        if accruals:
            _LOGGER.debug("accruals: %s", accruals)

            # Берём только валидные начисления (где есть title)
            latest_accrual = accruals[0]

            # ---------- Сумма начисления ----------
            amount = 0.0
            amount_cell = latest_accrual.get("listFields", {}) \
                .get("rows", [{}])[0] \
                .get("cells", [{}, {}])[1] \
                .get("value", "")

            amount_text = re.sub(r"<[^>]+>", "", amount_cell)

            amount_match = re.search(r"Начислено\s*([\d.,]+)", amount_text)
            if amount_match:
                amount = float(amount_match.group(1).replace(",", "."))

            # ---------- Атрибуты ----------
            extra_attributes = {}

            for accrual in accruals:
                _LOGGER.debug("accrual: %s", accrual)
                accrual_id = accrual["objectId"]["id"]

                # Дата
                date_cell = accrual["listFields"]["rows"][0]["cells"][0]["value"]

                date_text = re.sub(r"<[^>]+>", "", date_cell)

                # Сумма
                value_cell = accrual["listFields"]["rows"][0]["cells"][1]["value"]

                value_text = re.sub(r"<[^>]+>", "", value_cell)
                value_match = re.search(r"Начислено\s*([\d.,]+)", value_text)

                extra_attributes[accrual_id] = {
                    "date": date_text.strip(),
                    "amount": value_match.group(1) if value_match else None
                }

            sensor_payment_due = f"sensor.lsr_{entity_suffix}_payment_due".lower().replace("-", "_")

            entities.append(
                LSRSensor(
                    hass,
                    coordinator,
                    account_id,
                    "payment-due",
                    amount,
                    "payment_due",
                    "mdi:cash",
                    entity_id=sensor_payment_due,
                    unique_id=sensor_payment_due,
                    state_class="measurement",
                    extra_attributes=extra_attributes
                )
            )

        # Новый объединённый сенсор СКУД (основан на QR-коде)
        main_pass = account_data.get("main_pass", {})
        guest_passes_data = account_data.get("guest_passes", {})

        if main_pass or guest_passes_data:
            # Состояние = ПИН-код (или "Нет пина", если отсутствует)
            pin_code = main_pass.get("pin", "Нет пина")

            # Формируем красивый список гостевых пропусков для атрибутов
            guest_list = []
            guest_count = guest_passes_data.get("count", 0)
            for pass_data in guest_passes_data.get("items", []):
                from_date = datetime.fromtimestamp(pass_data['dateFrom']).strftime('%d.%m.%Y')
                to_date = datetime.fromtimestamp(pass_data['dateTo']).strftime('%d.%m.%Y')
                pass_str = (
                    f"{pass_data['strategy']['title']} | "
                    f"{from_date}–{to_date} | "
                    f"Пин: {pass_data.get('pin', '—')} | "
                    f"QR: {pass_data.get('qr', '—')}"
                )
                guest_list.append(pass_str)

            # Создаём сенсор
            skud_qr_entity_id = f"sensor.lsr_{entity_suffix}_skud_qr_code".lower().replace("-", "_")
            entities.append(
                LSRSensor(
                    hass,
                    coordinator,
                    account_id,
                    "skud-qr-code",
                    pin_code,  # ← состояние = ПИН-код
                    "skud_qr_code",
                    "mdi:qrcode",
                    entity_id=skud_qr_entity_id,
                    unique_id=skud_qr_entity_id,
                    friendly_name="СКУД QR-код",
                    extra_attributes={
                        "guest_passes_count": guest_count,
                        "guest_passes": guest_list,
                        "main_pass_text": main_pass.get("text", ""),
                        "main_pass_qr": main_pass.get("qr", ""),
                    }
                )
            )

    async_add_entities(entities)
    _LOGGER.debug("Added %s sensor entities", len(entities))


class LSRSensor(SensorEntity):
    """Representation of an LSR sensor.

    This class handles the creation and management of sensor entities for the LSR integration.
    """

    def __init__(
            self,
            hass: HomeAssistant,
            coordinator: LSRDataUpdateCoordinator,
            account_id: str,
            sensor_type: str,
            state: Union[str, int, float, datetime.date],
            entity_name: str,
            icon: str,
            entity_id: str,
            unique_id: str,
            state_class: str = None,
            entity_category: EntityCategory = None,
            unit_of_measurement: str = None,
            device_class: str = None,
            extra_attributes: dict = None,
            friendly_name: str = None
    ) -> None:
        """Initialize the sensor.

        Args:
            hass (HomeAssistant): The Home Assistant instance.
            coordinator (LSRDataUpdateCoordinator): The data coordinator for the integration.
            account_id (str): The account ID associated with the sensor.
            sensor_type (str): The type of the sensor.
            state (Union[str, int, float, datetime.date]): The initial state of the sensor.
            entity_name (str): The entity name key for translation.
            icon (str): The icon for the sensor.
            entity_id (str): The entity ID for the sensor.
            unique_id (str): The unique ID for the sensor.
            state_class (str, optional): The state class of the sensor.
            entity_category (EntityCategory, optional): The category of the sensor.
            unit_of_measurement (str, optional): The unit of measurement for the sensor.
            extra_attributes (dict, optional): Additional attributes for the sensor.
        """
        super().__init__()
        self.hass = hass
        self._coordinator = coordinator
        self._account_id = account_id
        self._sensor_type = sensor_type
        self._attr_unique_id = unique_id
        self.entity_id = entity_id
        self._attr_name = friendly_name if friendly_name else entity_name
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit_of_measurement
        if state_class:
            try:
                self._attr_state_class = SensorStateClass(state_class)
            except ValueError:
                _LOGGER.warning("Invalid state_class %s for %s", state_class, unique_id)
        self._attr_has_entity_name = False
        self._attr_extra_state_attributes = extra_attributes or {}
        self._state = state if state is not None else (
            0 if sensor_type in ["notification-count", "camera-count", "meter-count", "communalrequest-count-total",
                                 "communalrequest-count-done", "communalrequest-count-atwork",
                                 "communalrequest-count-onhold", "communalrequest-count-waitingforregistration",
                                 "guestpass"] else "Unknown")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._account_id)},
            name=coordinator.data.get(self._account_id, {}).get("account_title",
                                                                f"ЛСР Аккаунт {self._account_id[-8:]}"),
            manufacturer="ЛСР",
            model="Communal Account",
        )
        self._attr_entity_registry_enabled_default = True

        # Автоматическое распределение по категориям Home Assistant
        if self._sensor_type in ["mainpass-pin", "guestpass"]:
            self._attr_entity_category = None  # СКУД → основной список (visible)

        elif self._sensor_type == "payment-status":
            self._attr_entity_category = None  # Статус оплаты → основной список

        elif self._sensor_type == "communalrequest-count-total":
            self._attr_entity_category = None  # Заявки всего → основной список

        elif self._sensor_type == "meter-count":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC  # Счётчиков всего → Диагностика (скрыто)

        elif self._sensor_type.startswith(
                "communalrequest-count-") and self._sensor_type != "communalrequest-count-total":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC  # Остальные заявки → Диагностика

        elif self._sensor_type in ["address", "personal-account-number"]:
            self._attr_entity_category = None  # Адрес и № л/с → Настройки

        elif self._sensor_type in ["payment-due"]:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC  # Сумма к оплате → Диагностика

        elif self._sensor_type.startswith("meter-") and "-value" in self._sensor_type:
            self._attr_entity_category = None  # Показания отдельных счётчиков → основной список

        else:
            self._attr_entity_category = None  # Всё остальное — основной список

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Returns:
            bool: True if the account data is available, false otherwise.
        """
        is_available = self._coordinator.data.get(self._account_id) is not None
        return is_available

    @property
    def name(self):
        """Return the name of the sensor.

        Returns:
            str: The translated name of the sensor.
        """
        if self._sensor_type == "guestpass":
            return "СКУД Гостевые пропуска"
        if self._sensor_type == "camera-count":
            return "Количество камер"
        if self._sensor_type == "notification-count":
            return "Количество уведомлений"
        return self._attr_name

    @property
    def native_value(self):
        """Return the state of the sensor.

        Returns:
            Union[str, int, float]: The current state of the sensor, rounded to 4 decimal places for values.
        """
        state = self._coordinator.data.get(self._account_id, {}).get(self._sensor_type, self._state)
        if self._sensor_type in ["notification-count", "camera-count", "meter-count", "communalrequest-count-total",
                                 "communalrequest-count-done", "communalrequest-count-atwork",
                                 "communalrequest-count-onhold", "communalrequest-count-waitingforregistration",
                                 "guestpass"]:
            state = int(state) if state is not None else 998
        elif self._sensor_type.endswith("-value") or self._sensor_type == "payment-due":
            state = round(float(state) if state is not None else 0.0, 4)
        elif self._sensor_type.startswith("meter-") and "-poverka" not in self._sensor_type:
            state = str(state) if state is not None else "Unknown"
        else:
            state = str(state) if state is not None else "Unknown"
        _LOGGER.debug("Sensor %s native_value: %s", self._attr_unique_id, state)
        return state

    @property
    def extra_state_attributes(self):
        """Return the state attributes.

        Returns:
            dict: Additional attributes for the sensor entity.
        """
        base_attributes = {
            "account_id": self._account_id,
            "sensor_type": self._sensor_type,
            **self._attr_extra_state_attributes,
        }
        if self._sensor_type == "mainpass-pin":
            main_pass = self._coordinator.data.get(self._account_id, {}).get("main_pass", {})
            base_attributes.update({
                "text": main_pass.get("text", ""),
                "qr": main_pass.get("qr", "")
            })
        elif self._sensor_type == "guestpass":
            base_attributes.update(self._attr_extra_state_attributes or {})
        return base_attributes
