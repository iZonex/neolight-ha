# NeoLight 0.3.0 alpha 10

After a Vizit call, the tested monitor can accept RTSP connections yet send no
video frames. Reselecting its current `DOOR` channel restored video in the
owner's installation. Home Assistant now does that automatically if the
shared video bridge remains on its P2P backup source for one minute and a
preferred video channel is configured. It pauses while the native bridge
reports ringing or talking and limits recovery commands to one every five minutes. A preferred
channel of `0` keeps this feature off.

The automatic recovery path needs confirmation on the next ordinary call.
