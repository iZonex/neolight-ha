"""Captured NeoLight APK packets, with session-specific timestamps removed."""

import unittest

from protocol import TALK_START_TYPE, audio_packet, control_packet


class PacketTests(unittest.TestCase):
    def test_first_talk_start_matches_app(self) -> None:
        self.assertEqual(
            control_packet(TALK_START_TYPE, 0).hex(),
            "78563412060000000000000008000000080000000000000000000000",
        )

    def test_audio_frame_matches_app_header(self) -> None:
        frame = audio_packet(0x0BFB2FAC, bytes([0x7F]) * 320)
        self.assertEqual(
            frame[:36].hex(),
            "785634120600000085000000000000000100000000000000ac2ffb0b400100007f7f7f7f",
        )
        self.assertEqual(len(frame), 352)

    def test_talk_stop_matches_app(self) -> None:
        self.assertEqual(
            control_packet(0, 1).hex(),
            "78563412000000000000000008000000080000000000000001000000",
        )


if __name__ == "__main__":
    unittest.main()
