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

The ring detector accepts only fresh timestamped snapshots. A later read-only
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

- Verify Apple Home release physically and expose clear command failures.
- Add answer and hangup in the HA interface, then test call audio lifecycle.
- Confirm the call identifier and protocol 308 answer/stop events on this
  monitor before enabling those controls. The writable `ipc_doorbell_fb` DP
  used by another Tuya doorbell path is absent from the tested ALPHA Hybrid.
- Generate the private app profile from an authorized APK/session without
  requiring manual protocol inspection.
- Confirm clean installation, restart, upgrade, and removal on another host.
- Test another ALPHA Hybrid firmware and at least one other panel wiring mode.
