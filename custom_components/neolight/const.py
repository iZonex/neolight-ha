"""Constants for the NeoLight integration."""

from datetime import timedelta

DOMAIN = "neolight"
PLATFORMS = ("binary_sensor", "camera", "button", "event", "lock", "switch")
CONF_STREAM_ID = "stream_id"
CONF_RTSP_USER = "rtsp_user"
CONF_RTSP_PASSWORD = "rtsp_password"
POLL_INTERVAL = timedelta(seconds=5)
# Cloud alarm_message has no event timestamp and has produced a false relay action.
AUTO_UNLOCK_SAFETY_HOLD = True
