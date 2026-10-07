"""Select one of the monitor's video inputs from Home Assistant."""

import json
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .panel_protocol import PanelProfile
from .video_router import selected_channel

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    if runtime.mobile is not None and PanelProfile.from_schema(runtime.coordinator.data.schema).supports("channel"):
        async_add_entities([NeoLightChannelSelect(runtime, entry)])


class NeoLightChannelSelect(CoordinatorEntity, SelectEntity):
    """Expose the panel's own channel list and validated selection command."""

    _attr_has_entity_name = True
    _attr_name = "Video input"
    _attr_icon = "mdi:video-input-component"

    def __init__(self, runtime, entry: ConfigEntry) -> None:
        super().__init__(runtime.coordinator)
        self._runtime = runtime
        host = entry.data["host"]
        self._attr_unique_id = f"{host}_video_input"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name="NeoLight ALPHA Hybrid",
            manufacturer="NeoLight",
            model="ALPHA Hybrid",
            configuration_url=f"http://{host}/",
        )

    @property
    def available(self) -> bool:
        return bool(super().available and self.coordinator.data.cloud_online)

    def _channels(self) -> tuple[dict[str, int], int | None]:
        state = self.coordinator.data
        profile = PanelProfile.from_schema(state.schema)
        dp_id = str(profile.dp_ids["channel"])
        raw = state.dps.get(dp_id)
        value = json.loads(raw) if isinstance(raw, str) else {}
        channels = {
            f"{item['id']}: {item.get('n', 'Camera')}": item["id"]
            for item in value.get("chs", [])
            if isinstance(item, dict) and type(item.get("id")) is int
        }
        return channels, selected_channel(raw)

    @property
    def options(self) -> list[str]:
        try:
            return list(self._channels()[0])
        except (KeyError, TypeError, ValueError):
            return []

    @property
    def current_option(self) -> str | None:
        try:
            channels, current = self._channels()
            return next((name for name, channel in channels.items() if channel == current), None)
        except (KeyError, TypeError, ValueError):
            return None

    async def async_select_option(self, option: str) -> None:
        try:
            channels, _ = self._channels()
            channel = channels[option]
            vendor = self._runtime.vendor
            device = await self._runtime.mobile.read_device(vendor["paired_device_id"])
            if device.get("isOnline") is not True:
                raise ValueError("monitor is offline")
            schema = device.get("schema")
            profile = PanelProfile.from_schema(
                json.loads(schema) if isinstance(schema, str) else schema,
                required=("channel",),
            )
            raw = (device.get("dps") or {}).get(str(profile.dp_ids["channel"]))
            command = profile.channel_command(raw, channel)
            await self._runtime.mobile.publish_dps(vendor["paired_device_id"], command)
            await self._runtime.coordinator.async_request_refresh()
        except (KeyError, TypeError, ValueError) as error:
            raise HomeAssistantError(f"Video input unavailable: {error}") from error
        _LOGGER.info("NeoLight video input selected: %s", channel)
