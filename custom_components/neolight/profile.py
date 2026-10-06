"""Validate a private app profile without loading Home Assistant."""

import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5


APP_PROFILE_KEYS = {"api_host", "signing_key", "static_fields", "paired_device_id"}
STATIC_FIELD_KEYS = {"appVersion", "chKey", "clientId", "deviceId", "lang", "os", "ttid"}


def parse_app_profile(raw: str) -> dict[str, Any]:
    """Validate per-installation credentials without owner-specific defaults."""
    try:
        profile = json.loads(raw)
    except (ValueError, TypeError) as error:
        raise ValueError("invalid_profile") from error
    if not isinstance(profile, dict) or not APP_PROFILE_KEYS <= profile.keys():
        raise ValueError("invalid_profile")
    if not all(isinstance(profile[key], str) and profile[key] for key in
               ("api_host", "signing_key", "paired_device_id")):
        raise ValueError("invalid_profile")
    fields = profile["static_fields"]
    if not isinstance(fields, dict) or not STATIC_FIELD_KEYS <= fields.keys():
        raise ValueError("invalid_profile")
    if not all(isinstance(fields[key], str) and fields[key] for key in STATIC_FIELD_KEYS):
        raise ValueError("invalid_profile")
    if "://" in profile["api_host"] or "/" in profile["api_host"]:
        raise ValueError("invalid_profile")
    return {key: profile[key] for key in APP_PROFILE_KEYS}


def ha_static_fields(fields: dict[str, str]) -> dict[str, str]:
    """Use a stable HA installation ID distinct from the owner's phone app."""
    original = fields.get("deviceId")
    if not isinstance(original, str) or not original:
        raise ValueError("invalid_profile")
    result = dict(fields)
    result["deviceId"] = str(uuid5(NAMESPACE_URL, f"neolight-ha:{original}"))
    return result
