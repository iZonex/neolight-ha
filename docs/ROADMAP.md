# Release roadmap

## Verified in one installation

- Home Assistant Lock 1 opened the Vizit-connected entrance during a call.
- Apple Home Live showed the entrance and carried speech both ways.
- The local RTSP mux delivered H.264 video and PCMA audio to two clients.

## Automatic unlock validation

1. Capture the Vizit call end and answer signals. One fresh start was captured
   in MQTT and in cloud `alarm_message` with a matching snapshot timestamp.
2. Verify that the timestamped snapshot path stays unique across several
   calls, reconnects, and HA restarts.
3. Test one command per fresh call and expiry; check reconnect and restart
   behavior with the time-bounded one-time release.
4. Physically verify the final auto-release once with the owner present.

Step 4 succeeded on 2026-10-06: a single fresh Vizit ring led to one Lock 1
command acknowledged by the account API, and the owner confirmed that the
entrance opened. Persistent mode is available but off by default; missed rings
and other wiring modes still need testing.

The cloud ring detector accepts only fresh timestamped snapshots. A later read-only
check showed the app `callStatus=0` persisting for hours, so it cannot establish
a new entrance call or suppress a fresh snapshot. The duplicate window is
covered by offline tests.
A real multi-call trace is still needed to establish the shortest safe interval
between separate calls and to measure missed calls.
The HA ring event now records its signal source and an anonymized alarm hash;
the read-only MQTT observer records the matching hash when the cloud publishes
DP 185. These fields let a later ordinary call establish ordering without
opening the door or collecting video/audio.

On 2026-10-07 one ordinary Vizit call produced an MQTT protocol 43
`ac_doorbell` notification and a fresh DP 185 snapshot. HA sent one Lock 1
command, the account API acknowledged it, and the owner confirmed the entrance
opened. The native bridge then completed its tested Talk → Stop recovery. No
protocol 308 end event appeared in that call trace, so the bridge expires an
unanswered notification rather than assuming that an end event will arrive.

## Before a stable release

- Move the native P2P session and media relay into the HACS-installed HA
  integration, with a single session owner and lifecycle cleanup. Reuse HA's
  managed go2rtc where available on HA OS and Container. Keep the current
  Compose bridge as a tested compatibility path until live video, audio,
  talkback, concurrent viewing, and restart recovery pass on HA alone.
- Remove the manual app-profile extraction step from normal setup by deriving
  the required app identity from an authorized installation during the HA
  configuration flow. Keep secrets out of releases and diagnostics.
- Add a NeoLight-owned HomeKit accessory with verified iPhone microphone
  return, pairing, live video, rings, release, and reconnect behavior. The
  built-in HA HomeKit Bridge is an interim path for camera, panel audio, ring,
  and lock, but its camera path does not return the iPhone microphone. Keep
  Scrypted as the tested two-way path until the replacement passes live tests.
- Verify Apple Home release physically and expose clear command failures.
- Test HA answer and hangup controls during a real Vizit call; the controls
  already use the observed native call identifier and protocol 308 commands.
- Physically verify the HA browser microphone card during a real call,
  including close/timeout recovery and Apple Home contention.
- Verify native auto-release with app push disabled during a supervised Vizit
  call. A fresh `ac_doorbell` P2P call now permits one release without a cloud
  snapshot; cloud snapshot polling remains the fallback when the bridge is absent.
- Identify visitor snapshot retrieval and archive APIs before exposing history.
  The tested schema exposes timestamped motion image notifications; HA now
  emits a motion event from fresh notifications. Motion switching and raw SD
  status are also available. Polling may miss short-lived notifications.
- Verify inner DOOR analog-input switching and SD/HD stream selection before
  adding source controls; monitor channel DOOR/CAM selection is separate.
- Generate the private app profile from an authorized APK/session without
  requiring manual protocol inspection.
- Confirm clean installation, restart, upgrade, and removal on another host.
- Test another ALPHA Hybrid firmware and at least one other panel wiring mode.
