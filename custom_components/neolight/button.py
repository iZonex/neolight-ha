"""NeoLight panel's two relay controls."""

import asyncio
import json
import logging
import time

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .panel_protocol import PanelProfile


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add relay buttons when the app's DP transport is configured."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    profile = PanelProfile.from_schema(
        runtime.coordinator.data.schema if runtime.mobile is not None else []
    )
    buttons = []
    registry = entity_registry.async_get(hass)
    for control, name, enabled in (
        ("lock_1", "Lock 1", entry.options.get("enable_lock_1", True)),
        ("lock_2", "Lock 2", entry.options.get("enable_lock_2", False)),
    ):
        if runtime.mobile is not None and profile.supports(control) and enabled:
            buttons.append(NeoLightRelayButton(entry, runtime, control, name))
        elif not enabled:
            old_entity = registry.async_get_entity_id(
                "button", DOMAIN, f"{entry.data['host']}_{control}"
            )
            if old_entity:
                registry.async_remove(old_entity)
    async_add_entities(buttons)


class NeoLightRelayButton(ButtonEntity):
    """Publish the exact DP used by a dashboard lock button."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, runtime, control: str, name: str) -> None:
        host = entry.data["host"]
        self._runtime = runtime
        self._control = control
        self._attr_name = name
        self._attr_unique_id = f"{host}_{control}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name="NeoLight ALPHA Hybrid",
            manufacturer="NeoLight",
            model="ALPHA Hybrid",
            configuration_url=f"http://{host}/",
        )
        self._press_lock = asyncio.Lock()
        self._last_press = 0.0

    async def async_press(self) -> None:
        """Read the current DP, then send one release command through the app API."""
        async with self._press_lock:
            if time.monotonic() - self._last_press < 2:
                raise HomeAssistantError("Relay button was pressed too recently")
            vendor = self._runtime.vendor
            device = await self._runtime.mobile.read_device(vendor["paired_device_id"])
            if device.get("isOnline") is not True:
                raise HomeAssistantError("NeoLight device is offline")
            schema = device.get("schema")
            try:
                profile = PanelProfile.from_schema(
                    json.loads(schema) if isinstance(schema, str) else schema,
                    required=(self._control,),
                )
            except (ValueError, TypeError) as error:
                raise HomeAssistantError(f"NeoLight relay schema changed: {error}") from error
            dp_id = str(profile.dp_ids[self._control])
            current = (device.get("dps") or {}).get(dp_id)
            if current is True:
                raise HomeAssistantError("Relay command is already active")
            if current is not False:
                raise HomeAssistantError("Relay state is unknown")
            command = profile.lock_command(self._control, current)
            await self._runtime.mobile.publish_dps(vendor["paired_device_id"], command)
            self._last_press = time.monotonic()
            _LOGGER.info("NeoLight %s release command acknowledged by account API", self._control)
            await self._runtime.coordinator.async_request_refresh()
