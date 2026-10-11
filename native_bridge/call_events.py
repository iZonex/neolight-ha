"""Small localhost event stream for calls accepted by the native bridge."""

import json
import time


class CallEventStream:
    """Broadcast sanitized call events to connected Home Assistant listeners."""

    def __init__(self) -> None:
        self._writers = set()
        self._sequence = 0

    def add(self, writer) -> None:
        self._writers.add(writer)

    def remove(self, writer) -> None:
        self._writers.discard(writer)

    def ring(self, call_type: str) -> None:
        self._sequence += 1
        payload = (json.dumps({"event": "ring", "sequence": self._sequence,
                               "call_type": call_type, "received_at": time.time()}) + "\n").encode()
        for writer in tuple(self._writers):
            if writer.is_closing() or writer.transport.get_write_buffer_size() > 65536:
                self.remove(writer)
                writer.close()
            else:
                writer.write(payload)
