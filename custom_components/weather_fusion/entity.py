"""Base Korea Weather Fusion entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .fusion import WeatherFusionManager


class WeatherFusionEntity(Entity):
    """Entity driven by normalized weather-source snapshots."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: WeatherFusionManager) -> None:
        super().__init__()
        self.manager = manager
        # Class-level IDs used by status, weather and binary health entities.
        if self._attr_unique_id:
            self._attr_unique_id = self._attr_unique_id.replace(
                DOMAIN, manager.identity, 1
            )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.identity)},
            manufacturer="Korea Weather Fusion",
            model="Weather and air quality",
            name=manager.device_name,
            sw_version=manager.software_version,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to source updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self.manager.async_add_listener(self.async_write_ha_state))
