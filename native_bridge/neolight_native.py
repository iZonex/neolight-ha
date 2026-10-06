"""Native NeoLight P2P session with live RTSP audio and a talk socket.

The Tuya P2P SDK 0.1.1 supplies signaling, encryption and KCP. This adapter
adds the H.265 / PCM framing seen on the owner's ALPHA Hybrid and sends the
panel audio to FFmpeg. A localhost socket carries Apple Home microphone audio back
over the same P2P session.
"""

from __future__ import annotations

import asyncio
from collections import deque
import hashlib
import json
import logging
import os
from pathlib import Path
import time
from typing import Callable

import aiohttp
from tuya_ipc_p2p_sdk.signaling.envelope import aes_ecb_decrypt, decode_frame, parse_json_object
from tuya_ipc_p2p_sdk.signaling.moto_client import MotoClient
from tuya_ipc_p2p_sdk.control import parse_control
from tuya_ipc_p2p_sdk.crypto import decrypt_record, encrypt_record
from tuya_ipc_p2p_sdk.models import MqttIdentity, StreamConfig
from tuya_ipc_p2p_sdk.stream_session import StreamSession
from tuya_ipc_p2p_sdk.transport.kcp_segment import parse_segment
from tuya_ipc_p2p_sdk.transport.relay_session import VIDEO_CONVERSATION

from mobile_api import MobileApiClient, MobileApiError
from account_identity import native_static_fields
from call_signaling import ActiveCall, call_command, incoming_call
from panel_protocol import PanelProfile
from protocol import TALK_START_TYPE, audio_packet, control_packet

LOGGER = logging.getLogger("neolight_native")
STATE = Path(os.environ.get("NEOLIGHT_STATE", "/state"))
PUBLISH_URL = os.environ.get("NEOLIGHT_PUBLISH_URL", "rtsp://127.0.0.1:8556/neolight_native_audio")
VIDEO_URL = os.environ.get("NEOLIGHT_VIDEO_URL", "rtsp://127.0.0.1:8556/neolight_native_video")
TALK_PORT = int(os.environ.get("NEOLIGHT_TALK_PORT", "38556"))
VIDEO_TYPE = 0x00010003
AUDIO_TYPE = 0x00010005
CALL_MAX_AGE = 60


class CallAwareMotoClient(MotoClient):
    """Pass fresh call notifications to the same P2P session's talk control."""

    def __init__(self, *args, on_call: Callable[[ActiveCall], None], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._on_call = on_call

    def _consume(self, payload: bytes) -> None:
        try:
            decoded = parse_json_object(
                aes_ecb_decrypt(self._key, decode_frame(payload).body)
            )
            call = incoming_call(decoded, self._device_id)
            if call is not None:
                self._on_call(call)
                return
        except Exception:
            pass
        super()._consume(payload)


def md5(value: str) -> str:
    return hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()


class MediaReassembler:
    """Join AES records into the 36-byte-header Tuya AV frames they carry."""

    def __init__(self, frame_type: int, codec: int) -> None:
        self.marker = frame_type.to_bytes(4, "little")
        self.codec = codec
        self.buffer = bytearray()
        self.codec_counts: dict[int, int] = {}

    def feed(self, chunk: bytes) -> list[bytes]:
        self.buffer.extend(chunk)
        payloads: list[bytes] = []
        while len(self.buffer) >= 36:
            if self.buffer[:4] != self.marker:
                next_marker = self.buffer.find(self.marker, 1)
                if next_marker < 0:
                    del self.buffer[:-3]
                    break
                del self.buffer[:next_marker]
                continue
            length = int.from_bytes(self.buffer[32:36], "little")
            if length < 12 or length > 2048:
                del self.buffer[0]
                continue
            packet_length = 36 + length
            if len(self.buffer) < packet_length:
                # A damaged header can look valid yet ask us to wait forever
                # for bytes the next frame has already superseded.
                next_marker = self.buffer.find(self.marker, 36)
                if 0 <= next_marker < packet_length:
                    del self.buffer[:next_marker]
                    continue
                break
            packet = bytes(self.buffer[:packet_length])
            del self.buffer[:packet_length]
            codec = int.from_bytes(packet[44:48], "big")
            self.codec_counts[codec] = self.codec_counts.get(codec, 0) + 1
            if codec == self.codec:
                payloads.append(packet[48:])
        if len(self.buffer) > 8_000_000:
            self.buffer.clear()
        return payloads


class HevcReassembler:
    """Rejoin H.265 fragmentation units into Annex B NAL units."""

    def __init__(self) -> None:
        self.fragment = bytearray()
        self.input_types: dict[int, int] = {}
        self.fu_headers: dict[int, int] = {}

    def feed(self, payload: bytes) -> bytes | None:
        if len(payload) < 2:
            return None
        nal_type = (payload[0] >> 1) & 0x3F
        self.input_types[nal_type] = self.input_types.get(nal_type, 0) + 1
        if nal_type != 49:
            self.fragment.clear()
            return b"\x00\x00\x00\x01" + payload
        if len(payload) < 3:
            return None
        fu_header = payload[2]
        self.fu_headers[fu_header] = self.fu_headers.get(fu_header, 0) + 1
        if fu_header & 0x80:
            original_type = fu_header & 0x3F
            first_byte = (payload[0] & 0x81) | (original_type << 1)
            self.fragment = bytearray((first_byte, payload[1]))
        if not self.fragment:
            return None
        self.fragment.extend(payload[3:])
        if not (fu_header & 0x40):
            return None
        nal = b"\x00\x00\x00\x01" + bytes(self.fragment)
        self.fragment.clear()
        return nal


class PipePump:
    """Write FFmpeg pipe input without blocking P2P acknowledgements."""

    def __init__(self, fd: int, max_queued: int) -> None:
        self.fd = fd
        self.max_queued = max_queued
        self.queue: deque[memoryview] = deque()
        self.queued = 0
        self.loop = asyncio.get_running_loop()
        self.watching = False
        self.closed = False
        os.set_blocking(fd, False)

    def write(self, data: bytes) -> None:
        if self.closed or not data:
            return
        if self.queued + len(data) > self.max_queued:
            self.queue.clear()
            self.queued = 0
        self.queue.append(memoryview(data))
        self.queued += len(data)
        if not self.watching:
            self.loop.add_writer(self.fd, self._flush)
            self.watching = True

    def _flush(self) -> None:
        try:
            while self.queue:
                head = self.queue[0]
                try:
                    written = os.write(self.fd, head)
                except BlockingIOError:
                    break
                if written == len(head):
                    self.queue.popleft()
                else:
                    self.queue[0] = head[written:]
                self.queued -= written
        except (BrokenPipeError, OSError):
            self.close()
        if not self.queue and self.watching:
            self.loop.remove_writer(self.fd)
            self.watching = False

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.watching:
            self.loop.remove_writer(self.fd)
        os.close(self.fd)


class NeoLightSession(StreamSession):
    def __init__(self, config: StreamConfig, identity: MqttIdentity, uid: str,
                 on_video: Callable[[bytes], None], on_audio: Callable[[bytes], None]) -> None:
        super().__init__(config, identity, uid, lambda _: None)
        self.on_video = on_video
        self.on_audio = on_audio
        self.video_count = 0
        self.raw_video_records = 0
        self.video_record_prefixes: dict[str, int] = {}
        self.nal_types: dict[int, int] = {}
        self.video_frames = MediaReassembler(VIDEO_TYPE, 10)
        self.audio_frames = MediaReassembler(AUDIO_TYPE, 11)
        self.hevc = HevcReassembler()
        self.audio_count = 0
        self.last_video = time.monotonic()
        self.talk_active = False
        self._control_responses: asyncio.Queue[tuple[int, int]] = asyncio.Queue()
        self._incoming_call: ActiveCall | None = None
        self._incoming_at = 0.0
        self._answered_call: ActiveCall | None = None

    async def _async_connect_signaling(self, session_id: str) -> None:
        self._moto = CallAwareMotoClient(
            identity=self._identity,
            uid=self._uid,
            device_id=self._config.device_id,
            session_id=session_id,
            local_key=self._config.local_key,
            on_answer=self._on_answer,
            on_candidate=self._on_remote_candidate,
            on_disconnect=self._on_device_disconnect,
            on_call=self._on_incoming_call,
        )
        await self._moto.async_connect()

    def _on_incoming_call(self, call: ActiveCall) -> None:
        self._incoming_call = call
        self._incoming_at = time.monotonic()
        LOGGER.info("Incoming %s call is available for Apple Home Talk", call.call_type)

    async def answer_active_call(self) -> None:
        call = self._incoming_call
        if call is None or time.monotonic() - self._incoming_at > CALL_MAX_AGE:
            return
        moto = self._require_moto()
        await moto._async_publish(
            308, call_command(call.call_type, call.device_id, call.message_id,
                              "accept", call.channel_id)
        )
        self._answered_call = call
        LOGGER.info("NeoLight call answer sent for Apple Home Talk")

    async def hangup_active_call(self) -> None:
        call = self._answered_call
        self._answered_call = None
        if call is None:
            return
        moto = self._require_moto()
        await moto._async_publish(
            308, call_command(call.call_type, call.device_id, call.message_id,
                              "stop", call.channel_id)
        )
        if self._incoming_call == call:
            self._incoming_call = None
        LOGGER.info("NeoLight call hangup sent after Apple Home Talk")

    def _on_media_record(self, record: bytes) -> None:
        self.raw_video_records += 1
        try:
            plain = decrypt_record(self._answer_key, record)
        except Exception:
            return
        prefix = plain[:4].hex()
        self.video_record_prefixes[prefix] = self.video_record_prefixes.get(prefix, 0) + 1
        for payload in self.video_frames.feed(plain):
            nal = self.hevc.feed(payload)
            if nal is None:
                continue
            self.video_count += 1
            nal_type = (nal[4] >> 1) & 0x3F
            self.nal_types[nal_type] = self.nal_types.get(nal_type, 0) + 1
            self.last_video = time.monotonic()
            self.on_video(nal)

    def _send_channel_zero(self, send_key: bytes, receive_key: bytes) -> None:
        """Attach the media handler before Tuya's start burst emits the VPS."""
        relay = self._require_relay()

        def route(raw: bytes) -> None:
            segment = parse_segment(raw)
            if segment is None:
                return
            known = segment.conversation in relay._conversations
            conversation = relay._conversation(segment.conversation)
            if not known and segment.conversation == VIDEO_CONVERSATION:
                if not relay._video_ready.done():
                    relay._video_ready.set_result(conversation)
            if segment.conversation == VIDEO_CONVERSATION:
                conversation.set_message_handler(self._on_media_record)
            conversation.input(segment)

        relay._connection.set_segment_handler(route)
        super()._send_channel_zero(send_key, receive_key)

    def on_audio_record(self, record: bytes) -> None:
        try:
            plain = decrypt_record(self._answer_key, record)
        except Exception:
            return
        for payload in self.audio_frames.feed(plain):
            self.audio_count += 1
            self.on_audio(payload)

    def on_control_record(self, record: bytes) -> None:
        try:
            packet = parse_control(decrypt_record(self._answer_key, record))
        except Exception:
            return
        if packet is not None and packet.sub_command == 8:
            self._control_responses.put_nowait((packet.type, packet.flag))
            if packet.type in (6, 7):
                LOGGER.info("Talk control response type=%s flag=%s", packet.type, packet.flag)

    def enable_audio(self) -> None:
        relay = self._require_relay()
        relay._conversation(2).set_message_handler(self.on_audio_record)
        relay.control.set_message_handler(self.on_control_record)

    def send_control(self, packet_type: int, operation: int) -> None:
        relay = self._require_relay()
        relay.control.send(encrypt_record(self._config.p2p_session.aes_key, control_packet(packet_type, operation)))

    def send_audio(self, pcmu: bytes) -> None:
        if len(pcmu) != 320:
            raise ValueError("native talk audio must be 320 PCMU bytes")
        relay = self._require_relay()
        timestamp = int(time.monotonic() * 1000)
        relay._conversation(2).send(encrypt_record(self._config.p2p_session.aes_key, audio_packet(timestamp, pcmu)))


async def session_config() -> tuple[StreamConfig, MqttIdentity, str, str]:
    vendor = json.loads((STATE / "vendor_config.json").read_text())
    fields = native_static_fields(vendor["static_fields"])
    async with aiohttp.ClientSession() as http:
        client = MobileApiClient(
            http, vendor["api_host"], fields, vendor["signing_key"],
            email=vendor["email"], password=vendor["password"],
            country_code=vendor.get("country_code", "380"),
        )
        runtime = await client.login()
        info = await client.request("smartlife.m.user.info.get", "1.0")
        device = await client.read_device(vendor["paired_device_id"])
        preferred_channel = vendor.get("preferred_video_channel", 0)
        try:
            active_route = json.loads((STATE / "video_route.json").read_text())
            if (active_route.get("expires", 0) > time.time()
                    and type(active_route.get("call_channel")) is int):
                preferred_channel = active_route["call_channel"]
        except (FileNotFoundError, ValueError, TypeError):
            pass
        if type(preferred_channel) is int and preferred_channel > 0:
            try:
                schema = device["schema"]
                if isinstance(schema, str):
                    schema = json.loads(schema)
                profile = PanelProfile.from_schema(schema, required=("channel",))
                dp_id = str(profile.dp_ids["channel"])
                command = profile.channel_command(device["dps"][dp_id], preferred_channel)
                await client.publish_dps(vendor["paired_device_id"], command)
                LOGGER.info("Selected preferred video channel %s", preferred_channel)
                await asyncio.sleep(2)
            except (KeyError, TypeError, ValueError, MobileApiError) as error:
                LOGGER.warning("Preferred video channel unavailable: %s", type(error).__name__)
        raw = await client.request("m.ipc.v4.rtc.config.get", "1.0", {"devId": vendor["paired_device_id"]})
    config = StreamConfig.from_json(raw, vendor["paired_device_id"], device["localKey"])
    ecode = runtime["ecode"]
    app_key = fields["clientId"]
    uid = info["id"]
    broker = info["domain"]["mobileMqttsUrl"].split(":")[0]
    identity = MqttIdentity(
        host=broker, port=8883,
        client_id=f"com.neolight.neo_mb_{fields['deviceId']}native_{md5(uid + 'sdkfasodifca')}_DEFAULT",
        username=f"{runtime['partnerIdentity']}_v1_{app_key}_{fields['chKey']}_mb_{runtime['sid']}{md5(md5(app_key) + ecode)[16:]}",
        password=md5(md5(vendor["signing_key"]) + ecode)[8:24],
    )
    return config, identity, uid, md5(md5(app_key) + ecode)[-16:]


async def publish_process() -> tuple[asyncio.subprocess.Process, PipePump]:
    audio_read, audio_write = os.pipe()
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "warning",
            "-f", "s16le", "-ar", "8000", "-ac", "1", "-i", f"pipe:{audio_read}",
            "-c:a", "pcm_alaw", "-ar", "8000", "-ac", "1",
            "-rtsp_transport", "tcp", "-f", "rtsp", PUBLISH_URL,
            pass_fds=(audio_read,),
            stdin=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )
    finally:
        os.close(audio_read)
    return process, PipePump(audio_write, 64_000)


async def video_publish_process() -> tuple[asyncio.subprocess.Process, PipePump]:
    video_read, video_write = os.pipe()
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "warning",
            "-probesize", "4096", "-analyzeduration", "0",
            "-f", "hevc", "-r", "1", "-i", f"pipe:{video_read}",
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-pix_fmt", "yuv420p", "-vf", "scale=1280:-2", "-r", "15", "-g", "30",
            "-rtsp_transport", "tcp", "-f", "rtsp", VIDEO_URL,
            pass_fds=(video_read,), stdin=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    finally:
        os.close(video_read)
    return process, PipePump(video_write, 2_000_000)


async def handle_talk(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                      session: NeoLightSession) -> None:
    peer = writer.get_extra_info("peername")
    if session.talk_active:
        writer.close()
        await writer.wait_closed()
        return
    session.talk_active = True
    sent = 0
    signal_bytes = 0
    try:
        try:
            await session.answer_active_call()
        except Exception:
            LOGGER.exception("NeoLight call answer failed; continuing P2P Talk")
        # The official app sends type 6 when Talk starts on a fresh P2P session.
        # Outbound audio frames also use type 6, with a different header shape.
        session.send_control(TALK_START_TYPE, 0)
        await asyncio.sleep(0.4)
        while True:
            try:
                frame = await reader.readexactly(320)
            except asyncio.IncompleteReadError:
                break
            session.send_audio(frame)
            sent += 1
            signal_bytes += sum(value not in (0x7F, 0xFF) for value in frame)
            await asyncio.sleep(0.04)
    except Exception as error:
        LOGGER.warning("Talk channel ended: %s", type(error).__name__)
    finally:
        try:
            await session.hangup_active_call()
        except Exception:
            LOGGER.exception("NeoLight call hangup failed")
        try:
            session.send_control(0, 1)
        except Exception:
            pass
        session.talk_active = False
        writer.close()
        await writer.wait_closed()
        try:
            pending = len(session._require_relay()._conversation(2)._pending)
        except Exception:
            pending = -1
        LOGGER.info("Talk session from %s ended after %s frames; signal=%s/%s bytes; pending=%s",
                    peer, sent, signal_bytes, sent * 320, pending)


async def run_once() -> None:
    config, identity, uid, _ = await session_config()
    ffmpeg, audio = await publish_process()
    video_ffmpeg, video = await video_publish_process()
    session = NeoLightSession(config, identity, uid, video.write, audio.write)
    talk_server: asyncio.AbstractServer | None = None
    async def log_ffmpeg() -> None:
        assert ffmpeg.stderr is not None
        async for line in ffmpeg.stderr:
            LOGGER.warning("FFmpeg: %s", line.decode(errors="replace").rstrip()[-300:])

    async def log_video_ffmpeg() -> None:
        assert video_ffmpeg.stderr is not None
        async for line in video_ffmpeg.stderr:
            LOGGER.warning("Video FFmpeg: %s", line.decode(errors="replace").rstrip()[-300:])

    ffmpeg_log = asyncio.create_task(log_ffmpeg())
    video_ffmpeg_log = asyncio.create_task(log_video_ffmpeg())
    try:
        await session.async_start()
        session.enable_audio()
        talk_server = await asyncio.start_server(
            lambda reader, writer: handle_talk(reader, writer, session), "127.0.0.1", TALK_PORT,
        )
        LOGGER.info("P2P connected; native video, panel audio and localhost talk ready")
        closed = asyncio.create_task(session.async_wait_closed())
        exited = asyncio.create_task(ffmpeg.wait())
        video_exited = asyncio.create_task(video_ffmpeg.wait())
        last_report = time.monotonic()
        while True:
            done, _ = await asyncio.wait((closed, exited, video_exited), timeout=5, return_when=asyncio.FIRST_COMPLETED)
            if done:
                LOGGER.warning("P2P or publisher stopped; reconnecting")
                break
            if time.monotonic() - session.last_video > 20:
                LOGGER.warning("No P2P video for 20 seconds; reconnecting")
                break
            if time.monotonic() - last_report >= 10:
                LOGGER.info("P2P packets video=%s audio=%s; FFmpeg queued video=%s audio=%s",
                            session.video_count, session.audio_count, video.queued, audio.queued)
                LOGGER.info("P2P H.265 NAL types: %s", session.nal_types)
                LOGGER.info("P2P raw video records=%s, assembly bytes=%s",
                            session.raw_video_records, len(session.video_frames.buffer))
                LOGGER.info("P2P video record prefixes=%s, codecs=%s, input NAL types=%s, FU headers=%s",
                            sorted(session.video_record_prefixes.items(), key=lambda item: -item[1])[:4],
                            session.video_frames.codec_counts, session.hevc.input_types,
                            sorted(session.hevc.fu_headers.items(), key=lambda item: -item[1])[:12])
                last_report = time.monotonic()
        closed.cancel()
        exited.cancel()
        video_exited.cancel()
    finally:
        if talk_server is not None:
            talk_server.close()
            await talk_server.wait_closed()
        await session.async_close()
        video.close()
        audio.close()
        if ffmpeg.returncode is None:
            ffmpeg.terminate()
        if video_ffmpeg.returncode is None:
            video_ffmpeg.terminate()
        ffmpeg_log.cancel()
        video_ffmpeg_log.cancel()
        try:
            await ffmpeg_log
        except asyncio.CancelledError:
            pass
        try:
            await video_ffmpeg_log
        except asyncio.CancelledError:
            pass
        try:
            _, stderr = await asyncio.wait_for(ffmpeg.communicate(), timeout=5)
        except asyncio.TimeoutError:
            ffmpeg.kill()
            _, stderr = await ffmpeg.communicate()
        if stderr:
            LOGGER.warning("FFmpeg: %s", stderr.decode(errors="replace")[-400:])
        try:
            _, video_stderr = await asyncio.wait_for(video_ffmpeg.communicate(), timeout=5)
        except asyncio.TimeoutError:
            video_ffmpeg.kill()
            _, video_stderr = await video_ffmpeg.communicate()
        if video_stderr:
            LOGGER.warning("Video FFmpeg: %s", video_stderr.decode(errors="replace")[-400:])
        LOGGER.info("P2P session delivered %s video and %s audio packets", session.video_count, session.audio_count)


async def main() -> None:
    while True:
        try:
            await run_once()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            LOGGER.exception("P2P connection failed: %s", type(error).__name__)
        await asyncio.sleep(5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main())
