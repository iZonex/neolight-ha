"""Configuration accepts a different app profile without owner defaults."""

import json
import unittest

from custom_components.neolight.config_flow import parse_app_profile


class AppProfileTests(unittest.TestCase):
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
