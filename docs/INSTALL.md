# Installation

This alpha targets Home Assistant Container and Docker on the same Linux host.
Host networking is needed for the current RTSP, P2P audio, and HomeKit path.
Back up Home Assistant before installing.

## 1. Add the Home Assistant integration

Use [HACS custom repository installation](HACS.md), or copy
`custom_components/neolight` into the Home Assistant configuration directory's
`custom_components` folder, then restart Home Assistant. In
**Settings → Devices & services → Add integration**, select **NeoLight**.

Enter the monitor IP and, if known, the DOOR MainStream UUID and RTSP
credentials. The stream UUID is the identifier between `/` and `-MainStream`
in a working monitor RTSP URL. Choose **Local monitor and camera** to finish
without an app profile; an optional RTSP URL from a shared video bridge can be
entered on the next screen. At least one stream UUID or RTSP URL is required
for a camera entity. If neither is available yet, add the monitor now and set
the camera source later under **Configure → Advanced media**.

Choose **Link NeoLight account now** for cloud calls and door controls, or
select **Configure → Link NeoLight account** after local setup. This advanced
path requires a profile from your own paired app installation, with this shape:

```json
{
  "api_host": "regional-api.example.invalid",
  "signing_key": "private-key-from-your-own-app-session",
  "paired_device_id": "your-paired-monitor-id",
  "static_fields": {
    "appVersion": "app-version",
    "chKey": "channel-key",
    "clientId": "app-client-id",
    "deviceId": "installation-device-id",
    "lang": "en",
    "os": "Android",
    "ttid": "app-ttid"
  }
}
```

The profile values come from the NeoLight Android app and its signed API
requests; they are not the monitor's web password. This alpha does not yet
extract a profile inside HA. The [local profile helper](PROFILE_IMPORT.md)
builds and validates the JSON from your own Android app. Keep the profile private. The UI checks the
login and that the selected monitor belongs to the account. Runtime files are
written under `/config/neolight` with restricted permissions. Do not commit
that directory. The account path is optional; the local camera does not need
it.
For an existing manual setup with private files beside the integration code,
follow the [migration steps](HACS.md) before HACS replaces that directory.

If the NeoLight cloud is unavailable during a later HA restart, the LAN
monitor and configured RTSP camera still load. Cloud door and video-input
controls show unavailable until the account and device respond again. HA keeps
the last schema in private storage for the same paired monitor so these
entities can return without being recreated.

In the integration's **Configure** menu, use **Entrances and video** to choose
the camera and relay entities, **Calls** for the doorbell event,
**Automatic opening** for the relay rule and one-time test,
**Apple Home** for its ring webhook, and **NeoLight account** to update the
login. Manual RTSP details are under **Advanced media**. Saving one page
preserves the other pages' settings. Lock 2 is off by default because its
physical destination has not been verified. Configure the camera RTSP URL as
`rtsp://127.0.0.1:8556/neolight_door_with_audio` when the media stack below
is running on the same host and Home Assistant uses host networking. Set
**Preferred video channel** to the channel carrying the entrance camera if
the monitor returns to a blank or different input after a media reconnect.
`0` leaves the monitor's current selection alone. The tested ALPHA Hybrid
uses channel `1` for DOOR; confirm the mapping on other installations.
When the shared video bridge stays on its backup picture for a minute, HA
reselects a configured preferred channel to restore the monitor's RTSP video.
It does not run while the native bridge reports ringing or talking, and it
limits retries to once per five minutes. Setting the preferred channel to `0`
disables this recovery action.
The **Video input** entity lets you select any input exposed by the monitor.
**Call video channel** refers to the monitor's channel list (`DOOR`, `CAM2`,
etc.). On the tested installation, the entrance camera and Vizit video are
two analog sources within `DOOR`; `CAM2` is a different monitor channel and
does not select the second DOOR source. Keep both idle and call channel set to
`DOOR` until the inner source selection is verified. A fresh ring selects the
configured monitor channel; after the timeout, HA restores the channel that
was active before the ring. The default is off because wiring varies.

## 2. Start the media stack

On the Docker host, clone this repository. Copy `.env.compose.example` to
`.env` and set `NEOLIGHT_HA_CONFIG` to the absolute host path of Home
Assistant's config directory. The integration must already have written
`NEOLIGHT_HA_CONFIG/neolight/vendor_config.json`. The native bridge signs in
with a separate installation identity, so HA and media do not share a SID.

```sh
docker compose up -d --build go2rtc native avmux
docker compose ps
```

The go2rtc API and RTSP ports in `go2rtc.yaml` bind to loopback. The media
bridge holds one P2P session, publishes the monitor's audio, and combines it
with the local RTSP video. If RTSP drops, the mux can temporarily use its
lower frame rate P2P video.

For video diagnostics in HA, open **NeoLight → Configure → Advanced media** and
set **Video bridge health URL** to `http://127.0.0.1:38558/health` when HA and
the mux share host networking. The **Video bridge** diagnostic sensor reports
whether output video bytes are advancing, their age, and whether the mux is
using the monitor RTSP source or the native backup. It does not judge image
content. **App call signal** reports the cloud API's call flag; it does not
measure whether the analog handset is physically on-hook.

Set **Native bridge call control port** to `38557` in **Configure → Advanced media**
when the native media bridge runs on the same host network. HA then shows a
**Native call** diagnostic and enables **Answer call** and **Hang up call** only
when the bridge has received a fresh, controllable MQTT call. **End call**
remains a separate recovery control for a stuck analog handset. These controls
do not provide a microphone in the HA dashboard yet; use Apple Home Live for
two-way speech. The call buttons require a real call test on each panel model
before relying on them.

## 3. Optional Apple Home doorbell

Start an existing Scrypted installation or run the optional Compose service
after setting `NEOLIGHT_SCRYPTED_VOLUME`:

```sh
docker compose --profile homekit up -d scrypted
cd scrypted-neolight
npm ci
npm run build
```

Upload `scrypted-neolight/out/plugin.zip` to Scrypted as a local plugin. Set
its video URL to `rtsp://127.0.0.1:8556/neolight_door_with_audio`. In the HA
integration options, set **HomeKit ring webhook URL** to
`http://127.0.0.1:38765/ring` when Scrypted and HA share the host network.
Add the resulting Scrypted doorbell to its HomeKit plugin, then pair it in
Apple Home. The HA **Door release** lock can be shared separately through
HomeKit Bridge; its physical action from Apple Home remains unverified.

## Known limits

- Automatic unlock is off by default. Before enabling the **Auto unlock on
  ring** switch, use **Unlock once on the next ring** in the integration options
  for a supervised physical test. It arms a single Lock 1 release for fifteen
  minutes, accepts only a new timestamped call seen within ten seconds of its
  snapshot, and disarms after the attempt or expiry. Check the HA log and the
  physical door before enabling the persistent switch.
- The integration triggers a ring only from a fresh timestamped snapshot alarm.
  It also reports the APK's `callStatus` for diagnostics, but that flag may stay
  active for hours and cannot establish a new entrance call. Very short calls
  can still end between polls; a missed call cannot trigger automatic release.
- The Doorbell event's `last_auto_unlock_status` attribute reports the last
  attempt. `command_acknowledged` means the API accepted a relay command; it
  does not prove the physical door opened. The attributes clear after an HA
  restart.
- Apple Home Talk sends a Tuya call `accept` for a recent, supported video
  call and `stop` when Talk ends. The live ALPHA Hybrid / Vizit call type and
  physical answer/hangup behavior still require a call test. An ordinary
  `doorbell` call type is unsupported by this Tuya command. Live viewing by
  itself does not answer the call.
- Other NeoLight models, firmware, and analog adapters need their own testing.

For development details, see [architecture](ARCHITECTURE.md).
