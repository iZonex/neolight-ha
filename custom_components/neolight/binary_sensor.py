"""Local availability sensor for a NeoLight monitor."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the monitor status entity."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    entities = [NeoLightOnlineSensor(runtime.coordinator, entry, "local")]
    if runtime.mobile is not None:
        entities.append(NeoLightOnlineSensor(runtime.coordinator, entry, "cloud"))
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
