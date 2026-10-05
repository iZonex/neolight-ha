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


class RingMessageTests(unittest.TestCase):
    def test_observed_ipc_doorbell_alarm(self):
        self.assertTrue(module.is_doorbell_message(encode({
            "v": "3.0", "cmd": "ipc_doorbell", "type": "image", "files": [["path", "token"]]
        })))

    def test_unrelated_or_invalid_raw_values(self):
        self.assertFalse(module.is_doorbell_message(encode({"cmd": "motion"})))
        self.assertFalse(module.is_doorbell_message("not base64"))
        self.assertFalse(module.is_doorbell_message(None))

    def test_cached_alarm_does_not_ring_after_empty_poll_or_replay(self):
        old = encode({"cmd": "ipc_doorbell", "files": [["old"]]})
        new = encode({"cmd": "ipc_doorbell", "files": [["new"]]})
        detector = module.RingDeduplicator(old)
        self.assertFalse(detector.observe(None))
        self.assertFalse(detector.observe(old))
        self.assertTrue(detector.observe(new))
        self.assertFalse(detector.observe(old))
        self.assertFalse(detector.observe(new))

    def test_first_cloud_alarm_is_baseline_after_missing_initial_state(self):
        old = encode({"cmd": "ipc_doorbell", "files": [["old"]]})
        new = encode({"cmd": "ipc_doorbell", "files": [["new"]]})
        detector = module.RingDeduplicator()
        self.assertFalse(detector.observe(None))
        self.assertFalse(detector.observe(old))
        self.assertTrue(detector.observe(new))


if __name__ == "__main__":
    unittest.main()
