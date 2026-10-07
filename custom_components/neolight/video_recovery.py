"""Rate-limit recovery of a monitor RTSP stream after a call."""

from __future__ import annotations

import time


class VideoRecovery:
    """Reselect the configured channel only after sustained backup video."""

    def __init__(self, wait_seconds: int = 60, retry_seconds: int = 300) -> None:
        self.wait_seconds = wait_seconds
        self.retry_seconds = retry_seconds
        self.backup_since: float | None = None
        self.next_attempt_at = 0.0

    def should_reselect(
        self, health: dict | None, preferred_channel: int,
        call_state: str | None, now: float | None = None,
    ) -> bool:
        now = time.monotonic() if now is None else now
        if (type(preferred_channel) is not int or preferred_channel < 1
                or not isinstance(health, dict)
                or health.get("source") != "native_backup"):
            self.backup_since = None
            self.next_attempt_at = 0.0
            return False
        if self.backup_since is None:
            self.backup_since = now
        if (call_state in {"ringing", "answered"}
                or now - self.backup_since < self.wait_seconds
                or now < self.next_attempt_at):
            return False
        self.next_attempt_at = now + self.retry_seconds
        return True
