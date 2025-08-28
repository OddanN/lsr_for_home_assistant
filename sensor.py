# Version: 1.0.1
"""Custom component for LSR integration, providing sensor entities."""

import logging
import re
from datetime import datetime
from typing import Union
from homeassistant.components.sensor import SensorEntity, EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_registry import async_get as async_get_registry, async_entries_for_config_entry
from .const import DOMAIN
from .coordinator import LSRDataUpdateCoordinator
from .api_client import get_meters, get_meter_history

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the LSR sensor platform.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (ConfigEntry): The configuration entry for the integration.
        async_add_entities (AddEntitiesCallback): Callback to add entities to Home Assistant.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    # Existing sensors
    for account_id, account_data in coordinator.data.items():
        _LOGGER.debug("Creating sensors for account %s with data: %s", account_id, account_data)

        sensor_address_name = f"sensor.lsr_{account_id}_account_address".lower().replace("-", "_")
        entities.append(
            LSRSensor(
                hass,
                coordinator,
                account_id,
                "account-address",
                account_data.get("address", "Unknown"),
                "Адрес",
                icon="mdi:home",
                entity_id=sensor_address_name,
                unique_id=sensor_address_name,
            )
        )
        # Sensor for payment status
        sensor_payment_status = f"sensor.lsr_{account_id}_payment_status".lower().replace("-", "_")
        entities.append(
            LSRSensor(
                hass,
                coordinator,
                account_id,
                "payment-status",
                account_data.get("payment_status", "Unknown"),
                "Статус оплаты",
                icon="mdi:cash",
                entity_id=sensor_payment_status,
                unique_id=sensor_payment_status,
            )
        )
        # Sensor for notification count
        sensor_notification_count = f"sensor.lsr_{account_id}_notification_count".lower().replace("-", "_")
        notification_count = account_data.get("notification_count")
        entities.append(
            LSRSensor(
                hass,
                coordinator,
                account_id,
                "notification-count",
                int(notification_count) if notification_count is not None else 0,
                "Количество уведомлений",
                icon="mdi:bell",
                entity_id=sensor_notification_count,
                unique_id=sensor_notification_count,
                state_class="measurement",
            )
        )
        # Sensor for camera count
        sensor_camera_count = f"sensor.lsr_{account_id}_camera_count".lower().replace("-", "_")
        camera_count = account_data.get("camera_count")
        entities.append(
            LSRSensor(
                hass,
                coordinator,
                account_id,
                "camera-count",
                int(camera_count) if camera_count is not None else 0,
                "Количество камер",
                icon="mdi:camera",
                entity_id=sensor_camera_count,
                unique_id=sensor_camera_count,
                state_class="measurement",
            )
        )

    # New meter sensors
    account_id = list(coordinator.data.keys())[0]  # Use the first account_id
    access_token = coordinator.access_token

    # Get meter list
    meters = await get_meters(coordinator.session, access_token, account_id)
    meter_ids = [item["objectId"]["id"] for item in meters]
    _LOGGER.debug("Found meter IDs: %s", meter_ids)

    # Sensor for meter count
    sensor_meter_count = f"sensor.lsr_{account_id}_meter_count".lower().replace("-", "_")
    entities.append(
        LSRSensor(
            hass,
            coordinator,
            account_id,
            "meter-count",
            len(meter_ids),
            "Количество счётчиков",
            icon="mdi:counter",
            entity_id=sensor_meter_count,
            unique_id=sensor_meter_count,
            state_class="measurement",
        )
    )

    # Get data for each meter
    for item in meters:
        meter_id = item["objectId"]["id"]
        meter_title = item["objectId"]["title"]
        meter_type_id = item["type"]["id"]  # Use the objectId.type.id for unit of measurement
        meter_type_title = item["type"]["title"]
        # Extract meter_number from title (e.g., "ХВС на ГВС №8358216" -> "8358216")
        meter_number_match = re.search(r'№(\d+)', meter_title)
        meter_number = meter_number_match.group(1).lower().replace("-", "_") if meter_number_match else meter_id[
                                                                                                        -8:].lower().replace(
            "-", "_")
        _LOGGER.debug("Meter %s: title=%s, meter_number=%s, type_id=%s, type_title=%s", meter_id, meter_title,
                      meter_number, meter_type_id, meter_type_title)

        # Extract last meter value from item
        last_value_raw = item["lastMeterValue"]["listValue"]
        last_date = item["lastMeterValue"]["dateList"]
        if last_value_raw and last_date:
            last_value = float(last_value_raw.replace(",", "."))
        else:
            last_value = None
            _LOGGER.warning("No lastMeterValue data for meter %s", meter_id)

        # Extract meter poverka
        meter_poverka_raw = item["dataTitleCustomFields"]["rows"][2]["cells"][0]["value"]
        meter_poverka = re.sub(r'<[^>]+>', '', meter_poverka_raw).split(": ")[1].rstrip('.')
        try:
            poverka_date = datetime.strptime(meter_poverka,
                                             "%d.%m.%Y").date() if meter_poverka != "Не указана" else None
        except ValueError:
            poverka_date = None
            _LOGGER.warning("Invalid poverka date format for meter %s: %s", meter_id, meter_poverka)

        # Get meter history
        history_items = await get_meter_history(coordinator.session, access_token, meter_id)
        history_dict = {}
        for history_item in history_items:
            if history_item["value1"]["value"]:
                date_str = history_item["dateList"]
                value = float(history_item["value1"]["value"].replace(",", "."))
                history_dict[date_str] = value
        # Add last meter value if available
        if last_value and last_date:
            history_dict[last_date] = last_value

        history_pairs = sorted([(date_str, value) for date_str, value in history_dict.items()],
                               key=lambda x: datetime.strptime(x[0], "%d.%m.%Y"))
        _LOGGER.debug("Meter %s history pairs: %s", meter_id, history_pairs)

        # Initialize historical data in recorder
        sensor_entity_id = f"sensor.lsr_{account_id}_meter_{meter_number}_value".lower().replace("-", "_")
        if len(sensor_entity_id) > 255 or not all(c.isalnum() or c == '_' for c in sensor_entity_id[7:]):
            _LOGGER.error("Invalid entity ID (length > 255 or invalid chars): %s", sensor_entity_id)
            continue
        for date_str, value in history_pairs:
            date = datetime.strptime(date_str, "%d.%m.%Y").replace(hour=0, minute=0, second=0)
            hass.states.async_set(sensor_entity_id, str(round(value, 4)), {
                "friendly_name": f"Счётчик {meter_type_title} показания",
                "icon": "mdi:gauge",
                "unit_of_measurement": "м³" if meter_type_id in ["HotWater",
                                                                 "ColdWater"] else "Гкал" if meter_type_id == "Heating" else None
            }, date)

        # Set current state to the latest value
        latest_value = history_pairs[-1][1] if history_pairs else 0.0
        entities.append(
            LSRSensor(
                hass,
                coordinator,
                account_id,
                f"meter-{meter_id}-value",
                latest_value,
                f"Счётчик {meter_type_title} показания",
                icon="mdi:gauge",
                entity_id=sensor_entity_id,
                unique_id=sensor_entity_id,
                state_class="measurement",
                entity_category=EntityCategory.DIAGNOSTIC,
                unit_of_measurement="м³" if meter_type_id in ["HotWater",
                                                              "ColdWater"] else "Гкал" if meter_type_id == "Heating" else None
            )
        )

        # Sensor for meter title
        sensor_meter_title = f"sensor.lsr_{account_id}_meter_{meter_number}_title".lower().replace("-", "_")
        entities.append(
            LSRSensor(
                hass,
                coordinator,
                account_id,
                f"meter-{meter_id}-title",
                meter_title,
                f"Счётчик {meter_type_title}",
                icon="mdi:tag",
                entity_id=sensor_meter_title,
                unique_id=sensor_meter_title,
            )
        )

        # Sensor for meter poverka
        sensor_meter_poverka = f"sensor.lsr_{account_id}_meter_{meter_number}_poverka".lower().replace("-", "_")
        entities.append(
            LSRSensor(
                hass,
                coordinator,
                account_id,
                f"meter-{meter_id}-poverka",
                poverka_date,
                f"Счётчик {meter_type_title} поверка",
                icon="mdi:calendar-check",
                entity_id=sensor_meter_poverka,
                unique_id=sensor_meter_poverka,
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
            friendly_name: str,
            icon: str,
            entity_id: str,
            unique_id: str,
            state_class: str = None,
            entity_category: EntityCategory = None,
            unit_of_measurement: str = None,
            extra_attributes: dict = None,
    ) -> None:
        """Initialize the sensor.

        Args:
            hass (HomeAssistant): The Home Assistant instance.
            coordinator (LSRDataUpdateCoordinator): The data coordinator for the integration.
            account_id (str): The account ID associated with the sensor.
            sensor_type (str): The type of the sensor.
            state (Union[str, int, float, datetime.date]): The initial state of the sensor.
            friendly_name (str): The friendly name of the sensor.
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
        self._attr_name = friendly_name
        self._attr_icon = icon
        self._attr_has_entity_name = False
        self._state = state if state is not None else (
            0 if sensor_type in ["notification-count", "camera-count", "meter-count"] else "Unknown")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._account_id)},
            name=f"Счет ID {self._account_id}",
            manufacturer="ЛСР",
            model="Communal Account",
        )
        self._attr_entity_registry_enabled_default = True
        self._attr_state_class = state_class
        self._attr_entity_category = entity_category
        self._attr_unit_of_measurement = unit_of_measurement
        self._attr_extra_state_attributes = extra_attributes or {}
        _LOGGER.debug(
            "Initialized sensor %s with unique_id %s, entity_id=%s (not set directly), enabled_default: %s, state: %s",
            self._attr_name,
            self._attr_unique_id,
            entity_id,
            self._attr_entity_registry_enabled_default,
            self._state,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Returns:
            bool: True if the account data is available, false otherwise.
        """
        is_available = self._coordinator.data.get(self._account_id) is not None
        return is_available

    @property
    def state(self):
        """Return the state of the sensor.

        Returns:
            Union[str, int, float]: The current state of the sensor, rounded to 4 decimal places for values.
        """
        state = self._coordinator.data.get(self._account_id, {}).get(self._sensor_type, self._state)
        if self._sensor_type in ["notification-count", "camera-count", "meter-count"]:
            state = int(state) if state is not None else 0
        elif self._sensor_type.endswith("-value"):
            state = round(float(state) if state is not None else 0.0, 4)  # Округление до 4 знаков
        elif self._sensor_type.startswith("meter-") and "-poverka" not in self._sensor_type:
            state = str(state) if state is not None else "Unknown"
        else:
            state = str(state) if state is not None else "Unknown"
        _LOGGER.debug("Sensor %s state: %s", self._attr_unique_id, state)
        return state

    @property
    def extra_state_attributes(self):
        """Return the state attributes.

        Returns:
            dict: Additional attributes for the sensor entity.
        """
        return {
            "account_id": self._account_id,
            "sensor_type": self._sensor_type,
            **self._attr_extra_state_attributes,
        }