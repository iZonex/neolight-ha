"""Keep account and media state outside the HACS-managed integration folder."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile


def write_private_json(path: Path, data: dict) -> None:
    """Atomically write a private runtime file for the Docker sidecars."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, prefix=f".{path.name}-", delete=False
    ) as handle:
        os.chmod(handle.name, 0o600)
        json.dump(data, handle)
        temporary = handle.name
    os.replace(temporary, path)


def migrate_legacy_state(legacy_dir: Path, private_dir: Path) -> None:
    """Copy valid legacy settings once; never overwrite newer private state."""
    for name in ("vendor_config.json", "runtime_session.json", "video_route.json"):
        source = legacy_dir / name
        target = private_dir / name
        if target.exists() or not source.exists():
            continue
        try:
            data = json.loads(source.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            write_private_json(target, data)
