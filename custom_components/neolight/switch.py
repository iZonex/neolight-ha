"""Home Assistant controls for NeoLight call and motion behavior."""

import asyncio
import json
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AUTO_UNLOCK_SAFETY_HOLD, DOMAIN
from .panel_protocol import PanelProfile

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Show automatic opening directly on the NeoLight device page."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    switches = []
    if runtime.mobile is not None:
        profile = PanelProfile.from_schema(runtime.coordinator.data.schema)
        if profile.supports("motion"):
            switches.append(NeoLightMotionSwitch(entry, runtime))
    if AUTO_UNLOCK_SAFETY_HOLD:
        registry = entity_registry.async_get(hass)
        unique_id = f"{entry.data['host']}_auto_unlock_on_ring"
        for old_entity in tuple(registry.entities.values()):
            if (old_entity.domain == "switch" and old_entity.platform == DOMAIN
                    and old_entity.unique_id == unique_id):
                registry.async_remove(old_entity.entity_id)
                _LOGGER.info("Removed the unavailable NeoLight auto unlock switch")
    elif runtime.mobile is not None:
        switches.append(NeoLightAutoUnlockSwitch(entry))
    async_add_entities(switches)


class NeoLightMotionSwitch(CoordinatorEntity, SwitchEntity):
    """Control the monitor's motion detection using its paired DP schema."""

    _attr_has_entity_name = True
    _attr_translation_key = "motion_detection"
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, entry: ConfigEntry, runtime) -> None:
        super().__init__(runtime.coordinator)
        self._runtime = runtime
        host = entry.data["host"]
        self._attr_unique_id = f"{host}_motion_detection"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)}, name="NeoLight ALPHA Hybrid",
            manufacturer="NeoLight", model="ALPHA Hybrid",
            configuration_url=f"http://{host}/",
        )
        self._write_lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        state = self.coordinator.data
        if not state or not state.cloud_online:
            return False
        profile = PanelProfile.from_schema(state.schema)
        return profile.supports("motion") and type(
            state.dps.get(str(profile.dp_ids["motion"]))
        ) is bool

    @property
    def is_on(self) -> bool | None:
        if not self.available:
            return None
        profile = PanelProfile.from_schema(self.coordinator.data.schema)
        return self.coordinator.data.dps[str(profile.dp_ids["motion"])]

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_motion(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_motion(False)

    async def _set_motion(self, enabled: bool) -> None:
        async with self._write_lock:
            vendor = self._runtime.vendor
            device = await self._runtime.mobile.read_device(vendor["paired_device_id"])
            if device.get("isOnline") is not True:
                raise HomeAssistantError("NeoLight device is offline")
            schema = device.get("schema")
            try:
                profile = PanelProfile.from_schema(
                    json.loads(schema) if isinstance(schema, str) else schema,
                    required=("motion",),
                )
            except (ValueError, TypeError) as error:
                raise HomeAssistantError(f"NeoLight motion schema changed: {error}") from error
            dp_id = str(profile.dp_ids["motion"])
            current = (device.get("dps") or {}).get(dp_id)
            if type(current) is not bool:
                raise HomeAssistantError("NeoLight motion state is unknown")
            if current == enabled:
                return
            await self._runtime.mobile.publish_dps(
                vendor["paired_device_id"], profile.motion_command(enabled)
            )
            await self._runtime.coordinator.async_request_refresh()


class NeoLightAutoUnlockSwitch(SwitchEntity):
    """Enable or disable the configured relay pulse on a doorbell event."""

    _attr_has_entity_name = True
    _attr_name = "Auto unlock on ring"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:door-open"
    _attr_available = not AUTO_UNLOCK_SAFETY_HOLD

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        host = entry.data["host"]
        self._attr_unique_id = f"{host}_auto_unlock_on_ring"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name="NeoLight ALPHA Hybrid",
            manufacturer="NeoLight",
            model="ALPHA Hybrid",
            configuration_url=f"http://{host}/",
        )

    @property
    def is_on(self) -> bool:
        """Reflect the persisted HA setting."""
        return not AUTO_UNLOCK_SAFETY_HOLD and self._entry.options.get("auto_unlock_on_ring", False)

    async def async_turn_on(self, **kwargs) -> None:
        """Enable automatic opening for the next ring."""
        if AUTO_UNLOCK_SAFETY_HOLD:
            raise HomeAssistantError("NeoLight auto unlock is paused by the integration safety hold")
        self.hass.config_entries.async_update_entry(
            self._entry, options={**self._entry.options, "auto_unlock_on_ring": True}
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable automatic opening for the next ring."""
        self.hass.config_entries.async_update_entry(
            self._entry, options={**self._entry.options, "auto_unlock_on_ring": False}
        )
        self.async_write_ha_state()
