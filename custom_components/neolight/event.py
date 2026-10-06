"""Doorbell events reported by the paired NeoLight monitor."""

import asyncio
import logging
import time

import aiohttp

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import AUTO_UNLOCK_SAFETY_HOLD, DOMAIN
from .call_control import CallControlError, reset_call
from .call_state import started_new_call
from .release_policy import release_mode
from .ring_message import RingDeduplicator, doorbell_event
from .settings import runtime_directory
from .video_router import VideoRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Expose the alarm_message event when the mobile API is available."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    if runtime.mobile is not None and entry.options.get("enable_doorbell", True):
        async_add_entities([NeoLightDoorbellEvent(runtime, entry, runtime_directory(hass, entry))])


class NeoLightDoorbellEvent(CoordinatorEntity, EventEntity):
    """Trigger once when the cloud alarm message changes to a new ring."""

    _attr_has_entity_name = True
    _attr_name = "Doorbell"
    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_event_types = ["ring"]

    def __init__(self, runtime, entry: ConfigEntry, state_dir) -> None:
        super().__init__(runtime.coordinator)
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
        initial_raw = (runtime.coordinator.data.dps or {}).get("185") if runtime.coordinator.data else None
        self._ring_deduplicator = RingDeduplicator(initial_raw)
        self._last_call_status = runtime.coordinator.data.call_status if runtime.coordinator.data else None
        self._last_trigger = 0.0
        self._active_call_triggered = False
        self._pending_unlock: asyncio.Task | None = None
        self._test_consumed = False
        self._video_router = VideoRouter(
            runtime, state_dir / "video_route.json",
            entry.options.get("call_video_channel", 0),
            entry.options.get("call_video_hold_seconds", 90),
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._video_router.resume()

    def _handle_coordinator_update(self) -> None:
        state = self.coordinator.data
        raw = state.dps.get("185") if state else None
        deadline = self._entry.options.get("auto_unlock_test_deadline", 0)
        if (self._entry.options.get("auto_unlock_test_once")
                and (not isinstance(deadline, (int, float)) or time.time() > deadline)):
            self.hass.config_entries.async_update_entry(
                self._entry,
                options={**self._entry.options, "auto_unlock_test_once": False,
                         "auto_unlock_test_deadline": 0},
            )
        fresh_snapshot = self._ring_deduplicator.observe(raw)
        call_status = state.call_status if state else None
        fresh_call = started_new_call(self._last_call_status, call_status)
        if call_status is not None:
            self._last_call_status = call_status
            if call_status != 0:
                self._active_call_triggered = False
        if fresh_call or (fresh_snapshot and not self._active_call_triggered
                          and time.monotonic() - self._last_trigger > 30):
            self._last_trigger = time.monotonic()
            if call_status == 0:
                self._active_call_triggered = True
            self._trigger_event("ring")
            if (self._entry.options.get("route_video_on_ring")
                    and self._entry.options.get("call_video_channel", 0) > 0):
                selected = self._video_router.ring()
                self.hass.async_create_task(self._notify_after_video_route(selected))
            else:
                self.hass.async_create_task(self._notify_homekit_doorbell())
            event = doorbell_event(raw) if fresh_snapshot else None
            captured_at = event[0] if event else int(time.time())
            mode = release_mode(
                self._entry.options, captured_at, time.time(), AUTO_UNLOCK_SAFETY_HOLD
            )
            if mode and (self._pending_unlock is None or self._pending_unlock.done()):
                if mode != "once" or not self._test_consumed:
                    self._test_consumed = mode == "once"
                    _LOGGER.info("NeoLight auto unlock requested for fresh ring (%s)", mode)
                    self._pending_unlock = self.hass.async_create_task(
                        self._auto_unlock(captured_at, mode)
                    )
        super()._handle_coordinator_update()

    async def _notify_after_video_route(self, selected: asyncio.Event) -> None:
        """Give the video input time to change before HomeKit requests a preview."""
        try:
            await asyncio.wait_for(selected.wait(), timeout=8)
        except asyncio.TimeoutError:
            pass
        await asyncio.sleep(1)
        await self._notify_homekit_doorbell()

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

    async def _auto_unlock(self, captured_at: int, mode: str) -> None:
        """Use the same validated relay button as a manual HA press."""
        try:
            await asyncio.sleep(self._entry.options.get("auto_unlock_delay", 0))
            if release_mode(
                self._entry.options, captured_at, time.time(), AUTO_UNLOCK_SAFETY_HOLD
            ) != mode:
                _LOGGER.warning("NeoLight auto unlock skipped: ring or arming expired")
                return
            relay = self._entry.options.get("auto_unlock_relay", "lock_1")
            if relay not in {"lock_1", "lock_2"} or (mode == "once" and relay != "lock_1"):
                _LOGGER.error("NeoLight auto unlock relay is invalid")
                return
            registry = entity_registry.async_get(self.hass)
            unique_id = f"{self._entry.data['host']}_{relay}"
            button_id = next((entity.entity_id for entity in registry.entities.values()
                              if entity.domain == "button" and entity.platform == DOMAIN
                              and entity.unique_id == unique_id), None)
            if not button_id:
                _LOGGER.error("NeoLight auto unlock button is missing")
                return
            await self.hass.services.async_call(
                "button", "press", {"entity_id": button_id}, blocking=True
            )
            _LOGGER.info("NeoLight auto unlock command acknowledged for %s", relay)
            if self._entry.options.get("hangup_after_auto_unlock"):
                await asyncio.sleep(2)
                try:
                    await reset_call(self._entry.options.get("native_call_control_port", 0))
                    _LOGGER.info("NeoLight call ended after auto unlock")
                except CallControlError as error:
                    _LOGGER.warning("NeoLight auto unlock succeeded but call hangup failed: %s", error)
        except Exception:
            _LOGGER.exception("NeoLight auto unlock failed")
        finally:
            if mode == "once":
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    options={**self._entry.options, "auto_unlock_test_once": False,
                             "auto_unlock_test_deadline": 0},
                )
