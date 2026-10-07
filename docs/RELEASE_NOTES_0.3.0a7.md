# NeoLight 0.3.0 alpha 7

The native media bridge now tracks fresh MQTT calls and exposes a private
loopback call status. Home Assistant shows a **Native call** diagnostic and
context-sensitive **Answer call** / **Hang up call** buttons when the native
bridge is configured. Remote call cancellation, event age, and replayed call
IDs are handled without exporting identifiers or credentials to HA.
The AV mux now retries the monitor RTSP source after a publisher disappears
and leaves a failed backup source, avoiding a prolonged video outage after a
native bridge restart.

The owner's installation has been updated and its idle state, entity setup,
and live video have been checked. A controlled native bridge restart also
recovered the primary live stream without restarting the mux. A physical incoming call is still needed to
verify the new answer/hangup controls on the Vizit adapter. HA microphone talk,
Apple Home release, and inner `DOOR` source switching remain under development.
