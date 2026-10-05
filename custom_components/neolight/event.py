"""Doorbell events reported by the paired NeoLight monitor."""

import asyncio
import logging

import aiohttp

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import AUTO_UNLOCK_SAFETY_HOLD, DOMAIN
from .ring_message import RingDeduplicator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Expose the alarm_message event when the mobile API is available."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    if runtime.mobile is not None and entry.options.get("enable_doorbell", True):
        async_add_entities([NeoLightDoorbellEvent(runtime.coordinator, entry)])


class NeoLightDoorbellEvent(CoordinatorEntity, EventEntity):
    """Trigger once when the cloud alarm message changes to a new ring."""

    _attr_has_entity_name = True
    _attr_name = "Doorbell"
    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_event_types = ["ring"]

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        host = entry.data["host"]
        self._attr_unique_id = f"{host}_doorbell"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name="NeoLight ALPHA Hybrid",
            manufacturer="NeoLight",
            model="ALPHA Hybrid",
            configuration_url=f"http://{host}/",
        )
        initial_raw = (coordinator.data.dps or {}).get("185") if coordinator.data else None
        self._ring_deduplicator = RingDeduplicator(initial_raw)
        self._pending_unlock: asyncio.Task | None = None

    def _handle_coordinator_update(self) -> None:
        state = self.coordinator.data
        raw = state.dps.get("185") if state else None
        if self._ring_deduplicator.observe(raw):
            self._trigger_event("ring")
            self.hass.async_create_task(self._notify_homekit_doorbell())
            if not AUTO_UNLOCK_SAFETY_HOLD and self._entry.options.get("auto_unlock_on_ring", False):
                if self._pending_unlock is None or self._pending_unlock.done():
                    self._pending_unlock = self.hass.async_create_task(self._auto_unlock())
        super()._handle_coordinator_update()

    async def _notify_homekit_doorbell(self) -> None:
        """Pulse the Scrypted HomeKit doorbell on the same Docker host."""
        url = self._entry.options.get(
            "homekit_ring_url",
            "http://127.0.0.1:38765/ring" if "vendor" not in self._entry.data else "",
        )
        if not url:
            return
        try:
            session = async_get_clientsession(self.hass)
            async with session.post(
                url, timeout=2
            ) as response:
                response.raise_for_status()
        except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as error:
            _LOGGER.debug("NeoLight HomeKit doorbell relay unavailable: %s", error)

    async def _auto_unlock(self) -> None:
        """Use the same validated relay button as a manual HA press."""
        # Give the monitor time to establish the panel call channel.
        delay = self._entry.options.get("auto_unlock_delay", 0)
        await asyncio.sleep(delay)
        if not self._entry.options.get("auto_unlock_on_ring", True):
            return
        relay = self._entry.options.get("auto_unlock_relay", "lock_1")
        if relay not in {"lock_1", "lock_2"}:
            _LOGGER.error("NeoLight auto unlock relay is invalid")
            return
        registry = entity_registry.async_get(self.hass)
        button_id = registry.async_get_entity_id(
            "button", DOMAIN, f"{self._entry.data['host']}_{relay}"
        )
        if not button_id:
            _LOGGER.error("NeoLight auto unlock button is missing")
            return
        try:
            await self.hass.services.async_call(
                "button", "press", {"entity_id": button_id}, blocking=True
            )
            _LOGGER.info("NeoLight auto unlock sent to %s", relay)
        except HomeAssistantError as error:
            _LOGGER.error("NeoLight auto unlock failed: %s", error)
