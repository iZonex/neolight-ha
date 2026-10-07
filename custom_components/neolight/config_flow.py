"""UI configuration for a NeoLight monitor."""

import ipaddress
from typing import Any

from aiohttp import ClientError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .client import MonitorClient, MonitorUnavailable
from .const import CONF_RTSP_PASSWORD, CONF_RTSP_USER, CONF_STREAM_ID, DOMAIN
from .mobile_api import MobileApiClient, MobileApiError
from .options_validation import STREAM_ID_PATTERN, validate_option_section
from .panel_protocol import PanelProfile, channel_labels
from .profile import ha_static_fields, parse_app_profile
from .settings import load_vendor, runtime_directory


async def authenticate_app_profile(
    hass, raw_profile: str, email: str, password: str, country_code: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate account access to the paired monitor before saving secrets."""
    vendor = parse_app_profile(raw_profile)
    email = email.strip()
    country_code = country_code.strip()
    if not email or not password or not country_code.isdigit():
        raise ValueError("invalid_account")
    vendor.update(email=email, password=password, country_code=country_code)
    client = MobileApiClient(
        async_get_clientsession(hass), vendor["api_host"],
        ha_static_fields(vendor["static_fields"]), vendor["signing_key"],
        email=email, password=password, country_code=country_code,
    )
    login_result = await client.login()
    await client.read_device(vendor["paired_device_id"])
    if not all(login_result.get(key) for key in ("sid", "ecode", "partnerIdentity")):
        raise MobileApiError("Login lacks media session fields")
    vendor["sid"] = client.sid
    session = {key: login_result[key] for key in ("sid", "ecode", "partnerIdentity")}
    return vendor, session


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
                    return await self.async_step_connection()
        schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_STREAM_ID, default=""): str,
            vol.Optional(CONF_RTSP_USER, default=""): str,
            vol.Optional(CONF_RTSP_PASSWORD, default=""): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_connection(self, user_input: dict[str, Any] | None = None):
        """Let a new owner start locally without an APK-derived app profile."""
        return self.async_show_menu(step_id="connection", menu_options=["local", "cloud"])

    def _vendor(self, restream_url: str) -> dict[str, Any]:
        return {
            "monitor_host": self._local_data[CONF_HOST],
            "stream_id": self._local_data[CONF_STREAM_ID],
            "rtsp_user": self._local_data[CONF_RTSP_USER],
            "rtsp_password": self._local_data[CONF_RTSP_PASSWORD],
            "restream_url": restream_url,
        }

    def _create_monitor_entry(
        self, vendor: dict[str, Any], initial_session: dict[str, str] | None = None,
    ):
        cloud = "api_host" in vendor
        return self.async_create_entry(
            title=f"NeoLight {self._local_data[CONF_HOST]}",
            data={**self._local_data, "vendor": vendor,
                  "initial_session": initial_session or {}},
            options={
                "enable_camera": True,
                "enable_doorbell": cloud,
                "enable_lock_1": cloud,
                "enable_lock_2": False,
                "preferred_video_channel": 0,
                "homekit_ring_url": "",
                "auto_unlock_on_ring": False,
                "auto_unlock_test_once": False,
            },
        )

    async def async_step_local(self, user_input: dict[str, Any] | None = None):
        """Finish setup with local access; cloud linking remains available later."""
        errors: dict[str, str] = {}
        if user_input is not None:
            restream_url = user_input.get("restream_url", "").strip()
            if restream_url and not restream_url.startswith(("rtsp://", "rtsps://")):
                errors["base"] = "invalid_stream_url"
            else:
                return self._create_monitor_entry(self._vendor(restream_url))
        return self.async_show_form(
            step_id="local",
            data_schema=vol.Schema({vol.Optional("restream_url", default=""): str}),
            errors=errors,
        )

    async def async_step_cloud(self, user_input: dict[str, Any] | None = None):
        """Link the account with an owner-supplied app profile."""
        errors: dict[str, str] = {}
        if user_input is not None:
            raw_profile = user_input.get("app_profile", "").strip()
            restream = user_input.get("restream_url", "").strip()
            if restream and not restream.startswith(("rtsp://", "rtsps://")):
                errors["base"] = "invalid_stream_url"
            vendor = self._vendor(restream)
            initial_session: dict[str, str] = {}
            if not raw_profile:
                errors["base"] = "invalid_profile"
            if not errors:
                try:
                    linked_vendor, initial_session = await authenticate_app_profile(
                        self.hass, raw_profile, user_input.get("email", ""),
                        user_input.get("password", ""),
                        user_input.get("country_code", "380"),
                    )
                    vendor.update(linked_vendor)
                except ValueError as error:
                    errors["base"] = str(error)
                except (MobileApiError, ClientError, TimeoutError):
                    errors["base"] = "cannot_auth"
            if not errors:
                return self._create_monitor_entry(vendor, initial_session)
        schema = vol.Schema({
            vol.Required("app_profile"): str,
            vol.Required("email"): str,
            vol.Required("password"): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Optional("country_code", default="380"): str,
            vol.Optional("restream_url", default=""): str,
        })
        return self.async_show_form(step_id="cloud", data_schema=schema, errors=errors)


class NeoLightOptionsFlow(config_entries.OptionsFlow):
    """Keep everyday settings separate from connection details."""

    def __init__(self, config_entry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Choose one focused settings page."""
        current = await self.hass.async_add_executor_job(
            load_vendor, self._entry, runtime_directory(self.hass, self._entry)
        )
        pages = ["entrances", "advanced"]
        if "api_host" in current:
            pages = [
                "entrances", "calls", "automatic_opening", "apple_home",
                "advanced", "account",
            ]
        else:
            pages.append("link_account")
        return self.async_show_menu(step_id="init", menu_options=pages)

    async def _async_section(self, step_id: str, user_input: dict[str, Any] | None):
        current = await self.hass.async_add_executor_job(
            load_vendor, self._entry, runtime_directory(self.hass, self._entry)
        )
        if step_id == "entrances":
            runtime = getattr(self.hass, "data", {}).get(DOMAIN, {}).get(self._entry.entry_id)
            if runtime and runtime.coordinator.data:
                state = runtime.coordinator.data
                try:
                    profile = PanelProfile.from_schema(state.schema, required=("channel",))
                    current["_channel_labels"] = channel_labels(
                        state.dps[str(profile.dp_ids["channel"])]
                    )
                except (KeyError, TypeError, ValueError):
                    pass
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                if step_id == "link_account":
                    updates, _ = await authenticate_app_profile(
                        self.hass, user_input.get("app_profile", ""),
                        user_input.get("email", ""), user_input.get("password", ""),
                        user_input.get("country_code", "380"),
                    )
                    updates.update(enable_doorbell=True, enable_lock_1=True)
                else:
                    updates = validate_option_section(step_id, current, user_input)
                if step_id == "account":
                    email = updates["email"]
                    password = updates["password"]
                    country_code = updates["country_code"]
                    if (email != current.get("email") or password != current.get("password")
                            or country_code != current.get("country_code")):
                        client = MobileApiClient(
                            async_get_clientsession(self.hass), current["api_host"],
                            ha_static_fields(current["static_fields"]), current["signing_key"],
                            email=email, password=password, country_code=country_code,
                        )
                        await client.login()
                        await client.read_device(current["paired_device_id"])
                        updates["sid"] = ""
            except ValueError as error:
                errors["base"] = str(error)
            except (MobileApiError, ClientError, TimeoutError):
                errors["base"] = "cannot_auth"
            else:
                return self.async_create_entry(
                    title="", data={**self._entry.options, **updates}
                )
        return self.async_show_form(
            step_id=step_id, data_schema=option_section_schema(step_id, current), errors=errors
        )

    async def async_step_entrances(self, user_input: dict[str, Any] | None = None):
        return await self._async_section("entrances", user_input)

    async def async_step_calls(self, user_input: dict[str, Any] | None = None):
        return await self._async_section("calls", user_input)

    async def async_step_automatic_opening(self, user_input: dict[str, Any] | None = None):
        return await self._async_section("automatic_opening", user_input)

    async def async_step_apple_home(self, user_input: dict[str, Any] | None = None):
        return await self._async_section("apple_home", user_input)

    async def async_step_advanced(self, user_input: dict[str, Any] | None = None):
        return await self._async_section("advanced", user_input)

    async def async_step_account(self, user_input: dict[str, Any] | None = None):
        return await self._async_section("account", user_input)

    async def async_step_link_account(self, user_input: dict[str, Any] | None = None):
        return await self._async_section("link_account", user_input)


def option_section_schema(section: str, current: dict[str, Any]) -> vol.Schema:
    """Fields for one settings page, with persisted values as defaults."""
    if section == "entrances":
        if "api_host" not in current:
            return vol.Schema({
                vol.Required("enable_camera", default=current.get("enable_camera", True)): bool,
            })
        channel_names = current.get("_channel_labels")
        if channel_names:
            preferred_choices = {0: "0: Keep monitor selection"} | {
                channel: f"{channel}: {name}" for channel, name in channel_names.items()
            }
            call_choices = {0: "0: Do not switch"} | {
                channel: f"{channel}: {name}" for channel, name in channel_names.items()
            }
            preferred_validator = vol.In(preferred_choices)
            call_validator = vol.In(call_choices)
        else:
            preferred_validator = vol.All(vol.Coerce(int), vol.Range(min=0, max=32))
            call_validator = vol.All(vol.Coerce(int), vol.Range(min=0, max=32))
        return vol.Schema({
            vol.Required("enable_camera", default=current.get("enable_camera", True)): bool,
            vol.Required("enable_lock_1", default=current.get("enable_lock_1", True)): bool,
            vol.Required("enable_lock_2", default=current.get("enable_lock_2", False)): bool,
            vol.Required("preferred_video_channel", default=current.get("preferred_video_channel", 0)):
                preferred_validator,
            vol.Required("route_video_on_ring", default=current.get("route_video_on_ring", False)): bool,
            vol.Required("call_video_channel", default=current.get("call_video_channel", 0)):
                call_validator,
            vol.Required("call_video_hold_seconds", default=current.get("call_video_hold_seconds", 90)):
                vol.All(vol.Coerce(int), vol.Range(min=15, max=300)),
        })
    if section == "calls":
        return vol.Schema({
            vol.Required("enable_doorbell", default=current.get("enable_doorbell", True)): bool,
        })
    if section == "automatic_opening":
        return vol.Schema({
            vol.Required("auto_unlock_on_ring", default=current.get("auto_unlock_on_ring", False)): bool,
            vol.Required("auto_unlock_test_once", default=False): bool,
            vol.Required("auto_unlock_relay", default=current.get("auto_unlock_relay", "lock_1")):
                vol.In({"lock_1": "Entrance door (Lock 1)", "lock_2": "Lock 2"}),
            vol.Required("auto_unlock_delay", default=current.get("auto_unlock_delay", 0)):
                vol.All(vol.Coerce(int), vol.Range(min=0, max=30)),
            vol.Required("hangup_after_auto_unlock", default=current.get("hangup_after_auto_unlock", False)): bool,
        })
    if section == "apple_home":
        return vol.Schema({
            vol.Optional("homekit_ring_url", default=current.get("homekit_ring_url", "")): str,
        })
    if section == "advanced":
        return vol.Schema({
            vol.Required("native_call_control_port", default=current.get("native_call_control_port", 0)):
                vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
            vol.Optional("bridge_health_url", default=current.get("bridge_health_url", "")): str,
            vol.Optional("restream_url", default=current.get("restream_url", "")): str,
            vol.Optional("stream_id", default=current.get("stream_id", "")): str,
            vol.Optional("rtsp_user", default=current.get("rtsp_user", "")): str,
            vol.Optional("rtsp_password", default=""): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
        })
    if section == "account":
        return vol.Schema({
            vol.Required("email", default=current.get("email", "")): str,
            vol.Optional("password", default=""): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required("country_code", default=current.get("country_code", "380")): str,
        })
    if section == "link_account":
        return vol.Schema({
            vol.Required("app_profile"): str,
            vol.Required("email"): str,
            vol.Required("password"): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required("country_code", default="380"): str,
        })
    raise ValueError("unknown_options_page")
