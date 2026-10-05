"""The mobile SDK routes a DP write using both gateway and device IDs."""

import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components/neolight"))
from mobile_api import MobileApiClient  # noqa: E402


class MobilePublishTests(unittest.TestCase):
    def test_publish_includes_gateway_id(self):
        client = MobileApiClient(None, "example.invalid", {}, "key")
        client.request = AsyncMock(return_value=True)

        asyncio.run(client.publish_dps("monitor-id", {"231": "same-channel"}))

        client.request.assert_awaited_once_with(
            "thing.m.device.dp.publish", "1.0",
            {"gwId": "monitor-id", "devId": "monitor-id", "dps": '{"231":"same-channel"}'},
        )


if __name__ == "__main__":
    unittest.main()
