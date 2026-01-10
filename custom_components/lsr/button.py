# Version: 1.1.3
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

    def __init__(self, hass: HomeAssistant, coordinator: LSRDataUpdateCoordinator, entry_id: str):
        """Initialize the button."""
        self.hass = hass
        self._coordinator = coordinator
        self._attr_unique_id = f"lsr_{entry_id}_force_update"
        self._attr_name = "Force Update Sensors"
        self._attr_icon = "mdi:refresh"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=f"Счет ID {entry_id}",
            manufacturer="ЛСР",
            model="Communal Control",
        )
        self._attr_entity_registry_enabled_default = True

    async def async_press(self):
        """Handle the button press."""
        _LOGGER.debug("Forcing update of sensor data")
        await self._coordinator.async_force_update_sensors()
        _LOGGER.debug("Sensor data updated successfully")