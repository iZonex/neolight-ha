"""Constants for the NeoLight integration."""

from datetime import timedelta

DOMAIN = "neolight"
PLATFORMS = ("binary_sensor", "camera", "button", "event", "lock", "select", "sensor", "switch")
CONF_STREAM_ID = "stream_id"
CONF_RTSP_USER = "rtsp_user"
CONF_RTSP_PASSWORD = "rtsp_password"
POLL_INTERVAL = timedelta(seconds=5)
# A supervised fresh Vizit call physically opened Lock 1 on 2026-10-06.
AUTO_UNLOCK_SAFETY_HOLD = False
