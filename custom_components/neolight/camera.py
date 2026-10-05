"""RTSP camera exposed by the NeoLight monitor."""

import asyncio
import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_RTSP_PASSWORD, CONF_RTSP_USER, CONF_STREAM_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create a camera only when a verified stream identifier was supplied."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    if not entry.options.get("enable_camera", True):
        return
    if stream_id := runtime.vendor.get("stream_id") or entry.data.get(CONF_STREAM_ID):
        client = runtime.monitor
        source = runtime.vendor.get("restream_url") or client.rtsp_url(
            stream_id,
            runtime.vendor.get(CONF_RTSP_USER, entry.data.get(CONF_RTSP_USER, "")),
            runtime.vendor.get(CONF_RTSP_PASSWORD, entry.data.get(CONF_RTSP_PASSWORD, "")),
        )
        async_add_entities([NeoLightCamera(entry, source)])


class NeoLightCamera(Camera):
    """Video forwarded by the indoor monitor from its connected panel."""

    _attr_has_entity_name = True
    _attr_name = "Door camera"
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_use_stream_for_stills = False

    def __init__(self, entry: ConfigEntry, source: str) -> None:
        super().__init__()
        host = entry.data["host"]
        self._source = source
        self._attr_unique_id = f"{host}_door_camera"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name="NeoLight ALPHA Hybrid",
            manufacturer="NeoLight",
            model="ALPHA Hybrid",
            configuration_url=f"http://{host}/",
        )

    async def stream_source(self) -> str | None:
        """Return the observed RTSP route to Home Assistant's stream worker."""
        return self._source

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Get a fresh JPEG without relying on HA's cached stream keyframe."""
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-rtsp_transport", "tcp", "-i", self._source,
            "-ss", "2", "-an", "-frames:v", "1",
            "-vf", "scale=640:-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=9)
        except TimeoutError:
            process.kill()
            await process.communicate()
            _LOGGER.warning("NeoLight camera snapshot timed out")
            return None
        if process.returncode != 0 or not stdout:
            _LOGGER.warning("NeoLight camera snapshot failed")
            return None
        return stdout
