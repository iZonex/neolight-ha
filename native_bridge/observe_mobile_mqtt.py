"""Read-only trace of candidate Tuya call topics during one Vizit test.

Run inside the existing native bridge image. The observer uses a distinct MQTT
client ID and records only message metadata; it never publishes commands or
prints account credentials, device identifiers, or message bodies.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
import hashlib
import json
import logging
from pathlib import Path
import ssl
import sys
import time

import aiomqtt

from neolight_native import session_config
from tuya_ipc_p2p_sdk.signaling.envelope import decode_payload


def _digest(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _summarize(payload: bytes, local_key: str) -> dict:
    try:
        data = json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        try:
            data = decode_payload(local_key.encode(), payload)
        except Exception:
            return {"encoding": "unknown", "bytes": len(payload)}
    if not isinstance(data, dict):
        return {"encoding": "non-object", "bytes": len(payload)}
    body = data.get("data", data)
    if not isinstance(body, dict):
        body = {}
    header = body.get("header")
    if not isinstance(header, dict):
        header = {}
    message = body.get("msg")
    if not isinstance(message, dict):
        message = {}
    return {
        "protocol": data.get("protocol"),
        "header_type": header.get("type"),
        "session_hash": _digest(header.get("sessionid")),
        "message_keys": sorted(message)[:24],
        "body_keys": sorted(body)[:24],
        "top_keys": sorted(data)[:24],
        "bytes": len(payload),
    }


async def main(seconds: int = 600) -> None:
    config, identity, _ = await session_config()
    # An independent client must not disconnect the active P2P media session.
    identity = replace(identity, client_id=identity.client_id.replace("native_", "observe_"))
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    state = Path("/state")
    app_key = json.loads((state / "vendor_config.json").read_text())["static_fields"]["clientId"]
    ecode = json.loads((state / "runtime_session.json").read_text())["ecode"]
    msid = hashlib.md5((hashlib.md5(app_key.encode()).hexdigest() + ecode).encode()).hexdigest()[-16:]
    topics = [f"smart/mb/in/{config.device_id}", f"/av/u/{msid}"]
    async with aiomqtt.Client(
        hostname=identity.host, port=identity.port, username=identity.username,
        password=identity.password, identifier=identity.client_id,
        tls_context=context, clean_session=True,
    ) as client:
        for index, topic in enumerate(topics):
            try:
                await client.subscribe(topic, qos=1)
                print(json.dumps({"subscribed": index}), flush=True)
            except aiomqtt.MqttError as error:
                print(json.dumps({"subscription_error": index, "type": type(error).__name__}), flush=True)
        deadline = time.monotonic() + seconds
        messages = client.messages
        while time.monotonic() < deadline:
            try:
                async with asyncio.timeout(min(5, deadline - time.monotonic())):
                    message = await anext(messages)
            except TimeoutError:
                continue
            payload = message.payload
            if not isinstance(payload, bytes):
                continue
            print(json.dumps({
                "observed_at": time.time(),
                "topic_index": next((i for i, topic in enumerate(topics) if str(message.topic) == topic), -1),
                **_summarize(payload, config.local_key),
            }), flush=True)


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 600))
