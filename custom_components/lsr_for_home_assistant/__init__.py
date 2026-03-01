# Version: 1.3.0
# pylint: disable=import-error,mixed-line-endings,line-too-long
"""Initialization module for the LSR integration.

This module sets up the LSR integration by handling config entries, coordinators,
and platform setups for sensors and cameras.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .coordinator import LSRDataUpdateCoordinator, _coerce_scan_interval

PLATFORMS = [Platform.SENSOR, Platform.BUTTON, Platform.CAMERA, Platform.NUMBER]


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
    await _migrate_button_entity_ids(hass, entry, coordinator_instance)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
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


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options updates."""
    coordinator_instance = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator_instance is None:
        await hass.config_entries.async_reload(entry.entry_id)
        return
    scan_interval = _coerce_scan_interval(
        entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL))
    )
    coordinator_instance.update_interval = scan_interval
    await coordinator_instance.async_refresh()


async def _migrate_button_entity_ids(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator_instance: LSRDataUpdateCoordinator,
) -> None:
    """Normalize button entity_id/unique_id to match current naming scheme."""
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    entries = er.async_entries_for_config_entry(entity_reg, entry.entry_id)
    if not entries:
        return

    device_id_to_account_id = {}
    for device in device_reg.devices.values():
        for identifier in device.identifiers:
            if identifier[0] == DOMAIN:
                device_id_to_account_id[device.id] = identifier[1]

    for entity in entries:
        if entity.domain != "button" or entity.platform != DOMAIN:
            continue
        account_id = device_id_to_account_id.get(entity.device_id)
        if not account_id:
            continue
        personal_account_number = coordinator_instance.data.get(account_id, {}).get(
            "personal_account_number",
            account_id[-8:],
        )
        entity_suffix = personal_account_number if personal_account_number else account_id[-8:]
        target_unique_id = f"lsr_{entity_suffix}_force_update"
        target_entity_id = f"button.lsr_{entity_suffix}_force_update"
        if entity.unique_id == target_unique_id and entity.entity_id == target_entity_id:
            continue
        if entity_reg.async_get(target_entity_id) is not None:
            continue
        entity_reg.async_update_entity(
            entity.entity_id,
            new_unique_id=target_unique_id,
            new_entity_id=target_entity_id,
        )
