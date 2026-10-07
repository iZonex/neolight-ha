"""Per-install settings shared with the optional media containers."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .private_state import migrate_legacy_state, write_private_json


def legacy_vendor_path() -> Path:
    """Keep existing installations working while they migrate to the UI."""
    return Path(__file__).with_name("vendor_config.json")


def runtime_directory(hass: HomeAssistant, entry: ConfigEntry) -> Path:
    """Use storage outside custom_components for every entry type."""
    return Path(hass.config.path("neolight"))


def load_vendor(entry: ConfigEntry, state_dir: Path | None = None) -> dict:
    """Prefer the config entry; read the old private JSON only for legacy entries."""
    if "vendor" in entry.data:
        vendor = dict(entry.data["vendor"])
    else:
        path = state_dir / "vendor_config.json" if state_dir else legacy_vendor_path()
        if not path.exists():
            path = legacy_vendor_path()
        vendor = json.loads(path.read_text()) if path.exists() else {}
        vendor.setdefault("homekit_ring_url", "http://127.0.0.1:38765/ring")
    return {**vendor, **entry.options}
