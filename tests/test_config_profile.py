"""Configuration accepts a different app profile without owner defaults."""

import json
import unittest

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components/neolight/profile.py"
spec = importlib.util.spec_from_file_location("neolight_profile_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
parse_app_profile = module.parse_app_profile
ha_static_fields = module.ha_static_fields


class AppProfileTests(unittest.TestCase):
    def test_ha_uses_a_stable_separate_installation_id(self):
        fields = {"deviceId": "owner-phone", "clientId": "same-app"}
        result = ha_static_fields(fields)
        self.assertEqual(result, ha_static_fields(fields))
        self.assertNotEqual(result["deviceId"], fields["deviceId"])
        self.assertEqual(result["clientId"], fields["clientId"])
        self.assertEqual(fields["deviceId"], "owner-phone")

    def test_accepts_complete_profile(self):
        profile = {
            "api_host": "api.example.invalid",
            "signing_key": "test-only-key",
            "paired_device_id": "test-device",
            "static_fields": {
                "appVersion": "1", "chKey": "channel", "clientId": "client",
                "deviceId": "installation", "lang": "en", "os": "Android",
                "ttid": "test",
            },
        }
        self.assertEqual(parse_app_profile(json.dumps(profile)), profile)

    def test_rejects_missing_signature_and_wrong_host(self):
        with self.assertRaises(ValueError):
            parse_app_profile('{"api_host":"https://api.example.invalid"}')


if __name__ == "__main__":
    unittest.main()
