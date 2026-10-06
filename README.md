# NeoLight for Home Assistant

[![Open NeoLight in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=iZonex&repository=neolight-ha&category=integration)
[![Validation](https://github.com/iZonex/neolight-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/iZonex/neolight-ha/actions/workflows/validate.yml)
[![Latest release](https://img.shields.io/github/v/release/iZonex/neolight-ha?include_prereleases)](https://github.com/iZonex/neolight-ha/releases)

A Home Assistant integration for the NeoLight ALPHA Hybrid indoor monitor, with
an optional media bridge and Scrypted plugin for Apple Home. It provides a
door camera, a doorbell event, availability, and relay controls. The media
bridge carries live video and two-way audio.

> **Alpha:** tested with one ALPHA Hybrid and a Vizit analog adapter. Other
> monitors, firmware, and wiring need separate verification. Automatic unlock
> is disabled while fresh-call and physical release checks are completed.

## Install

**[Open NeoLight in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=iZonex&repository=neolight-ha&category=integration)**

1. Open the link above on a device that can access your Home Assistant. HACS
   must already be installed. If the repository is not added automatically,
   use **HACS → Custom repositories**, enter
   `https://github.com/iZonex/neolight-ha`, and select **Integration**.
2. Download the `main` branch in HACS, then restart Home Assistant. The
   published releases are alpha prereleases, which HACS may hide by default.
3. Open [Add NeoLight integration](https://my.home-assistant.io/redirect/config_flow_start/?domain=neolight)
   or use **Settings → Devices & services → Add integration → NeoLight**.
4. Enter the monitor and stream details. Read the [installation guide](docs/INSTALL.md)
   for a local camera, cloud controls, media services, and Apple Home.

HACS installs only the Home Assistant component. The native media bridge,
go2rtc, and Scrypted are separate services for live audio, talkback, and
Apple Home. See [HACS installation details](docs/HACS.md) or the
[manual installation path](docs/INSTALL.md).

## Features and current limits

| Feature | Current state |
|---|---|
| Door camera in Home Assistant | Available with a configured RTSP stream; live audio uses the optional media stack |
| Door release | Home Assistant Lock 1 physically opened the tested Vizit entrance during an active call |
| Apple Home doorbell | Live video and speech in both directions worked in the tested installation through Scrypted |
| Ring event | Experimental cloud event; the tested alarm contains a snapshot timestamp, but polling may miss a call |
| Automatic unlock | One-time supervised test available in options; persistent mode held until physical verification |
| Apple Home release | Paired, but the physical relay action has not yet been verified |
| Incoming-call answer/hangup in HA | Not implemented; Apple Home Live talk starts an on-demand media session |

The current media stack supports one configured monitor per Home Assistant
installation. A local-only camera can be configured without an app profile.
Cloud controls require a private profile from your own NeoLight app
installation. Private runtime settings are stored under `/config/neolight`.

## Project layout

| Path | Purpose |
|---|---|
| [`custom_components/neolight`](custom_components/neolight) | Home Assistant configuration and entities; installed by HACS |
| [`native_bridge`](native_bridge) | Tuya P2P session, panel audio, microphone return, RTSP mux |
| [`scrypted-neolight`](scrypted-neolight) | Apple Home doorbell video, snapshots, talkback |
| [`compose.yaml`](compose.yaml) | Optional media services on a Linux Docker host |

Read the [architecture and protocol notes](docs/ARCHITECTURE.md) for how the
parts connect. Contributors adding another monitor or entrance panel should
start with the [device research guide](docs/REVERSE_ENGINEERING.md) and
[contributing notes](CONTRIBUTING.md). See the [roadmap](docs/ROADMAP.md),
[security policy](SECURITY.md), and [releases](https://github.com/iZonex/neolight-ha/releases).

## Relay safety

Relay names are device data points, not descriptions of what they open.
Verify each physical target before use. Lock 2 is disabled by default in new
configurations. The door release entity sends a pulse request; it does not
measure the physical lock position.
