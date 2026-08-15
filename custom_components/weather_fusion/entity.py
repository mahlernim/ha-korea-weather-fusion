"""Base Korea Weather Fusion entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .fusion import WeatherFusionManager


class WeatherFusionEntity(Entity):
    """Entity driven by normalized weather-source snapshots."""

    _attr_has_entity_name = True

    def __init__(self, manager: WeatherFusionManager) -> None:
        self.manager = manager
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            manufacturer="Local Home Assistant",
            model="State fusion helper",
            name="Korea Weather Fusion",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to source updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self.manager.async_add_listener(self.async_write_ha_state))
