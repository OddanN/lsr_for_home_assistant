# Version: 1.2.0
"""Custom component for LSR integration, providing button entities."""

import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN
from .coordinator import LSRDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the LSR button platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        LSRForceUpdateButton(hass, coordinator, entry.entry_id)
    ]
    async_add_entities(entities)
    _LOGGER.debug("Added button entities")

class LSRForceUpdateButton(ButtonEntity):
    """Button to force update sensor data."""

    def __init__(self, coordinator, account_id):
        """Initialize the button."""
        self._coordinator = coordinator
        self._account_id = account_id

        # Получаем номер л/с из координатора (должен быть добавлен в coordinator.py)
        personal_account_number = coordinator.data.get(account_id, {}).get("personal_account_number",
                                                                           account_id[-8:])
        entity_suffix = personal_account_number

        self._attr_unique_id = f"lsr_{entity_suffix}_force_update"
        self._attr_entity_id = f"button.lsr_{entity_suffix}_force_update"  # ← опционально, если хочешь явный entity_id

        self._attr_name = "Обновить данные"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_id)},
            name=coordinator.data.get(account_id, {}).get("account_title", f"ЛСР Л/с №{personal_account_number}"),
            manufacturer="ЛСР",
            model="Communal Account",
        )

        self._attr_has_entity_name = False  # ← главное изменение

    async def async_press(self):
        """Handle the button press."""
        _LOGGER.debug("Forcing update of sensor data")
        await self._coordinator.async_force_update_sensors()
        _LOGGER.debug("Sensor data updated successfully")