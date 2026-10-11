"""Receive validated call events from the localhost native bridge."""

import asyncio
import json
import logging
import time

from homeassistant.helpers.dispatcher import async_dispatcher_send

_LOGGER = logging.getLogger(__name__)


async def watch_native_calls(hass, entry_id: str, port: int) -> None:
    """Reconnect while the integration is loaded; publish only fresh ring signals."""
    if not 1 <= port <= 65535:
        return
    while True:
        writer = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", port), timeout=3
            )
            writer.write(b"watch\n")
            await writer.drain()
            if await asyncio.wait_for(reader.readline(), timeout=3) != b"ok\n":
                raise ValueError("Native bridge does not support call events")
            while line := await reader.readline():
                try:
                    event = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    continue
                if (isinstance(event, dict) and event.get("event") == "ring"
                        and type(event.get("sequence")) is int
                        and event.get("call_type") in {"ac_doorbell", "doorbell"}
                        and type(event.get("received_at")) in {int, float}
                        and abs(time.time() - event["received_at"]) <= 10):
                    async_dispatcher_send(hass, f"neolight_{entry_id}_native_ring", event)
        except (OSError, asyncio.TimeoutError, ValueError) as error:
            _LOGGER.debug("NeoLight native call stream disconnected: %s", error)
        finally:
            if writer is not None:
                writer.close()
                await writer.wait_closed()
        await asyncio.sleep(2)
