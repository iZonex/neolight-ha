"""Momentary door release exposed as a HomeKit lock."""

import asyncio

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a door release when the paired account can control Lock 1."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    if runtime.mobile is not None and entry.options.get("enable_lock_1", True):
        async_add_entities([NeoLightDoorRelease(entry)])


class NeoLightDoorRelease(LockEntity):
    """Press Lock 1 and return to locked after the relay pulse."""

    _attr_has_entity_name = True
    _attr_name = "Door release"
    _attr_is_locked = True

    def __init__(self, entry: ConfigEntry) -> None:
        host = entry.data["host"]
        self._host = host
        self._attr_unique_id = f"{host}_door_release"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name="NeoLight ALPHA Hybrid",
            manufacturer="NeoLight",
            model="ALPHA Hybrid",
            configuration_url=f"http://{host}/",
        )
        self._reset_task: asyncio.Task | None = None

    async def async_unlock(self, **kwargs) -> None:
        """Send the same validated command as the HA Lock 1 button."""
        registry = entity_registry.async_get(self.hass)
        button_id = registry.async_get_entity_id(
            "button", DOMAIN, f"{self._host}_lock_1"
        )
        if not button_id:
            raise HomeAssistantError("NeoLight Lock 1 button is unavailable")
        await self.hass.services.async_call(
            "button", "press", {"entity_id": button_id}, blocking=True
        )
        self._attr_is_locked = False
        self.async_write_ha_state()
        if self._reset_task is not None:
            self._reset_task.cancel()
        self._reset_task = self.hass.async_create_task(self._reset_after_pulse())

    async def async_lock(self, **kwargs) -> None:
        """The physical relay returns to its locked state by itself."""
        self._attr_is_locked = True
        self.async_write_ha_state()

    async def _reset_after_pulse(self) -> None:
        await asyncio.sleep(2)
        self._attr_is_locked = True
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._reset_task is not None:
            self._reset_task.cancel()
