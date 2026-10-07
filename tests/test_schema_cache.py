"""An offline monitor may reuse only its own previously observed DP schema."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


PATH = Path(__file__).parents[1] / "custom_components/neolight/schema_cache.py"
SPEC = importlib.util.spec_from_file_location("neolight_schema_cache", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SchemaCacheTests(unittest.TestCase):
    def test_same_device_can_load_cached_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schema.json"
            schema = [{"code": "accessory_lock", "id": 148}]
            path.write_text(json.dumps({"device_id": "device-a", "schema": schema}))
            self.assertEqual(MODULE.load_cached_schema(path, "device-a"), schema)
            self.assertEqual(MODULE.load_cached_schema(path, "device-b"), [])
            self.assertEqual(MODULE.load_cached_schema(path, None), [])

    def test_missing_or_invalid_cache_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schema.json"
            self.assertEqual(MODULE.load_cached_schema(path, "device-a"), [])
            path.write_text("not-json")
            self.assertEqual(MODULE.load_cached_schema(path, "device-a"), [])
            path.write_text(json.dumps({"device_id": "device-a", "schema": {}}))
            self.assertEqual(MODULE.load_cached_schema(path, "device-a"), [])
