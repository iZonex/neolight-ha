# NeoLight 0.3.0 alpha 8

An optional local profile helper now builds the NeoLight app profile for HA
from files extracted from your own Android installation. It verifies the
captured app request signature, supports choosing one of several paired
devices, and writes the profile with owner-only permissions. The helper never
contacts the vendor API or prints keys. See the [profile import guide](PROFILE_IMPORT.md).

The builder was validated against a private NeoLight 1.1.0 capture. The new
Frida collection helpers still need a fresh installation test. The local
monitor/camera path remains available without a profile. Alpha 7's live call
controls still need physical answer/hangup verification on the Vizit adapter.
