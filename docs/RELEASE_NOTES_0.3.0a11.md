# NeoLight 0.3.0 alpha 11

A real Vizit call confirmed that the tested monitor sends a protocol 43
`ac_doorbell` notification. After automatic opening, the native bridge's
Talk → Stop recovery succeeded but the transient call status incorrectly
remained `ringing` for up to a minute. It now clears that call when the local
reset sequence completes, so Home Assistant does not keep offering Answer
after a successful local reset.

Physical Answer and Hang up actions still need confirmation during a live
call. The automatic RTSP recovery introduced in alpha 10 also awaits its
next live-call test.
