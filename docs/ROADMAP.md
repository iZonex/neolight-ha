# Release roadmap

## Verified in one installation

- Home Assistant Lock 1 opened the Vizit-connected entrance during a call.
- Apple Home Live showed the entrance and carried speech both ways.
- The local RTSP mux delivered H.264 video and PCMA audio to two clients.

## Before enabling automatic unlock

1. Capture the Vizit call start and end signal independently of the stale
   cloud `alarm_message` value.
2. Confirm a unique call identifier or another signal with equivalent replay
   protection.
3. Test one command per fresh call, expiry, reconnect, and restart behavior.
4. Physically verify the final auto-release once with the owner present.

## Before a stable release

- Verify Apple Home release physically and expose clear command failures.
- Add answer and hangup in the HA interface, then test call audio lifecycle.
- Generate the private app profile from an authorized APK/session without
  requiring manual protocol inspection.
- Confirm clean installation, restart, upgrade, and removal on another host.
- Test another ALPHA Hybrid firmware and at least one other panel wiring mode.
