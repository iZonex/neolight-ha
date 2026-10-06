"""UI configuration for a NeoLight monitor."""

import ipaddress
import re
import time
from typing import Any

from aiohttp import ClientError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .client import MonitorClient, MonitorUnavailable
from .const import AUTO_UNLOCK_SAFETY_HOLD, CONF_RTSP_PASSWORD, CONF_RTSP_USER, CONF_STREAM_ID, DOMAIN
from .mobile_api import MobileApiClient, MobileApiError
from .profile import ha_static_fields, parse_app_profile
from .settings import load_vendor


STREAM_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
def account_schema(current: dict[str, Any]) -> vol.Schema:
    """Show the account and door release settings in HA."""
    fields = {
        vol.Required("auto_unlock_relay", default=current.get("auto_unlock_relay", "lock_1")):
            vol.In({"lock_1": "Lock 1", "lock_2": "Lock 2"}),
        vol.Required("auto_unlock_delay", default=current.get("auto_unlock_delay", 0)):
            vol.All(vol.Coerce(int), vol.Range(min=0, max=30)),
        vol.Required("auto_unlock_test_once", default=False): bool,
        vol.Required("enable_camera", default=current.get("enable_camera", True)): bool,
        vol.Required("enable_doorbell", default=current.get("enable_doorbell", True)): bool,
        vol.Required("enable_lock_1", default=current.get("enable_lock_1", True)): bool,
        vol.Required("enable_lock_2", default=current.get("enable_lock_2", False)): bool,
        vol.Required("native_call_control_port", default=current.get("native_call_control_port", 0)):
            vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
        vol.Required("hangup_after_auto_unlock", default=current.get("hangup_after_auto_unlock", False)): bool,
        vol.Required("preferred_video_channel", default=current.get("preferred_video_channel", 0)):
            vol.All(vol.Coerce(int), vol.Range(min=0, max=32)),
        vol.Required("route_video_on_ring", default=current.get("route_video_on_ring", False)): bool,
        vol.Required("call_video_channel", default=current.get("call_video_channel", 0)):
            vol.All(vol.Coerce(int), vol.Range(min=0, max=32)),
        vol.Required("call_video_hold_seconds", default=current.get("call_video_hold_seconds", 90)):
            vol.All(vol.Coerce(int), vol.Range(min=15, max=300)),
        vol.Optional("restream_url", default=current.get("restream_url", "")): str,
        vol.Optional("homekit_ring_url", default=current.get("homekit_ring_url", "")): str,
        vol.Optional("stream_id", default=current.get("stream_id", "")): str,
        vol.Optional("rtsp_user", default=current.get("rtsp_user", "")): str,
        vol.Optional("rtsp_password", default=""): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
    if "api_host" in current:
        fields.update({
            vol.Required("email", default=current.get("email", "")): str,
            vol.Optional("password", default=""): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required("country_code", default=current.get("country_code", "380")): str,
        })
    if not AUTO_UNLOCK_SAFETY_HOLD:
        fields[vol.Required("auto_unlock_on_ring", default=current.get("auto_unlock_on_ring", False))] = bool
    return vol.Schema(fields)


async def validate_account(hass, vendor: dict[str, Any], current: dict[str, Any], user_input: dict[str, Any]):
    """Return updated options after checking new credentials if they changed."""
    test_once = user_input["auto_unlock_test_once"]
    options = {
        "auto_unlock_on_ring": (
            user_input.get("auto_unlock_on_ring", False)
            and not AUTO_UNLOCK_SAFETY_HOLD and not test_once
        ),
        "auto_unlock_test_once": test_once,
        "auto_unlock_test_deadline": int(time.time()) + 900 if test_once else 0,
        "auto_unlock_relay": user_input["auto_unlock_relay"],
        "auto_unlock_delay": user_input["auto_unlock_delay"],
        "enable_camera": user_input["enable_camera"],
        "enable_doorbell": user_input["enable_doorbell"],
        "enable_lock_1": user_input["enable_lock_1"],
        "enable_lock_2": user_input["enable_lock_2"],
        "native_call_control_port": user_input["native_call_control_port"],
        "hangup_after_auto_unlock": user_input["hangup_after_auto_unlock"],
        "preferred_video_channel": user_input["preferred_video_channel"],
        "route_video_on_ring": user_input["route_video_on_ring"],
        "call_video_channel": user_input["call_video_channel"],
        "call_video_hold_seconds": user_input["call_video_hold_seconds"],
        "restream_url": user_input.get("restream_url", "").strip(),
        "homekit_ring_url": user_input.get("homekit_ring_url", "").strip(),
        "stream_id": user_input.get("stream_id", "").strip().lower(),
        "rtsp_user": user_input.get("rtsp_user", "").strip(),
        "rtsp_password": user_input.get("rtsp_password", "") or current.get("rtsp_password", ""),
    }
    if options["stream_id"] and not STREAM_ID_PATTERN.fullmatch(options["stream_id"]):
        raise ValueError("invalid_stream_id")
    if options["restream_url"] and not options["restream_url"].startswith(("rtsp://", "rtsps://")):
        raise ValueError("invalid_stream_url")
    if options["homekit_ring_url"] and not options["homekit_ring_url"].startswith(("http://", "https://")):
        raise ValueError("invalid_ring_url")
    if options["route_video_on_ring"] and not options["call_video_channel"]:
        raise ValueError("invalid_call_video_channel")
    if options["hangup_after_auto_unlock"] and not options["native_call_control_port"]:
        raise ValueError("invalid_call_control_port")
    if "api_host" not in vendor:
        return options
    email = user_input["email"].strip()
    password = user_input.get("password", "") or current.get("password", "")
    country_code = user_input["country_code"].strip()
    if not email or not password or not country_code.isdigit():
        raise ValueError("invalid_account")
    changed = (email != current.get("email") or
               password != current.get("password") or
               country_code != current.get("country_code"))
    options.update(email=email, password=password, country_code=country_code)
    if changed:
        client = MobileApiClient(
            async_get_clientsession(hass),
            vendor["api_host"], ha_static_fields(vendor["static_fields"]), vendor["signing_key"],
            email=email, password=password, country_code=country_code,
        )
        await client.login()
        await client.read_device(vendor["paired_device_id"])
        # Re-login in the runtime after changing the account credentials.
        options["sid"] = ""
    return options


class NeoLightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Add a monitor using its LAN address."""

    VERSION = 1

    def __init__(self) -> None:
        self._local_data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Open account settings from the HA device configuration UI."""
        return NeoLightOptionsFlow(config_entry)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Expose account and automatic opening settings through Configure."""
        entry = self._get_reconfigure_entry()
        current = await self.hass.async_add_executor_job(load_vendor, entry)
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                updates = await validate_account(self.hass, current, current, user_input)
            except ValueError as error:
                errors["base"] = str(error)
            except (MobileApiError, ClientError, TimeoutError):
                errors["base"] = "cannot_auth"
            else:
                return self.async_update_reload_and_abort(
                    entry, options={**entry.options, **updates}
                )
        return self.async_show_form(
            step_id="reconfigure", data_schema=account_schema(current), errors=errors
        )

    async def async_step_import(self, user_input: dict[str, Any]):
        """Import the owner's paired device from local private settings."""
        host = user_input[CONF_HOST]
        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=f"NeoLight {host}", data=user_input)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Validate the monitor before storing configuration."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            stream_id = user_input.get(CONF_STREAM_ID, "").strip()
            try:
                ipaddress.ip_address(host)
            except ValueError:
                errors[CONF_HOST] = "invalid_host"
            if stream_id and not STREAM_ID_PATTERN.fullmatch(stream_id):
                errors[CONF_STREAM_ID] = "invalid_stream_id"
            if not errors:
                try:
                    await MonitorClient(async_get_clientsession(self.hass), host).probe()
                except MonitorUnavailable:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()
                    self._local_data = {
                        CONF_HOST: host,
                        CONF_STREAM_ID: stream_id.lower(),
                        CONF_RTSP_USER: user_input.get(CONF_RTSP_USER, ""),
                        CONF_RTSP_PASSWORD: user_input.get(CONF_RTSP_PASSWORD, ""),
                    }
                    return await self.async_step_cloud()
        schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_STREAM_ID, default=""): str,
            vol.Optional(CONF_RTSP_USER, default=""): str,
            vol.Optional(CONF_RTSP_PASSWORD, default=""): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_cloud(self, user_input: dict[str, Any] | None = None):
        """Accept an app profile and account, or create a local-only monitor."""
        errors: dict[str, str] = {}
        if user_input is not None:
            raw_profile = user_input.get("app_profile", "").strip()
            restream = user_input.get("restream_url", "").strip()
            if restream and not restream.startswith(("rtsp://", "rtsps://")):
                errors["base"] = "invalid_stream_url"
            vendor: dict[str, Any] = {
                "monitor_host": self._local_data[CONF_HOST],
                "stream_id": self._local_data[CONF_STREAM_ID],
                "rtsp_user": self._local_data[CONF_RTSP_USER],
                "rtsp_password": self._local_data[CONF_RTSP_PASSWORD],
                "restream_url": restream,
            }
            initial_session: dict[str, str] = {}
            if raw_profile and not errors:
                try:
                    vendor.update(parse_app_profile(raw_profile))
                    email = user_input.get("email", "").strip()
                    password = user_input.get("password", "")
                    country = user_input.get("country_code", "380").strip()
                    if not email or not password or not country.isdigit():
                        raise ValueError("invalid_account")
                    vendor.update(email=email, password=password, country_code=country)
                    client = MobileApiClient(
                        async_get_clientsession(self.hass), vendor["api_host"],
                        ha_static_fields(vendor["static_fields"]), vendor["signing_key"],
                        email=email, password=password, country_code=country,
                    )
                    login_result = await client.login()
                    await client.read_device(vendor["paired_device_id"])
                    if not all(login_result.get(key) for key in ("sid", "ecode", "partnerIdentity")):
                        raise MobileApiError("Login lacks media session fields")
                    vendor["sid"] = client.sid
                    initial_session = {
                        key: login_result[key]
                        for key in ("sid", "ecode", "partnerIdentity")
                        if key in login_result
                    }
                except ValueError as error:
                    errors["base"] = str(error)
                except (MobileApiError, ClientError, TimeoutError):
                    errors["base"] = "cannot_auth"
            elif any(user_input.get(key) for key in ("email", "password")):
                errors["base"] = "invalid_profile"
            if not errors:
                return self.async_create_entry(
                    title=f"NeoLight {self._local_data[CONF_HOST]}",
                    data={**self._local_data, "vendor": vendor,
                          "initial_session": initial_session},
                    options={
                        "enable_camera": True,
                        "enable_doorbell": bool(raw_profile),
                        "enable_lock_1": bool(raw_profile),
                        "enable_lock_2": False,
                        "preferred_video_channel": 0,
                        "homekit_ring_url": "",
                        "auto_unlock_on_ring": False,
                        "auto_unlock_test_once": False,
                    },
                )
        schema = vol.Schema({
            vol.Optional("app_profile", default=""): str,
            vol.Optional("email", default=""): str,
            vol.Optional("password", default=""): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Optional("country_code", default="380"): str,
            vol.Optional("restream_url", default=""): str,
        })
        return self.async_show_form(step_id="cloud", data_schema=schema, errors=errors)


class NeoLightOptionsFlow(config_entries.OptionsFlow):
    """Update the account used for this paired NeoLight monitor."""

    def __init__(self, config_entry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Validate a new login before saving it to the config entry."""
        current = await self.hass.async_add_executor_job(load_vendor, self._entry)
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                updates = await validate_account(self.hass, current, current, user_input)
            except ValueError as error:
                errors["base"] = str(error)
            except (MobileApiError, ClientError, TimeoutError):
                errors["base"] = "cannot_auth"
            else:
                return self.async_create_entry(
                    title="", data={**self._entry.options, **updates}
                )
        return self.async_show_form(
            step_id="init", data_schema=account_schema(current), errors=errors
        )
