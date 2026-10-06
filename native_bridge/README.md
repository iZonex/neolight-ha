# Native media bridge

`neolight_native.py` maintains one encrypted Tuya P2P session using
`tuya-ipc-p2p-sdk==0.1.1`. It publishes panel audio as PCMA/8000, keeps a
low-frame-rate P2P video fallback, and accepts PCMU/8000 microphone frames on
loopback port 38556. `avmux.py` combines the monitor's local RTSP video with
that audio and publishes `neolight_door_with_audio` through go2rtc.

Use the root [installation guide](../docs/INSTALL.md) and `compose.yaml` for
a new installation. Both containers read private runtime settings exported by
the HA integration to `/config/neolight`. The native bridge needs
`vendor_config.json`; the mux also needs the RTSP fields in that file. The
bridge signs in with its own stable client identity, so HA session refreshes
do not invalidate its media session. If `preferred_video_channel` is set to
a nonzero channel in HA, the native bridge selects it when connecting, using
the paired device's writable channel DP. The config file does not belong in Git.
While HA has an active call route, the bridge uses its temporary channel on
reconnection and leaves the idle preference untouched. HA restores the input
selected before the call after the configured timeout.

The publish URLs, talk port, go2rtc API URL, mux output stream, and runtime
path can be changed with the `NEOLIGHT_*` environment variables in the two
Python modules. Keep the talk socket and go2rtc API on loopback.

Observed behavior: the first Talk in a new P2P session used control type 6;
outgoing G.711 packets used media type 6. Two-way speech was physically
confirmed on one ALPHA Hybrid. The bridge now captures fresh MQTT protocol 43
calls addressed to the paired device. For a call type supported by the APK's
video-call manager, Apple Home Talk sends protocol 308 `accept` and Talk end
sends `stop`. These call controls are not yet physically confirmed on Vizit.

`observe_call_signaling.py` is a read-only diagnostic for the next ordinary
call. Mount the HA integration's private config directory at `/state` and run
it in a separate short-lived container using the native bridge image. It reuses
HA's saved session without logging in, subscribes with a distinct MQTT client
ID, and prints only protocol numbers, call event labels, and hashed call IDs.
The tested ALPHA Hybrid does not advertise the SDK's writable
`ipc_doorbell_fb` DP, so its `answered` / `refused` commands must not be used
for this model. The APK's video call manager instead uses MQTT protocol 308.
The bridge takes the live message ID from protocol 43 and issues 308 only when
the user starts Talk during that call. It skips the SDK's unsupported
`doorbell` call type. Applicability to this analog adapter needs a call test.
The HA integration also exposes read-only `Doorbell 1–4 ringing` diagnostic
entities when the live schema advertises a Ring/Normal enum for those inputs.
The HA ring entity additionally polls the APK's
`m.ipc.doorbell.call.status.get` endpoint and treats a transition into
`callStatus=0` as a fresh call when the snapshot alarm is absent.
