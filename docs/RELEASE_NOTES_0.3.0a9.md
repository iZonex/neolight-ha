# NeoLight 0.3.0 alpha 9

The Home Assistant Doorbell event now shows the last automatic release
attempt. Its status distinguishes a scheduled command, an expired ring,
an unavailable relay, a failed command, and an API acknowledgement. An
acknowledgement does not prove that the physical entrance opened. The status
survives a configuration reload and clears on a full Home Assistant restart.

The installation guide now points to the correct Advanced media page for
the native call control port, and the README accurately describes the
experimental answer and hangup controls. Physical answer/hangup on the
tested Vizit adapter still needs one ordinary call test.
