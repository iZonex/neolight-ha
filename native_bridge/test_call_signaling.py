"""Ensure observer logs no private message or device identifiers."""

import unittest

from call_signaling import call_command, summarize_message


class CallSignalingTests(unittest.TestCase):
    def test_protocol_308_summary_hashes_call_identifiers(self):
        source = {"protocol": 308, "data": {"type": "video_doorbell", "data": {
            "devId": "private-device", "eData": "private-message", "cid": "private-channel",
            "event": "stop"}}}
        summary = summarize_message(source, 123)
        self.assertEqual(summary["protocol"], 308)
        self.assertEqual(summary["call_event"], "stop")
        self.assertEqual(summary["call_type"], "video_doorbell")
        self.assertNotIn("private-", str(summary))
        self.assertEqual(len(summary["message_hash"]), 12)

    def test_apk_protocol_308_accept_and_stop_bodies(self):
        self.assertEqual(
            call_command("video_doorbell", "device", "message", "accept", "channel"),
            {"type": "video_doorbell", "data": {
                "devId": "device", "event": "accept", "eData": "message",
                "cid": "channel",
            }},
        )
        self.assertEqual(call_command("video_doorbell", "device", "message", "stop"),
                         {"type": "video_doorbell", "data": {
                             "devId": "device", "event": "stop", "eData": "message",
                         }})

    def test_image_doorbell_and_missing_message_cannot_be_controlled(self):
        with self.assertRaises(ValueError):
            call_command("doorbell", "device", "message", "accept")
        with self.assertRaises(ValueError):
            call_command("video_doorbell", "device", "", "stop")


if __name__ == "__main__":
    unittest.main()
