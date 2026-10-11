"""Bounded local microphone socket sessions, independent of Home Assistant."""

from __future__ import annotations

import asyncio
import base64
import binascii
from dataclasses import dataclass, field
from secrets import token_urlsafe
import time

_SESSION_IDLE_SECONDS = 3.0
_MAX_AUDIO_BYTES = 3200

@dataclass
class TalkSession:
    """One microphone owner and one native socket, with a short idle lease."""

    entry_id: str
    user_id: str
    token: str
    writer: asyncio.StreamWriter
    last_audio: float = field(default_factory=time.monotonic)
    watchdog: asyncio.Task | None = None

    async def close(self) -> None:
        self.writer.close()
        await self.writer.wait_closed()


class TalkSessions:
    def __init__(self) -> None:
        self._sessions: dict[str, TalkSession] = {}
        self._start_lock = asyncio.Lock()

    async def start(self, entry_id: str, user_id: str, port: int) -> TalkSession:
        async with self._start_lock:
            if entry_id in self._sessions:
                raise ValueError("NeoLight microphone is already in use")
            if not 1 <= port <= 65535:
                raise ValueError("NeoLight talk bridge is not configured")
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", port), timeout=3
                )
            except (OSError, asyncio.TimeoutError) as error:
                raise ValueError("NeoLight talk bridge is unavailable") from error
            session = TalkSession(entry_id, user_id, token_urlsafe(24), writer)
            self._sessions[entry_id] = session
            session.watchdog = asyncio.create_task(self._watch(session))
            return session

    async def audio(self, entry_id: str, user_id: str, token: str, encoded: str) -> None:
        session = self._owned(entry_id, user_id, token)
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("Invalid microphone audio") from error
        if not 320 <= len(data) <= _MAX_AUDIO_BYTES or len(data) % 320:
            raise ValueError("Microphone audio must contain complete 40 ms frames")
        if session.writer.is_closing() or session.writer.transport.get_write_buffer_size() > 16000:
            await self.stop(entry_id, user_id, token)
            raise ValueError("NeoLight talk bridge is too slow or disconnected")
        session.writer.write(data)
        try:
            await asyncio.wait_for(session.writer.drain(), timeout=2)
        except (OSError, asyncio.TimeoutError) as error:
            await self.stop(entry_id, user_id, token)
            raise ValueError("NeoLight talk bridge disconnected") from error
        session.last_audio = time.monotonic()

    async def stop(self, entry_id: str, user_id: str, token: str) -> None:
        session = self._owned(entry_id, user_id, token)
        self._sessions.pop(entry_id, None)
        if session.watchdog:
            session.watchdog.cancel()
        await session.close()

    async def close_entry(self, entry_id: str) -> None:
        session = self._sessions.pop(entry_id, None)
        if session:
            if session.watchdog:
                session.watchdog.cancel()
            await session.close()

    def _owned(self, entry_id: str, user_id: str, token: str) -> TalkSession:
        session = self._sessions.get(entry_id)
        if not session or session.user_id != user_id or session.token != token:
            raise ValueError("NeoLight microphone session is not active")
        return session

    async def _watch(self, session: TalkSession) -> None:
        try:
            while True:
                await asyncio.sleep(0.5)
                if time.monotonic() - session.last_audio > _SESSION_IDLE_SECONDS:
                    self._sessions.pop(session.entry_id, None)
                    await session.close()
                    return
        except asyncio.CancelledError:
            pass


