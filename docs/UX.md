# NeoLight user experience and configuration design

This is the target interaction model for the Home Assistant integration and
its optional Apple Home bridge. It describes intended behavior; items marked
**planned** are not claims about the current alpha.

## Product rule

The owner configures one **NeoLight intercom** in Home Assistant. Home Assistant
owns credentials, source mapping, automation, and diagnostics. Apple Home is a
daily-use view of the same doorbell, video, microphone, and entrance release.
There must be one documented media source for both clients, so opening two
views never opens two sessions to the monitor.

Every control should answer one user question. A number such as `DP231`,
`38557`, or `CAM2` is a diagnostic detail, not a normal setting label. The UI
must distinguish a verified ability from a configured but untested one.

## First run in Home Assistant

| Step | Owner sees | Integration verifies |
| --- | --- | --- |
| 1. Find monitor | Discovered monitors, or a field for its LAN address | Monitor identity and local reachability |
| 2. Link NeoLight | Region, account email, password; **Local camera only** remains available | Login, paired device, session, supported controls; **planned:** derive the app profile automatically rather than ask for JSON |
| 3. Map entrances | Cards with a live still: **Entrance camera** and **Intercom video**; choose the source for idle and for a call | Available sources, preview age, ability to switch and restore without leaving the handset up |
| 4. Verify door | One named **Entrance door** control, optionally a second named relay; explicit one-time physical test | Online state, relay command acknowledgement; owner confirms what physically opened |
| 5. Media and Apple Home | Simple statuses: video, panel audio, microphone return, Apple Home bridge | RTSP feed, local bridge, audio path, Scrypted bridge; show only the steps still needed |
| 6. Finish | Summary of working, untested, and unavailable functions | Save configuration and create entities only for supported functions |

The wizard saves after the monitor and account are validated. An optional
bridge failure cannot discard a working camera or relay setup. A returning
owner resumes at the failed step. Credentials remain masked. The current
`app_profile` JSON, stream UUID, RTSP URL, host networking, local ports, and
webhook URL belong in an **Advanced / manual setup** path until discovery and
bridge provisioning are implemented.

## Device page in Home Assistant

```text
NeoLight intercom · Entrance
Live preview                 [Open entrance]
Call: Idle / Ringing / Talking / Ending / Needs attention
Audio: Ready                 [Answer] [End call]
Automatic opening: Off/On   [Test once]

Settings: Entrances · Calls · Automatic opening · Apple Home · Advanced
Diagnostics: Monitor · Cloud · Video · Audio · Ring signal · Last call
```

**Open entrance** is a momentary action. It must never imply that the lock's
physical state was measured. **Answer** appears only when a current call can
be identified and the protocol is verified for that call type. **End call**
remains available as a recovery action when the monitor is stuck off-hook.
The normal device page hides raw relay buttons and per-channel Ring sensors;
those stay as diagnostic entities for automation and troubleshooting. The
owner can rename the entrance and both physical video sources. No unsupported
control is shown as if it worked.

## Call and video behavior

| State | HA and Apple Home behavior |
| --- | --- |
| Idle | Show the chosen entrance preview and current health. Viewing Live does not claim that a call was answered. |
| Ringing | Correlate one fresh event with one call ID, switch to its mapped video source, ring once, and show the answer/release actions. |
| Talking | Route panel audio and microphone return through the shared bridge. Show that the handset is up. |
| Released | Record one release request and its acknowledgement. If automatic opening is enabled, end the conversation after the configured delay. |
| Ended | Send the matching stop command, restore the idle source, clear the call UI, and confirm the monitor returned to idle. |
| Needs attention | Show which path failed and an actionable recovery such as **End call**, **Reconnect video**, or **Sign in again**. |

End-of-call confirmation should drive source restoration. The current fixed
video hold timeout remains a fallback if the end event is missing. A call
trigger is accepted only when fresh and linked to the configured entrance;
duplicates, reconnect replays, and stale snapshots cannot ring Apple Home or
open the door again. An uncertain signal is shown as uncertain, never as a
successful release.

## Configuration pages

1. **Entrances:** names, source preview, idle video, call video, relay target.
   A source change includes a reversible preview and explicit save.
2. **Calls:** panel audio, microphone return, answer behavior, hangup timeout,
   and whether on-demand talk is allowed without a ring. Show capability and
   verification status for each item.
3. **Automatic opening:** off by default; one-time supervised test; chosen
   entrance, delay, permitted call source, and automatic hangup. Show last
   attempt as *detected → command sent → acknowledged → physically confirmed
   by owner*. Keep a one-command-per-call guard.
4. **Apple Home:** bridge state, pairing instructions, preview age, ring
   delivery, microphone test, and the entrance release accessory. Place the
   doorbell and lock in the same Apple Home room; do not imply they form one
   native tile if the bridge exposes them separately.
5. **Advanced:** account region, manual app profile, RTSP details, bridge
   addresses and ports, raw channel mapping, and privacy-safe diagnostics.

The Apple Home UI is for live viewing, talk, ringing, and release. All setup
and troubleshooting stays in HA. The bridge reports **No Response** only when
its stream is actually unavailable; a stale snapshot and an unverified call
signal get separate diagnostic states in HA.

## Failure messages and recovery

| Problem | Message and next action |
| --- | --- |
| Monitor unavailable | “Monitor is offline at this LAN address.” Offer address check and retry. |
| Account expired | “NeoLight sign-in expired.” Open a reauthentication flow. |
| Live preview stale | “Last frame was N seconds ago.” Offer stream reconnect; do not show the frame as live. |
| Call not detected | “The monitor rang, but no fresh app signal reached HA.” Keep automatic opening idle and record the time. |
| Release command rejected | “Door release was not acknowledged.” Keep the physical state unknown and offer retry. |
| Handset still up | “Call did not end on the monitor.” Offer **End call** and show whether the reset command was acknowledged. |

Diagnostics export must redact passwords, signed URLs, account IDs, device
IDs, tokens, audio, and snapshots. It can include component versions,
timestamps, signal age, state transitions, and error categories.

## Implementation order and acceptance

1. **Clean up the existing HA form:** split account, video, calls, opening,
   Apple Home, and advanced controls; preserve existing config entries and
   options. Add missing translations and never reset a saved option merely
   because its page was opened.
2. **Expose truthful device status:** call state, current video source,
   preview age, bridge health, and last opening attempt. Keep low-level DPs
   under diagnostics.
3. **Complete call lifecycle:** correlate ring/start/end across app signals,
   answer only supported calls, stop the matching call, recover a stale
   handset, and restore the idle video source.
4. **Guided setup:** discover/validate monitor and stream where possible;
   remove the JSON-profile requirement from the normal path; test each
   capability without actuating the door until the owner chooses a one-time
   test.
5. **Apple Home setup:** one shared video feed, current snapshots, call
   notifications, working talkback, and a named release control. Verify two
   simultaneous viewers and recovery after bridge/HA restarts.

Done means a new owner can install from HACS, connect an authorized monitor,
identify two video sources, see a current preview in HA and Apple Home, answer
and finish a call, open the intended door, and configure a tested automatic
opening rule without editing JSON or container files. Unsupported hardware
must be identified during setup and shown with a clear limited-function path.
