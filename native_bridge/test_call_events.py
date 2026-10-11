"""Verify localhost call event payloads never contain call identifiers."""

import json
import unittest

from call_events import CallEventStream


class _Writer:
    def __init__(self):
        self.sent = []
        self.transport = self

    def is_closing(self):
        return False

    def get_write_buffer_size(self):
        return 0

    def write(self, data):
        self.sent.append(data)


class CallEventStreamTests(unittest.TestCase):
    def test_ring_payload_is_small_and_contains_no_private_identifiers(self):
        stream = CallEventStream()
        writer = _Writer()
        stream.add(writer)
        stream.ring("ac_doorbell")
        stream.ring("ac_doorbell")
        first, second = (json.loads(item) for item in writer.sent)
        self.assertEqual(first["event"], "ring")
        self.assertEqual(second["sequence"], first["sequence"] + 1)
        self.assertEqual(set(first), {"event", "sequence", "call_type", "received_at"})
