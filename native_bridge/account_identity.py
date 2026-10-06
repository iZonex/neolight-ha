"""Give the media bridge its own repeatable mobile installation identity."""

from collections.abc import Mapping
from uuid import NAMESPACE_URL, uuid5


def native_static_fields(fields: Mapping[str, str]) -> dict[str, str]:
    """Keep the app profile while separating its SID from Home Assistant's."""
    original = fields.get("deviceId")
    if not isinstance(original, str) or not original:
        raise ValueError("The app profile has no deviceId")
    result = dict(fields)
    result["deviceId"] = str(uuid5(NAMESPACE_URL, f"neolight-native:{original}"))
    return result
