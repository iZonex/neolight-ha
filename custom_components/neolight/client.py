"""Read-only local monitor adapter.

Call control, audio and relay commands will be added only after the protocol
for the paired monitor has been verified.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import quote

from aiohttp import ClientError, ClientSession, ClientTimeout


class MonitorUnavailable(Exception):
    """The configured monitor did not answer as a NeoLight monitor."""


@dataclass(frozen=True)
class MonitorState:
    """State established by a successful local HTTP probe."""

    online: bool
    cloud_online: bool = False
    dps: Mapping[str, Any] = field(default_factory=dict)
    schema: list[Mapping[str, Any]] = field(default_factory=list)


class MonitorClient:
    """Small local transport shared by HA entities."""

    def __init__(self, session: ClientSession, host: str) -> None:
        self._session = session
        self.host = host

    async def probe(self) -> MonitorState:
        """Check the known web UI fingerprint without logging in."""
        try:
            async with self._session.get(
                f"http://{self.host}/index.html", timeout=ClientTimeout(total=5)
            ) as response:
                if response.status != 200:
                    raise MonitorUnavailable(f"HTTP {response.status}")
                page = await response.text()
        except (TimeoutError, ClientError) as error:
            raise MonitorUnavailable("Monitor HTTP probe failed") from error
        if 'src="js/html/index.js"' not in page or "Add-Devices" not in page:
            raise MonitorUnavailable("Unexpected web UI")
        return MonitorState(online=True)

    def rtsp_url(self, stream_id: str, user: str, password: str) -> str:
        """Construct the observed monitor RTSP path for HA's stream worker."""
        credential = ""
        if user:
            credential = quote(user, safe="")
            if password:
                credential += ":" + quote(password, safe="")
            credential += "@"
        return f"rtsp://{credential}{self.host}:8554/{stream_id}-MainStream"
