# NeoLight 0.3.0 alpha 5

Hotfix for ring detection in alpha 4. On the tested monitor, the app's
`callStatus=0` can persist for hours. It no longer creates an Apple Home ring
or prevents a fresh, timestamped snapshot from triggering one. Automatic
opening continues to require a fresh snapshot and stays off by default for
new installations.

The local-first setup, RTSP URL-only camera, cloud outage behavior, media
bridge, and installation instructions from alpha 4 are included. HACS installs
the HA integration; two-way audio and Apple Home still require the separate
media and Scrypted services in the [installation guide](INSTALL.md).

The snapshot alarm is cloud-polled and can still miss short calls. A second
call within 20 seconds may be merged with the first. Incoming-call answer and
hangup in HA, physical Apple Home release, and switching two analog video
sources inside `DOOR` remain unverified.
