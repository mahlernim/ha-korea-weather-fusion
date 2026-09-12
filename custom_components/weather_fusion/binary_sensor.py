"""Korea Weather Fusion health sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import WeatherFusionEntity
from .fusion import WeatherFusionManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up fusion health entities."""
    manager: WeatherFusionManager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            WeatherFusionHealth(manager),
            WeatherFusionForecastHealth(manager),
            WeatherFusionWeatheriHealth(manager, "weatheri_forecast"),
            WeatherFusionWeatheriHealth(manager, "weatheri_air"),
        ]
    )


class WeatherFusionHealth(WeatherFusionEntity, BinarySensorEntity):
    """Report whether every representative numeric metric is available."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:source-merge-check"
    _attr_translation_key = "data_current"
    _attr_unique_id = f"{DOMAIN}_data_current"

    @property
    def suggested_object_id(self) -> str:
        return "data_current"

    @property
    def is_on(self) -> bool:
        return self.manager.health()[0]

    @property
    def extra_state_attributes(self):
        return self.manager.health()[1]


class WeatherFusionForecastHealth(WeatherFusionEntity, BinarySensorEntity):
    """Report text-forecast freshness separately from numeric health."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:weather-partly-cloudy"
    _attr_translation_key = "forecast_data_current"
    _attr_unique_id = f"{DOMAIN}_forecast_data_current"

    @property
    def suggested_object_id(self) -> str:
        return "forecast_data_current"

    @property
    def is_on(self) -> bool:
        return self.manager.forecast_health()[0]

    @property
    def extra_state_attributes(self):
        return self.manager.forecast_health()[1]


class WeatherFusionWeatheriHealth(WeatherFusionEntity, BinarySensorEntity):
    """Report one internal Weatheri resource's freshness."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:database-check"

    def __init__(self, manager: WeatherFusionManager, group: str) -> None:
        super().__init__(manager)
        self._group = group
        suffix = (
            "forecast_data_current"
            if group == "weatheri_forecast"
            else "air_data_current"
        )
        self._attr_translation_key = f"weatheri_{suffix}"
        self._attr_unique_id = f"{manager.identity}_weatheri_{suffix}"
        self._suggested_object_id = f"weatheri_{suffix}"

    @property
    def suggested_object_id(self) -> str:
        return self._suggested_object_id

    @property
    def is_on(self) -> bool:
        return self.manager.weatheri_source_health(self._group)[0]

    @property
    def extra_state_attributes(self):
        return self.manager.weatheri_source_health(self._group)[1]
