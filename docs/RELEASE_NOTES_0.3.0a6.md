# NeoLight 0.3.0 alpha 6

This update preserves older manual installations when moving to HACS.
The integration now stores its private app profile, session, and video-route
state in `/config/neolight`, outside the HACS-managed component directory.
On startup it copies any legacy files that are still present without replacing
newer private files. Existing media containers must also mount the new
directory as `/state` before the legacy files are removed. Follow the
[migration steps](HACS.md) before HACS replaces an older manual installation.

Alpha 5's snapshot-only ringing fix and alpha 4's local-first setup are
included. This remains an alpha for one tested ALPHA Hybrid / Vizit
installation. Cloud calls require an owner-supplied app profile; the polled
ring signal can miss short calls, and HA incoming-call answer, physical Apple
Home release, and inner `DOOR` video switching need further verification.
