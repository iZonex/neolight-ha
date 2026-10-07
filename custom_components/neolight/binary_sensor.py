"""Local availability sensor for a NeoLight monitor."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .call_state import ring_channels
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the monitor status entity."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    entities = [NeoLightOnlineSensor(runtime.coordinator, entry, "local")]
    if runtime.mobile is not None:
        entities.append(NeoLightOnlineSensor(runtime.coordinator, entry, "cloud"))
        for channel, dp_id in ring_channels(runtime.coordinator.data.schema).items():
            entities.append(NeoLightRingSensor(runtime.coordinator, entry, channel, dp_id))
    async_add_entities(entities)


class NeoLightOnlineSensor(CoordinatorEntity, BinarySensorEntity):
    """Shows whether the monitor responds to its local HTTP UI."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: ConfigEntry, source: str) -> None:
        super().__init__(coordinator)
        self._source = source
        host = entry.data["host"]
        self._attr_name = "Monitor online" if source == "local" else "Cloud connected"
        self._attr_unique_id = f"{host}_{source}_online"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name="NeoLight ALPHA Hybrid",
            manufacturer="NeoLight",
            model="ALPHA Hybrid",
            configuration_url=f"http://{host}/",
        )

    @property
    def is_on(self) -> bool:
        """Return latest successful probe result."""
        if not self.coordinator.data:
            return False
        return (self.coordinator.data.online if self._source == "local"
                else self.coordinator.data.cloud_online)

    @property
    def available(self) -> bool:
        """Keep the diagnostic entity visible when the monitor goes offline."""
        return True


class NeoLightRingSensor(CoordinatorEntity, BinarySensorEntity):
    """Expose the monitor's read-only Ring/Normal state for one channel."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:doorbell"

    def __init__(self, coordinator, entry: ConfigEntry, channel: int, dp_id: int) -> None:
        super().__init__(coordinator)
        host = entry.data["host"]
        self._dp_id = str(dp_id)
        self._attr_name = f"Doorbell {channel} ringing"
        self._attr_unique_id = f"{host}_doorbell_{channel}_ringing"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name="NeoLight ALPHA Hybrid",
            manufacturer="NeoLight",
            model="ALPHA Hybrid",
            configuration_url=f"http://{host}/",
        )

    @property
    def is_on(self) -> bool | None:
        """Report unknown when cloud state is unavailable or unrecognized."""
        value = self.coordinator.data.dps.get(self._dp_id) if self.coordinator.data else None
        return value == "Ring" if isinstance(value, str) and value in {"Ring", "Normal"} else None

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.cloud_online)
