"""Live schema must explicitly describe a read-only Ring/Normal input."""

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components/neolight/call_state.py"
spec = importlib.util.spec_from_file_location("neolight_call_state_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CallStateTests(unittest.TestCase):
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
