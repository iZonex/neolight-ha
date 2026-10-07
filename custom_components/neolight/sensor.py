"""Diagnostic status for the app call signal and optional video bridge."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    entities = []
    if runtime.mobile is not None:
        entities.append(NeoLightAppCallSignal(runtime.coordinator, entry))
    if runtime.vendor.get("bridge_health_url"):
        entities.append(NeoLightVideoBridgeStatus(runtime.coordinator, entry))
    if entry.options.get("native_call_control_port", 0):
        entities.append(NeoLightNativeCallStatus(runtime.coordinator, entry))
    async_add_entities(entities)


class NeoLightStatusSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: ConfigEntry, suffix: str) -> None:
        super().__init__(coordinator)
        host = entry.data["host"]
        self._attr_unique_id = f"{host}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name="NeoLight ALPHA Hybrid",
            manufacturer="NeoLight",
            model="ALPHA Hybrid",
            configuration_url=f"http://{host}/",
        )


class NeoLightAppCallSignal(NeoLightStatusSensor):
    """The mobile API's call flag; it cannot measure the analog handset."""

    _attr_translation_key = "app_call_signal"
    _attr_icon = "mdi:phone-in-talk"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "app_call_signal")

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.cloud_online
                    and self.coordinator.data.call_status is not None)

    @property
    def native_value(self) -> str | None:
        if not self.available:
            return None
        return "active" if self.coordinator.data.call_status == 0 else "no_app_call"

    @property
    def extra_state_attributes(self) -> dict:
        return ({"app_call_status_code": self.coordinator.data.call_status}
                if self.coordinator.data else {})


class NeoLightVideoBridgeStatus(NeoLightStatusSensor):
    """Show progress of frames published by the shared AV mux."""

    _attr_translation_key = "video_bridge"
    _attr_icon = "mdi:video-wireless"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "video_bridge_status")

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.video_health)

    @property
    def native_value(self) -> str | None:
        if not self.available:
            return None
        return self.coordinator.data.video_health["status"]

    @property
    def extra_state_attributes(self) -> dict:
        if not self.available:
            return {}
        return {
            "video_source": self.coordinator.data.video_health.get("source"),
            "video_age_seconds": self.coordinator.data.video_health.get("video_age_seconds"),
        }


class NeoLightNativeCallStatus(NeoLightStatusSensor):
    """Transient MQTT call known to the native P2P bridge."""

    _attr_translation_key = "native_call"
    _attr_icon = "mdi:phone"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "native_call")

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.native_call)

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.native_call["state"] if self.available else None

    @property
    def extra_state_attributes(self) -> dict:
        if not self.available:
            return {}
        state = self.coordinator.data.native_call
        return {"talk_active": state["talk_active"],
                "call_type": state.get("call_type"), "age_seconds": state.get("age_seconds")}
