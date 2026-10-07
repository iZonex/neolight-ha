# NeoLight 0.3.0 alpha 4

This prerelease makes a local-first HACS installation usable without an app
profile. After entering the monitor address, choose **Local monitor and
camera**. A camera can use either the monitor stream UUID or a shared RTSP
URL. The NeoLight account can be linked later through **Configure**.

For installations with a linked account, local monitor and camera entities now
survive a cloud outage at HA startup. Cloud controls become unavailable until
the service responds. A private cache restores only the DP schema belonging
to the same paired monitor. The automatic release path requires a fresh,
timestamped call snapshot; an app call-status transition alone cannot open
the door. Correlated reports of one detected call share a single release
attempt.

The release also includes the existing shared video bridge and Apple Home
talkback work from this development branch. HACS installs the HA integration;
two-way audio and Apple Home still require the separate media and Scrypted
services described in the [installation guide](INSTALL.md).

## Verified

- Home Assistant unit tests, media tests, HACS validation, and hassfest.
- Local setup, RTSP URL-only camera creation, and cloud-control availability
  against the installed Home Assistant runtime without changing the live entry.
- On one ALPHA Hybrid / Vizit installation: Live video, speech in both
  directions, manual Lock 1 release, and one supervised automatic release.

## Known limits

- Cloud calls and door controls still require a private app profile from the
  owner's own NeoLight installation; the integration does not extract it.
- The cloud-polled ring signal can miss short calls. Incoming-call answer and
  hangup in HA and physical Apple Home release remain unverified.
- Video switching between the two analog sources inside `DOOR` is not yet
  supported. Other NeoLight models, firmware, and wiring are untested.
