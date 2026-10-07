"""Verify temporary channel selection restores the original input."""

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[1] / "custom_components/neolight"
package = types.ModuleType("neolight_router_test")
package.__path__ = [str(ROOT)]
sys.modules[package.__name__] = package
settings = types.ModuleType("neolight_router_test.settings")
settings.write_private_json = lambda path, data: path.write_text(json.dumps(data))
sys.modules[settings.__name__] = settings
for name in ("panel_protocol", "video_router"):
    spec = importlib.util.spec_from_file_location(f"neolight_router_test.{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

from neolight_router_test.video_router import VideoRouter, selected_channel  # noqa: E402


SCHEMA = [{"code": "ipc_c_switch_channel", "id": 231, "type": "obj",
           "schema_type": "string", "mode": "rw"}]


class FakeMobile:
    def __init__(self):
        self.channel = 1
        self.published = []

    async def read_device(self, _):
        return {"isOnline": True, "schema": SCHEMA, "dps": {"231": json.dumps({
            "cc": self.channel, "chs": [{"id": 1}, {"id": 2}],
        })}}

    async def publish_dps(self, _, command):
        self.channel = json.loads(command["231"])["cc"]
        self.published.append(self.channel)


class VideoRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_ring_selects_call_input_then_restores_previous_input(self):
        with tempfile.TemporaryDirectory() as directory:
            mobile = FakeMobile()
            runtime = types.SimpleNamespace(mobile=mobile, vendor={"paired_device_id": "private"})
            state_path = Path(directory) / "video_route.json"
            router = VideoRouter(runtime, state_path, 2, 0)
            router.ring()
            await asyncio.wait_for(router._task, 1)
            self.assertEqual(mobile.published, [2, 1])
            self.assertEqual(mobile.channel, 1)
            self.assertFalse(state_path.exists())

    def test_malformed_channel_does_not_select(self):
        self.assertIsNone(selected_channel('{"cc":true}'))
        self.assertIsNone(selected_channel('{"cc":"2"}'))
        self.assertEqual(selected_channel('{"cc":2}'), 2)


if __name__ == "__main__":
    unittest.main()
