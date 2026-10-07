"""A failed primary stream should recover once without channel command spam."""

import importlib.util
from pathlib import Path
import unittest


PATH = Path(__file__).parents[1] / "custom_components/neolight/video_recovery.py"
SPEC = importlib.util.spec_from_file_location("neolight_video_recovery", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VideoRecoveryTests(unittest.TestCase):
    def test_sustained_backup_waits_for_call_then_limits_retry(self):
        recovery = MODULE.VideoRecovery(wait_seconds=60, retry_seconds=300)
        backup = {"source": "native_backup", "status": "live"}
        self.assertFalse(recovery.should_reselect(backup, 1, "ringing", 100))
        self.assertFalse(recovery.should_reselect(backup, 1, "idle", 159))
        self.assertTrue(recovery.should_reselect(backup, 1, "idle", 160))
        self.assertFalse(recovery.should_reselect(backup, 1, "idle", 400))
        self.assertTrue(recovery.should_reselect(backup, 1, "idle", 460))
        self.assertFalse(recovery.should_reselect({"source": "monitor_rtsp"}, 1, "idle", 461))
        self.assertFalse(recovery.should_reselect(backup, 1, "idle", 462))

    def test_disabled_preference_never_changes_monitor(self):
        recovery = MODULE.VideoRecovery(wait_seconds=60)
        backup = {"source": "native_backup", "status": "live"}
        self.assertFalse(recovery.should_reselect(backup, 0, None, 100))
        self.assertFalse(recovery.should_reselect(backup, 0, None, 1000))
