"""A fresh call can request at most one time-bounded test release."""

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components/neolight/release_policy.py"
spec = importlib.util.spec_from_file_location("neolight_release_policy_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleasePolicyTests(unittest.TestCase):
    def test_one_shot_needs_a_fresh_ring_and_unexpired_arm(self):
        options = {"auto_unlock_test_once": True, "auto_unlock_test_deadline": 1100}
        self.assertEqual(module.release_mode(options, 1000, 1003, True), "once")
        self.assertIsNone(module.release_mode(options, 1000, 1011, True))
        self.assertIsNone(module.release_mode(options, 1000, 1101, True))
        self.assertIsNone(module.release_mode(options, 1010, 1003, True))

    def test_persistent_release_respects_safety_hold(self):
        options = {"auto_unlock_on_ring": True}
        self.assertIsNone(module.release_mode(options, 1000, 1003, True))
        self.assertEqual(module.release_mode(options, 1000, 1003, False), "persistent")

    def test_expired_one_shot_does_not_fall_back_to_persistent(self):
        options = {"auto_unlock_on_ring": True, "auto_unlock_test_once": True,
                   "auto_unlock_test_deadline": 1001}
        self.assertIsNone(module.release_mode(options, 1000, 1003, False))


if __name__ == "__main__":
    unittest.main()
