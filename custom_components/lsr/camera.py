# Version: 1.1.3
"""Custom component for LSR integration, providing camera entities."""

import logging
from homeassistant.components.camera import CameraEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class LSRMainPassQRCamera(CameraEntity):
    """Representation of LSR main pass QR camera."""

    def __init__(self, coordinator, account_id, camera_data):
        self._coordinator = coordinator
        self._account_id = account_id
        self._camera_data = camera_data

        # Получаем номер л/с из координатора
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

        self._attr_has_entity_name = False  # ← отключаем префикс

        # Опционально: если есть stream URL
        self._stream_source = camera_data.get("stream_url")  # ← добавь в camera_data

    @property
    def is_streaming(self) -> bool:
        """Return true if the camera is streaming."""
        return bool(self._stream_source)

    async def async_camera_image(self):
        """Return bytes of camera image."""
        # Реализуй получение скриншота, если API позволяет
        # return await self._coordinator.get_camera_snapshot(self._camera_data['id'])
        return None  # пока заглушка

    @property
    def stream_source(self):
        """Return the source of the stream."""
        return self._stream_source

    @property
    def frontend_url(self):
        """Return URL to the camera's frontend."""
        return self._stream_source  # если стрим доступен через URL