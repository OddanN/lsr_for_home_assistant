# Version: 1.0.4
"""Custom component for LSR integration, providing sensor entities."""

import logging
import re
from datetime import datetime
from typing import Union, Callable
# noinspection PyProtectedMember
from homeassistant.components.sensor import SensorEntity, \
    EntityCategory  # EntityCategory is part of the official API, ignore __all__ warning if persists
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN
from .coordinator import LSRDataUpdateCoordinator
from .api_client import get_meters, get_meter_history, get_communal_requests

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: Callable[[list], None],  # AddEntitiesCallback type
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
        "account-address": {"name": "account_address", "icon": "mdi:home"},
        "payment-status": {"name": "payment_status", "icon": "mdi:cash"},
        "notification-count": {"name": "notification_count", "icon": "mdi:bell"},
        "camera-count": {"name": "camera_count", "icon": "mdi:camera"},
        "meter-count": {"name": "meter_count", "icon": "mdi:counter"},
    }

    for account_id, account_data in coordinator.data.items():
        _LOGGER.debug("Creating sensors for account %s with data: %s", account_id, account_data)

        for sensor_type, config in sensor_types.items():
            state = account_data.get(sensor_type.replace("-", "_"),
                                     "Unknown" if sensor_type not in ["notification-count", "camera-count",
                                                                      "meter-count"] else 0)
            entity_id = f"sensor.lsr_{account_id}_{config['name']}".lower().replace("-", "_")
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
                    unique_id=entity_id,
                    state_class="measurement" if sensor_type.endswith("count") else None,
                )
            )

    # New meter sensors
    account_id = list(coordinator.data.keys())[0]  # Use the first account_id
    access_token = coordinator.access_token

    # Get meter list
    meters = await get_meters(coordinator.session, access_token, account_id)
    meter_ids = [item["objectId"]["id"] for item in meters]
    _LOGGER.debug("Found meter IDs: %s", meter_ids)

    for item in meters:
        meter_id = item["objectId"]["id"]
        meter_title = item["objectId"]["title"]
        meter_type_id = item["type"]["id"]
        meter_type_title = item["type"]["title"]
        meter_number_match = re.search(r'№(\d+)', meter_title)
        meter_number = meter_number_match.group(1).lower().replace("-", "_") if meter_number_match else meter_id[
            -8:].lower().replace("-", "_")
        _LOGGER.debug("Meter %s: title=%s, meter_number=%s, type_id=%s, type_title=%s", meter_id, meter_title,
                      meter_number, meter_type_id, meter_type_title)

        last_value_raw = item["lastMeterValue"]["listValue"]
        last_date = item["lastMeterValue"]["dateList"]
        last_value = float(last_value_raw.replace(",", ".")) if last_value_raw and last_date else None
        _LOGGER.warning("No lastMeterValue data for meter %s" % meter_id) if last_value is None else None

        meter_poverka_raw = item["dataTitleCustomFields"]["rows"][2]["cells"][0]["value"]
        meter_poverka = re.sub(r'<[^>]+>', '', meter_poverka_raw).split(": ")[1].rstrip('.')
        poverka_date = datetime.strptime(meter_poverka, "%d.%m.%Y").date() if meter_poverka != "Не указана" else None

        history_items = await get_meter_history(coordinator.session, access_token, meter_id)
        history_dict = {}
        for history_item in history_items:
            if history_item["value1"]["value"]:
                date_str = history_item["dateList"]
                value = float(history_item["value1"]["value"].replace(",", "."))
                history_dict[date_str] = value
        if last_value and last_date:
            history_dict[last_date] = last_value

        history_pairs = sorted([(date_str, value) for date_str, value in history_dict.items()],
                               key=lambda x: datetime.strptime(x[0], "%d.%m.%Y"))
        _LOGGER.debug("Meter %s history pairs: %s", meter_id, history_pairs)

        sensor_entity_id = f"sensor.lsr_{account_id}_meter_{meter_number}_value".lower().replace("-", "_")
        for date_str, value in history_pairs:
            date = datetime.strptime(date_str, "%d.%m.%Y").replace(hour=0, minute=0, second=0)
            hass.states.async_set(sensor_entity_id, str(round(value, 4)), {
                "friendly_name": f"Meter {meter_type_title} Reading",
                "icon": "mdi:gauge",
                "unit_of_measurement": "m³" if meter_type_id in ["HotWater",
                                                                 "ColdWater"] else "Gcal" if meter_type_id == "Heating" else None
            }, date)

        latest_value = history_pairs[-1][1] if history_pairs else 0.0
        entities.append(
            LSRSensor(
                hass,
                coordinator,
                account_id,
                f"meter-{meter_id}-value",
                latest_value,
                f"meter_value",
                "mdi:gauge",
                entity_id=sensor_entity_id,
                unique_id=sensor_entity_id,
                state_class="measurement",
                entity_category=EntityCategory.DIAGNOSTIC,
                unit_of_measurement="m³" if meter_type_id in ["HotWater",
                                                              "ColdWater"] else "Gcal" if meter_type_id == "Heating" else None
            )
        )

        sensor_meter_title = f"sensor.lsr_{account_id}_meter_{meter_number}_title".lower().replace("-", "_")
        entities.append(
            LSRSensor(
                hass,
                coordinator,
                account_id,
                f"meter-{meter_id}-title",
                meter_title,
                f"meter_title",
                "mdi:tag",
                entity_id=sensor_meter_title,
                unique_id=sensor_meter_title,
            )
        )

        sensor_meter_poverka = f"sensor.lsr_{account_id}_meter_{meter_number}_poverka".lower().replace("-", "_")
        entities.append(
            LSRSensor(
                hass,
                coordinator,
                account_id,
                f"meter-{meter_id}-poverka",
                poverka_date,
                f"meter_poverka",
                "mdi:calendar-check",
                entity_id=sensor_meter_poverka,
                unique_id=sensor_meter_poverka,
            )
        )

    # Get communal requests
    communal_requests = await get_communal_requests(coordinator.session, access_token, account_id)
    total_requests = len(communal_requests)
    done_requests = [req for req in communal_requests if req.get("status", {}).get("id") == "Done"]
    atwork_requests = [req for req in communal_requests if req.get("status", {}).get("id") == "AtWork"]
    onhold_requests = [req for req in communal_requests if req.get("status", {}).get("id") == "OnHold"]

    # Sensor for total communal requests
    sensor_total_requests = f"sensor.lsr_{account_id}_communalrequest_count_total".lower().replace("-", "_")
    entities.append(
        LSRSensor(
            hass,
            coordinator,
            account_id,
            "communalrequest-count-total",
            total_requests,
            "communalrequest_count_total",
            "mdi:playlist-check",
            entity_id=sensor_total_requests,
            unique_id=sensor_total_requests,
            state_class="measurement",
        )
    )

    # Sensor for done communal requests
    sensor_done_requests = f"sensor.lsr_{account_id}_communalrequest_count_done".lower().replace("-", "_")
    entities.append(
        LSRSensor(
            hass,
            coordinator,
            account_id,
            "communalrequest-count-done",
            len(done_requests),
            "communalrequest_count_done",
            "mdi:check-circle",
            entity_id=sensor_done_requests,
            unique_id=sensor_done_requests,
            state_class="measurement",
            extra_attributes={"titles": [req["objectId"]["title"] for req in done_requests]},
        )
    )

    # Sensor for atwork communal requests
    sensor_atwork_requests = f"sensor.lsr_{account_id}_communalrequest_count_atwork".lower().replace("-", "_")
    entities.append(
        LSRSensor(
            hass,
            coordinator,
            account_id,
            "communalrequest-count-atwork",
            len(atwork_requests),
            "communalrequest_count_atwork",
            "mdi:progress-clock",
            entity_id=sensor_atwork_requests,
            unique_id=sensor_atwork_requests,
            state_class="measurement",
            extra_attributes={"titles": [req["objectId"]["title"] for req in atwork_requests]},
        )
    )

    # Sensor for onhold communal requests
    sensor_onhold_requests = f"sensor.lsr_{account_id}_communalrequest_count_onhold".lower().replace("-", "_")
    entities.append(
        LSRSensor(
            hass,
            coordinator,
            account_id,
            "communalrequest-count-onhold",
            len(onhold_requests),
            "communalrequest_count_onhold",
            "mdi:pause-circle",
            entity_id=sensor_onhold_requests,
            unique_id=sensor_onhold_requests,
            state_class="measurement",
            extra_attributes={"titles": [req["objectId"]["title"] for req in onhold_requests]},
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
            extra_attributes: dict = None,
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
        self._attr_name = entity_name
        self._attr_icon = icon
        self._attr_has_entity_name = True
        self._state = state if state is not None else (
            0 if sensor_type in ["notification-count", "camera-count", "meter-count", "communalrequest-count-total",
                                 "communalrequest-count-done", "communalrequest-count-atwork",
                                 "communalrequest-count-onhold"] else "Unknown")
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
    def name(self):
        """Return the name of the sensor.

        Returns:
            str: The translated name of the sensor.
        """
        return self.hass.config.localized_string(self._attr_name) or self._attr_name

    @property
    def native_value(self):
        """Return the state of the sensor.

        Returns:
            Union[str, int, float]: The current state of the sensor, rounded to 4 decimal places for values.
        """
        state = self._coordinator.data.get(self._account_id, {}).get(self._sensor_type, self._state)
        if self._sensor_type in ["notification-count", "camera-count", "meter-count", "communalrequest-count-total",
                                 "communalrequest-count-done", "communalrequest-count-atwork",
                                 "communalrequest-count-onhold"]:
            state = int(state) if state is not None else 0
        elif self._sensor_type.endswith("-value"):
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
        return {
            "account_id": self._account_id,
            "sensor_type": self._sensor_type,
            **self._attr_extra_state_attributes,
        }