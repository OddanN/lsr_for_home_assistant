# Version: 1.0.0
"""Initialization module for the LSR integration.

This module sets up the LSR integration by handling config entries, coordinators,
and platform setups for sensors and cameras.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .coordinator import LSRDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR, Platform.CAMERA]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """set up LSR from a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (ConfigEntry): The configuration entry for the integration.

    Returns:
        bool: True if setup is successful.
    """
    hass.data.setdefault(DOMAIN, {})
    coordinator_instance = LSRDataUpdateCoordinator(hass, entry)
    await coordinator_instance.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator_instance
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """unload a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (ConfigEntry): The configuration entry to unload.

    Returns:
        bool: True if unloading is successful.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok