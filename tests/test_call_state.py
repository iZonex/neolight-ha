"""Call episodes need fresh snapshot evidence, even with an active app flag."""

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components/neolight/call_state.py"
spec = importlib.util.spec_from_file_location("neolight_call_state_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CallStateTests(unittest.TestCase):
    def test_snapshot_starts_episode_even_if_app_flag_is_stuck_active(self):
        detector = module.RingEpisodeDetector()
        self.assertIsNone(detector.observe(False, 100))
        self.assertEqual(detector.observe(True, 101).number, 1)
        self.assertEqual(detector.observe(True, 126).number, 2)

    def test_multiple_alarms_within_one_call_are_merged(self):
        detector = module.RingEpisodeDetector()
        self.assertEqual(detector.observe(True, 101).source, "snapshot")
        self.assertIsNone(detector.observe(True, 105))
        self.assertIsNone(detector.observe(True, 120))
        self.assertEqual(detector.observe(True, 121).number, 2)

    def test_release_requires_one_fresh_snapshot_per_episode(self):
        detector = module.RingEpisodeDetector()
        gate = module.ReleaseEpisodeGate()
        self.assertFalse(gate.observe(False, detector.episode_number))
        self.assertEqual(detector.observe(True, 101).number, 1)
        self.assertTrue(gate.observe(True, detector.episode_number))
        self.assertFalse(gate.observe(True, detector.episode_number))
        self.assertIsNone(detector.observe(True, 105))
        self.assertFalse(gate.observe(True, detector.episode_number))
        self.assertEqual(detector.observe(True, 126).number, 2)
        self.assertTrue(gate.observe(True, detector.episode_number))

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
