"""Home Assistant controls for NeoLight call behavior."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import AUTO_UNLOCK_SAFETY_HOLD, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Show automatic opening directly on the NeoLight device page."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    if AUTO_UNLOCK_SAFETY_HOLD:
        registry = entity_registry.async_get(hass)
        old_entity = registry.async_get_entity_id(
            "switch", DOMAIN, f"{entry.data['host']}_auto_unlock_on_ring"
        )
        if old_entity:
            registry.async_remove(old_entity)
        return
    if runtime.mobile is not None:
        async_add_entities([NeoLightAutoUnlockSwitch(entry)])


class NeoLightAutoUnlockSwitch(SwitchEntity):
    """Enable or disable the configured relay pulse on a doorbell event."""

    _attr_has_entity_name = True
    _attr_name = "Auto unlock on ring"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:door-open"
    _attr_available = not AUTO_UNLOCK_SAFETY_HOLD

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        host = entry.data["host"]
        self._attr_unique_id = f"{host}_auto_unlock_on_ring"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name="NeoLight ALPHA Hybrid",
            manufacturer="NeoLight",
            model="ALPHA Hybrid",
            configuration_url=f"http://{host}/",
        )

    @property
    def is_on(self) -> bool:
        """Reflect the persisted HA setting."""
        return not AUTO_UNLOCK_SAFETY_HOLD and self._entry.options.get("auto_unlock_on_ring", False)

    async def async_turn_on(self, **kwargs) -> None:
        """Enable automatic opening for the next ring."""
        if AUTO_UNLOCK_SAFETY_HOLD:
            raise HomeAssistantError("NeoLight auto unlock is paused while false ring events are investigated")
        self.hass.config_entries.async_update_entry(
            self._entry, options={**self._entry.options, "auto_unlock_on_ring": True}
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable automatic opening for the next ring."""
        self.hass.config_entries.async_update_entry(
            self._entry, options={**self._entry.options, "auto_unlock_on_ring": False}
        )
        self.async_write_ha_state()
