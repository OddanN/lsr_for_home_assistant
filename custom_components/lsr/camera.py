# Version: 1.2.0
"""Camera platform for LSR integration."""

import logging
from datetime import datetime
from homeassistant.components.camera import Camera  # ← правильный импорт
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class LSRMainPassQRCamera(Camera):
    """Representation of LSR main pass QR camera."""

    def __init__(self, coordinator, account_id, camera_data):
        self._coordinator = coordinator
        self._account_id = account_id
        self._camera_data = camera_data

        # Номер л/с из координатора (если добавлен)
        personal_account_number = coordinator.data.get(account_id, {}).get("personal_account_number", account_id[-8:])
        entity_suffix = personal_account_number

        self._attr_unique_id = f"lsr_{entity_suffix}_mainpass_qr_camera"
        self._attr_name = "СКУД QR-камера"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_id)},
            name=coordinator.data.get(account_id, {}).get("account_title", f"ЛСР Л/с №{personal_account_number}"),
            manufacturer="ЛСР",
            model="Communal Account",
        )

        self._attr_has_entity_name = False  # отключаем префикс

    @property
    def is_streaming(self) -> bool:
        """Return true if the camera is streaming."""
        return True  # если стрим всегда доступен

    async def async_camera_image(self):
        """Return bytes of camera image."""
        # Реализуй получение скриншота, если API позволяет
        return None  # пока заглушка

    @property
    def stream_source(self):
        """Return the source of the stream."""
        # Здесь должен быть реальный URL стрима из camera_data
        return self._camera_data.get("stream_url")  # добавь в camera_data при загрузке
