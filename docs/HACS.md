# Install through HACS

This repository is an **alpha custom repository**, not a default HACS catalog
entry. HACS installs only `custom_components/neolight`. The native media bridge,
go2rtc, and optional Scrypted plugin are separate services; install them from
the [full installation guide](INSTALL.md) when you need live audio, talkback,
or Apple Home.

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

Existing manual installations should back up the HA configuration first. HACS
manages the integration directory after installation. Do not place private
runtime profiles or credentials under `custom_components/neolight`; the
integration writes runtime files under `/config/neolight`.

The bundled icon and logo are shown by Home Assistant 2026.3 and later.
Older Home Assistant versions may show the default integration image. Other
versions have not been tested for compatibility.

After installation, HACS creates a repository switch that controls whether
its update entity considers prereleases. Enable that disabled-by-default
switch in Home Assistant if you want HACS to track alpha release updates.

For HACS custom repository steps, see the [official HACS instructions](https://www.hacs.dev/docs/faq/custom_repositories/).
