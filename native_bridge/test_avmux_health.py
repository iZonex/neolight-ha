"""Only output progress should make the bridge report live video."""

import unittest

import avmux


class VideoHealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous = dict(avmux.health)

    def tearDown(self) -> None:
        avmux.health.update(self.previous)

    def test_recent_output_is_live(self):
        avmux.health.update(source="monitor_rtsp", publisher=True,
                            started_at=80.0, last_video_at=99.0)
        self.assertEqual(avmux.health_snapshot(100.0), {
            "status": "live", "source": "monitor_rtsp", "publisher": True,
            "video_age_seconds": 1.0,
        })

    def test_old_output_is_stale_even_with_publisher(self):
        avmux.health.update(source="monitor_rtsp", publisher=True,
                            started_at=70.0, last_video_at=80.0)
        self.assertEqual(avmux.health_snapshot(100.0)["status"], "stale")

    def test_new_process_has_starting_state(self):
        avmux.health.update(source="native_backup", publisher=False,
                            started_at=95.0, last_video_at=None)
        self.assertEqual(avmux.health_snapshot(100.0)["status"], "starting")
