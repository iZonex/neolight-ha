"""NeoLight ALPHA Hybrid device in Home Assistant."""

import asyncio
from dataclasses import dataclass
import json
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import MonitorClient, MonitorState
from .const import DOMAIN, PLATFORMS, POLL_INTERVAL
from .mobile_api import MobileApiClient, MobileApiError
from .profile import ha_static_fields
from .settings import legacy_vendor_path, load_vendor, runtime_directory, write_private_json

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema({vol.Optional(DOMAIN): vol.Schema({})}, extra=vol.ALLOW_EXTRA)


@dataclass
class NeoLightRuntime:
    """Shared clients for one configured monitor."""

    monitor: MonitorClient
    mobile: MobileApiClient | None
    coordinator: DataUpdateCoordinator[MonitorState]
    vendor: dict


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Allow a local YAML entry to import the private paired-device config."""
    if DOMAIN in config:
        path = legacy_vendor_path()
        if not path.exists():
            _LOGGER.error("NeoLight vendor_config.json is missing")
            return False
        vendor = await hass.async_add_executor_job(lambda: json.loads(path.read_text()))
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "import"},
                data={
                    CONF_HOST: vendor["monitor_host"],
                    "stream_id": vendor.get("stream_id", ""),
                    "rtsp_user": vendor.get("rtsp_user", ""),
                    "rtsp_password": vendor.get("rtsp_password", ""),
                },
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the monitor and the autonomous app API client."""
    session = async_get_clientsession(hass)
    client = MonitorClient(session, entry.data["host"])
    vendor = await hass.async_add_executor_job(load_vendor, entry)
    state_dir = runtime_directory(hass, entry)
    if vendor:
        await hass.async_add_executor_job(write_private_json, state_dir / "vendor_config.json", vendor)
    if "vendor" in entry.data:
        if entry.data.get("initial_session") and not (state_dir / "runtime_session.json").exists():
            await hass.async_add_executor_job(
                write_private_json, state_dir / "runtime_session.json", entry.data["initial_session"]
            )

    async def save_mobile_session(result: dict) -> None:
        """Keep a session file for older media bridge installations."""
        values = {key: result[key] for key in ("sid", "ecode", "partnerIdentity") if key in result}
        await hass.async_add_executor_job(write_private_json, state_dir / "runtime_session.json", values)

    mobile = (
        MobileApiClient(
            session, vendor["api_host"], ha_static_fields(vendor["static_fields"]),
            vendor["signing_key"],
            "" if vendor.get("email") and vendor.get("password") else vendor.get("sid", ""),
            vendor.get("email", ""), vendor.get("password", ""),
            vendor.get("country_code", "380"),
            on_login=save_mobile_session,
        )
        if all(key in vendor for key in ("api_host", "static_fields", "signing_key", "paired_device_id")) else None
    )
    if mobile is not None and not mobile.sid:
        await mobile.login()

    last_schema: list = []

    async def fetch_state() -> MonitorState:
        nonlocal last_schema
        local_result, cloud_result, call_result = await asyncio.gather(
            client.probe(),
            mobile.read_device(vendor["paired_device_id"]) if mobile else asyncio.sleep(0, result=None),
            mobile.request("m.ipc.doorbell.call.status.get", "1.0",
                           {"devId": vendor["paired_device_id"]}) if mobile else asyncio.sleep(0, result=None),
            return_exceptions=True,
        )
        local_online = not isinstance(local_result, Exception)
        cloud_online = isinstance(cloud_result, dict) and cloud_result.get("isOnline") is True
        if mobile is not None and not isinstance(cloud_result, dict) and not last_schema:
            raise UpdateFailed(str(cloud_result))
        if not local_online and not isinstance(cloud_result, dict):
            error = cloud_result if isinstance(cloud_result, Exception) else local_result
            raise UpdateFailed(str(error))
        if isinstance(cloud_result, MobileApiError):
            _LOGGER.warning("NeoLight account API: %s", cloud_result)
        schema = cloud_result.get("schema", []) if isinstance(cloud_result, dict) else []
        if isinstance(schema, str):
            try:
                schema = json.loads(schema)
            except ValueError:
                schema = []
        if not isinstance(schema, list):
            schema = []
        if schema:
            last_schema = schema
        elif not isinstance(cloud_result, dict):
            schema = last_schema
        return MonitorState(
            online=local_online,
            cloud_online=cloud_online,
            dps=cloud_result.get("dps", {}) if isinstance(cloud_result, dict) else {},
            schema=schema,
            call_status=(call_result.get("callStatus")
                         if isinstance(call_result, dict)
                         and type(call_result.get("callStatus")) is int else None),
        )

    coordinator: DataUpdateCoordinator[MonitorState] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"NeoLight {entry.data['host']}",
        update_method=fetch_state,
        update_interval=POLL_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = NeoLightRuntime(client, mobile, coordinator, vendor)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply account changes made through the HA options form."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload NeoLight platforms."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
