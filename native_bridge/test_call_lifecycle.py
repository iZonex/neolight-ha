"""A replay or elapsed call must not become answerable again."""

import unittest

from call_lifecycle import CallLifecycle
from call_signaling import ActiveCall


class CallLifecycleTests(unittest.TestCase):
    def test_fresh_answer_hangup_and_private_status(self):
        call = ActiveCall("video_doorbell", "private-device", "private-message", "private-channel")
        tracker = CallLifecycle()
        self.assertTrue(tracker.receive(call, 100))
        self.assertFalse(tracker.receive(call, 110))
        self.assertEqual(tracker.answerable(111), call)
        self.assertNotIn("private-", str(tracker.public_status(111, False)))
        tracker.mark_answered(112)
        self.assertEqual(tracker.state(113), "answered")
        tracker.clear()
        self.assertEqual(tracker.state(114), "idle")

    def test_expired_call_is_not_answerable(self):
        call = ActiveCall("ipc_doorbell", "device", "message", None)
        tracker = CallLifecycle()
        tracker.receive(call, 100)
        self.assertIsNone(tracker.answerable(161))
        self.assertEqual(tracker.state(161), "idle")
        self.assertFalse(tracker.receive(call, 200))
        self.assertTrue(tracker.receive(ActiveCall("ipc_doorbell", "device", "next", None), 200))
        tracker.mark_answered(201)
        self.assertEqual(tracker.state(502), "idle")


if __name__ == "__main__":
    unittest.main()
