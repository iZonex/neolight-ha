# Native media bridge

`neolight_native.py` maintains one encrypted Tuya P2P session using
`tuya-ipc-p2p-sdk==0.1.1`. It publishes panel audio as PCMA/8000, keeps a
low-frame-rate P2P video fallback, and accepts PCMU/8000 microphone frames on
loopback port 38556. `avmux.py` combines the monitor's local RTSP video with
that audio and publishes `neolight_door_with_audio` through go2rtc.

Use the root [installation guide](../docs/INSTALL.md) and `compose.yaml` for
a new installation. Both containers read private runtime settings exported by
the HA integration to `/config/neolight`. The native bridge needs
`vendor_config.json` and `runtime_session.json`; the mux also needs the RTSP
fields in `vendor_config.json`. Neither file belongs in Git.

The publish URLs, talk port, go2rtc API URL, mux output stream, and runtime
path can be changed with the `NEOLIGHT_*` environment variables in the two
Python modules. Keep the talk socket and go2rtc API on loopback.

Observed behavior: the first Talk in a new P2P session used control type 6;
outgoing G.711 packets used media type 6. Two-way speech was physically
confirmed on one ALPHA Hybrid. Answering an incoming call and hanging it up
from HA remain separate work.
