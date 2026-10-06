"""Sanitize Tuya call signaling before recording diagnostic metadata."""

from __future__ import annotations

from hashlib import sha256
import re
from typing import Any


_SAFE_LABEL = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def _digest(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return sha256(value.encode()).hexdigest()[:12]


def _label(value: object) -> str | None:
    return value if isinstance(value, str) and _SAFE_LABEL.fullmatch(value) else None


def summarize_message(message: Any, size: int) -> dict[str, Any]:
    """Return call metadata without IDs, credentials, or payload contents."""
    if not isinstance(message, dict):
        return {"encoding": "non-object", "bytes": size}
    body = message.get("data")
    if not isinstance(body, dict):
        body = message
    header = body.get("header")
    if not isinstance(header, dict):
        header = {}
    nested = body.get("data")
    if not isinstance(nested, dict):
        nested = body
    result = {
        "protocol": message.get("protocol") if type(message.get("protocol")) is int else None,
        "header_type": _label(header.get("type")),
        "call_type": _label(body.get("type")),
        "call_event": _label(nested.get("event")),
        "message_hash": _digest(nested.get("eData")),
        "channel_hash": _digest(nested.get("cid")),
        "keys": sorted(key for key in nested if isinstance(key, str))[:24],
        "bytes": size,
    }
    return result


def call_command(
    call_type: str, device_id: str, message_id: str, event: str,
    channel_id: str | None = None,
) -> dict[str, Any]:
    """Build the APK's protocol 308 accept/stop body for a known active call.

    Publishing is deliberately separate: this cannot identify a live call or
    establish that the paired analog adapter supports protocol 308.
    """
    if event not in {"accept", "stop"}:
        raise ValueError("Unsupported call event")
    if call_type == "doorbell" or not _label(call_type):
        raise ValueError("Call type is unsupported")
    if not all(isinstance(value, str) and value for value in (device_id, message_id)):
        raise ValueError("A device and message ID are required")
    data = {"devId": device_id, "event": event, "eData": message_id}
    if channel_id is not None:
        if not isinstance(channel_id, str) or not channel_id:
            raise ValueError("Channel ID is invalid")
        data["cid"] = channel_id
    return {"type": call_type, "data": data}
