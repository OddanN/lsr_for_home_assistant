# Version: 1.3.0
# pylint: disable=import-error,too-many-instance-attributes,line-too-long,mixed-line-endings
"""Custom component for LSR integration, providing number entities."""

import logging
from datetime import timedelta

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN
from .coordinator import _coerce_scan_interval

_LOGGER = logging.getLogger(__name__)

MIN_SCAN_INTERVAL_HOURS = 1
MAX_SCAN_INTERVAL_HOURS = 12
SCAN_INTERVAL_STEP = 1


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the LSR number platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for account_id in coordinator.data.keys():
        entities.append(LSRScanIntervalNumber(hass, entry, account_id, coordinator))
    async_add_entities(entities)
    _LOGGER.debug("Added number entities")


def _normalize_scan_interval_hours(raw_value) -> int:
    if raw_value is None:
        return MAX_SCAN_INTERVAL_HOURS
    if isinstance(raw_value, timedelta):
        return int(raw_value.total_seconds() / 3600)
    if isinstance(raw_value, str):
        try:
            raw_value = float(raw_value)
        except ValueError:
            return MAX_SCAN_INTERVAL_HOURS
    if isinstance(raw_value, (int, float)):
        if raw_value > 24:
            return int(raw_value / 3600)
        return int(raw_value)
    return MAX_SCAN_INTERVAL_HOURS


class LSRScanIntervalNumber(NumberEntity):
    """Number entity to control scan interval in hours."""

    _attr_native_min_value = MIN_SCAN_INTERVAL_HOURS
    _attr_native_max_value = MAX_SCAN_INTERVAL_HOURS
    _attr_native_step = SCAN_INTERVAL_STEP
    _attr_native_unit_of_measurement = "ч"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, account_id: str, coordinator) -> None:
        self.hass = hass
        self._entry = entry
        self._account_id = account_id
        self._coordinator = coordinator
        self._pending_refresh_cancel = None
        personal_account_number = coordinator.data.get(account_id, {}).get(
            "personal_account_number",
            account_id[-8:],
        )
        entity_suffix = personal_account_number if personal_account_number else account_id[-8:]
        self._attr_unique_id = f"lsr_{entity_suffix}_scan_interval"
        self.entity_id = f"number.lsr_{entity_suffix}_scan_interval"
        self._attr_name = "Интервал обновления"
        self._attr_icon = "mdi:timer-outline"
        self._attr_has_entity_name = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_id)},
            name=coordinator.data.get(account_id, {}).get("account_title", f"ЛСР Л/с №{account_id[-8:]}"),
            manufacturer="ЛСР",
            model="Communal Account",
        )

    @property
    def native_value(self):
        """Return current scan interval in hours."""
        raw_value = self._entry.options.get(CONF_SCAN_INTERVAL, self._entry.data.get(CONF_SCAN_INTERVAL, 12))
        value = _normalize_scan_interval_hours(raw_value)
        value = max(self._attr_native_min_value, min(self._attr_native_max_value, value))
        return value

    async def async_set_native_value(self, value: float) -> None:
        """Set scan interval in hours and reload config entry."""
        value_int = int(round(value))
        value_int = max(self._attr_native_min_value, min(self._attr_native_max_value, value_int))
        _LOGGER.debug("Setting scan interval to %s hours", value_int)
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, CONF_SCAN_INTERVAL: value_int},
        )
        # Update coordinator interval without full reload to avoid temporary unavailability.
        self._coordinator.update_interval = _coerce_scan_interval(value_int)
        if self._pending_refresh_cancel:
            self._pending_refresh_cancel()
            self._pending_refresh_cancel = None
        self._pending_refresh_cancel = async_call_later(
            self.hass,
            2.0,
            lambda _now: self.hass.async_create_task(self._coordinator.async_refresh()),
        )
