"""Read-only MQTT call observer using HA's existing session and a unique client ID.

Run in a short-lived diagnostic container with the HA integration's private
configuration mounted read-only at /state. No login, DP publish, or P2P media
session is created. Output contains sanitized metadata only.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import ssl
import sys
import time
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import aiomqtt
import aiohttp
from tuya_ipc_p2p_sdk.signaling.envelope import (
    aes_ecb_decrypt,
    decode_frame,
    parse_json_object,
)

from call_signaling import summarize_message
from mobile_api import MobileApiClient


STATE = Path("/state")


def md5(value: str) -> str:
    return hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()


async def observe(seconds: int) -> None:
    vendor = json.loads((STATE / "vendor_config.json").read_text())
    runtime = json.loads((STATE / "runtime_session.json").read_text())
    fields = dict(vendor["static_fields"])
    fields["deviceId"] = str(uuid5(NAMESPACE_URL, f"neolight-ha:{fields['deviceId']}"))
    async with aiohttp.ClientSession() as http:
        client = MobileApiClient(
            http, vendor["api_host"], fields, vendor["signing_key"], sid=runtime["sid"]
        )
        info = await client.request("smartlife.m.user.info.get", "1.0")
        device = await client.request(
            "tuya.m.device.get", "1.0", {"devId": vendor["paired_device_id"]}
        )
    app_key = fields["clientId"]
    broker = info["domain"]["mobileMqttsUrl"].split(":")[0]
    tls = ssl.create_default_context()
    tls.check_hostname = False
    tls.verify_mode = ssl.CERT_NONE
    deadline = time.monotonic() + seconds
    client_id = f"com.neolight.neo_mb_{fields['deviceId']}call_observe_{md5(info['id'] + 'sdkfasodifca')}_DEFAULT"
    while time.monotonic() < deadline:
        try:
            runtime = json.loads((STATE / "runtime_session.json").read_text())
            ecode = runtime["ecode"]
            msid = md5(md5(app_key) + ecode)[-16:]
            topics = [f"smart/mb/in/{vendor['paired_device_id']}", f"/av/u/{msid}"]
            username = (
                f"{runtime['partnerIdentity']}_v1_{app_key}_{fields['chKey']}_mb_{runtime['sid']}"
                f"{md5(md5(app_key) + ecode)[16:]}"
            )
            password = md5(md5(vendor["signing_key"]) + ecode)[8:24]
            async with aiomqtt.Client(
                hostname=broker, port=8883, username=username, password=password,
                identifier=client_id, tls_context=tls, clean_session=True,
            ) as mqtt:
                for index, topic in enumerate(topics):
                    await mqtt.subscribe(topic, qos=1)
                    print(json.dumps({"subscribed": index}), flush=True)
                messages = mqtt.messages
                while time.monotonic() < deadline:
                    try:
                        async with asyncio.timeout(min(5, deadline - time.monotonic())):
                            received = await anext(messages)
                    except TimeoutError:
                        continue
                    payload = received.payload
                    if not isinstance(payload, bytes):
                        continue
                    try:
                        decoded = json.loads(payload)
                    except (ValueError, UnicodeDecodeError):
                        try:
                            decoded = parse_json_object(
                                aes_ecb_decrypt(
                                    device["localKey"].encode(), decode_frame(payload).body
                                )
                            )
                        except Exception:
                            decoded = None
                    summary = summarize_message(decoded, len(payload))
                    print(json.dumps({
                        "observed_at": time.time(),
                        "topic_index": next(
                            (index for index, topic in enumerate(topics)
                             if str(received.topic) == topic), -1
                        ),
                        **summary,
                    }), flush=True)
        except (aiomqtt.MqttError, OSError, TimeoutError) as error:
            print(json.dumps({"reconnecting_after": type(error).__name__}), flush=True)
            await asyncio.sleep(min(5, max(0, deadline - time.monotonic())))


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    asyncio.run(observe(int(sys.argv[1]) if len(sys.argv) > 1 else 3600))
