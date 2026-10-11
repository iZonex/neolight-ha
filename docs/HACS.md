# Install through HACS

This repository is an **alpha custom repository**, not a default HACS catalog
entry. HACS installs only `custom_components/neolight`. The native media bridge,
go2rtc, and optional Scrypted plugin are separate services; install them from
the [full installation guide](INSTALL.md) when you need live audio, talkback,
or Apple Home.

## What one HACS install provides

The HACS package alone can discover the local monitor, create the HA device,
show a camera when a working RTSP stream UUID or URL is supplied, and expose
local availability. Linking a NeoLight app profile in **Configure** adds the
cloud backed ring, relay, motion, and device controls. No Docker service is
required for those controls. The app profile still needs to be generated from
the owner's installation using the [profile helper](PROFILE_IMPORT.md).

The tested full media path currently uses separate native, go2rtc, and AV mux
services. They share one P2P session, provide audio and talkback, and keep
multiple viewers from opening competing streams on the monitor. Scrypted
publishes the two-way doorbell to Apple Home. HACS only installs files inside
`custom_components`; it cannot deploy those services into Docker or Scrypted.

Our target is to make the HA integration run the native session and media
relay itself, so a HACS install plus HA configuration can provide the full HA
feature set. That migration must preserve one device session, bounded media
processes, call cleanup after answer/unlock, and recovery after HA restart.
Apple Home two-way talk also needs a HomeKit path that can carry the return
microphone; until that is implemented and verified, Scrypted remains an
optional companion rather than something HACS can silently install.

Each change is checked by HACS validation, hassfest, and a clean HA Container
boot that copies **only** the HACS integration directory. This boot check does
not prove account login, panel audio, or Apple Home behavior on another model.

[Open NeoLight directly in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=iZonex&repository=neolight-ha&category=integration).
This My Home Assistant link opens the repository in your own instance; HACS
must already be installed. It does not install the integration automatically.

1. Install and configure HACS in Home Assistant.
2. In HACS, open the top-right menu → **Custom repositories**.
3. Enter `https://github.com/iZonex/neolight-ha` and choose **Integration**.
4. Add the repository, open **NeoLight ALPHA Hybrid**, and download the
   default branch (`main`). The published releases are prereleases and HACS
   may hide them until prereleases are enabled for this repository.
5. Restart Home Assistant, then open **Settings → Devices & services → Add
   integration → NeoLight**. Start with **Local monitor and camera**; the app
   profile is needed only for cloud calls and door controls, and can be linked
   later. Follow [installation](INSTALL.md) for the camera source and optional
   media stack.

Existing manual installations should back up the HA configuration first. If
`/config/custom_components/neolight/vendor_config.json` exists, copy it and
any `runtime_session.json` or `video_route.json` into `/config/neolight`
**before HACS replaces the integration folder**. From a shell inside the HA
container:

```sh
mkdir -p /config/neolight && chmod 700 /config/neolight
for name in vendor_config.json runtime_session.json video_route.json; do
  source="/config/custom_components/neolight/$name"
  target="/config/neolight/$name"
  if [ -f "$source" ] && [ ! -e "$target" ]; then
    cp "$source" "$target" && chmod 600 "$target"
  fi
done
```

Do not delete the old files until the upgraded integration and media bridge
have been verified. The integration also copies legacy files automatically
when it starts before HACS removes them. HACS manages the integration folder;
new runtime settings live under `/config/neolight`. Older manually created
media containers may still mount the legacy folder as `/state`; change that
mount to `/config/neolight` on the HA host before removing old files.

The bundled icon and logo are shown by Home Assistant 2026.3 and later.
Older Home Assistant versions may show the default integration image. Other
versions have not been tested for compatibility.

After installation, HACS creates a repository switch that controls whether
its update entity considers prereleases. Enable that disabled-by-default
switch in Home Assistant if you want HACS to track alpha release updates.

For HACS custom repository steps, see the [official HACS instructions](https://www.hacs.dev/docs/faq/custom_repositories/).
