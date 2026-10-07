"""Read-only per-channel ringing capabilities from the live device schema."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NamedTuple


class RingEpisode(NamedTuple):
    """One accepted call, regardless of how many signals describe it."""

    number: int
    source: str


class RingEpisodeDetector:
    """Accept only fresh snapshot alarms, with a short duplicate guard."""

    MERGE_SECONDS = 20

    def __init__(self) -> None:
        self._last_episode_at = float("-inf")
        self._episode_number = 0

    def observe(self, fresh_snapshot: bool, now: float) -> RingEpisode | None:
        """Return a new episode only for a validated and non-duplicate alarm."""
        if not fresh_snapshot:
            return None
        if now - self._last_episode_at < self.MERGE_SECONDS:
            return None
        self._episode_number += 1
        self._last_episode_at = now
        return RingEpisode(self._episode_number, "snapshot")

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
