# Version: 1.1.3
"""Initialization module for the LSR integration.

This module sets up the LSR integration by handling config entries, coordinators,
and platform setups for sensors and cameras.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

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

@callback
def async_create_lsr_groups(hass: HomeAssistant, entry: ConfigEntry):
    """Создаёт группы для аккаунта LSR при первой настройке."""
    account_id = entry.entry_id  # или используй entry.data.get("account_id"), если есть

    # Группа 1: Основное (всегда видимые сенсоры)
    hass.services.call(
        "group",
        "create",
        {
            "name": f"ЛСР - Основное ({account_id})",
            "entities": [
                f"sensor.lsr_{account_id}_meter_count",
                f"sensor.lsr_{account_id}_address",
                f"sensor.lsr_{account_id}_personal_account",
                f"sensor.lsr_{account_id}_notification_count",
                f"sensor.lsr_{account_id}_camera_count",
                # добавь сюда все value-сенсоры счётчиков, если хочешь
            ],
            "icon": "mdi:home-automation",
        },
        blocking=True,
    )

    # Группа 2: Счётчики (отдельная группа для всех показаний)
    hass.services.call(
        "group",
        "create",
        {
            "name": f"ЛСР - Счётчики ({account_id})",
            "entities": [
                f"sensor.lsr_{account_id}_meter_{meter_number}_value"  # ← динамически, см. ниже
                for meter_number in [...]  # можно собрать из coordinator.data
            ],
            "icon": "mdi:water-meter",
        },
        blocking=True,
    )

    # Группа 3: Заявки (диагностика)
    hass.services.call(
        "group",
        "create",
        {
            "name": f"ЛСР - Заявки ({account_id})",
            "entities": [
                f"sensor.lsr_{account_id}_communalrequest_count_total",
                f"sensor.lsr_{account_id}_communalrequest_count_done",
                # и остальные
            ],
            "icon": "mdi:clipboard-text",
        },
        blocking=True,
    )

    # Группа 4: Управление (СКУД, кнопки и т.д.)
    hass.services.call(
        "group",
        "create",
        {
            "name": f"ЛСР - Управление ({account_id})",
            "entities": [
                f"sensor.lsr_{account_id}_mainpass_pin",
                f"sensor.lsr_{account_id}_guestpass",
                # добавь кнопки, если будут
            ],
            "icon": "mdi:shield-key",
        },
        blocking=True,
    )