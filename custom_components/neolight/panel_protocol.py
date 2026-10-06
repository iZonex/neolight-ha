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


def channel_labels(raw: str) -> dict[int, str]:
    """Name actual monitor channels; analog inputs within DOOR are not listed."""
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("chs"), list):
        raise ValueError("Channel list is unavailable")
    return {
        item["id"]: str(item.get("n") or "Camera")
        for item in data["chs"]
        if isinstance(item, dict) and type(item.get("id")) is int
        and 1 <= item["id"] <= 32
    }


@dataclass(frozen=True)
class PanelProfile:
    """Map the observed panel controls to a paired device's runtime schema."""

    dp_ids: Mapping[str, int]

    @classmethod
    def from_schema(
        cls, schema: list[Mapping[str, Any]], required: tuple[str, ...] = ()
    ) -> "PanelProfile":
        """Resolve available controls; validate each control before exposing it."""
        if not isinstance(schema, list):
            raise ValueError("Panel schema is missing")
        by_code = {item.get("code"): item for item in schema if isinstance(item, Mapping)}
        ids: dict[str, int] = {}
        for control, code in PANEL_CODES.items():
            item = by_code.get(code)
            if item is None:
                continue
            expected_type = "string" if control == "channel" else "bool"
            property_spec = item.get("property")
            property_type = item.get("schema_type") or (
                property_spec.get("type") if isinstance(property_spec, Mapping) else None
            )
            if (item.get("type") != "obj" or property_type != expected_type
                    or item.get("mode") != "rw"):
                if control in required:
                    raise ValueError(f"Panel DP {code} is not writable as {expected_type}")
                continue
            try:
                ids[control] = int(item["id"])
            except (KeyError, TypeError, ValueError) as error:
                if control in required:
                    raise ValueError(f"Panel DP {code} has no numeric ID") from error
        for control in required:
            if control not in PANEL_CODES or control not in ids:
                raise ValueError(f"Panel control {control} is unavailable")
        return cls(dp_ids=ids)

    def supports(self, control: str) -> bool:
        return control in self.dp_ids

    def lock_command(self, lock: str, current_value: bool) -> dict[str, bool]:
        """Build the exact boolean toggle used by the app's Lock buttons."""
        if lock not in ("lock_1", "lock_2"):
            raise ValueError("Unknown lock control")
        if not self.supports(lock):
            raise ValueError(f"Panel control {lock} is unavailable")
        if type(current_value) is not bool:
            raise ValueError("Current lock DP state must be a boolean")
        return {str(self.dp_ids[lock]): not current_value}

    def channel_command(self, current_value: str, channel_id: int) -> dict[str, str]:
        """Build the panel's cmd=1 channel selection without dropping metadata."""
        data = json.loads(current_value)
        channels = data.get("chs")
        if type(channel_id) is not int or not isinstance(channels, list):
            raise ValueError("Invalid channel list or channel ID")
        if not self.supports("channel"):
            raise ValueError("Panel channel selection is unavailable")
        if not any(item.get("id") == channel_id for item in channels):
            raise ValueError("Channel is absent from this device")
        data["cmd"] = 1
        data["cc"] = channel_id
        return {str(self.dp_ids["channel"]): json.dumps(data, separators=(",", ":"))}
