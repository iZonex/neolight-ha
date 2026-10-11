"""Verify browser audio is bounded and only its owner can stop the socket."""

import asyncio
import base64
import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components/neolight/talk_transport.py"
spec = importlib.util.spec_from_file_location("neolight_talk_transport_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class TalkTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.received = asyncio.Future()

        async def accept(reader, writer):
            data = await reader.read()
            self.received.set_result(data)
            writer.close()
            await writer.wait_closed()

        self.server = await asyncio.start_server(accept, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        self.sessions = module.TalkSessions()

    async def asyncTearDown(self):
        await self.sessions.close_entry("entry")
        self.server.close()
        await self.server.wait_closed()

    async def test_valid_frames_reach_socket_and_owner_stops(self):
        session = await self.sessions.start("entry", "owner", self.port)
        frames = bytes([0xFF]) * 640
        await self.sessions.audio("entry", "owner", session.token,
                                  base64.b64encode(frames).decode())
        with self.assertRaises(ValueError):
            await self.sessions.stop("entry", "other", session.token)
        await self.sessions.stop("entry", "owner", session.token)
        self.assertEqual(await asyncio.wait_for(self.received, 2), frames)

    async def test_rejects_malformed_audio_and_second_microphone(self):
        session = await self.sessions.start("entry", "owner", self.port)
        with self.assertRaises(ValueError):
            await self.sessions.start("entry", "other", self.port)
        with self.assertRaises(ValueError):
            await self.sessions.audio("entry", "owner", session.token, "not base64!")
        with self.assertRaises(ValueError):
            await self.sessions.audio("entry", "owner", session.token,
                                      base64.b64encode(bytes(319)).decode())
        with self.assertRaises(ValueError):
            await self.sessions.audio("entry", "owner", "bad token",
                                      base64.b64encode(bytes(320)).decode())
