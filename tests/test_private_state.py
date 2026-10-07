"""HACS upgrades must not delete existing private monitor credentials."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


PATH = Path(__file__).parents[1] / "custom_components/neolight/private_state.py"
SPEC = importlib.util.spec_from_file_location("neolight_private_state", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PrivateStateTests(unittest.TestCase):
    def test_migrates_legacy_state_without_removing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy, private = Path(directory) / "integration", Path(directory) / "private"
            legacy.mkdir()
            for name in ("vendor_config.json", "runtime_session.json", "video_route.json"):
                (legacy / name).write_text(json.dumps({"marker": name}))
            MODULE.migrate_legacy_state(legacy, private)
            for name in ("vendor_config.json", "runtime_session.json", "video_route.json"):
                self.assertEqual(json.loads((private / name).read_text()), {"marker": name})
                self.assertTrue((legacy / name).exists())
                self.assertEqual(os.stat(private / name).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(private).st_mode & 0o777, 0o700)

    def test_existing_private_file_wins_and_invalid_source_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy, private = Path(directory) / "integration", Path(directory) / "private"
            legacy.mkdir()
            private.mkdir()
            (legacy / "vendor_config.json").write_text('{"source":"old"}')
            (private / "vendor_config.json").write_text('{"source":"new"}')
            (legacy / "runtime_session.json").write_text("broken-json")
            MODULE.migrate_legacy_state(legacy, private)
            self.assertEqual(json.loads((private / "vendor_config.json").read_text()),
                             {"source": "new"})
            self.assertFalse((private / "runtime_session.json").exists())
