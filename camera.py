# Version: 1.0.0
"""Custom component for LSR integration, providing camera entities."""

import logging
import aiohttp
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import LSRDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """set up the LSR camera platform.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (ConfigEntry): The configuration entry for the integration.
        async_add_entities (AddEntitiesCallback): Callback to add entities to Home Assistant.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for account_id, account_data in coordinator.data.items():
        for camera in account_data.get("cameras", []):
            # Validate stream_url and preview_url
            stream_url = camera.get("stream_url")
            preview_url = camera.get("preview")
            if not stream_url or not isinstance(stream_url, str):
                _LOGGER.warning("Invalid or missing stream_url for camera %s (account %s)", camera.get("id"), account_id)
                continue
            if not preview_url or not isinstance(preview_url, str):
                _LOGGER.warning("Invalid or missing preview_url for camera %s (account %s)", camera.get("id"), account_id)
                preview_url = None
            entity_id = f"camera.lsr_{account_id}_camera_{camera['id']}".lower().replace("-", "_")
            entities.append(
                LSRCamera(
                    coordinator,
                    account_id,
                    camera["id"],
                    camera["title"],
                    stream_url,
                    preview_url,
                    entity_id,
                    entity_id,  # Устанавливаем unique_id равным entity_id
                )
            )
    async_add_entities(entities)
    _LOGGER.debug("Added %s camera entities", len(entities))

class LSRCamera(Camera):
    """Representation of an LSR camera.

    This class handles the creation and management of camera entities for the LSR integration.
    """

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
        """initialize the camera.

        Args:
            coordinator (LSRDataUpdateCoordinator): The data coordinator for the integration.
            account_id (str): The account ID associated with the camera.
            camera_id (str): The unique ID of the camera.
            name (str): The name of the camera.
            stream_url (str): The URL for the camera stream.
            preview_url (str | None): The URL for the camera preview image, if available.
            entity_id (str): The entity ID for the camera.
            unique_id (str): The unique ID for the camera.
        """
        super().__init__()
        self._coordinator = coordinator
        self._account_id = account_id
        self._camera_id = camera_id
        self._attr_unique_id = unique_id
        self._attr_name = name  # Используем title из API
        self._attr_has_entity_name = False
        self._stream_url = stream_url
        self._preview_url = preview_url
        self._attr_preload_stream = True  # Enable stream preloading
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._account_id)},  # Общее устройство
            name=f"Счет ID {self._account_id}",
            manufacturer="ЛСР",
            model="Communal Camera",
        )
        self._attr_entity_registry_enabled_default = True
        _LOGGER.debug(
            "Initialized camera %s with unique_id %s, entity_id=%s (not set directly), stream_url: %s, preview: %s, preload_stream: %s",
            self._attr_name, self._attr_unique_id, entity_id, self._stream_url, self._preview_url, self._attr_preload_stream
        )

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Returns:
            bool: True if the stream URL is available, false otherwise.
        """
        is_available = bool(self._stream_url)
        return is_available

    async def async_camera_image(self) -> bytes | None:
        """Return bytes of camera image.

        Returns:
            bytes | None: The image data if successful, none otherwise.
        """
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

    @property
    def stream_source(self) -> str | None:
        """Return the stream source URL.

        Returns:
            str | None: The stream URL if available, none otherwise.
        """
        _LOGGER.debug("Attempting to provide stream source for %s: %s", self._attr_unique_id, self._stream_url)
        return self._stream_url if self._stream_url else None

    @property
    def extra_state_attributes(self):
        """Return the state attributes.

        Returns:
            dict: Additional attributes for the camera entity.
        """
        return {
            "account_id": self._account_id,
            "camera_id": self._camera_id,
            "stream_url": self._stream_url,
            "preview_url": self._preview_url,
            "preload_stream": self._attr_preload_stream,
        }