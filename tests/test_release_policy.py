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

    def test_native_vizit_call_can_release_without_a_snapshot(self):
        options = {"auto_unlock_on_ring": True}
        signal = {"call_type": "ac_doorbell", "received_at": 1000.4}
        self.assertEqual(
            module.native_release_mode(options, signal, 1002, False), "persistent"
        )
        self.assertEqual(
            module.native_release_mode(options, signal, 1010.1, False), "persistent"
        )
        self.assertIsNone(module.native_release_mode(options, signal, 1011, False))
        self.assertIsNone(module.native_release_mode(options, signal, 1002, True))

    def test_native_release_rejects_other_or_untrusted_signals(self):
        options = {"auto_unlock_on_ring": True}
        for signal in (
            {"call_type": "doorbell", "received_at": 1000},
            {"call_type": "ac_doorbell", "received_at": "1000"},
            {"call_type": "ac_doorbell", "received_at": 1010},
        ):
            with self.subTest(signal=signal):
                self.assertIsNone(module.native_release_mode(options, signal, 1002, False))


if __name__ == "__main__":
    unittest.main()
