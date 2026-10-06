# Adding another monitor or entrance panel

This guide is for contributors investigating equipment and accounts they own or
are authorized to test. The current implementation is based on one ALPHA
Hybrid monitor with a Vizit analog adapter. A shared app SDK or similar UI does
not establish that another model has the same data points, call signaling, or
relay wiring.

## 1. Record the installation

Before changing code, record the monitor model and firmware, app version,
entrance panel and adapter model, IP versus analog wiring, which physical door
each relay serves, and whether the phone and monitor are on the same LAN.
Record the monitor's advertised video streams and codecs. Keep IP addresses,
account details, device identifiers, and stream credentials private.

Use this matrix for each candidate feature:

| Feature | Trigger or command | Evidence source | Physical result | Confidence |
|---|---|---|---|---|
| Call start | Entrance button | App + fresh event trace | Phone rings | Observed |
| Answer / hangup | App control | App trace | Monitor call state changes | Observed |
| Video / audio each direction | App live view | Media trace | Picture and speech heard | Observed |
| Relay 1 / 2 | App unlock | Schema + state + person at door | Named door opens | Observed |

Use **observed** only after the physical result was checked. Use **inferred**
for a command found in code or an API acknowledgement. Use **unknown** when no
test was run. Include model and firmware with every result.

## 2. Trace one controlled call

Capture an idle baseline, then perform one sequence with clock times: entrance
button → phone rings → answer → speech in both directions → unlock → hang up.
Capture on your own monitor/router or inspect your own app's logs. Compare the
before and after state for each step. Wireshark or `tshark` can separate RTSP,
SIP, UDP media, HTTPS, and MQTT traffic; encrypted traffic may reveal timing
and endpoints without exposing command contents. For a local RTSP stream,
`ffprobe` can identify video/audio codecs and whether the feed is available
outside a call. If inspecting an APK/XAPK from your own installation, `jadx`
or `apktool` can locate the manifest, SDK entry points, and call/control
handlers. Treat APK code paths as hypotheses until a device test confirms
them.

Keep a timeline with event identifiers and timestamps, if present. Repeat the
trace after reconnect and restart. An event that returns unchanged after a
reconnect is cached state, not proof of a new call. Compare idle, active call,
answered call, and ended call states separately. Avoid repeated relay tests;
one deliberate test with the owner at the door establishes the physical target.

## 3. Find the implementation boundary

| Question | Current code |
|---|---|
| How are app requests signed and sent? | [`mobile_api.py`](../custom_components/neolight/mobile_api.py) |
| Where is the cloud device state read? | [`client.py`](../custom_components/neolight/client.py) |
| How are relay and channel DPs selected? | [`panel_protocol.py`](../custom_components/neolight/panel_protocol.py) |
| How is the current ring payload parsed? | [`ring_message.py`](../custom_components/neolight/ring_message.py), [`event.py`](../custom_components/neolight/event.py) |
| Where is the HA configuration UI? | [`config_flow.py`](../custom_components/neolight/config_flow.py) |
| How are P2P media and talk handled? | [`neolight_native.py`](../native_bridge/neolight_native.py), [`protocol.py`](../native_bridge/protocol.py), [`avmux.py`](../native_bridge/avmux.py) |
| Where is Apple Home connected? | [`plugin.ts`](../scrypted-neolight/src/plugin.ts) |

For the tested device, the runtime schema maps `accessory_lock` to Lock 1,
`ipc_c_lock` to Lock 2, and `ipc_c_switch_channel` to channel selection.
`PanelProfile.from_schema` checks their type and writability before use. The
numeric DP IDs are learned from the paired device; they are not universal.
The observed `alarm_message` DP carried `ipc_doorbell` during a fresh Vizit
call. Its snapshot filename contained a matching Unix timestamp. The parser
uses that time and the filename to reject stale and repeated alarms. A later
supervised one-time auto release physically opened the Vizit entrance. The
signal is still polled, so calls may be missed, and the complete call lifecycle
is not yet verified. Persistent auto unlock is off by default.

For another model, add a model or capability profile only after comparing its
live schema and behavior. Do not change the existing mapping globally based
on one other device. Separate monitor capabilities from entrance-panel wiring:
a monitor may support a relay while a particular adapter connects it to a
different physical target.

## 4. Prove a change

Add a small, sanitized fixture for any new message or schema shape. Tests
should cover missing/read-only DPs, stale or repeated call events, reconnects,
and one command per fresh call. Verify a fresh install and restart in HA.
Check video in HA and Apple Home, including two simultaneous viewers, then
test each audio direction independently. A cloud API success response proves
only that a command was accepted; record physical relay results separately.
Keep automatic unlock disabled for a model until fresh call detection,
expiration, deduplication, and the release window have been verified on that
installation.

Submit a [new-model report](../.github/ISSUE_TEMPLATE/new-model.yml) or PR with
the matrix, exact firmware, sanitized evidence, and the tests performed. Strip
account credentials, app signing material, tokens, device IDs, private IPs,
faces, voices, and full RTSP URLs from logs and captures. Prefer short,
purpose-built fixtures over uploading a raw capture or decompiled app.
