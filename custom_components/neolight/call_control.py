"""Local control of the optional native P2P bridge."""

from __future__ import annotations

import asyncio
import json


class CallControlError(Exception):
    """The native bridge could not finish the current conversation."""


async def _command(port: int, command: str) -> bytes:
    if not 1 <= port <= 65535:
        raise CallControlError("Native call control is not configured")
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", port), timeout=2
        )
        try:
            writer.write(command.encode() + b"\n")
            await writer.drain()
            response = await asyncio.wait_for(reader.readline(), timeout=4)
        finally:
            writer.close()
            await writer.wait_closed()
    except (OSError, asyncio.TimeoutError) as error:
        raise CallControlError("Native call control is unavailable") from error
    return response


async def reset_call(port: int) -> None:
    """Ask the localhost bridge for the tested Talk -> Stop sequence."""
    if await _command(port, "reset") != b"ok\n":
        raise CallControlError("Native bridge could not finish the call")


async def read_call_status(port: int) -> dict | None:
    """Read transient native call state without exposing call identifiers."""
    if not port:
        return None
    try:
        status = json.loads(await _command(port, "status"))
    except (CallControlError, ValueError):
        return None
    if (not isinstance(status, dict) or status.get("state") not in
            {"idle", "ringing", "answered"} or type(status.get("talk_active")) is not bool):
        return None
    return {"state": status["state"], "talk_active": status["talk_active"],
            "call_type": status.get("call_type"), "age_seconds": status.get("age_seconds")}


async def answer_call(port: int) -> None:
    response = await _command(port, "answer")
    if response != b"ok\n":
        raise CallControlError("No fresh controllable call" if response == b"no_call\n"
                               else "Native bridge is busy")


async def hangup_call(port: int) -> None:
    response = await _command(port, "hangup")
    if response != b"ok\n":
        raise CallControlError("No answered call" if response == b"no_call\n"
                               else "Native bridge is busy")
