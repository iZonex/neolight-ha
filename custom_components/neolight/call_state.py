"""Read-only per-channel ringing capabilities from the live device schema."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def ring_channels(schema: list[Mapping[str, Any]]) -> dict[int, int]:
    """Return channel -> DP ID for read-only Ring/Normal enum controls."""
    found: dict[int, int] = {}
    if not isinstance(schema, list):
        return found
    for item in schema:
        if not isinstance(item, Mapping):
            continue
        code = item.get("code")
        if code not in {f"doorbell{number}" for number in range(1, 5)}:
            continue
        prop = item.get("property")
        values = prop.get("range") if isinstance(prop, Mapping) else None
        if (item.get("type") != "obj" or item.get("mode") != "ro"
                or not isinstance(prop, Mapping) or prop.get("type") != "enum"
                or not isinstance(values, list)
                or not {"Ring", "Normal"}.issubset(values)):
            continue
        try:
            found[int(code[-1])] = int(item["id"])
        except (KeyError, TypeError, ValueError):
            continue
    return found
