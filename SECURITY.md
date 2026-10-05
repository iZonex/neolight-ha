# Security

Keep the Home Assistant configuration directory, `/config/neolight`, and
Scrypted's data volume private. They contain account sessions and may contain
device keys. Do not expose the go2rtc RTSP/API ports or the native talk socket
outside the trusted host and network. Use a dedicated NeoLight account when
your installation supports it.

Automatic unlocking is deliberately disabled because the observed cloud ring
signal can replay a cached value. Do not wire the current `Doorbell` event to
an unlocking automation. Relay commands should be tested with someone at the
door, and Lock 2 should remain disabled until its physical target is known.

To report a security issue, open a private GitHub security advisory for this
repository. Do not attach unredacted captures or credentials to a public
issue.
