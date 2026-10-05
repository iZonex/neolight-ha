# NeoLight for Home Assistant

An experimental Home Assistant integration and optional media bridge for the
NeoLight ALPHA Hybrid indoor monitor. It exposes a door camera, a doorbell
event, availability, and relay controls. A Scrypted plugin connects live
video and two-way audio to Apple Home.

## Status

This is an **alpha release for technically experienced owners**. It was
developed against one ALPHA Hybrid with a Vizit analog adapter. Home Assistant
Lock 1 physically opened that entrance during an active call, and Apple Home
live video and speech worked in both directions. These observations do not
establish compatibility with other firmware, wiring, relays, or panel models.
The current media stack supports one configured monitor per HA installation.

Incoming Vizit call detection is still under investigation. The current cloud
alarm can replay an old ring after reconnecting, so **automatic opening is
blocked in code**. The Home Assistant auto-unlock switch remains unavailable.
Apple Home door release has paired, but its physical relay action is not yet
verified.

## Components

| Component | Purpose |
|---|---|
| `custom_components/neolight` | Home Assistant configuration and entities |
| `native_bridge` | Tuya P2P session, panel audio, microphone return, RTSP mux |
| `scrypted-neolight` | Apple Home doorbell video, snapshots, talkback |
| `compose.yaml` | Optional media services on a Linux Docker host |

The native bridge and local monitor RTSP path are the current media route.

## Install

Install the Home Assistant component through [HACS as a custom repository](docs/HACS.md)
or [manually](docs/INSTALL.md). Read the full installation guide before starting
the media containers. New installations use the Home Assistant UI and store private
runtime settings under `/config/neolight`; no account credentials belong in
this repository. A local-only camera can be configured without an app profile.
Cloud controls require a private app profile obtained from your own NeoLight
app installation.

For the observed protocol and known limits, see [architecture](docs/ARCHITECTURE.md).
For development and publication policy, see [contributing](CONTRIBUTING.md)
and [security](SECURITY.md). Outstanding release work is tracked in the
[roadmap](docs/ROADMAP.md). Contributors supporting another monitor or entrance
panel should follow the [reverse-engineering guide](docs/REVERSE_ENGINEERING.md).

## Safety

Relay names are device data points, not descriptions of what a relay opens.
Verify the physical target of every relay before using it. Lock 2 is disabled
by default in new configurations. The door release entity represents a pulse
request; it does not measure the physical lock position.
