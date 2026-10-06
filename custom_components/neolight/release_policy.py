"""Bound automatic relay requests to a fresh, single doorbell call."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


MAX_RELEASE_AGE = 10
MAX_CLOCK_LEAD = 2


def release_mode(
    options: Mapping[str, Any], captured_at: int, now: float, safety_hold: bool
) -> str | None:
    """Return the permitted mode for one timestamped call, if any."""
    if captured_at > now + MAX_CLOCK_LEAD or now - captured_at > MAX_RELEASE_AGE:
        return None
    if options.get("auto_unlock_test_once"):
        deadline = options.get("auto_unlock_test_deadline", 0)
        if type(deadline) in (int, float) and now <= deadline:
            return "once"
        return None
    if not safety_hold and options.get("auto_unlock_on_ring", False):
        return "persistent"
    return None
