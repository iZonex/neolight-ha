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

    def test_push_and_dp_metadata_omit_payload_values(self):
        push = summarize_message({"protocol": 43, "data": {"etype": "ipc_doorbell",
                                  "edata": "private-call-id", "devId": "private-device"}}, 90)
        self.assertEqual(push["push_type"], "ipc_doorbell")
        self.assertNotIn("private-", str(push))
        dp = summarize_message({"protocol": 4, "data": {"dps": {
            "185": "private-alarm", "239": "Ring", "240": "Normal"}}}, 80)
        self.assertEqual(dp["dp_ids"], ["185", "239", "240"])
        self.assertEqual(dp["ring_states"], {"239": "Ring", "240": "Normal"})
        self.assertNotIn("private-alarm", str(dp))


if __name__ == "__main__":
    unittest.main()
