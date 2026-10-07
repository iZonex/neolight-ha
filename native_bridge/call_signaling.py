"""Sanitize Tuya call signaling before recording diagnostic metadata."""

from __future__ import annotations

from hashlib import sha256
import json
import re
from dataclasses import dataclass
import time
from typing import Any


_SAFE_LABEL = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


@dataclass(frozen=True)
class ActiveCall:
    """A recent call notification addressed to this paired device."""

    call_type: str
    device_id: str
    message_id: str
    channel_id: str | None


def incoming_call(message: Any, expected_device_id: str,
                  now_wall: float | None = None) -> ActiveCall | None:
    """Extract only the fields the APK uses for its call control command."""
    if not isinstance(message, dict) or message.get("protocol") != 43:
        return None
    body = message.get("data")
    if not isinstance(body, dict) or body.get("devId") != expected_device_id:
        return None
    call_type = body.get("etype")
    message_id = body.get("edata")
    channel_id = body.get("cid")
    if (not _label(call_type) or call_type == "doorbell"
            or not isinstance(message_id, str) or not message_id
            or len(message_id) > 512):
        return None
    if channel_id is not None and (not isinstance(channel_id, str) or not channel_id):
        return None
    recorded_at = body.get("time")
    if type(recorded_at) in (int, float) and recorded_at > 0:
        if recorded_at > 10_000_000_000:
            recorded_at /= 1000
        now_wall = time.time() if now_wall is None else now_wall
        if not -10 <= now_wall - recorded_at <= 60:
            return None
    return ActiveCall(call_type, expected_device_id, message_id, channel_id)


def ended_call_type(message: Any, expected_device_id: str) -> str | None:
    """Recognize a device-originated call end without trusting another device."""
    if not isinstance(message, dict) or message.get("protocol") != 308:
        return None
    body = message.get("data")
    if not isinstance(body, dict):
        return None
    detail = body.get("data")
    if (not isinstance(detail, dict) or detail.get("devId") != expected_device_id
            or detail.get("event") not in {"cancel", "stop"}):
        return None
    return _label(body.get("type"))


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
    if result["protocol"] == 43:
        result["push_type"] = _label(nested.get("etype"))
        result["push_data_hash"] = _digest(nested.get("edata"))
    if result["protocol"] == 4:
        dps = nested.get("dps")
        result["dp_format"] = type(dps).__name__ if dps is not None else None
        if isinstance(dps, str):
            try:
                dps = json.loads(dps)
            except ValueError:
                dps = None
        if isinstance(dps, dict):
            result["dp_ids"] = sorted(
                key for key in dps if isinstance(key, str) and key.isdigit()
            )[:24]
            result["ring_states"] = {
                key: dps[key] for key in ("239", "240", "247", "248")
                if isinstance(dps.get(key), str) and dps[key] in {"Ring", "Normal"}
            }
            result["alarm_hash"] = _digest(dps.get("185"))
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
