"""Verify commands against the schema and behavior observed in the panel."""

import importlib.util
import json
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components/neolight/panel_protocol.py"
spec = importlib.util.spec_from_file_location("neolight_panel_protocol_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


SCHEMA = [
    {"code": "accessory_lock", "id": "148", "type": "obj", "schema_type": "bool", "mode": "rw"},
    {"code": "ipc_c_lock", "id": "232", "type": "obj", "schema_type": "bool", "mode": "rw"},
    {"code": "ipc_c_switch_channel", "id": "231", "type": "obj", "schema_type": "string", "mode": "rw"},
]


class PanelProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = module.PanelProfile.from_schema(SCHEMA)

    def test_lock_buttons_use_their_actual_dp_ids_and_toggle(self):
        self.assertEqual(self.profile.lock_command("lock_1", False), {"148": True})
        self.assertEqual(self.profile.lock_command("lock_2", True), {"232": False})

    def test_channel_selection_keeps_device_channel_list(self):
        current = '{"res":1,"err":0,"cc":1,"chs":[{"id":1,"n":"DOOR"},{"id":2,"n":"CAM2"}]}'
        command = self.profile.channel_command(current, 2)
        data = json.loads(command["231"])
        self.assertEqual((data["cmd"], data["cc"]), (1, 2))
        self.assertEqual(data["chs"][0]["n"], "DOOR")
        self.assertEqual(module.channel_labels(current), {1: "DOOR", 2: "CAM2"})

    def test_partial_schema_exposes_only_confirmed_controls(self):
        profile = module.PanelProfile.from_schema(SCHEMA[:1])
        self.assertTrue(profile.supports("lock_1"))
        self.assertFalse(profile.supports("lock_2"))
        self.assertEqual(profile.lock_command("lock_1", False), {"148": True})
        with self.assertRaises(ValueError):
            profile.lock_command("lock_2", False)
        with self.assertRaises(ValueError):
            module.PanelProfile.from_schema(SCHEMA[:1], required=("lock_2",))

    def test_rejects_read_only_or_malformed_dps(self):
        read_only = [{**SCHEMA[0], "mode": "ro"}, *SCHEMA[1:]]
        self.assertFalse(module.PanelProfile.from_schema(read_only).supports("lock_1"))
        with self.assertRaises(ValueError):
            module.PanelProfile.from_schema(read_only, required=("lock_1",))
        self.assertFalse(module.PanelProfile.from_schema([{**SCHEMA[0], "id": "bad"}]).supports("lock_1"))
        with self.assertRaises(ValueError):
            module.PanelProfile.from_schema([{**SCHEMA[0], "id": "bad"}], required=("lock_1",))
        with self.assertRaises(ValueError):
            self.profile.channel_command('{"chs":[{"id":1}]}', 2)

    def test_accepts_cloud_schema_property_types(self):
        cloud_schema = [
            {key: value for key, value in item.items() if key != "schema_type"}
            | {"property": {"type": item["schema_type"]}}
            for item in SCHEMA
        ]
        self.assertEqual(module.PanelProfile.from_schema(cloud_schema).dp_ids["lock_1"], 148)


if __name__ == "__main__":
    unittest.main()
