"""Read-only per-channel ringing capabilities from the live device schema."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NamedTuple


def started_new_call(previous: int | None, current: int | None) -> bool:
    """The APK treats callStatus=0 as a currently ringing call."""
    return previous is not None and previous != 0 and current == 0


class RingEpisode(NamedTuple):
    """One accepted call, regardless of how many signals describe it."""

    number: int
    source: str


class RingEpisodeDetector:
    """Merge snapshot and call-status signals before any door action."""

    MERGE_SECONDS = 20
    STATUS_CORRELATION_SECONDS = 120

    def __init__(self, initial_call_status: int | None = None, now: float = 0) -> None:
        self._last_status = initial_call_status
        self._active = initial_call_status == 0
        self._last_episode_at = now if self._active else float("-inf")
        self._episode_number = 0
        self._snapshot_waiting_for_status_at: float | None = None

    def observe(
        self, fresh_snapshot: bool, call_status: int | None, now: float,
    ) -> RingEpisode | None:
        """Return one new episode, never a second action for a merged signal."""
        status_start = started_new_call(self._last_status, call_status)
        was_active = self._active
        if call_status is not None:
            self._last_status = call_status
            self._active = call_status == 0
        if (status_start and self._snapshot_waiting_for_status_at is not None
                and now - self._snapshot_waiting_for_status_at < self.STATUS_CORRELATION_SECONDS):
            self._snapshot_waiting_for_status_at = None
            return None
        if not fresh_snapshot and not status_start:
            return None
        elapsed = now - self._last_episode_at
        if elapsed < self.MERGE_SECONDS:
            return None
        if was_active:
            return None
        self._episode_number += 1
        self._last_episode_at = now
        self._snapshot_waiting_for_status_at = (
            now if fresh_snapshot and call_status != 0 else None
        )
        return RingEpisode(self._episode_number, "snapshot" if fresh_snapshot else "call_status")

    @property
    def episode_number(self) -> int:
        """The latest accepted episode; zero means no fresh call since startup."""
        return self._episode_number


class ReleaseEpisodeGate:
    """Require fresh snapshot evidence and consume it once per call."""

    def __init__(self) -> None:
        self._last_evidenced_episode = 0

    def observe(self, fresh_snapshot: bool, episode_number: int) -> bool:
        if not fresh_snapshot or episode_number <= self._last_evidenced_episode:
            return False
        self._last_evidenced_episode = episode_number
        return True


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
