"""Decode the alarm_message DP observed during an entrance-panel call."""

from __future__ import annotations

import base64
from collections import deque
from hashlib import sha256
import json
import re
import time


_SNAPSHOT_TIME = re.compile(r"/(\d{10})\.[A-Za-z0-9]+$")
_MAX_EVENT_AGE = 60
_MAX_CLOCK_LEAD = 5


def doorbell_event(raw: str | None) -> tuple[int, bytes] | None:
    """Extract the capture time and stable snapshot ID from an IPC alarm."""
    if not isinstance(raw, str):
        return None
    try:
        message = json.loads(base64.b64decode(raw, validate=True))
    except (ValueError, TypeError, UnicodeDecodeError):
        return None
    if not isinstance(message, dict) or message.get("cmd") != "ipc_doorbell":
        return None
    files = message.get("files")
    if not isinstance(files, list) or not files or not isinstance(files[0], list):
        return None
    if not files[0] or not isinstance(files[0][0], str):
        return None
    match = _SNAPSHOT_TIME.search(files[0][0])
    if match is None:
        return None
    return int(match.group(1)), sha256(files[0][0].encode()).digest()


def is_doorbell_message(raw: str | None) -> bool:
    """Accept only alarms carrying the observed timestamped snapshot path."""
    return doorbell_event(raw) is not None


class RingDeduplicator:
    """Ignore cached cloud alarms, including replays after empty API polls."""

    def __init__(
        self, initial_raw: str | None = None, max_seen: int = 128,
        started_at: float | None = None,
    ) -> None:
        self._seen: set[bytes] = set()
        self._order: deque[bytes] = deque()
        self._started_at = int(time.time() if started_at is None else started_at)
        self._max_seen = max_seen
        initial = doorbell_event(initial_raw)
        if initial is not None:
            self._remember(initial[1])

    def _remember(self, digest: bytes) -> None:
        if digest in self._seen:
            return
        self._seen.add(digest)
        self._order.append(digest)
        if len(self._order) > self._max_seen:
            self._seen.remove(self._order.popleft())

    def observe(self, raw: str | None, now: float | None = None) -> bool:
        """Return true only for a new alarm captured during this HA runtime."""
        event = doorbell_event(raw)
        if event is None:
            return False
        captured_at, digest = event
        if digest in self._seen:
            return False
        observed_at = time.time() if now is None else now
        if (captured_at < self._started_at or
                observed_at - captured_at > _MAX_EVENT_AGE or
                captured_at - observed_at > _MAX_CLOCK_LEAD):
            return False
        self._remember(digest)
        return True
