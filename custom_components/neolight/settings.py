"""Per-install settings shared with the optional media containers."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


def legacy_vendor_path() -> Path:
    """Keep existing installations working while they migrate to the UI."""
    return Path(__file__).with_name("vendor_config.json")


def runtime_directory(hass: HomeAssistant, entry: ConfigEntry) -> Path:
    if "vendor" in entry.data:
        return Path(hass.config.path("neolight"))
    return legacy_vendor_path().parent


def load_vendor(entry: ConfigEntry) -> dict:
    """Prefer the config entry; read the old private JSON only for legacy entries."""
    if "vendor" in entry.data:
        vendor = dict(entry.data["vendor"])
    else:
        path = legacy_vendor_path()
        vendor = json.loads(path.read_text()) if path.exists() else {}
        vendor.setdefault("homekit_ring_url", "http://127.0.0.1:38765/ring")
    return {**vendor, **entry.options}


def write_private_json(path: Path, data: dict) -> None:
    """Atomically export runtime settings for the Docker sidecars."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, prefix=f".{path.name}-", delete=False
    ) as handle:
        os.chmod(handle.name, 0o600)
        json.dump(data, handle)
        temporary = handle.name
    os.replace(temporary, path)
