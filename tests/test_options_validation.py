"""Focused settings pages must not reset unrelated controls."""

import importlib.util
from pathlib import Path
import unittest


PATH = Path(__file__).parents[1] / "custom_components/neolight/options_validation.py"
SPEC = importlib.util.spec_from_file_location("neolight_options_validation", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OptionsValidationTests(unittest.TestCase):
    def test_apple_home_page_leaves_automatic_opening_alone(self):
        saved = {"auto_unlock_on_ring": True, "auto_unlock_relay": "lock_1"}
        update = MODULE.validate_option_section(
            "apple_home", saved, {"homekit_ring_url": " http://127.0.0.1:38765/ring "}
        )
        self.assertEqual(update, {"homekit_ring_url": "http://127.0.0.1:38765/ring"})
        self.assertTrue(saved["auto_unlock_on_ring"])

    def test_one_time_opening_disables_persistent_mode(self):
        saved = {"enable_doorbell": True, "enable_lock_1": True,
                 "native_call_control_port": 38557}
        update = MODULE.validate_option_section("automatic_opening", saved, {
            "auto_unlock_on_ring": True, "auto_unlock_test_once": True,
            "auto_unlock_relay": "lock_1", "auto_unlock_delay": 0,
            "hangup_after_auto_unlock": True,
        })
        self.assertFalse(update["auto_unlock_on_ring"])
        self.assertGreater(update["auto_unlock_test_deadline"], 0)

    def test_unsupported_call_channel_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_call_video_channel"):
            MODULE.validate_option_section("entrances", {}, {
                "enable_camera": True, "enable_lock_1": True, "enable_lock_2": False,
                "preferred_video_channel": 1, "route_video_on_ring": True,
                "call_video_channel": 0, "call_video_hold_seconds": 90,
            })

    def test_cannot_disable_ring_events_while_auto_opening_is_on(self):
        with self.assertRaisesRegex(ValueError, "doorbell_required"):
            MODULE.validate_option_section("calls", {
                "auto_unlock_on_ring": True, "native_call_control_port": 38557,
            }, {"enable_doorbell": False})

    def test_existing_installation_uses_lock_one_default(self):
        saved = {"auto_unlock_on_ring": True, "auto_unlock_relay": "lock_1",
                 "enable_doorbell": True, "native_call_control_port": 38557}
        result = MODULE.validate_option_section("automatic_opening", saved, {
            "auto_unlock_on_ring": True, "auto_unlock_test_once": False,
            "auto_unlock_relay": "lock_1", "auto_unlock_delay": 0,
            "hangup_after_auto_unlock": True,
        })
        self.assertTrue(result["auto_unlock_on_ring"])

    def test_one_time_opening_needs_a_ring_source(self):
        with self.assertRaisesRegex(ValueError, "doorbell_required"):
            MODULE.validate_option_section("automatic_opening", {
                "enable_doorbell": False, "enable_lock_1": True,
            }, {"auto_unlock_on_ring": False, "auto_unlock_test_once": True,
                "auto_unlock_relay": "lock_1", "auto_unlock_delay": 0,
                "hangup_after_auto_unlock": False})

    def test_advanced_port_cannot_break_enabled_hangup(self):
        with self.assertRaisesRegex(ValueError, "invalid_call_control_port"):
            MODULE.validate_option_section("advanced", {
                "hangup_after_auto_unlock": True,
            }, {"native_call_control_port": 0, "restream_url": "",
                "stream_id": "", "rtsp_user": "", "rtsp_password": ""})

    def test_password_is_preserved_when_account_page_is_saved(self):
        result = MODULE.validate_option_section(
            "account", {"password": "old-secret"},
            {"email": " user@example.com ", "password": "", "country_code": "380"},
        )
        self.assertEqual(result, {"email": "user@example.com",
                                  "password": "old-secret", "country_code": "380"})
