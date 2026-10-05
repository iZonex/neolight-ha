# NeoLight Apple Home doorbell adapter

This Scrypted plugin exposes one Doorbell with live video, cached snapshots,
ring events, and a microphone return path. Home Assistant sends each detected
ring to `http://127.0.0.1:38765/ring`. Both containers use host networking.

The video URL defaults to `rtsp://127.0.0.1:8556/neolight_door_with_audio`.
That go2rtc stream contains H.264 video transcoded from the monitor's local RTSP
MainStream and PCMA audio
from the separate native P2P session. The native bridge accepts PCMU
microphone frames on loopback TCP port 38556 and forwards them to the monitor
using the same control and audio packet format observed in the Android app.
Scrypted's `startIntercom` encodes the HomeKit microphone input to PCMU/8000
and sends it to that port; `stopIntercom` ends the P2P talk session.

The owner confirmed speech in both directions through Apple Home Live. The
incoming-call answer/hangup flow still needs verification. The plugin does not
yet expose door release;
the Home Assistant integration owns that control.

One video reader stays open and extracts a JPEG each second. Snapshot
requests receive the cached image without starting another camera session.
The reader restarts if frames stop. Set Scrypted Core's **Scrypted Server
Addresses** to the HA host LAN IPv4 address so HomeKit RTP sockets bind to
the correct interface.

Install Scrypted and its HomeKit plugin, then build with `npm ci`, `npm run
check`, and `npm run build`. Deploy the plugin zip through Scrypted, enable
the HomeKit mixin on `NeoLight Door`, and pair it as a standalone accessory.
The plugin settings expose the video URL, native talk port, and ring webhook
port. `deploy_local.py` is a private development helper and is not part of
the published source.
