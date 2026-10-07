"""Publish monitor RTSP video and native audio, with P2P video as backup."""

from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import signal
import subprocess
import threading
import time
from urllib.parse import quote
from urllib.request import urlopen


LOG = logging.getLogger("neolight_avmux")
STREAM = os.environ.get("NEOLIGHT_AV_STREAM", "neolight_door_with_audio")
API = os.environ.get("NEOLIGHT_GO2RTC_API", "http://127.0.0.1:1985/api/streams")
BACKUP_VIDEO = os.environ.get("NEOLIGHT_BACKUP_VIDEO", "rtsp://127.0.0.1:8556/neolight_native_video")
NATIVE_AUDIO = os.environ.get("NEOLIGHT_NATIVE_AUDIO", "rtsp://127.0.0.1:8556/neolight_native_audio")
OUTPUT_URL = os.environ.get("NEOLIGHT_AV_OUTPUT", f"rtsp://127.0.0.1:8556/{STREAM}")
HA_ENTRIES = Path(os.environ.get("NEOLIGHT_HA_ENTRIES", "/ha-storage/core.config_entries"))
STATE = Path(os.environ.get("NEOLIGHT_STATE", "/state"))
HEALTH_PORT = int(os.environ.get("NEOLIGHT_AV_HEALTH_PORT", "38558"))
running = True
health = {"source": None, "publisher": False, "started_at": None, "last_video_at": None}


def health_snapshot(now: float | None = None) -> dict:
    """Report actual output byte progress without exposing media credentials."""
    now = time.monotonic() if now is None else now
    age = (round(now - health["last_video_at"], 1)
           if health["last_video_at"] is not None else None)
    if health["publisher"] and age is not None and age <= 15:
        status = "live"
    elif health["started_at"] is not None and now - health["started_at"] < 15:
        status = "starting"
    else:
        status = "stale"
    return {"status": status, "source": health["source"],
            "publisher": health["publisher"], "video_age_seconds": age}


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        body = json.dumps(health_snapshot()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        pass


def monitor_video_url() -> str:
    """Read RTSP credentials from HA's private config entry, without logging them."""
    exported = STATE / "vendor_config.json"
    if HA_ENTRIES.exists():
        entries = json.loads(HA_ENTRIES.read_text())["data"]["entries"]
        device = next(entry["data"] for entry in entries if entry.get("domain") == "neolight")
    else:
        device = json.loads(exported.read_text())
    user = quote(device["rtsp_user"], safe="")
    password = quote(device["rtsp_password"], safe="")
    host = device.get("monitor_host") or device["host"]
    stream_id = device["stream_id"]
    if not user or not password or not stream_id:
        raise ValueError("HA NeoLight RTSP settings are incomplete")
    return f"rtsp://{user}:{password}@{host}:8554/{stream_id}-MainStream"


def command_for(backup: bool, primary_video: str) -> list[str]:
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "quiet", "-nostats",
        "-rtsp_transport", "tcp", "-timeout", "10000000",
        "-i", BACKUP_VIDEO if backup else primary_video,
        "-rtsp_transport", "tcp", "-timeout", "10000000",
        "-i", NATIVE_AUDIO,
        "-map", "0:v:0", "-map", "1:a:0",
    ]
    if backup:
        command.extend(("-c:v", "copy"))
    else:
        command.extend((
            "-c:v", "libx264", "-preset", "superfast", "-tune", "zerolatency",
            "-pix_fmt", "yuv420p", "-vf", "scale=1280:-2", "-r", "15", "-g", "50",
        ))
    command.extend((
        "-c:a", "copy", "-max_interleave_delta", "0",
        "-rtsp_transport", "tcp", "-f", "rtsp",
        OUTPUT_URL,
    ))
    return command


def primary_healthy(primary_video: str) -> bool:
    try:
        probe = subprocess.run(
            ["ffmpeg", "-v", "error", "-rtsp_transport", "tcp", "-timeout", "3000000",
             "-i", primary_video, "-an", "-frames:v", "1", "-f", "null", "-"],
            capture_output=True, timeout=5, check=False,
        )
        return probe.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def next_source(backup: bool, failures: int, return_primary: bool) -> tuple[bool, int]:
    """Retry each failed source once; never remain on a dead backup forever."""
    if return_primary:
        return False, 0
    failures += 1
    if failures >= 2:
        return not backup, 0
    return backup, failures


def stop(_signal: int, _frame: object) -> None:
    global running
    running = False


def publishing() -> tuple[bool, int] | None:
    try:
        with urlopen(API, timeout=2) as response:
            streams = json.load(response)
    except Exception:
        return None
    producers = streams.get(STREAM, {}).get("producers") or []
    if not producers:
        return False, 0
    video_bytes = sum(
        receiver.get("bytes", 0)
        for producer in producers
        for receiver in producer.get("receivers", [])
        if receiver.get("codec", {}).get("codec_type") == "video"
    )
    return True, video_bytes


def main() -> None:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    server = ThreadingHTTPServer(("127.0.0.1", HEALTH_PORT), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    backup = False
    startup_failures = 0
    while running:
        try:
            primary_video = monitor_video_url()
        except (OSError, ValueError, KeyError, StopIteration) as error:
            LOG.warning("Monitor RTSP configuration unavailable: %s", type(error).__name__)
            time.sleep(5)
            continue
        LOG.info("Starting %s video source", "native backup" if backup else "monitor RTSP")
        health.update(source="native_backup" if backup else "monitor_rtsp",
                      publisher=False, started_at=time.monotonic(), last_video_at=None)
        process = subprocess.Popen(command_for(backup, primary_video), stderr=subprocess.DEVNULL)
        started = time.monotonic()
        absent = 0
        stalled = 0
        last_video_bytes = 0
        last_primary_probe = started
        primary_healthy_count = 0
        return_primary = False
        while running and process.poll() is None:
            time.sleep(5)
            if time.monotonic() - started < 12:
                continue
            state = publishing()
            if state is None:
                continue
            active, video_bytes = state
            health["publisher"] = active
            if active and video_bytes != last_video_bytes:
                health["last_video_at"] = time.monotonic()
                startup_failures = 0
            absent = 0 if active else absent + 1
            if absent >= 2:
                LOG.warning("RTSP publisher disappeared; restarting FFmpeg")
                break
            if active:
                stalled = stalled + 1 if video_bytes == last_video_bytes else 0
                last_video_bytes = video_bytes
                if stalled >= 3:
                    LOG.warning("RTSP video stalled; restarting FFmpeg")
                    break
            if backup and time.monotonic() - last_primary_probe >= 30:
                last_primary_probe = time.monotonic()
                primary_healthy_count = primary_healthy_count + 1 if primary_healthy(primary_video) else 0
                if primary_healthy_count >= 2:
                    LOG.info("Monitor RTSP recovered; returning to full frame rate")
                    return_primary = True
                    break
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        health["publisher"] = False
        if running:
            LOG.warning("FFmpeg exited (%s)", process.returncode)
            backup, startup_failures = next_source(backup, startup_failures, return_primary)
            time.sleep(3)
    server.shutdown()
    server.server_close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
