"""Profile import must verify signatures and keep output private."""

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import urlencode


PATH = Path(__file__).parents[1] / "tools/build_profile.py"
sys.path.insert(0, str(PATH.parent))
SPEC = importlib.util.spec_from_file_location("neolight_profile_builder", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProfileBuilderTests(unittest.TestCase):
    def test_builds_profile_only_for_matching_signed_capture(self):
        fields = {key: f"value-{key}" for key in MODULE.STATIC_FIELDS}
        fields.update(a="smartlife.p.time.get", v="1.0", time="1234")
        sign = MODULE._load_function(
            MODULE.ROOT / "custom_components/neolight/mobile_api.py", "sign_mobile_request")
        fields["sign"] = sign(fields, "test-key")
        capture = {"url": "https://regional.example/api.json", "body": urlencode(fields)}
        profile = MODULE.build_profile(capture, "test-key", "paired-device")
        self.assertEqual(profile["api_host"], "regional.example")
        self.assertEqual(profile["paired_device_id"], "paired-device")
        self.assertNotIn("sign", profile)
        with self.assertRaisesRegex(ValueError, "does not match"):
            MODULE.build_profile(capture, "wrong-key", "paired-device")

    def test_private_file_and_single_device_requirement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schema = root / "schema.json"
            schema.write_text(json.dumps([{"device_id": "private-id"}]))
            self.assertEqual(MODULE.paired_device_id(schema), "private-id")
            schema.write_text(json.dumps([{"device_id": "one"}, {"device_id": "two"}]))
            with self.assertRaisesRegex(ValueError, "device-index"):
                MODULE.paired_device_id(schema)
            self.assertEqual(MODULE.paired_device_id(schema, 1), "two")
            output = root / "profile.json"
            MODULE.write_private(output, {"secret": "private"})
            self.assertEqual(os.stat(output).st_mode & 0o777, 0o600)
