"""Motion images must never replay as new HA events after restart or reconnect."""

import base64
import importlib.util
import json
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components/neolight/motion_message.py"
spec = importlib.util.spec_from_file_location("neolight_motion_message_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def image(captured_at, token="token"):
    payload = {"v": "3.0", "bucket": "example-bucket",
               "files": [[f"/device/motion/{captured_at}.jpeg", token]]}
    return base64.b64encode(json.dumps(payload).encode()).decode()


class MotionMessageTests(unittest.TestCase):
    def test_observed_motion_shape_and_fresh_event(self):
        self.assertEqual(module.motion_snapshot(image(1700000010))[0], 1700000010)
        detector = module.MotionDeduplicator(started_at=1700000000)
        self.assertEqual(detector.observe(image(1700000010), now=1700000011), 1700000010)
        self.assertIsNone(detector.observe(image(1700000010, "rotated"), now=1700000012))

    def test_cached_and_out_of_window_images_are_ignored(self):
        old = image(1700000000)
        detector = module.MotionDeduplicator(old, started_at=1700000005)
        self.assertIsNone(detector.observe(old, now=1700000010))
        self.assertIsNone(detector.observe(image(1700000004), now=1700000010))
        self.assertIsNone(detector.observe(image(1700000010), now=1700000080))
        self.assertIsNone(detector.observe(image(1700000020), now=1700000010))
        self.assertEqual(detector.observe(image(1700000011), now=1700000012), 1700000011)

    def test_invalid_payloads_are_ignored(self):
        for raw in (None, "not-base64", base64.b64encode(b"[]").decode(),
                    base64.b64encode(b'{"v":"3.0","files":[]}').decode()):
            self.assertIsNone(module.motion_snapshot(raw))


if __name__ == "__main__":
    unittest.main()
