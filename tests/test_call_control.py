"""The HA call reset must require an explicit response from the local bridge."""

import asyncio
import importlib.util
from pathlib import Path
import unittest


PATH = Path(__file__).parents[1] / "custom_components/neolight/call_control.py"
SPEC = importlib.util.spec_from_file_location("neolight_call_control", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CallControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_reset_sends_one_command_and_requires_ok(self):
        received = []

        async def handle(reader, writer):
            received.append(await reader.readline())
            writer.write(b"ok\n")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        try:
            await MODULE.reset_call(server.sockets[0].getsockname()[1])
        finally:
            server.close()
            await server.wait_closed()
        self.assertEqual(received, [b"reset\n"])

    async def test_busy_bridge_is_not_reported_as_success(self):
        async def handle(reader, writer):
            await reader.readline()
            writer.write(b"busy\n")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        try:
            with self.assertRaises(MODULE.CallControlError):
                await MODULE.reset_call(server.sockets[0].getsockname()[1])
        finally:
            server.close()
            await server.wait_closed()
