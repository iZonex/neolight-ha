"""Private schema fallback for local setup during a cloud outage."""

from __future__ import annotations

import json
from pathlib import Path


def load_cached_schema(path: Path, device_id: str | None) -> list:
    """Use a previous schema only for the same paired monitor."""
    if not device_id:
        return []
    try:
        cached = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    if not isinstance(cached, dict) or cached.get("device_id") != device_id:
        return []
    schema = cached.get("schema")
    return schema if isinstance(schema, list) else []
