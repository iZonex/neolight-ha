"""Track only call notifications received by the active native session."""

from __future__ import annotations

from dataclasses import dataclass, field

from call_signaling import ActiveCall


RING_MAX_AGE = 60
ANSWER_MAX_AGE = 300


@dataclass
class CallLifecycle:
    call: ActiveCall | None = None
    received_at: float = 0
    answered_at: float | None = None
    seen: list[tuple[str, str]] = field(default_factory=list, repr=False)

    def receive(self, call: ActiveCall, now: float) -> bool:
        """Ignore a repeated notification for the same call identifier."""
        identifier = (call.device_id, call.message_id)
        if identifier in self.seen:
            return False
        self.seen.append(identifier)
        if len(self.seen) > 128:
            self.seen.pop(0)
        self.call = call
        self.received_at = now
        self.answered_at = None
        return True

    def state(self, now: float) -> str:
        if self.call is None:
            return "idle"
        if self.answered_at is not None:
            if now - self.answered_at <= ANSWER_MAX_AGE:
                return "answered"
        elif now - self.received_at <= RING_MAX_AGE:
            return "ringing"
        self.clear()
        return "idle"

    def answerable(self, now: float) -> ActiveCall | None:
        return self.call if self.state(now) == "ringing" else None

    def mark_answered(self, now: float) -> None:
        if self.answerable(now) is None:
            raise ValueError("No fresh call can be answered")
        self.answered_at = now

    def answered(self, now: float) -> ActiveCall | None:
        return self.call if self.state(now) == "answered" else None

    def clear(self) -> None:
        """End the active call without forgetting replay protection."""
        self.call = None
        self.received_at = 0
        self.answered_at = None

    def public_status(self, now: float, talk_active: bool) -> dict:
        """Exclude device, message, and channel identifiers from diagnostics."""
        state = self.state(now)
        return {"state": state, "talk_active": talk_active,
                "call_type": self.call.call_type if state != "idle" else None,
                "age_seconds": round(now - self.received_at, 1) if state != "idle" else None}
