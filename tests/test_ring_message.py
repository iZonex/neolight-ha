"""The event decoder must ignore other alarm payloads and malformed raw DPs."""

import base64
import importlib.util
import json
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components/neolight/ring_message.py"
spec = importlib.util.spec_from_file_location("neolight_ring_message_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def encode(payload):
    return base64.b64encode(json.dumps(payload).encode()).decode()


def alarm(captured_at, token="token"):
    return encode({
        "v": "3.0", "cmd": "ipc_doorbell", "type": "image",
        "files": [[f"/device/snapshot/{captured_at}.jpeg", token]],
    })


class RingMessageTests(unittest.TestCase):
    def test_observed_ipc_doorbell_alarm(self):
        raw = alarm(1700000001)
        self.assertTrue(module.is_doorbell_message(raw))
        self.assertEqual(module.doorbell_event(raw)[0], 1700000001)

    def test_unrelated_or_invalid_raw_values(self):
        self.assertFalse(module.is_doorbell_message(encode({"cmd": "motion"})))
        self.assertFalse(module.is_doorbell_message(encode({
            "cmd": "ipc_doorbell", "files": [["/snapshot/no-time.jpeg", "token"]]
        })))
        self.assertFalse(module.is_doorbell_message("not base64"))
        self.assertFalse(module.is_doorbell_message(None))

    def test_cached_alarm_does_not_ring_after_empty_poll_or_replay(self):
        old = alarm(1700000000)
        new = alarm(1700000010)
        detector = module.RingDeduplicator(old, started_at=1700000005)
        self.assertFalse(detector.observe(None))
        self.assertFalse(detector.observe(old, now=1700000011))
        self.assertTrue(detector.observe(new, now=1700000011))
        self.assertFalse(detector.observe(alarm(1700000010, "rotated"), now=1700000012))
        self.assertFalse(detector.observe(old, now=1700000013))

    def test_first_fresh_alarm_fires_after_empty_initial_state(self):
        old = alarm(1700000000)
        new = alarm(1700000010)
        detector = module.RingDeduplicator(started_at=1700000005)
        self.assertFalse(detector.observe(None))
        self.assertFalse(detector.observe(old, now=1700000006))
        self.assertTrue(detector.observe(new, now=1700000011))

    def test_restart_and_clock_window_reject_stale_or_future_alarms(self):
        detector = module.RingDeduplicator(started_at=1700000100)
        self.assertFalse(detector.observe(alarm(1700000099), now=1700000101))
        self.assertFalse(detector.observe(alarm(1700000101), now=1700000170))
        self.assertFalse(detector.observe(alarm(1700000110), now=1700000101))
        self.assertTrue(detector.observe(alarm(1700000102), now=1700000103))


if __name__ == "__main__":
    unittest.main()
