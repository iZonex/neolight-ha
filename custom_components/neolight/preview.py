"""Open the same DOOR preview that the NeoLight app opens before relay control."""

import asyncio
from contextlib import asynccontextmanager
import logging

from homeassistant.exceptions import HomeAssistantError


_LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def async_open_preview(source: str | None):
    """Keep DOOR preview connected until the relay command finishes."""
    if not source:
        yield
        return
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-rtsp_transport", "tcp", "-i", source,
            "-an", "-progress", "pipe:1", "-f", "null", "-",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError as error:
        raise HomeAssistantError("NeoLight preview could not start") from error
    try:
        async def wait_for_frame() -> None:
            assert process.stdout is not None
            while line := await process.stdout.readline():
                if line.startswith(b"frame=") and int(line.partition(b"=")[2]) > 0:
                    return
            raise HomeAssistantError("NeoLight preview connection failed")

        try:
            await asyncio.wait_for(wait_for_frame(), timeout=12)
        except TimeoutError as error:
            raise HomeAssistantError("NeoLight preview did not produce a frame") from error
        _LOGGER.debug("NeoLight DOOR preview active during relay command")
        yield
    finally:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=3)
            except TimeoutError:
                process.kill()
                await process.wait()
