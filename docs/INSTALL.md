# Installation

This alpha targets Home Assistant Container and Docker on the same Linux host.
Host networking is needed for the current RTSP, P2P audio, and HomeKit path.
Back up Home Assistant before installing.

## 1. Add the Home Assistant integration

Use [HACS custom repository installation](HACS.md), or copy
`custom_components/neolight` into the Home Assistant configuration directory's
`custom_components` folder, then restart Home Assistant. In
**Settings → Devices & services → Add integration**, select **NeoLight**.

Enter the monitor IP, the DOOR MainStream UUID, and its RTSP credentials. The
stream UUID is the identifier between `/` and `-MainStream` in a working
monitor RTSP URL. The next screen accepts an optional private app profile and
NeoLight account credentials. Leave the profile and account blank for a
local-only camera setup. For cloud control, use your own paired account and a
profile with this shape:

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
extract a profile automatically. Keep the profile private. The UI checks the
login and that the selected monitor belongs to the account. Runtime files are
written under `/config/neolight` with restricted permissions. Do not commit
that directory.

In the integration's **Configure** form, select which entities to expose.
Lock 2 is off by default because its physical destination has not been
verified. Configure the camera RTSP URL as
`rtsp://127.0.0.1:8556/neolight_door_with_audio` when the media stack below
is running on the same host and Home Assistant uses host networking. Set
**Preferred video channel** to the channel carrying the entrance camera if
the monitor returns to a blank or different input after a media reconnect.
`0` leaves the monitor's current selection alone. The tested ALPHA Hybrid
uses channel `1` for DOOR; confirm the mapping on other installations.

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
- The cloud doorbell event is polled and may miss a call. A missed call cannot
  trigger the one-time release.
- Incoming-call answer/hangup through HA is not implemented. Apple Home Live
  talk is an on-demand media session.
- Other NeoLight models, firmware, and analog adapters need their own testing.

For development details, see [architecture](ARCHITECTURE.md).
