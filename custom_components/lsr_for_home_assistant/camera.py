# Version: 1.2.2
"""Custom component for LSR integration, providing camera entities."""

import logging
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import LSRDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities,
) -> None:
    """Set up the LSR camera platform.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (ConfigEntry): The configuration entry for the integration.
        async_add_entities: Callback to add entities to Home Assistant.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for account_id, account_data in coordinator.data.items():
        personal_account_number = account_data.get("personal_account_number", "unknown")
        entity_suffix = personal_account_number if personal_account_number != "unknown" else account_id[-8:]

        # Add existing cameras
        for camera in account_data.get("cameras", []):
            stream_url = camera.get("stream_url")
            preview_url = camera.get("preview")
            if not stream_url or not isinstance(stream_url, str):
                _LOGGER.warning("Invalid or missing stream_url for camera %s (account %s)", camera.get("id"),
                                account_id)
                continue
            if not preview_url or not isinstance(preview_url, str):
                _LOGGER.warning("Invalid or missing preview_url for camera %s (account %s)", camera.get("id"),
                                account_id)
                preview_url = None
            entity_id = f"camera.lsr_{entity_suffix}_camera_{camera['id']}".lower().replace("-", "_")
            entities.append(
                LSRCamera(
                    coordinator,
                    account_id,
                    camera["id"],
                    camera["title"],
                    stream_url,
                    preview_url,
                    entity_id,
                    entity_id,
                )
            )

        # Add main pass QR camera
        main_pass = account_data.get("main_pass", {})
        if main_pass and main_pass.get("qr"):
            qr_entity_id = f"camera.lsr_{entity_suffix}_mainpass_qr".lower().replace("-", "_")
            entities.append(
                LSRMainPassQRCamera(
                    coordinator,
                    account_id,
                    main_pass["qr"],
                    main_pass.get("text", ""),
                    qr_entity_id,
                    qr_entity_id,
                )
            )

    async_add_entities(entities)
    _LOGGER.debug("Added %s camera entities", len(entities))


class LSRCamera(Camera):
    """Representation of an LSR camera."""

    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
            self,
            coordinator: LSRDataUpdateCoordinator,
            account_id: str,
            camera_id: str,
            name: str,
            stream_url: str,
            preview_url: str | None,
            entity_id: str,
            unique_id: str,
    ) -> None:
        """Initialize the camera."""
        super().__init__()
        self._coordinator = coordinator
        self._account_id = account_id
        self._camera_id = camera_id
        self._attr_unique_id = unique_id
        self.entity_id = entity_id
        self._attr_name = name
        self._attr_has_entity_name = False
        self._stream_url = stream_url
        self._preview_url = preview_url
        self._attr_preload_stream = True
        self._stream = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._account_id)},
            name=coordinator.data.get(self._account_id, {}).get("account_title",
                                                                f"ЛСР Аккаунт {self._account_id[-8:]}"),
            manufacturer="ЛСР",
            model="Communal Account",
        )
        self._attr_entity_registry_enabled_default = True
        _LOGGER.debug(
            "Initialized camera %s with unique_id %s, entity_id=%s, stream_url: %s",
            self._attr_name, self._attr_unique_id, entity_id, self._stream_url
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        is_available = bool(self._stream_url)
        return is_available

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Return bytes of camera image."""
        if not self._preview_url:
            _LOGGER.debug("No preview URL for camera %s", self._camera_id)
            return None
        try:
            async with self._coordinator.session.get(self._preview_url, timeout=10) as resp:
                if resp.status != 200:
                    _LOGGER.error("Failed to fetch camera image for %s: HTTP %s", self._camera_id, resp.status)
                    return None
                return await resp.read()
        except Exception as err:
            _LOGGER.error("Error fetching camera image for %s: %s", self._camera_id, err)
            return None

    async def stream_source(self) -> str | None:
        """Return the stream source URL.

        ВНИМАНИЕ: Это должен быть асинхронный метод, а не свойство!
        Home Assistant вызывает его как async метод.
        """
        _LOGGER.debug("Providing stream source for %s: %s", self._attr_unique_id, self._stream_url)
        return self._stream_url if self._stream_url else None

    async def async_create_stream(self):
        """Create a stream."""
        try:
            # В Home Assistant 2025 API мог измениться
            # Попробуем разные варианты импорта
            from homeassistant.components.stream import create_stream

            if not self._stream_url:
                return None

            if self._stream is None:
                self._stream = create_stream(
                    self.hass,
                    self._stream_url,
                    options={
                        "use_wallclock_as_timestamps": True,
                    }
                )
                _LOGGER.debug("Stream created for %s", self._attr_unique_id)
        except ImportError as err:
            _LOGGER.debug("First import method failed: %s", err)
            try:
                # Альтернативный вариант импорта
                from homeassistant.components.stream import async_create_stream as create_stream

                if self._stream is None:
                    self._stream = create_stream(
                        self.hass,
                        self._stream_url,
                        options={
                            "use_wallclock_as_timestamps": True,
                        }
                    )
                    _LOGGER.debug("Stream created (alt import) for %s", self._attr_unique_id)
            except ImportError as err2:
                _LOGGER.error("Cannot import stream creation function: %s", err2)
                return None
        except Exception as err:
            _LOGGER.error("Failed to create stream for %s: %s", self._attr_unique_id, err)
            return None

        return self._stream

    async def async_handle_web_rtc_offer(self, offer_sdp: str) -> str | None:
        """Handle WebRTC offer for HLS stream."""
        stream = await self.async_create_stream()
        if stream:
            try:
                return await stream.async_handle_web_rtc_offer(offer_sdp)
            except Exception as err:
                _LOGGER.error("Error handling WebRTC offer for %s: %s", self._attr_unique_id, err)
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "account_id": self._account_id,
            "camera_id": self._camera_id,
            "stream_url": self._stream_url,
            "preview_url": self._preview_url,
            "preload_stream": self._attr_preload_stream,
        }


class LSRMainPassQRCamera(Camera):
    """Representation of an LSR main pass QR code as a camera."""

    def __init__(
            self,
            coordinator: LSRDataUpdateCoordinator,
            account_id: str,
            qr_url: str,
            text: str,
            entity_id: str,
            unique_id: str,
    ) -> None:
        """Initialize the QR camera."""
        super().__init__()
        self._coordinator = coordinator
        self._account_id = account_id
        self._qr_url = qr_url
        self._text = text
        self._attr_unique_id = unique_id
        self.entity_id = entity_id
        self._attr_name = "СКУД QR-код"
        self._attr_has_entity_name = False
        self._attr_preload_stream = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._account_id)},
            name=coordinator.data.get(self._account_id, {}).get("account_title",
                                                                f"ЛСР Аккаунт {self._account_id[-8:]}"),
            manufacturer="ЛСР",
            model="Communal Account",
        )
        self._attr_entity_registry_enabled_default = True
        _LOGGER.debug(
            "Initialized QR camera %s with unique_id %s, entity_id=%s, qr_url: %s",
            self._attr_name, self._attr_unique_id, entity_id, self._qr_url
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return bool(self._qr_url)

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Return bytes of QR code image."""
        if not self._qr_url:
            _LOGGER.debug("No QR URL for camera %s", self._attr_unique_id)
            return None
        try:
            async with self._coordinator.session.get(self._qr_url, timeout=10) as resp:
                if resp.status != 200:
                    _LOGGER.error("Failed to fetch QR image for %s: HTTP %s", self._attr_unique_id, resp.status)
                    return None
                return await resp.read()
        except Exception as err:
            _LOGGER.error("Error fetching QR image for %s: %s", self._attr_unique_id, err)
            return None

    async def stream_source(self) -> str | None:
        """QR camera doesn't support streaming."""
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "account_id": self._account_id,
            "qr_url": self._qr_url,
            "text": self._text,
        }
