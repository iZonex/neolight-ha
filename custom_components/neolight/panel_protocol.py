"""DP commands used by the downloaded IP10K3 React Native panel.

This module only builds commands. A transport must publish them and confirm
the resulting device state before HA exposes a control to the user.
"""

import json
from dataclasses import dataclass
from typing import Any, Mapping


PANEL_CODES = {
    "lock_1": "accessory_lock",
    "lock_2": "ipc_c_lock",
    "channel": "ipc_c_switch_channel",
}


@dataclass(frozen=True)
class PanelProfile:
    """Map the observed panel controls to a paired device's runtime schema."""

    dp_ids: Mapping[str, int]

    @classmethod
    def from_schema(cls, schema: list[Mapping[str, Any]]) -> "PanelProfile":
        by_code = {item["code"]: item for item in schema}
        ids: dict[str, int] = {}
        for control, code in PANEL_CODES.items():
            item = by_code.get(code)
            if item is None or item.get("type") != "obj":
                raise ValueError(f"Panel DP {code} is missing or has an unexpected type")
            expected_type = "string" if control == "channel" else "bool"
            property_type = item.get("schema_type") or (item.get("property") or {}).get("type")
            if property_type != expected_type or item.get("mode") != "rw":
                raise ValueError(f"Panel DP {code} is not writable as {expected_type}")
            ids[control] = int(item["id"])
        return cls(dp_ids=ids)

    def lock_command(self, lock: str, current_value: bool) -> dict[str, bool]:
        """Build the exact boolean toggle used by the app's Lock buttons."""
        if lock not in ("lock_1", "lock_2"):
            raise ValueError("Unknown lock control")
        if type(current_value) is not bool:
            raise ValueError("Current lock DP state must be a boolean")
        return {str(self.dp_ids[lock]): not current_value}

    def channel_command(self, current_value: str, channel_id: int) -> dict[str, str]:
        """Build the panel's cmd=1 channel selection without dropping metadata."""
        data = json.loads(current_value)
        channels = data.get("chs")
        if type(channel_id) is not int or not isinstance(channels, list):
            raise ValueError("Invalid channel list or channel ID")
        if not any(item.get("id") == channel_id for item in channels):
            raise ValueError("Channel is absent from this device")
        data["cmd"] = 1
        data["cc"] = channel_id
        return {str(self.dp_ids["channel"]): json.dumps(data, separators=(",", ":"))}
