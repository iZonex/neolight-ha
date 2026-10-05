"""Checks the monitor fingerprint and RTSP URL without any device writes."""

import asyncio
import importlib.util
from pathlib import Path
import sys
import unittest


CLIENT_PATH = Path(__file__).resolve().parents[1] / "custom_components/neolight/client.py"
spec = importlib.util.spec_from_file_location("neolight_client_under_test", CLIENT_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class Response:
    def __init__(self, status, body):
        self.status = status
        self.body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def text(self):
        return self.body


class Session:
    def __init__(self, status, body):
        self.response = Response(status, body)
        self.requested_url = None

    def get(self, url, **_):
        self.requested_url = url
        return self.response


class MonitorClientTests(unittest.TestCase):
    def test_probe_accepts_known_web_ui(self):
        session = Session(200, '<script src="js/html/index.js"></script><div id="Add-Devices">')
        client = module.MonitorClient(session, "192.0.2.10")
        state = asyncio.run(client.probe())
        self.assertTrue(state.online)
        self.assertEqual(session.requested_url, "http://192.0.2.10/index.html")

    def test_probe_rejects_unrelated_web_server(self):
        session = Session(200, "<html>not a monitor</html>")
        with self.assertRaises(module.MonitorUnavailable):
            asyncio.run(module.MonitorClient(session, "192.0.2.10").probe())

    def test_rtsp_credentials_are_url_encoded(self):
        client = module.MonitorClient(None, "192.0.2.10")
        source = client.rtsp_url("12345678-1234-1234-1234-123456789abc", "a@b", "x:/z")
        self.assertEqual(
            source,
            "rtsp://a%40b:x%3A%2Fz@192.0.2.10:8554/"
            "12345678-1234-1234-1234-123456789abc-MainStream",
        )


if __name__ == "__main__":
    unittest.main()
