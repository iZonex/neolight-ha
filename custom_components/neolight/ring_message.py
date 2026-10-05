"""Decode the alarm_message DP observed during an entrance-panel call."""

from __future__ import annotations

import base64
from collections import deque
from hashlib import sha256
import json


def is_doorbell_message(raw: str | None) -> bool:
    """Accept only the panel's base64 JSON IPC doorbell alarm."""
    if not isinstance(raw, str):
        return False
    try:
        message = json.loads(base64.b64decode(raw, validate=True))
    except (ValueError, TypeError, UnicodeDecodeError):
        return False
    return isinstance(message, dict) and message.get("cmd") == "ipc_doorbell"


class RingDeduplicator:
    """Ignore cached cloud alarms, including replays after empty API polls."""

    def __init__(self, initial_raw: str | None = None, max_seen: int = 128) -> None:
        self._seen: set[bytes] = set()
        self._order: deque[bytes] = deque()
        self._primed = False
        self._max_seen = max_seen
        if is_doorbell_message(initial_raw):
            self._remember(initial_raw)
            self._primed = True

    def _remember(self, raw: str) -> None:
        digest = sha256(raw.encode()).digest()
        if digest in self._seen:
            return
        self._seen.add(digest)
        self._order.append(digest)
        if len(self._order) > self._max_seen:
            self._seen.remove(self._order.popleft())

    def observe(self, raw: str | None) -> bool:
        """Return true only for a distinct alarm after the current value is known."""
        if not is_doorbell_message(raw):
            return False
        digest = sha256(raw.encode()).digest()
        if digest in self._seen:
            return False
        self._remember(raw)
        if not self._primed:
            self._primed = True
            return False
        return True
