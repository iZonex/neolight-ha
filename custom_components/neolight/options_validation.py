"""Validate one NeoLight settings page without touching other options."""

import re
import time
from typing import Any

STREAM_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")


def validate_option_section(section: str, current: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    """Validate one page without changing unrelated saved settings."""
    updates = dict(values)
    combined = {**current, **updates}
    if section == "entrances":
        if combined["route_video_on_ring"] and not combined["call_video_channel"]:
            raise ValueError("invalid_call_video_channel")
        if combined.get("auto_unlock_on_ring") and not combined.get(
                f"enable_{combined.get('auto_unlock_relay', 'lock_1')}",
                combined.get("auto_unlock_relay", "lock_1") == "lock_1"):
            raise ValueError("invalid_auto_unlock_relay")
    elif section == "calls":
        if not combined["enable_doorbell"] and combined.get("auto_unlock_on_ring"):
            raise ValueError("doorbell_required")
    elif section == "automatic_opening":
        if combined["hangup_after_auto_unlock"] and not combined.get("native_call_control_port"):
            raise ValueError("invalid_call_control_port")
        opening_requested = combined["auto_unlock_on_ring"] or combined["auto_unlock_test_once"]
        if opening_requested and not combined.get("enable_doorbell", True):
            raise ValueError("doorbell_required")
        if opening_requested and not combined.get(
                f"enable_{combined['auto_unlock_relay']}", combined["auto_unlock_relay"] == "lock_1"):
            raise ValueError("invalid_auto_unlock_relay")
        if updates["auto_unlock_test_once"]:
            updates["auto_unlock_on_ring"] = False
        updates["auto_unlock_test_deadline"] = (
            int(time.time()) + 900 if updates["auto_unlock_test_once"] else 0
        )
    elif section == "apple_home":
        url = updates["homekit_ring_url"].strip()
        if url and not url.startswith(("http://", "https://")):
            raise ValueError("invalid_ring_url")
        updates["homekit_ring_url"] = url
    elif section == "advanced":
        if combined.get("hangup_after_auto_unlock") and not combined["native_call_control_port"]:
            raise ValueError("invalid_call_control_port")
        url = updates["restream_url"].strip()
        stream_id = updates["stream_id"].strip().lower()
        if url and not url.startswith(("rtsp://", "rtsps://")):
            raise ValueError("invalid_stream_url")
        if stream_id and not STREAM_ID_PATTERN.fullmatch(stream_id):
            raise ValueError("invalid_stream_id")
        updates["restream_url"] = url
        updates["stream_id"] = stream_id
        updates["rtsp_user"] = updates["rtsp_user"].strip()
        updates["rtsp_password"] = updates.get("rtsp_password") or current.get("rtsp_password", "")
    elif section == "account":
        email = updates["email"].strip()
        country = updates["country_code"].strip()
        password = updates.get("password") or current.get("password", "")
        if not email or not password or not country.isdigit():
            raise ValueError("invalid_account")
        updates = {"email": email, "password": password, "country_code": country}
    else:
        raise ValueError("unknown_options_page")
    return updates
