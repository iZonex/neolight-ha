"""Live schema must explicitly describe a read-only Ring/Normal input."""

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components/neolight/call_state.py"
spec = importlib.util.spec_from_file_location("neolight_call_state_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CallStateTests(unittest.TestCase):
    def test_snapshot_then_status_is_one_episode(self):
        detector = module.RingEpisodeDetector(initial_call_status=2, now=100)
        self.assertEqual(detector.observe(True, 2, 101).source, "snapshot")
        self.assertIsNone(detector.observe(False, 0, 105))
        self.assertIsNone(detector.observe(False, 0, 125))

    def test_status_then_snapshot_is_one_episode(self):
        detector = module.RingEpisodeDetector(initial_call_status=2, now=100)
        self.assertEqual(detector.observe(False, 0, 101).source, "call_status")
        self.assertIsNone(detector.observe(True, 0, 106))

    def test_late_status_still_belongs_to_snapshot_call(self):
        detector = module.RingEpisodeDetector(initial_call_status=2, now=100)
        self.assertEqual(detector.observe(True, 2, 101).number, 1)
        self.assertIsNone(detector.observe(False, 0, 126))
        self.assertIsNone(detector.observe(True, 0, 130))
        detector.observe(False, 2, 140)
        self.assertEqual(detector.observe(False, 0, 165).number, 2)

    def test_status_jitter_does_not_repeat_episode(self):
        detector = module.RingEpisodeDetector(initial_call_status=2, now=100)
        self.assertIsNotNone(detector.observe(False, 0, 101))
        self.assertIsNone(detector.observe(False, 2, 105))
        self.assertIsNone(detector.observe(False, 0, 109))

    def test_new_call_after_end_is_new_episode(self):
        detector = module.RingEpisodeDetector(initial_call_status=2, now=100)
        self.assertEqual(detector.observe(False, 0, 101).number, 1)
        self.assertIsNone(detector.observe(False, 2, 110))
        self.assertEqual(detector.observe(False, 0, 126).number, 2)

    def test_snapshot_and_status_same_poll_does_not_hide_next_call(self):
        detector = module.RingEpisodeDetector(initial_call_status=2, now=100)
        self.assertEqual(detector.observe(True, 0, 101).number, 1)
        detector.observe(False, 2, 110)
        self.assertEqual(detector.observe(False, 0, 126).number, 2)

    def test_active_call_repeated_snapshot_is_not_new_episode(self):
        detector = module.RingEpisodeDetector(initial_call_status=2, now=100)
        self.assertEqual(detector.observe(True, 0, 101).number, 1)
        self.assertIsNone(detector.observe(True, 0, 130))

    def test_startup_active_call_is_not_replayed(self):
        detector = module.RingEpisodeDetector(initial_call_status=0, now=100)
        self.assertIsNone(detector.observe(False, 0, 101))
        self.assertIsNone(detector.observe(True, 0, 105))
        self.assertIsNone(detector.observe(True, 0, 130))
        detector.observe(False, 2, 110)
        self.assertEqual(detector.observe(False, 0, 126).number, 1)

    def test_new_snapshots_work_without_call_status(self):
        detector = module.RingEpisodeDetector(now=100)
        self.assertEqual(detector.observe(True, None, 101).number, 1)
        self.assertIsNone(detector.observe(True, None, 106))
        self.assertEqual(detector.observe(True, None, 126).number, 2)

    def test_call_status_only_triggers_on_new_active_call(self):
        self.assertTrue(module.started_new_call(2, 0))
        self.assertFalse(module.started_new_call(None, 0))
        self.assertFalse(module.started_new_call(0, 0))
        self.assertFalse(module.started_new_call(2, 2))

    def test_resolves_only_read_only_doorbell_enums(self):
        valid = lambda code, dp_id: {"code": code, "id": dp_id, "type": "obj",
                                      "mode": "ro", "property": {"type": "enum",
                                                                  "range": ["Ring", "Normal"]}}
        schema = [valid("doorbell1", 239), valid("doorbell4", 248),
                  {**valid("doorbell2", 240), "mode": "rw"},
                  {**valid("doorbell3", 247), "property": {"type": "bool"}}]
        self.assertEqual(module.ring_channels(schema), {1: 239, 4: 248})


if __name__ == "__main__":
    unittest.main()
