"""Temporarily select a call camera and restore the previous panel channel."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
import time

from .panel_protocol import PanelProfile
from .settings import write_private_json

_LOGGER = logging.getLogger(__name__)


def selected_channel(raw: object) -> int | None:
    """Read the active channel without trusting an arbitrary cloud DP payload."""
    if not isinstance(raw, str):
        return None
    try:
        channel = json.loads(raw).get("cc")
    except (ValueError, AttributeError):
        return None
    return channel if type(channel) is int and channel > 0 else None


class VideoRouter:
    """One route per monitor; a new ring extends the current call window."""

    def __init__(self, runtime, state_path: Path, call_channel: int, hold_seconds: int) -> None:
        self._runtime = runtime
        self._state_path = state_path
        self._call_channel = call_channel
        self._hold_seconds = hold_seconds
        self._deadline = 0.0
        self._task: asyncio.Task | None = None
        self._selected = asyncio.Event()

    def ring(self) -> asyncio.Event:
        self._deadline = time.time() + self._hold_seconds
        if self._task is None or self._task.done():
            self._selected.clear()
            self._task = asyncio.create_task(self._route())
        elif self._state_path.exists():
            try:
                state = json.loads(self._state_path.read_text())
                state["expires"] = self._deadline
                write_private_json(self._state_path, state)
            except (ValueError, OSError):
                _LOGGER.warning("NeoLight call video deadline could not be extended")
        return self._selected

    def resume(self) -> None:
        """Restore a call route after a Home Assistant reload or restart."""
        try:
            state = json.loads(self._state_path.read_text())
            target = state["call_channel"]
            previous = state["previous_channel"]
            deadline = state["expires"]
            if (type(target) is not int or type(previous) is not int
                    or type(deadline) not in (int, float)
                    or target < 1 or previous < 1):
                raise ValueError("invalid call route state")
        except (FileNotFoundError, ValueError, KeyError, TypeError):
            return
        self._deadline = deadline
        self._selected.set()
        self._task = asyncio.create_task(self._finish(target, previous))

    async def _device(self):
        vendor = self._runtime.vendor
        device = await self._runtime.mobile.read_device(vendor["paired_device_id"])
        if device.get("isOnline") is not True:
            raise ValueError("monitor is offline")
        schema = device.get("schema")
        if isinstance(schema, str):
            schema = json.loads(schema)
        profile = PanelProfile.from_schema(schema, required=("channel",))
        dp_id = str(profile.dp_ids["channel"])
        raw = (device.get("dps") or {}).get(dp_id)
        if selected_channel(raw) is None:
            raise ValueError("current video channel is unknown")
        return profile, dp_id, raw

    async def _wait_for_channel(self, channel: int, dp_id: str) -> None:
        """A cloud publish can be acknowledged before the DP state changes."""
        for _ in range(7):
            device = await self._runtime.mobile.read_device(
                self._runtime.vendor["paired_device_id"]
            )
            if selected_channel((device.get("dps") or {}).get(dp_id)) == channel:
                return
            await asyncio.sleep(1)
        raise TimeoutError(f"video input {channel} was not confirmed")

    async def _route(self) -> None:
        previous: int | None = None
        try:
            profile, dp_id, raw = await self._device()
            previous = selected_channel(raw)
            if previous == self._call_channel:
                return
            command = profile.channel_command(raw, self._call_channel)
            await asyncio.to_thread(write_private_json, self._state_path, {
                "call_channel": self._call_channel,
                "previous_channel": previous,
                "expires": self._deadline,
            })
            await self._runtime.mobile.publish_dps(
                self._runtime.vendor["paired_device_id"], command
            )
            await self._wait_for_channel(self._call_channel, dp_id)
            _LOGGER.info("NeoLight video routed to call channel %s", self._call_channel)
            self._selected.set()
            await self._finish(self._call_channel, previous)
        except Exception:
            _LOGGER.exception("NeoLight call video routing failed")
            if self._state_path.exists() and previous is not None:
                await self._finish(self._call_channel, previous)
        finally:
            self._selected.set()

    async def _finish(self, target: int, previous: int) -> None:
        try:
            while self._deadline > time.time():
                await asyncio.sleep(min(self._deadline - time.time(), 5))
            for attempt in range(3):
                try:
                    profile, dp_id, raw = await self._device()
                    if selected_channel(raw) == target:
                        command = profile.channel_command(raw, previous)
                        await self._runtime.mobile.publish_dps(
                            self._runtime.vendor["paired_device_id"], command
                        )
                        await self._wait_for_channel(previous, dp_id)
                        _LOGGER.info("NeoLight video restored to channel %s", previous)
                    self._state_path.unlink(missing_ok=True)
                    return
                except Exception:
                    _LOGGER.exception("NeoLight call video restore attempt %s failed", attempt + 1)
                    await asyncio.sleep(5)
        except asyncio.CancelledError:
            raise
