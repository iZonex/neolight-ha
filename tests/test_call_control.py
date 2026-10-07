"""The HA controls accept only explicit responses from the loopback bridge."""

import asyncio
import importlib.util
from pathlib import Path
import unittest


PATH = Path(__file__).parents[1] / "custom_components/neolight/call_control.py"
SPEC = importlib.util.spec_from_file_location("neolight_call_control", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CallControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.response = b""
        self.commands = []

        async def serve(reader, writer):
            self.commands.append(await reader.readline())
            writer.write(self.response)
            await writer.drain()
            writer.close()

        self.server = await asyncio.start_server(serve, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def test_status_is_sanitized_and_unavailable_bridge_is_none(self):
        self.response = b'{"state":"ringing","talk_active":false,"call_type":"ipc_doorbell","age_seconds":2,"message_id":"private"}\n'
        status = await MODULE.read_call_status(self.port)
        self.assertEqual(status["state"], "ringing")
        self.assertNotIn("message_id", status)
        self.assertEqual(self.commands, [b"status\n"])
        self.assertIsNone(await MODULE.read_call_status(0))

    async def test_answer_and_hangup_reject_missing_call(self):
        self.response = b"no_call\n"
        with self.assertRaises(MODULE.CallControlError):
            await MODULE.answer_call(self.port)
        with self.assertRaises(MODULE.CallControlError):
            await MODULE.hangup_call(self.port)
        self.assertEqual(self.commands, [b"answer\n", b"hangup\n"])

    async def test_successful_control(self):
        self.response = b"ok\n"
        await MODULE.answer_call(self.port)
        await MODULE.hangup_call(self.port)
        await MODULE.reset_call(self.port)
        self.assertEqual(self.commands, [b"answer\n", b"hangup\n", b"reset\n"])

    async def test_busy_reset_is_not_success(self):
        self.response = b"busy\n"
        with self.assertRaises(MODULE.CallControlError):
            await MODULE.reset_call(self.port)
