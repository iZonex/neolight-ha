"""Local control of the optional native P2P bridge."""

import asyncio


class CallControlError(Exception):
    """The native bridge could not finish the current conversation."""


async def reset_call(port: int) -> None:
    """Ask the localhost bridge for the tested Talk -> Stop sequence."""
    if not 1 <= port <= 65535:
        raise CallControlError("Native call control is not configured")
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", port), timeout=2
        )
        try:
            writer.write(b"reset\n")
            await writer.drain()
            response = await asyncio.wait_for(reader.readline(), timeout=4)
        finally:
            writer.close()
            await writer.wait_closed()
    except (OSError, asyncio.TimeoutError) as error:
        raise CallControlError("Native call control is unavailable") from error
    if response != b"ok\n":
        raise CallControlError("Native bridge could not finish the call")
