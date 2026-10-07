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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .call_control import CallControlError, answer_call, hangup_call, reset_call
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
            unique_id = f"{entry.data['host']}_{control}"
            for old_entity in tuple(registry.entities.values()):
                if (old_entity.domain == "button" and old_entity.platform == DOMAIN
                        and old_entity.unique_id == unique_id):
                    registry.async_remove(old_entity.entity_id)
    if entry.options.get("native_call_control_port", 0):
        buttons.append(NeoLightEndCallButton(entry))
        buttons.append(NeoLightCallButton(entry, runtime, "answer"))
        buttons.append(NeoLightCallButton(entry, runtime, "hangup"))
    async_add_entities(buttons)


class NeoLightEndCallButton(ButtonEntity):
    """Finish a stuck conversation using the local native bridge."""

    _attr_has_entity_name = True
    _attr_name = "End call"

    def __init__(self, entry: ConfigEntry) -> None:
        host = entry.data["host"]
        self._port = entry.options["native_call_control_port"]
        self._attr_unique_id = f"{host}_end_call"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name="NeoLight ALPHA Hybrid",
            manufacturer="NeoLight",
            model="ALPHA Hybrid",
            configuration_url=f"http://{host}/",
        )

    async def async_press(self) -> None:
        try:
            await reset_call(self._port)
        except CallControlError as error:
            raise HomeAssistantError(str(error)) from error


class NeoLightCallButton(CoordinatorEntity, ButtonEntity):
    """Control only a fresh call reported by the native bridge."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, runtime, action: str) -> None:
        super().__init__(runtime.coordinator)
        host = entry.data["host"]
        self._port = entry.options["native_call_control_port"]
        self._action = action
        self._attr_name = "Answer call" if action == "answer" else "Hang up call"
        self._attr_unique_id = f"{host}_{action}_call"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)}, name="NeoLight ALPHA Hybrid",
            manufacturer="NeoLight", model="ALPHA Hybrid",
            configuration_url=f"http://{host}/",
        )

    @property
    def available(self) -> bool:
        state = self.coordinator.data.native_call if self.coordinator.data else None
        return bool(state and state["state"] == (
            "ringing" if self._action == "answer" else "answered"))

    async def async_press(self) -> None:
        try:
            if self._action == "answer":
                await answer_call(self._port)
            else:
                await hangup_call(self._port)
        except CallControlError as error:
            raise HomeAssistantError(str(error)) from error
        await self.coordinator.async_request_refresh()


class NeoLightRelayButton(CoordinatorEntity, ButtonEntity):
    """Publish the exact DP used by a dashboard lock button."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, runtime, control: str, name: str) -> None:
        super().__init__(runtime.coordinator)
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

    @property
    def available(self) -> bool:
        return bool(super().available and self.coordinator.data.cloud_online)

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
