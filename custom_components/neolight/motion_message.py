"""Read a motion snapshot notification from the paired monitor's raw DP."""

from __future__ import annotations

import base64
from collections import deque
from hashlib import sha256
import json
import re
import time
from collections.abc import Mapping
from typing import Any


_SNAPSHOT_TIME = re.compile(r"/(\d{10})\.[A-Za-z0-9]+$")
_MAX_AGE_SECONDS = 60
_MAX_CLOCK_LEAD_SECONDS = 5


def motion_dp_id(schema: list[Mapping[str, Any]]) -> str | None:
    """Use only the observed read-only raw image DP, regardless of its wrapper."""
    if not isinstance(schema, list):
        return None
    for item in schema:
        if (isinstance(item, Mapping) and item.get("code") == "movement_detect_pic"
                and item.get("type") in {"raw", "obj"} and item.get("mode") == "ro"):
            try:
                return str(int(item["id"]))
            except (KeyError, TypeError, ValueError):
                return None
    return None


def motion_snapshot(raw: str | None) -> tuple[int, bytes] | None:
    """Return capture time and path digest; never retain the image URL or token."""
    if not isinstance(raw, str):
        return None
    try:
        message = json.loads(base64.b64decode(raw, validate=True))
    except (ValueError, TypeError, UnicodeDecodeError):
        return None
    if not isinstance(message, dict) or message.get("v") != "3.0":
        return None
    files = message.get("files")
    if not isinstance(files, list) or not files or not isinstance(files[0], list):
        return None
    if not files[0] or not isinstance(files[0][0], str):
        return None
    path = files[0][0]
    match = _SNAPSHOT_TIME.search(path)
    if match is None:
        return None
    return int(match.group(1)), sha256(path.encode()).digest()


class MotionDeduplicator:
    """Accept a fresh motion image only once per HA runtime."""

    def __init__(self, initial_raw: str | None = None,
                 started_at: float | None = None, max_seen: int = 128) -> None:
        self._started_at = int(time.time() if started_at is None else started_at)
        self._max_seen = max_seen
        self._seen: set[bytes] = set()
        self._order: deque[bytes] = deque()
        initial = motion_snapshot(initial_raw)
        if initial is not None:
            self._remember(initial[1])

    def _remember(self, digest: bytes) -> None:
        if digest in self._seen:
            return
        self._seen.add(digest)
        self._order.append(digest)
        if len(self._order) > self._max_seen:
            self._seen.remove(self._order.popleft())

    def observe(self, raw: str | None, now: float | None = None) -> int | None:
        """Return the capture time of a new image, if it is recent."""
        event = motion_snapshot(raw)
        if event is None:
            return None
        captured_at, digest = event
        if digest in self._seen:
            return None
        observed_at = time.time() if now is None else now
        if (captured_at < self._started_at
                or observed_at - captured_at > _MAX_AGE_SECONDS
                or captured_at - observed_at > _MAX_CLOCK_LEAD_SECONDS):
            return None
        self._remember(digest)
        return captured_at
