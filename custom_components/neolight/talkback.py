"""Authenticated WebSocket commands for the NeoLight browser microphone."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from .const import DOMAIN
from .talk_transport import TalkSessions

def _sessions(hass: HomeAssistant) -> TalkSessions:
    return hass.data[f"{DOMAIN}_talk_sessions"]


def _entry_for_camera(hass: HomeAssistant, connection, camera: str):
    registry = entity_registry.async_get(hass)
    record = registry.async_get(camera)
    if (record is None or record.domain != "camera" or record.platform != DOMAIN
            or not record.config_entry_id or not
            connection.user.permissions.check_entity(camera, POLICY_CONTROL)):
        return None
    return hass.config_entries.async_get_entry(record.config_entry_id)


@websocket_api.websocket_command({vol.Required("type"): "neolight/talk_start",
                                  vol.Required("camera"): str})
@websocket_api.async_response
async def ws_talk_start(hass, connection, msg) -> None:
    entry = _entry_for_camera(hass, connection, msg["camera"])
    if entry is None or not entry.options.get("native_call_control_port"):
        connection.send_error(msg["id"], "not_allowed", "NeoLight talk is unavailable")
        return
    try:
        session = await _sessions(hass).start(
            entry.entry_id, connection.user.id, entry.options.get("native_talk_port", 38556)
        )
    except ValueError as error:
        connection.send_error(msg["id"], "talk_unavailable", str(error))
        return
    connection.send_result(msg["id"], {"entry_id": entry.entry_id, "token": session.token})


@websocket_api.websocket_command({vol.Required("type"): "neolight/talk_audio",
                                  vol.Required("entry_id"): str,
                                  vol.Required("token"): str,
                                  vol.Required("audio"): vol.All(str, vol.Length(min=1, max=5000))})
@websocket_api.async_response
async def ws_talk_audio(hass, connection, msg) -> None:
    try:
        await _sessions(hass).audio(
            msg["entry_id"], connection.user.id, msg["token"], msg["audio"]
        )
    except ValueError as error:
        connection.send_error(msg["id"], "talk_audio_failed", str(error))
        return
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): "neolight/talk_stop",
                                  vol.Required("entry_id"): str,
                                  vol.Required("token"): str})
@websocket_api.async_response
async def ws_talk_stop(hass, connection, msg) -> None:
    try:
        await _sessions(hass).stop(msg["entry_id"], connection.user.id, msg["token"])
    except ValueError as error:
        connection.send_error(msg["id"], "talk_stop_failed", str(error))
        return
    connection.send_result(msg["id"])


def setup_talkback(hass: HomeAssistant) -> None:
    hass.data[f"{DOMAIN}_talk_sessions"] = TalkSessions()
    websocket_api.async_register_command(hass, ws_talk_start)
    websocket_api.async_register_command(hass, ws_talk_audio)
    websocket_api.async_register_command(hass, ws_talk_stop)
